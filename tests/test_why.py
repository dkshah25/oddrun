"""Behavioral unit and integration tests for Phase 2 causal diagnosis engine."""

import os
import sys
from unittest.mock import patch

from oddrun.cli import main
from oddrun.diagnose import EvidenceLevel, diagnose_behavior, format_diagnosis_text
from oddrun.execution import (
    BehaviorSignature,
    ExecutionRecord,
    ExecutionResult,
    ExecutionStatus,
    normalize_diagnostic_text,
    record_execution,
    run_command_subprocess,
)
from oddrun.experiments import (
    Candidate,
    CandidateTier,
    classify_candidate_tier,
    rank_candidates,
)
from oddrun.io import load_record, save_record, save_snapshot
from oddrun.models import EnvironmentSnapshot, PythonInfo, SystemInfo


def make_test_snapshot(env=None, pkgs=None) -> EnvironmentSnapshot:
    return EnvironmentSnapshot(
        python=PythonInfo("3.10.0", "CPython", "/bin/python", "/usr", "/usr", "linux"),
        system=SystemInfo("Linux", "5.0", "x86_64", "x86_64", "/app", "UTC"),
        environment=env or {"PATH": "/usr/bin", "TZ": "UTC"},
        packages=pkgs or {"pytest": "7.4.0"},
    )


def make_test_record(
    env=None, exit_code=1, exc_type="KeyError", diag="KeyError: 'IST'"
):
    snap = make_test_snapshot(env=env)
    sig = BehaviorSignature(
        is_success=(exit_code == 0),
        termination_kind="EXIT_CODE",
        exit_code=exit_code,
        exception_type=exc_type,
        normalized_diag=diag,
    )
    res = ExecutionResult(
        status=ExecutionStatus.SUCCESS,
        exit_code=exit_code,
        stdout="",
        stderr=diag,
        duration_ms=10.0,
        behavior_signature=sig,
    )
    return ExecutionRecord(
        command=[sys.executable, "-c", "pass"],
        environment_snapshot=snap,
        execution_result=res,
        recorded_at="2026-09-12T10:00:00Z",
    )


def test_candidate_safety_tier_classification():
    t1 = CandidateTier.TIER_1_SAFE
    t2 = CandidateTier.TIER_2_PATH
    t3 = CandidateTier.TIER_3_OBSERVED

    assert classify_candidate_tier("environment", "TZ", "UTC") == t1
    assert classify_candidate_tier("environment", "LANG", "C.UTF-8") == t1
    assert classify_candidate_tier("environment", "MY_APP_VAR", "123") == t1
    assert classify_candidate_tier("environment", "PATH", "/bin") == t2
    assert classify_candidate_tier("environment", "PYTHONPATH", "/src") == t2
    assert classify_candidate_tier("python", "version", "3.12") == t3


def test_candidate_ranking_order():
    candidates = [
        Candidate("environment", "PATH", "/a", "/b", CandidateTier.TIER_2_PATH),
        Candidate("environment", "MY_VAR", "1", "2", CandidateTier.TIER_1_SAFE),
        Candidate(
            "environment", "TZ", "Asia/Kolkata", "UTC", CandidateTier.TIER_1_SAFE
        ),
        Candidate("environment", "LANG", "en_US", "C", CandidateTier.TIER_1_SAFE),
    ]
    ranked = rank_candidates(candidates)
    assert [c.key for c in ranked] == ["TZ", "LANG", "MY_VAR", "PATH"]


def test_output_normalization_and_secret_protection():
    env = {"SECRET_KEY": "supersecret123", "PATH": "/usr/bin"}
    raw_diag = (
        "Traceback at line 42 0x7f9a8b1c: "
        "Error using supersecret123 in /var/app/test.py"
    )
    normalized = normalize_diagnostic_text(raw_diag, env)

    assert "supersecret123" not in normalized
    assert "<present>" in normalized or "[PATH]" in normalized
    assert "0x7f9a8b1c" not in normalized


def test_shell_false_metacharacter_safety():
    res = run_command_subprocess(
        [
            sys.executable,
            "-c",
            "import sys; print(sys.argv[1])",
            "hello; echo injected",
        ],
        env=dict(os.environ),
    )
    assert res.status == ExecutionStatus.SUCCESS
    assert "hello; echo injected" in res.stdout


