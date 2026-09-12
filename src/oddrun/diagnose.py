"""Causal diagnosis engine, evidence classification, and report generation."""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from oddrun.compare import compare_snapshots
from oddrun.execution import (
    BehaviorSignature,
    ExecutionRecord,
    ExecutionResult,
    run_command_subprocess,
)
from oddrun.experiments import (
    Candidate,
    OutcomeClassification,
    build_candidate_matrix,
    run_candidate_experiment,
)
from oddrun.io import load_target_artifact
from oddrun.models import EnvironmentSnapshot
from oddrun.snapshot import capture_environment


class EvidenceLevel(Enum):
    """Causal evidence rating level."""

    STRONG = "STRONG"
    MODERATE = "MODERATE"
    WEAK = "WEAK"
    UNSTABLE = "UNSTABLE"
    NO_EVIDENCE = "NO_EVIDENCE"


@dataclass(frozen=True)
class CausalFactorReport:
    """Detailed causal evidence report for a single Candidate factor."""

    candidate: Candidate
    evidence_level: EvidenceLevel
    forward_runs: str
    reverse_status: str
    explanation: str
    recommendation: str


@dataclass(frozen=True)
class DiagnosisReport:
    """Complete diagnostic report produced by oddrun why."""

    command: list[str]
    target_label: str
    baseline_status: str  # 'STABLE_BASELINE', 'UNSTABLE_BASELINE', 'BASELINE_FAILING'
    baseline_signature: BehaviorSignature | None
    target_signature: BehaviorSignature | None
    total_differences: int
    eligible_count: int
    excluded_count: int
    causal_factors: list[CausalFactorReport] = field(default_factory=list)
    unstable_candidates: list[Candidate] = field(default_factory=list)
    error_message: str | None = None

    @property
    def has_causal_factors(self) -> bool:
        return len(self.causal_factors) > 0


def format_diagnosis_text(report: DiagnosisReport) -> str:
    """Format a DiagnosisReport into clean, human-readable terminal text."""
    cmd_str = " ".join(report.command)

    if report.error_message:
        return (
            "OddRun Causal Diagnosis Error\n"
            "============================================================\n"
            f"Command: {cmd_str}\n\n"
            f"ERROR: {report.error_message}"
        )

    if report.baseline_status == "UNSTABLE_BASELINE":
        return (
            "OddRun Causal Diagnosis Error\n"
            "============================================================\n"
            f"Command: {cmd_str}\n\n"
            "ERROR: Non-deterministic behavior detected in baseline environment.\n"
            "OddRun executed the command 3 times and observed inconsistent outcomes.\n"
            "Causal diagnosis cannot be reliably performed on an unstable baseline."
        )

    if report.baseline_status == "BASELINE_FAILING":
        diag = (
            report.baseline_signature.normalized_diag
            if report.baseline_signature
            else "Failure"
        )
        return (
            "OddRun Causal Diagnosis Error\n"
            "============================================================\n"
            f"Command: {cmd_str}\n\n"
            "ERROR: Command is already failing in the baseline environment.\n"
            f"Baseline Diagnostic: {diag}\n\n"
            "To diagnose environment differences, the baseline command must pass."
        )

    eligible_str = f"{report.eligible_count} candidates tested"
    lines: list[str] = [
        "OddRun Causal Diagnosis",
        "============================================================",
        f"Command         : {cmd_str}",
        f"Target Record   : {report.target_label}",
        f"Differences     : {report.total_differences} total ({eligible_str})",
        "",
        "[1/3] Baseline Stability ... PASS (3/3 identical runs)",
        "[2/3] Testing Candidates...",
    ]

    for factor in report.causal_factors:
        c = factor.candidate
        runs = factor.forward_runs
        lines.append(
            f"  {c.key}={c.target_value} .................... "
            f"REPRODUCED FAILURE ({runs})"
        )

    if not report.has_causal_factors:
        lines.append("  (No candidate factor reproduced the target failure)")

    lines.append("")
    lines.append("[3/3] Evaluating Causal Evidence...")
    lines.append("")

    if report.has_causal_factors:
        if len(report.causal_factors) == 1:
            title = "EXPERIMENTALLY SUPPORTED CAUSAL FACTOR"
        else:
            title = "INDEPENDENT CAUSAL FACTORS"

        lines.extend([
            title,
            "============================================================",
        ])

        for factor in report.causal_factors:
            c = factor.candidate
            lines.extend([
                f"Factor       : {c.key}",
                f"Baseline     : {c.baseline_value} (PASS)",
                f"Target       : {c.target_value} (FAIL)",
                f"Forward Test : {factor.forward_runs}",
                f"Reverse Test : {factor.reverse_status}",
                f"Evidence     : {factor.evidence_level.value} (Forward Verified)",
                "",
                "Interpretation:",
                f"  {factor.explanation}",
                "",
                "Recommendation:",
                f"  {factor.recommendation}",
                "------------------------------------------------------------",
            ])

        lines.append("")
        lines.append(
            "Note: This is strong causal evidence, "
            "not proof that these are the unique possible causes."
        )
    else:
        lines.extend([
            "NO CAUSAL FACTOR CONFIRMED",
            "============================================================",
            "None of the tested environmental factors reproduced the target failure.",
            "The failure may depend on un-tested factors or system dependencies.",
        ])

    return "\n".join(lines)


def generate_recommendation(key: str) -> str:
    """Generate concise remediation recommendations for common factors."""
    key_upper = key.upper()
    if key_upper == "TZ":
        return (
            "Avoid relying on system timezone. Use explicit timezone-aware datetimes."
        )
    if key_upper == "LANG" or key_upper.startswith("LC_"):
        return (
            "Avoid depending on locale formatting. Explicitly pass locale or encoding."
        )
    if key_upper == "PYTHONPATH":
        return (
            "Ensure module imports rely on package installation, not PYTHONPATH."
        )
    if key_upper == "CWD":
        return (
            "Avoid relative path assumptions; resolve paths relative to package root."
        )
    return f"Ensure application behavior does not implicitly depend on '{key}'."


