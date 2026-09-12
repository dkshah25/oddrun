"""Unit tests for snapshot comparison logic."""

from oddrun.compare import compare_snapshots
from oddrun.models import EnvironmentSnapshot, PythonInfo, SystemInfo


def make_sample_snapshot(
    py_version="3.10.0",
    os_name="Linux",
    env=None,
    pkgs=None,
) -> EnvironmentSnapshot:
    return EnvironmentSnapshot(
        python=PythonInfo(
            version=py_version,
            implementation="CPython",
            executable="/bin/python",
            sys_prefix="/prefix",
            base_prefix="/prefix",
            platform="linux",
        ),
        system=SystemInfo(
            os_name=os_name,
            os_release="5.0",
            architecture="x86_64",
            processor="x86_64",
            cwd="/app",
            timezone="UTC",
        ),
        environment=env or {"PATH": "/usr/bin"},
        packages=pkgs or {"requests": "2.31.0"},
        captured_at="2026-09-12T12:00:00Z",
    )


def test_compare_identical_snapshots():
    snap_a = make_sample_snapshot()
    snap_b = make_sample_snapshot()

    diff = compare_snapshots(snap_a, snap_b)
    assert diff.has_differences is False
    assert len(diff.differences) == 0


def test_compare_python_version_change():
    snap_a = make_sample_snapshot(py_version="3.10.0")
    snap_b = make_sample_snapshot(py_version="3.11.0")

    diff = compare_snapshots(snap_a, snap_b)
    assert diff.has_differences is True
    assert len(diff.differences) == 1

    item = diff.differences[0]
    assert item.category == "python"
    assert item.key == "version"
    assert item.left_value == "3.10.0"
    assert item.right_value == "3.11.0"
    assert item.change_type == "changed"


def test_compare_environment_added_and_removed_keys():
    snap_a = make_sample_snapshot(env={"FOO": "1", "BAR": "2"})
    snap_b = make_sample_snapshot(env={"BAR": "2", "BAZ": "3"})

    diff = compare_snapshots(snap_a, snap_b)
    assert diff.has_differences is True
    assert len(diff.differences) == 2

    # Deterministic sorting check: BAZ (added) comes before FOO (removed) alphabetically
    diff_baz = diff.differences[0]
    assert diff_baz.key == "BAZ"
    assert diff_baz.change_type == "added"
    assert diff_baz.left_value is None
    assert diff_baz.right_value == "3"

    diff_foo = diff.differences[1]
    assert diff_foo.key == "FOO"
    assert diff_foo.change_type == "removed"
    assert diff_foo.left_value == "1"
    assert diff_foo.right_value is None


def test_compare_package_changes():
    snap_a = make_sample_snapshot(pkgs={"numpy": "1.24.0"})
    snap_b = make_sample_snapshot(pkgs={"numpy": "1.26.0", "pandas": "2.0.0"})

    diff = compare_snapshots(snap_a, snap_b)
    assert diff.has_differences is True
    assert len(diff.differences) == 2

    pkg_diffs = [d for d in diff.differences if d.category == "packages"]
    assert len(pkg_diffs) == 2
    assert pkg_diffs[0].key == "numpy"
    assert pkg_diffs[0].change_type == "changed"
    assert pkg_diffs[1].key == "pandas"
    assert pkg_diffs[1].change_type == "added"
