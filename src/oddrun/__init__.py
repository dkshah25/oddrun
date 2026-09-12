"""OddRun - When the same code doesn't behave the same."""

from oddrun.compare import compare_snapshots
from oddrun.diagnose import diagnose_behavior
from oddrun.execution import ExecutionRecord, record_execution
from oddrun.io import load_record, load_snapshot, save_record, save_snapshot
from oddrun.models import (
    DiffItem,
    EnvironmentSnapshot,
    PythonInfo,
    SnapshotDiff,
    SystemInfo,
)
from oddrun.snapshot import capture_environment

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "EnvironmentSnapshot",
    "ExecutionRecord",
    "PythonInfo",
    "SystemInfo",
    "SnapshotDiff",
    "DiffItem",
    "capture_environment",
    "compare_snapshots",
    "diagnose_behavior",
    "load_record",
    "load_snapshot",
    "record_execution",
    "save_record",
    "save_snapshot",
]
