"""Integration tests for the OddRun CLI."""

import pytest

from oddrun.cli import main
from oddrun.io import load_snapshot, save_snapshot
from oddrun.models import EnvironmentSnapshot, PythonInfo, SystemInfo


def test_cli_help(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "OddRun - When the same code doesn't behave the same." in captured.out


def test_cli_version(capsys):
    try:
        main(["--version"])
    except SystemExit as exc:
        assert exc.code == 0
    captured = capsys.readouterr()
    assert "oddrun" in captured.out


def test_cli_capture(tmp_path, capsys):
    output_file = tmp_path / "test_snap.json"
    exit_code = main(["capture", "--output", str(output_file)])

    assert exit_code == 0
    assert output_file.is_file()

    captured = capsys.readouterr()
    assert "Successfully captured environment snapshot" in captured.out

    loaded = load_snapshot(output_file)
    assert loaded.python.version != ""


def test_cli_compare_identical(tmp_path, capsys):
    snap_file = tmp_path / "snap.json"
    snap = EnvironmentSnapshot(
        python=PythonInfo("3.10.0", "CPython", "/py", "/py", "/py", "linux"),
        system=SystemInfo("Linux", "5.0", "x86_64", "x86_64", "/app", "UTC"),
        environment={"PATH": "/bin"},
        packages={"pytest": "7.0.0"},
    )
    save_snapshot(snap, snap_file)

    exit_code = main(["compare", str(snap_file), str(snap_file)])
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "No differences found between snapshots." in captured.out


def test_cli_compare_differences(tmp_path, capsys):
    snap_a_file = tmp_path / "snap_a.json"
    snap_b_file = tmp_path / "snap_b.json"

    snap_a = EnvironmentSnapshot(
        python=PythonInfo("3.10.0", "CPython", "/py", "/py", "/py", "linux"),
        system=SystemInfo("Linux", "5.0", "x86_64", "x86_64", "/app", "UTC"),
        environment={"PATH": "/bin"},
        packages={"pytest": "7.0.0"},
    )
    snap_b = EnvironmentSnapshot(
        python=PythonInfo("3.11.0", "CPython", "/py", "/py", "/py", "linux"),
        system=SystemInfo("Linux", "5.0", "x86_64", "x86_64", "/app", "UTC"),
        environment={"PATH": "/bin"},
        packages={"pytest": "7.4.0"},
    )

    save_snapshot(snap_a, snap_a_file)
    save_snapshot(snap_b, snap_b_file)

    exit_code = main(["compare", str(snap_a_file), str(snap_b_file)])
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "Total Differences: 2" in captured.out
    assert "version: 3.10.0 -> 3.11.0" in captured.out
    assert "pytest: 7.0.0 -> 7.4.0" in captured.out


def test_cli_compare_json_option(tmp_path, capsys):
    snap_a_file = tmp_path / "snap_a.json"
    snap_b_file = tmp_path / "snap_b.json"

    snap_a = EnvironmentSnapshot(
        python=PythonInfo("3.10.0", "CPython", "/py", "/py", "/py", "linux"),
        system=SystemInfo("Linux", "5.0", "x86_64", "x86_64", "/app", "UTC"),
    )
    snap_b = EnvironmentSnapshot(
        python=PythonInfo("3.11.0", "CPython", "/py", "/py", "/py", "linux"),
        system=SystemInfo("Linux", "5.0", "x86_64", "x86_64", "/app", "UTC"),
    )

    save_snapshot(snap_a, snap_a_file)
    save_snapshot(snap_b, snap_b_file)

    exit_code = main(["compare", str(snap_a_file), str(snap_b_file), "--json"])
    assert exit_code == 0

    captured = capsys.readouterr()
    assert '"has_differences": true' in captured.out


def test_cli_file_not_found(capsys):
    exit_code = main(["compare", "nonexistent_a.json", "nonexistent_b.json"])
    assert exit_code == 1

    captured = capsys.readouterr()
    assert "ERROR: Could not read snapshot" in captured.err


def test_cli_record_nonexistent_executable_fails(tmp_path, capsys):
    output_file = tmp_path / "rec.json"
    exit_code = main(
        ["record", "--output", str(output_file), "--", "nonexistent_command_12345"]
    )
    assert exit_code == 1
    assert not output_file.exists()

    captured = capsys.readouterr()
    assert "ERROR: Could not execute command" in captured.err

