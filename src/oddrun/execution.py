"""Subprocess execution runner, timeout cleanup, and output normalization."""

from __future__ import annotations

import os
import re
import signal
import subprocess
import sys
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from oddrun.models import EnvironmentSnapshot
from oddrun.security import redact_environment
from oddrun.snapshot import capture_environment


class ExecutionStatus(Enum):
    """Status of subprocess execution attempt."""

    SUCCESS = "SUCCESS"
    TIMEOUT = "TIMEOUT"
    EXEC_ERROR = "EXEC_ERROR"


@dataclass(frozen=True)
class BehaviorSignature:
    """Normalized structural fingerprint of process execution outcome."""

    is_success: bool
    termination_kind: str  # 'EXIT_CODE', 'SIGNAL', 'TIMEOUT', 'EXEC_ERROR'
    exit_code: int | None
    exception_type: str | None
    normalized_diag: str

    def matches(self, other: BehaviorSignature) -> bool:
        """Determine whether two executions represent identical program behavior."""
        if self.is_success != other.is_success:
            return False
        if self.termination_kind != other.termination_kind:
            return False
        if (
            self.exit_code is not None
            and other.exit_code is not None
            and self.exit_code != other.exit_code
        ):
            return False
        if (
            self.exception_type
            and other.exception_type
            and self.exception_type != other.exception_type
        ):
            return False
        if (
            self.normalized_diag
            and other.normalized_diag
            and self.normalized_diag != other.normalized_diag
        ):
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BehaviorSignature:
        return cls(
            is_success=bool(data.get("is_success", False)),
            termination_kind=str(data.get("termination_kind", "EXIT_CODE")),
            exit_code=data.get("exit_code"),
            exception_type=data.get("exception_type"),
            normalized_diag=str(data.get("normalized_diag", "")),
        )


@dataclass(frozen=True)
class ExecutionResult:
    """Complete captured result of a subprocess execution."""

    status: ExecutionStatus
    exit_code: int | None
    stdout: str
    stderr: str
    duration_ms: float
    behavior_signature: BehaviorSignature
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_ms": self.duration_ms,
            "behavior_signature": self.behavior_signature.to_dict(),
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExecutionResult:
        status_str = str(data.get("status", "SUCCESS"))
        try:
            status = ExecutionStatus(status_str)
        except ValueError:
            status = ExecutionStatus.SUCCESS

        sig_data = data.get("behavior_signature", {})
        sig = BehaviorSignature.from_dict(
            sig_data if isinstance(sig_data, dict) else {}
        )

        return cls(
            status=status,
            exit_code=data.get("exit_code"),
            stdout=str(data.get("stdout", "")),
            stderr=str(data.get("stderr", "")),
            duration_ms=float(data.get("duration_ms", 0.0)),
            behavior_signature=sig,
            error_message=data.get("error_message"),
        )


@dataclass(frozen=True)
class ExecutionRecord:
    """EnvironmentSnapshot combined with an observed ExecutionResult for a command."""

    command: list[str]
    environment_snapshot: EnvironmentSnapshot
    execution_result: ExecutionResult
    schema_version: str = "1.0"
    recorded_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "recorded_at": self.recorded_at,
            "command": list(self.command),
            "environment_snapshot": self.environment_snapshot.to_dict(),
            "execution_result": self.execution_result.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExecutionRecord:
        snap_data = data.get("environment_snapshot", {})
        res_data = data.get("execution_result", {})

        snap = EnvironmentSnapshot.from_dict(
            snap_data if isinstance(snap_data, dict) else {}
        )
        res = ExecutionResult.from_dict(
            res_data if isinstance(res_data, dict) else {}
        )

        cmd_raw = data.get("command", [])
        cmd = [str(x) for x in cmd_raw] if isinstance(cmd_raw, list) else []

        return cls(
            schema_version=str(data.get("schema_version", "1.0")),
            recorded_at=str(data.get("recorded_at", "")),
            command=cmd,
            environment_snapshot=snap,
            execution_result=res,
        )


def normalize_diagnostic_text(text: str, env: dict[str, str] | None = None) -> str:
    """Normalize diagnostic text for deterministic signature comparison."""
    if not text:
        return ""

    normalized = text

    # Redact known environment secrets if env provided
    if env:
        redacted = redact_environment(env)
        for key, val in env.items():
            if val and len(val) > 2 and redacted.get(key) == "<present>":
                normalized = normalized.replace(val, "<present>")

    # Replace memory addresses e.g. 0x7f9a8b1c
    normalized = re.sub(r"0x[0-9a-fA-F]+", "[ADDR]", normalized)

    # Replace line numbers e.g. line 42
    normalized = re.sub(r"line \d+", "line [N]", normalized)

    # Replace absolute file paths with relative basenames
    normalized = re.sub(
        r"/[^\s:\'\"]+?/([^/\s:\'\"]+\.[a-zA-Z0-9]+)", r"[PATH]/\1", normalized
    )
    normalized = re.sub(
        r"[a-zA-Z]:\\[^\s:\'\"]+?\\([^\s:\\'\"]+\.[a-zA-Z0-9]+)",
        r"[PATH]/\1",
        normalized,
    )

    lines = [line.strip() for line in normalized.splitlines() if line.strip()]
    if not lines:
        return ""

    return " | ".join(lines[-2:])


def parse_exception_type(stderr: str) -> str | None:
    """Extract exception type string from stderr if present (e.g. KeyError)."""
    if not stderr:
        return None

    match = re.search(
        r"([A-Za-z_][A-Za-z0-9_]*Error|[A-Za-z_][A-Za-z0-9_]*Exception):", stderr
    )
    if match:
        return match.group(1)
    return None