def diagnose_behavior(
    target_record: ExecutionRecord | EnvironmentSnapshot | str | Path,
    command: Sequence[str],
    allow_path_perturbation: bool = False,
    max_experiments: int = 10,
    timeout_seconds: float = 30.0,
) -> DiagnosisReport:
    """Perform causal diagnosis for a command against a target ExecutionRecord."""
    cmd_list = list(command)
    if not cmd_list:
        return DiagnosisReport(
            command=[],
            target_label="unknown",
            baseline_status="ERROR",
            baseline_signature=None,
            target_signature=None,
            total_differences=0,
            eligible_count=0,
            excluded_count=0,
            error_message="No command specified for diagnosis",
        )

    # 1. Load target artifact
    if isinstance(target_record, (str, Path)):
        target_label = str(target_record)
        try:
            artifact = load_target_artifact(target_record)
        except Exception as exc:
            return DiagnosisReport(
                command=cmd_list,
                target_label=target_label,
                baseline_status="ERROR",
                baseline_signature=None,
                target_signature=None,
                total_differences=0,
                eligible_count=0,
                excluded_count=0,
                error_message=f"Could not load target record: {exc}",
            )
    else:
        target_label = "target_record"
        artifact = target_record

    # 2. Check if target artifact contains an observed ExecutionRecord
    if isinstance(artifact, EnvironmentSnapshot):
        return DiagnosisReport(
            command=cmd_list,
            target_label=target_label,
            baseline_status="ERROR",
            baseline_signature=None,
            target_signature=None,
            total_differences=0,
            eligible_count=0,
            excluded_count=0,
            error_message=(
                "Target behavior is UNOBSERVED.\n"
                "The supplied file contains environment info "
                "but no observed execution result.\n\n"
                "Use 'oddrun record --output target-run.json -- COMMAND' "
                "on the target environment first."
            ),
        )

    record: ExecutionRecord = artifact
    target_snap = record.environment_snapshot
    target_signature = record.execution_result.behavior_signature

    # 3. Capture baseline environment
    baseline_snap = capture_environment()
    baseline_env = dict(os.environ)
    baseline_cwd = os.getcwd()

    # 4. Baseline Verification: Run command 3 times in baseline environment
    baseline_results: list[ExecutionResult] = []
    for _ in range(3):
        res = run_command_subprocess(
            cmd_list, baseline_env, cwd=baseline_cwd, timeout_seconds=timeout_seconds
        )
        baseline_results.append(res)

    base_sig = baseline_results[0].behavior_signature

    # Verify baseline stability (3/3 identical signatures)
    for res in baseline_results[1:]:
        if not res.behavior_signature.matches(base_sig):
            return DiagnosisReport(
                command=cmd_list,
                target_label=target_label,
                baseline_status="UNSTABLE_BASELINE",
                baseline_signature=base_sig,
                target_signature=target_signature,
                total_differences=0,
                eligible_count=0,
                excluded_count=0,
            )

    # Verify baseline is passing (exit code 0 and is_success)
    if not base_sig.is_success:
        return DiagnosisReport(
            command=cmd_list,
            target_label=target_label,
            baseline_status="BASELINE_FAILING",
            baseline_signature=base_sig,
            target_signature=target_signature,
            total_differences=0,
            eligible_count=0,
            excluded_count=0,
        )

    # 5. Compare baseline snapshot vs target snapshot
    diff = compare_snapshots(
        baseline_snap, target_snap, left_label="baseline", right_label="target"
    )

    # 6. Build candidate matrix
    matrix = build_candidate_matrix(
        diff,
        allow_path_perturbation=allow_path_perturbation,
        max_experiments=max_experiments,
    )

    causal_factors: list[CausalFactorReport] = []
    unstable_candidates: list[Candidate] = []

    # 7. Execute experiments for eligible candidates
    for cand in matrix.eligible_candidates:
        outcome = run_candidate_experiment(
            candidate=cand,
            argv=cmd_list,
            baseline_env=baseline_env,
            baseline_cwd=baseline_cwd,
            target_signature=target_signature,
            baseline_signature=base_sig,
            timeout_seconds=timeout_seconds,
        )

        if outcome.outcome_classification == OutcomeClassification.TARGET_MATCH:
            forward_runs_str = f"{outcome.total_runs}/{outcome.total_runs}"
            explanation = (
                f"Changing factor '{cand.key}' from baseline value "
                f"('{cand.baseline_value}') to target value "
                f"('{cand.target_value}') consistently reproduced target failure."
            )
            rec = generate_recommendation(cand.key)

            causal_factors.append(
                CausalFactorReport(
                    candidate=cand,
                    evidence_level=EvidenceLevel.MODERATE,
                    forward_runs=forward_runs_str,
                    reverse_status="UNAVAILABLE (Static Snapshot Mode)",
                    explanation=explanation,
                    recommendation=rec,
                )
            )
        elif (
            outcome.outcome_classification == OutcomeClassification.UNSTABLE_EXPERIMENT
        ):
            unstable_candidates.append(cand)

    return DiagnosisReport(
        command=cmd_list,
        target_label=target_label,
        baseline_status="STABLE_BASELINE",
        baseline_signature=base_sig,
        target_signature=target_signature,
        total_differences=len(diff.differences),
        eligible_count=len(matrix.eligible_candidates),
        excluded_count=len(matrix.excluded_candidates),
        causal_factors=causal_factors,
        unstable_candidates=unstable_candidates,
    )