def test_reject_plain_unobserved_snapshot(tmp_path):
    snap_path = tmp_path / "plain_snap.json"
    save_snapshot(make_test_snapshot(), snap_path)

    report = diagnose_behavior(snap_path, [sys.executable, "-c", "pass"])
    assert report.baseline_status == "ERROR"
    assert report.error_message is not None
    assert "Target behavior is UNOBSERVED" in report.error_message


def test_record_execution_saves_failing_command(tmp_path):
    record_path = tmp_path / "record.json"
    rec = record_execution([sys.executable, "-c", "import sys; sys.exit(1)"])
    save_record(rec, record_path)

    assert record_path.is_file()
    loaded = load_record(record_path)
    assert loaded.execution_result.exit_code == 1
    assert loaded.execution_result.behavior_signature.is_success is False


def test_diagnose_timezone_causal_factor(tmp_path):
    target_path = tmp_path / "target_rec.json"
    target_rec = make_test_record(
        env={"TZ": "UTC"}, exit_code=1, exc_type="KeyError", diag="KeyError: 'IST'"
    )
    save_record(target_rec, target_path)

    sig_pass = BehaviorSignature(True, "EXIT_CODE", 0, None, "")
    sig_fail = BehaviorSignature(
        False, "EXIT_CODE", 1, "KeyError", "KeyError: 'IST'"
    )

    res_pass = ExecutionResult(ExecutionStatus.SUCCESS, 0, "", "", 10.0, sig_pass)
    res_fail = ExecutionResult(
        ExecutionStatus.SUCCESS, 1, "", "KeyError: 'IST'", 10.0, sig_fail
    )

    with patch("oddrun.diagnose.capture_environment") as mock_cap, \
         patch("oddrun.diagnose.run_command_subprocess") as mock_run_diag, \
         patch("oddrun.experiments.run_command_subprocess") as mock_run_exp:

        mock_cap.return_value = make_test_snapshot(env={"TZ": "Asia/Kolkata"})
        mock_run_diag.side_effect = [res_pass, res_pass, res_pass]
        mock_run_exp.side_effect = [res_fail, res_fail, res_fail]

        report = diagnose_behavior(target_path, [sys.executable, "-c", "pass"])
        assert report.baseline_status == "STABLE_BASELINE"
        assert report.has_causal_factors is True
        assert len(report.causal_factors) == 1

        factor = report.causal_factors[0]
        assert factor.candidate.key == "TZ"
        assert factor.evidence_level == EvidenceLevel.MODERATE

        text = format_diagnosis_text(report)
        assert "EXPERIMENTALLY SUPPORTED CAUSAL FACTOR" in text
        assert "TZ" in text


def test_diagnose_different_error_not_target_match(tmp_path):
    """Disambiguation Test: Perturbation failure (ValueError) != Target (KeyError)."""
    target_path = tmp_path / "target_rec.json"
    target_rec = make_test_record(
        env={"TZ": "UTC"}, exit_code=1, exc_type="KeyError", diag="KeyError: 'IST'"
    )
    save_record(target_rec, target_path)

    sig_pass = BehaviorSignature(True, "EXIT_CODE", 0, None, "")
    # Perturbation produces ValueError instead of target's KeyError
    sig_different_err = BehaviorSignature(
        False, "EXIT_CODE", 1, "ValueError", "ValueError: Bad config"
    )

    res_pass = ExecutionResult(ExecutionStatus.SUCCESS, 0, "", "", 10.0, sig_pass)
    res_different_err = ExecutionResult(
        ExecutionStatus.SUCCESS, 1, "", "ValueError", 10.0, sig_different_err
    )

    with patch("oddrun.diagnose.capture_environment") as mock_cap, \
         patch("oddrun.diagnose.run_command_subprocess") as mock_run_diag, \
         patch("oddrun.experiments.run_command_subprocess") as mock_run_exp:

        mock_cap.return_value = make_test_snapshot(env={"TZ": "Asia/Kolkata"})
        mock_run_diag.side_effect = [res_pass, res_pass, res_pass]
        mock_run_exp.side_effect = [res_different_err]

        report = diagnose_behavior(target_path, [sys.executable, "-c", "pass"])
        assert report.baseline_status == "STABLE_BASELINE"
        # Must NOT call ValueError a match for KeyError!
        assert report.has_causal_factors is False