def extract_behavior_signature(
    status: ExecutionStatus,
    exit_code: int | None,
    stdout: str,
    stderr: str,
    env: dict[str, str] | None = None,
) -> BehaviorSignature:
    """Construct a structural BehaviorSignature from process execution output."""
    if status == ExecutionStatus.EXEC_ERROR:
        return BehaviorSignature(
            is_success=False,
            termination_kind="EXEC_ERROR",
            exit_code=None,
            exception_type="ExecError",
            normalized_diag="EXEC_ERROR",
        )

    if status == ExecutionStatus.TIMEOUT:
        return BehaviorSignature(
            is_success=False,
            termination_kind="TIMEOUT",
            exit_code=None,
            exception_type="TimeoutError",
            normalized_diag="TIMEOUT",
        )

    is_success = exit_code == 0
    term_kind = "EXIT_CODE" if exit_code is not None else "SIGNAL"
    exc_type = parse_exception_type(stderr)

    diag_source = stderr if stderr.strip() else stdout
    normalized_diag = normalize_diagnostic_text(diag_source, env)

    return BehaviorSignature(
        is_success=is_success,
        termination_kind=term_kind,
        exit_code=exit_code,
        exception_type=exc_type,
        normalized_diag=normalized_diag,
    )


def _kill_process_tree(proc: subprocess.Popen[str]) -> None:
    """Attempt cross-platform process tree termination gracefully on timeout."""
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        else:
            pgid = os.getpgid(proc.pid)
            os.killpg(pgid, signal.SIGKILL)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def run_command_subprocess(
    argv: list[str],
    env: dict[str, str],
    cwd: str | Path | None = None,
    timeout_seconds: float = 30.0,
) -> ExecutionResult:
    """Execute a command in an isolated subprocess with explicit env and cwd."""
    if not argv:
        sig = extract_behavior_signature(ExecutionStatus.EXEC_ERROR, None, "", "")
        return ExecutionResult(
            status=ExecutionStatus.EXEC_ERROR,
            exit_code=None,
            stdout="",
            stderr="",
            duration_ms=0.0,
            behavior_signature=sig,
            error_message="Empty argument list provided",
        )

    effective_cwd = str(cwd) if cwd else os.getcwd()
    if not os.path.exists(effective_cwd):
        sig = extract_behavior_signature(ExecutionStatus.EXEC_ERROR, None, "", "")
        return ExecutionResult(
            status=ExecutionStatus.EXEC_ERROR,
            exit_code=None,
            stdout="",
            stderr="",
            duration_ms=0.0,
            behavior_signature=sig,
            error_message=(
                f"Specified working directory does not exist: '{effective_cwd}'"
            ),
        )

    is_win = sys.platform == "win32"
    creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP if is_win else 0
    start_session = not is_win

    start_time = time.perf_counter()

    try:
        proc = subprocess.Popen(
            argv,
            shell=False,
            env=env,
            cwd=effective_cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=creation_flags,
            start_new_session=start_session,
        )
    except FileNotFoundError:
        sig = extract_behavior_signature(ExecutionStatus.EXEC_ERROR, None, "", "")
        return ExecutionResult(
            status=ExecutionStatus.EXEC_ERROR,
            exit_code=None,
            stdout="",
            stderr="",
            duration_ms=0.0,
            behavior_signature=sig,
            error_message=f"Executable '{argv[0]}' not found in PATH",
        )
    except Exception as exc:
        sig = extract_behavior_signature(ExecutionStatus.EXEC_ERROR, None, "", "")
        return ExecutionResult(
            status=ExecutionStatus.EXEC_ERROR,
            exit_code=None,
            stdout="",
            stderr="",
            duration_ms=0.0,
            behavior_signature=sig,
            error_message=f"Failed to spawn process: {exc}",
        )

    try:
        stdout_data, stderr_data = proc.communicate(timeout=timeout_seconds)
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        exit_code = proc.returncode

        sig = extract_behavior_signature(
            ExecutionStatus.SUCCESS, exit_code, stdout_data, stderr_data, env
        )
        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            exit_code=exit_code,
            stdout=stdout_data or "",
            stderr=stderr_data or "",
            duration_ms=duration_ms,
            behavior_signature=sig,
        )
    except subprocess.TimeoutExpired:
        _kill_process_tree(proc)
        try:
            proc.wait(timeout=2.0)
        except Exception:
            pass

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        sig = extract_behavior_signature(ExecutionStatus.TIMEOUT, None, "", "")
        return ExecutionResult(
            status=ExecutionStatus.TIMEOUT,
            exit_code=None,
            stdout="",
            stderr="",
            duration_ms=duration_ms,
            behavior_signature=sig,
            error_message=(
                f"Command execution timed out after {timeout_seconds} seconds"
            ),
        )


def record_execution(
    command: Sequence[str], timeout_seconds: float = 30.0
) -> ExecutionRecord:
    """Execute command ONCE and record snapshot + result."""
    cmd_list = list(command)
    snap = capture_environment()
    raw_env = dict(os.environ)

    res = run_command_subprocess(
        cmd_list, raw_env, cwd=os.getcwd(), timeout_seconds=timeout_seconds
    )
    rec_time = datetime.now(timezone.utc).isoformat()

    return ExecutionRecord(
        command=cmd_list,
        environment_snapshot=snap,
        execution_result=res,
        recorded_at=rec_time,
    )
