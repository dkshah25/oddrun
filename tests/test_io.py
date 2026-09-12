"""Unit tests for snapshot serialization and file I/O."""

import io
import json

import pytest

from oddrun.io import (
    InvalidSnapshotFormatError,
    SnapshotNotFoundError,
    load_snapshot,
    save_snapshot,
)
from oddrun.models import EnvironmentSnapshot, PythonInfo, SystemInfo


def make_minimal_snapshot() -> EnvironmentSnapshot:
    return EnvironmentSnapshot(
        python=PythonInfo(
            version="3.10.0",
            implementation="CPython",
            executable="/bin/python",
            sys_prefix="/prefix",
            base_prefix="/prefix",
            platform="linux",
        ),
        system=SystemInfo(
            os_name="Linux",
            os_release="5.0",
            architecture="x86_64",
            processor="x86_64",
            cwd="/app",
            timezone="UTC",
        ),
        environment={"PATH": "/usr/bin"},
        packages={"pytest": "7.0.0"},
        captured_at="2026-09-12T12:00:00Z",
    )


def test_save_and_load_file_roundtrip(tmp_path):
    snapshot = make_minimal_snapshot()
    file_path = tmp_path / "snapshot.json"

    save_snapshot(snapshot, file_path)
    assert file_path.is_file()

    loaded = load_snapshot(file_path)
    assert loaded == snapshot


def test_save_and_load_stream_roundtrip():
    snapshot = make_minimal_snapshot()
    stream = io.StringIO()

    save_snapshot(snapshot, stream)
    stream.seek(0)

    loaded = load_snapshot(stream)
    assert loaded == snapshot


def test_load_nonexistent_file():
    with pytest.raises(SnapshotNotFoundError):
        load_snapshot("/nonexistent/path/to/snapshot.json")


def test_load_malformed_json_stream():
    stream = io.StringIO("{ invalid json ...")
    with pytest.raises(InvalidSnapshotFormatError):
        load_snapshot(stream)


def test_load_invalid_schema_stream():
    stream = io.StringIO(json.dumps({"schema_version": "1.0", "foo": "bar"}))
    with pytest.raises(InvalidSnapshotFormatError):
        load_snapshot(stream)
