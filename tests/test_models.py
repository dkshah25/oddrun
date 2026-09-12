"""Unit tests for OddRun data models."""

from oddrun.models import (
    SCHEMA_VERSION,
    DiffItem,
    EnvironmentSnapshot,
    PythonInfo,
    SnapshotDiff,
    SystemInfo,
)


def test_python_info_dict_roundtrip():
    info = PythonInfo(
        version="3.10.12",
        implementation="CPython",
        executable="/usr/bin/python3",
        sys_prefix="/usr",
        base_prefix="/usr",
        platform="linux",
        cache_tag="cpython-310",
    )
    d = info.to_dict()
    assert d["version"] == "3.10.12"
    assert d["cache_tag"] == "cpython-310"

    reconstructed = PythonInfo.from_dict(d)
    assert reconstructed == info


def test_system_info_dict_roundtrip():
    info = SystemInfo(
        os_name="Linux",
        os_release="5.15.0",
        architecture="x86_64",
        processor="x86_64",
        cwd="/workspace",
        timezone="UTC",
    )
    d = info.to_dict()
    assert d["os_name"] == "Linux"
    assert d["cwd"] == "/workspace"

    reconstructed = SystemInfo.from_dict(d)
    assert reconstructed == info


def test_environment_snapshot_dict_roundtrip():
    py = PythonInfo("3.11.0", "CPython", "/py", "/py", "/py", "linux")
    sys_info = SystemInfo("Linux", "6.0", "x86_64", "x86_64", "/app", "UTC")
    env = {"PATH": "/bin", "LANG": "en_US.UTF-8"}
    pkgs = {"pytest": "7.4.0", "oddrun": "0.1.0a1"}

    snapshot = EnvironmentSnapshot(
        python=py,
        system=sys_info,
        environment=env,
        packages=pkgs,
        captured_at="2026-09-12T12:00:00Z",
    )

    d = snapshot.to_dict()
    assert d["schema_version"] == SCHEMA_VERSION
    assert d["captured_at"] == "2026-09-12T12:00:00Z"
    assert d["environment"]["PATH"] == "/bin"
    assert d["packages"]["pytest"] == "7.4.0"

    reconstructed = EnvironmentSnapshot.from_dict(d)
    assert reconstructed.python == py
    assert reconstructed.system == sys_info
    assert reconstructed.environment == env
    assert reconstructed.packages == pkgs


def test_snapshot_diff_properties():
    diff_item = DiffItem(
        category="environment",
        key="FOO",
        left_value="1",
        right_value="2",
        change_type="changed",
    )
    diff = SnapshotDiff(
        left_label="a",
        right_label="b",
        differences=[diff_item],
    )
    assert diff.has_differences is True
    assert diff.to_dict()["difference_count"] == 1

    empty_diff = SnapshotDiff(left_label="a", right_label="b", differences=[])
    assert empty_diff.has_differences is False
    assert empty_diff.to_dict()["difference_count"] == 0
