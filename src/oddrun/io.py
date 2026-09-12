"""Serialization and file I/O operations for OddRun snapshots and execution records."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TextIO

from oddrun.execution import ExecutionRecord
from oddrun.models import EnvironmentSnapshot


class SnapshotIOError(Exception):
    """Base exception for snapshot I/O errors."""


class SnapshotNotFoundError(SnapshotIOError):
    """Raised when a snapshot file does not exist."""


class InvalidSnapshotFormatError(SnapshotIOError):
    """Raised when a file is malformed JSON or has an invalid schema."""


def save_snapshot(
    snapshot: EnvironmentSnapshot, target: str | Path | TextIO
) -> None:
    """Save an EnvironmentSnapshot as a formatted, deterministic JSON file or stream."""
    data = snapshot.to_dict()
    json_text = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"

    if isinstance(target, (str, Path)):
        path = Path(target)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(json_text)
    else:
        target.write(json_text)


def load_snapshot(source: str | Path | TextIO) -> EnvironmentSnapshot:
    """Load and validate an EnvironmentSnapshot from a JSON file or stream."""
    raw_data = _load_raw_json(source)

    if not isinstance(raw_data, dict):
        raise InvalidSnapshotFormatError("Snapshot root must be a JSON object")

    required_sections = ("python", "system")
    for section in required_sections:
        if section not in raw_data or not isinstance(raw_data[section], dict):
            raise InvalidSnapshotFormatError(
                f"Invalid snapshot structure: missing or invalid '{section}' object"
            )

    try:
        return EnvironmentSnapshot.from_dict(raw_data)
    except Exception as exc:
        raise InvalidSnapshotFormatError(
            f"Failed to construct snapshot object: {exc}"
        ) from exc


def save_record(
    record: ExecutionRecord, target: str | Path | TextIO
) -> None:
    """Save an ExecutionRecord as a formatted, deterministic JSON file or stream."""
    data = record.to_dict()
    json_text = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"

    if isinstance(target, (str, Path)):
        path = Path(target)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(json_text)
    else:
        target.write(json_text)


def load_record(source: str | Path | TextIO) -> ExecutionRecord:
    """Load and validate an ExecutionRecord from a JSON file or stream."""
    raw_data = _load_raw_json(source)

    if not isinstance(raw_data, dict):
        raise InvalidSnapshotFormatError("Record root must be a JSON object")

    if "execution_result" not in raw_data:
        raise InvalidSnapshotFormatError(
            "Target file does not contain an observed execution_result"
        )

    try:
        return ExecutionRecord.from_dict(raw_data)
    except Exception as exc:
        raise InvalidSnapshotFormatError(
            f"Failed to construct execution record: {exc}"
        ) from exc


def load_target_artifact(
    source: str | Path | TextIO,
) -> ExecutionRecord | EnvironmentSnapshot:
    """Load either an ExecutionRecord or a plain EnvironmentSnapshot from JSON."""
    raw_data = _load_raw_json(source)
    if not isinstance(raw_data, dict):
        raise InvalidSnapshotFormatError("Artifact root must be a JSON object")

    if "execution_result" in raw_data:
        return ExecutionRecord.from_dict(raw_data)

    if "python" in raw_data and "system" in raw_data:
        return EnvironmentSnapshot.from_dict(raw_data)

    raise InvalidSnapshotFormatError(
        "Invalid OddRun artifact: expected EnvironmentSnapshot or ExecutionRecord"
    )


def _load_raw_json(source: str | Path | TextIO) -> dict:
    if isinstance(source, (str, Path)):
        path = Path(source)
        if not path.is_file():
            raise SnapshotNotFoundError(f"File not found: '{path}'")
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as exc:
            raise InvalidSnapshotFormatError(
                f"Failed to parse '{path}': Invalid JSON ({exc.msg})"
            ) from exc
        except Exception as exc:
            raise SnapshotIOError(f"Failed to read file '{path}': {exc}") from exc
    else:
        try:
            return json.load(source)
        except json.JSONDecodeError as exc:
            raise InvalidSnapshotFormatError(
                f"Failed to parse JSON stream: Invalid JSON ({exc.msg})"
            ) from exc
