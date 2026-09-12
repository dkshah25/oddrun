"""Realistic end-to-end scenario tests for environment comparison."""

from oddrun.compare import compare_snapshots
from oddrun.models import EnvironmentSnapshot, PythonInfo, SystemInfo


def create_baseline_snapshot() -> EnvironmentSnapshot:
    """Create a baseline environment snapshot fixture."""
    return EnvironmentSnapshot(
        python=PythonInfo(
            version="3.10.12",
            implementation="CPython",
            executable="/usr/bin/python3",
            sys_prefix="/usr",
            base_prefix="/usr",
            platform="linux",
            cache_tag="cpython-310",
        ),
        system=SystemInfo(
            os_name="Linux",
            os_release="5.15.0",
            architecture="x86_64",
            processor="x86_64",
            cwd="/app",
            timezone="UTC",
        ),
        environment={
            "PATH": "/usr/local/bin:/usr/bin",
            "LANG": "en_US.UTF-8",
            "PYTHONPATH": "/app/src",
            "API_KEY": "<present>",
        },
        packages={
            "numpy": "1.24.3",
            "pandas": "2.0.1",
            "pytest": "7.4.0",
        },
        captured_at="2026-09-12T10:00:00Z",
    )


def test_scenario_environment_variable_difference():
    """Scenario 1: Detect differences in environment variables between local and CI."""
    local_snap = create_baseline_snapshot()

    # CI environment has different PYTHONPATH and additional CI env var
    ci_env = dict(local_snap.environment)
    ci_env["PYTHONPATH"] = "/workspace/src"
    ci_env["CI"] = "true"

    ci_snap = EnvironmentSnapshot(
        python=local_snap.python,
        system=local_snap.system,
        environment=ci_env,
        packages=local_snap.packages,
        captured_at="2026-09-12T10:05:00Z",
    )

    diff = compare_snapshots(local_snap, ci_snap, left_label="local", right_label="ci")

    assert diff.has_differences is True
    env_diffs = [d for d in diff.differences if d.category == "environment"]
    assert len(env_diffs) == 2

    # CI variable added
    ci_diff = next(d for d in env_diffs if d.key == "CI")
    assert ci_diff.change_type == "added"
    assert ci_diff.left_value is None
    assert ci_diff.right_value == "true"

    # PYTHONPATH changed
    path_diff = next(d for d in env_diffs if d.key == "PYTHONPATH")
    assert path_diff.change_type == "changed"
    assert path_diff.left_value == "/app/src"
    assert path_diff.right_value == "/workspace/src"


def test_scenario_timezone_system_difference():
    """Scenario 2: Detect system timezone differences between dev machine and server."""
    dev_snap = create_baseline_snapshot()

    # Server system running on UTC while dev machine runs on EST
    dev_sys = SystemInfo(
        os_name="Darwin",
        os_release="22.5.0",
        architecture="arm64",
        processor="arm",
        cwd="/Users/dev/project",
        timezone="EST",
    )

    dev_machine_snap = EnvironmentSnapshot(
        python=dev_snap.python,
        system=dev_sys,
        environment=dev_snap.environment,
        packages=dev_snap.packages,
        captured_at="2026-09-12T10:00:00Z",
    )

    diff = compare_snapshots(
        dev_machine_snap, dev_snap, left_label="mac", right_label="linux"
    )

    assert diff.has_differences is True
    sys_diffs = [d for d in diff.differences if d.category == "system"]

    tz_diff = next(d for d in sys_diffs if d.key == "timezone")
    assert tz_diff.change_type == "changed"
    assert tz_diff.left_value == "EST"
    assert tz_diff.right_value == "UTC"


def test_scenario_package_version_difference():
    """Scenario 3: Detect package version mismatch causing behavioral divergence."""
    dev_snap = create_baseline_snapshot()

    # Production server has numpy 1.26.0 and missing pytest
    prod_pkgs = {
        "numpy": "1.26.0",
        "pandas": "2.0.1",
    }

    prod_snap = EnvironmentSnapshot(
        python=dev_snap.python,
        system=dev_snap.system,
        environment=dev_snap.environment,
        packages=prod_pkgs,
        captured_at="2026-09-12T10:00:00Z",
    )

    diff = compare_snapshots(dev_snap, prod_snap, left_label="dev", right_label="prod")

    assert diff.has_differences is True
    pkg_diffs = [d for d in diff.differences if d.category == "packages"]
    assert len(pkg_diffs) == 2

    # numpy changed
    numpy_diff = next(d for d in pkg_diffs if d.key == "numpy")
    assert numpy_diff.change_type == "changed"
    assert numpy_diff.left_value == "1.24.3"
    assert numpy_diff.right_value == "1.26.0"

    # pytest removed in prod
    pytest_diff = next(d for d in pkg_diffs if d.key == "pytest")
    assert pytest_diff.change_type == "removed"
    assert pytest_diff.left_value == "7.4.0"
    assert pytest_diff.right_value is None