def test_cli_record_and_why_integration(tmp_path, capsys):
    target_path = tmp_path / "target_rec.json"
    target_rec = make_test_record(
        env={"TZ": "UTC"}, exit_code=1, exc_type="KeyError", diag="KeyError: 'IST'"
    )
    save_record(target_rec, target_path)

    sig_pass = BehaviorSignature(True, "EXIT_CODE", 0, None, "")
    sig_fail = BehaviorSignature(
        False, "EXIT_CODE", 1, "KeyError", "KeyError: 'IST'"
    )

    res_pass = ExecutionResult(ExecutionStatus.SUCCESS, 0, "", "", 10.0, sig_pass)
    res_fail = ExecutionResult(
        ExecutionStatus.SUCCESS, 1, "", "KeyError: 'IST'", 10.0, sig_fail
    )

    with patch("oddrun.diagnose.capture_environment") as mock_cap, \
         patch("oddrun.diagnose.run_command_subprocess") as mock_run_diag, \
         patch("oddrun.experiments.run_command_subprocess") as mock_run_exp:

        mock_cap.return_value = make_test_snapshot(env={"TZ": "Asia/Kolkata"})
        mock_run_diag.side_effect = [res_pass, res_pass, res_pass]
        mock_run_exp.side_effect = [res_fail, res_fail, res_fail]

        exit_code = main(["why", str(target_path), "--", sys.executable, "-c", "pass"])
        assert exit_code == 0

        captured = capsys.readouterr()
        assert "OddRun Causal Diagnosis" in captured.out
        assert "TZ" in captured.out


def test_real_subprocess_e2e_timezone_and_error_disambiguation(tmp_path):
    """Real subprocess E2E test verifying record + why with TZ perturbation."""
    script_path = tmp_path / "target_program.py"
    script_code = (
        "import os, sys\n"
        "tz = os.environ.get('TZ', 'Asia/Kolkata')\n"
        "if tz == 'UTC':\n"
        "    raise KeyError('Timezone is UTC!')\n"
        "print('PASS: Timezone OK')\n"
    )
    script_path.write_text(script_code, encoding="utf-8")

    rec_path = tmp_path / "target_rec.json"

    # 1. Target environment has TZ=UTC
    with patch.dict(os.environ, {"TZ": "UTC"}):
        rec = record_execution([sys.executable, str(script_path)])
        save_record(rec, rec_path)

    assert rec.execution_result.exit_code != 0
    assert rec.execution_result.behavior_signature.exception_type == "KeyError"

    # 2. Baseline environment has TZ=Asia/Kolkata
    with patch.dict(os.environ, {"TZ": "Asia/Kolkata"}):
        report = diagnose_behavior(rec_path, [sys.executable, str(script_path)])

    assert report.baseline_status == "STABLE_BASELINE"
    assert report.has_causal_factors is True
    assert len(report.causal_factors) == 1
    assert report.causal_factors[0].candidate.key == "TZ"

    # 3. Disambiguation check: Script that raises ValueError instead of KeyError
    mismatch_script = tmp_path / "mismatch_program.py"
    mismatch_code = (
        "import os, sys\n"
        "tz = os.environ.get('TZ', 'Asia/Kolkata')\n"
        "if tz == 'UTC':\n"
        "    raise ValueError('Different error!')\n"
        "print('PASS')\n"
    )
    mismatch_script.write_text(mismatch_code, encoding="utf-8")

    # Diagnose target_rec (KeyError) against mismatch script
    # (which raises ValueError on TZ=UTC)
    with patch.dict(os.environ, {"TZ": "Asia/Kolkata"}):
        report_mismatch = diagnose_behavior(
            rec_path, [sys.executable, str(mismatch_script)]
        )

    assert report_mismatch.baseline_status == "STABLE_BASELINE"
    # Must NOT match ValueError with KeyError!
    assert report_mismatch.has_causal_factors is False


