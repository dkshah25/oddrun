"""Command-line interface for OddRun."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from oddrun import __version__
from oddrun.compare import compare_snapshots
from oddrun.diagnose import diagnose_behavior, format_diagnosis_text
from oddrun.execution import ExecutionStatus, record_execution
from oddrun.io import SnapshotIOError, load_snapshot, save_record, save_snapshot
from oddrun.models import SnapshotDiff
from oddrun.snapshot import capture_environment


def format_diff_text(diff: SnapshotDiff) -> str:
    """Format a SnapshotDiff into readable text lines."""
    if not diff.has_differences:
        return "No differences found between snapshots."

    lines: list[str] = [
        f"OddRun Environment Comparison: {diff.left_label} vs {diff.right_label}",
        f"Total Differences: {len(diff.differences)}",
        "-" * 60,
    ]

    current_cat = ""
    for item in diff.differences:
        if item.category != current_cat:
            current_cat = item.category
            lines.append(f"\n[{current_cat.upper()}]")

        if item.change_type == "added":
            lines.append(f"  + {item.key}: {item.right_value}")
        elif item.change_type == "removed":
            lines.append(f"  - {item.key}: (was: {item.left_value})")
        else:
            lines.append(f"  ~ {item.key}: {item.left_value} -> {item.right_value}")

    return "\n".join(lines)


def run_capture(args: argparse.Namespace) -> int:
    """Execute 'oddrun capture' subcommand."""
    snapshot = capture_environment()
    output_path = args.output or "oddrun-snapshot.json"

    try:
        save_snapshot(snapshot, output_path)
        print(f"Successfully captured environment snapshot: {output_path}")
        return 0
    except SnapshotIOError as exc:
        print(f"ERROR: Could not write snapshot: {output_path}", file=sys.stderr)
        print(f"Reason: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        if args.debug:
            raise
        print(f"ERROR: Unexpected failure during capture: {exc}", file=sys.stderr)
        return 1


def run_record(args: argparse.Namespace) -> int:
    """Execute 'oddrun record' subcommand."""
    command_argv = args.command
    if not command_argv:
        print("ERROR: No command specified for recording.", file=sys.stderr)
        msg = "Usage: oddrun record --output RECORD.json -- COMMAND [ARGUMENTS...]"
        print(msg, file=sys.stderr)
        return 1

    output_path = args.output or "oddrun-record.json"

    try:
        record = record_execution(command_argv, timeout_seconds=args.timeout)
        if record.execution_result.status == ExecutionStatus.EXEC_ERROR:
            err_msg = record.execution_result.error_message or "Execution failed"
            print(f"ERROR: Could not execute command: {err_msg}", file=sys.stderr)
            return 1

        save_record(record, output_path)
        outcome = "PASS" if record.execution_result.exit_code == 0 else "FAIL"
        code = record.execution_result.exit_code
        print(
            f"Successfully recorded execution "
            f"(Outcome: {outcome}, Exit Code: {code}): {output_path}"
        )
        return 0
    except SnapshotIOError as exc:
        print(f"ERROR: Could not write record file: {output_path}", file=sys.stderr)
        print(f"Reason: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        if args.debug:
            raise
        print(f"ERROR: Unexpected failure during recording: {exc}", file=sys.stderr)
        return 1


def run_compare(args: argparse.Namespace) -> int:
    """Execute 'oddrun compare' subcommand."""
    left_file = args.snapshot1
    right_file = args.snapshot2

    try:
        left_snap = load_snapshot(left_file)
    except SnapshotIOError as exc:
        print(f"ERROR: Could not read snapshot: {left_file}", file=sys.stderr)
        print(f"Reason: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        if args.debug:
            raise
        print(f"ERROR: Failed loading snapshot '{left_file}': {exc}", file=sys.stderr)
        return 1

    try:
        right_snap = load_snapshot(right_file)
    except SnapshotIOError as exc:
        print(f"ERROR: Could not read snapshot: {right_file}", file=sys.stderr)
        print(f"Reason: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        if args.debug:
            raise
        print(f"ERROR: Failed loading snapshot '{right_file}': {exc}", file=sys.stderr)
        return 1

    diff = compare_snapshots(
        left_snap, right_snap, left_label=str(left_file), right_label=str(right_file)
    )

    if args.json:
        print(json.dumps(diff.to_dict(), indent=2))
    else:
        print(format_diff_text(diff))

    return 0


def run_why(args: argparse.Namespace) -> int:
    """Execute 'oddrun why' subcommand."""
    target_record = args.target_record
    command_argv = args.command

    if not command_argv:
        print("ERROR: No command specified for diagnosis.", file=sys.stderr)
        msg = "Usage: oddrun why TARGET_RECORD.json -- COMMAND [ARGUMENTS...]"
        print(msg, file=sys.stderr)
        return 1

    try:
        report = diagnose_behavior(
            target_record=target_record,
            command=command_argv,
            allow_path_perturbation=args.allow_path_perturbation,
            max_experiments=args.max_experiments,
            timeout_seconds=args.timeout,
        )
        print(format_diagnosis_text(report))
        return 0 if not report.error_message else 1
    except SnapshotIOError as exc:
        print(f"ERROR: Could not read target record: {target_record}", file=sys.stderr)
        print(f"Reason: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        if args.debug:
            raise
        print(f"ERROR: Causal diagnosis failed: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    """Construct the main argument parser for OddRun CLI."""
    parser = argparse.ArgumentParser(
        prog="oddrun",
        description="OddRun - When the same code doesn't behave the same.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable full exception tracebacks on error.",
    )

    subparsers = parser.add_subparsers(dest="subcommand", help="Subcommands")

    # Command: capture
    capture_parser = subparsers.add_parser(
        "capture",
        help="Capture a privacy-aware snapshot of the current environment.",
    )
    capture_parser.add_argument(
        "-o",
        "--output",
        default="oddrun-snapshot.json",
        help="Path to output JSON file (default: oddrun-snapshot.json).",
    )

    # Command: record
    record_parser = subparsers.add_parser(
        "record",
        help="Execute a command and record environment snapshot + behavior signature.",
    )
    record_parser.add_argument(
        "-o",
        "--output",
        default="oddrun-record.json",
        help="Path to output JSON record file (default: oddrun-record.json).",
    )
    record_parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Timeout in seconds for recording command execution (default: 30.0).",
    )
    record_parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Command and arguments to execute after '--' separator.",
    )

    # Command: compare
    compare_parser = subparsers.add_parser(
        "compare",
        help="Compare two environment snapshot files.",
    )
    compare_parser.add_argument(
        "snapshot1",
        help="Path to first snapshot JSON file.",
    )
    compare_parser.add_argument(
        "snapshot2",
        help="Path to second snapshot JSON file.",
    )
    compare_parser.add_argument(
        "--json",
        action="store_true",
        help="Output comparison results in structured JSON format.",
    )

    # Command: why
    why_parser = subparsers.add_parser(
        "why",
        help="Diagnose which environmental difference causes a program to fail.",
    )
    why_parser.add_argument(
        "target_record",
        help="Path to target ExecutionRecord JSON file.",
    )
    why_parser.add_argument(
        "--allow-path-perturbation",
        action="store_true",
        help=(
            "Allow testing Tier-2 executable/import factors "
            "(PATH, PYTHONPATH, PYTHONHOME)."
        ),
    )
    why_parser.add_argument(
        "--max-experiments",
        type=int,
        default=10,
        help="Maximum candidate perturbation experiments to test (default: 10).",
    )
    why_parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Timeout in seconds per perturbation experiment (default: 30.0).",
    )
    why_parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Command and arguments to execute after '--' separator.",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""
    parser = build_parser()

    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    command_argv: list[str] = []

    if "--" in raw_argv:
        split_idx = raw_argv.index("--")
        oddrun_args = raw_argv[:split_idx]
        command_argv = raw_argv[split_idx + 1 :]
    else:
        oddrun_args = raw_argv

    args = parser.parse_args(oddrun_args)
    if command_argv:
        args.command = command_argv
    elif hasattr(args, "command") and args.command and args.command[0] == "--":
        args.command = args.command[1:]

    if not args.subcommand:
        parser.print_help()
        return 0

    if args.subcommand == "capture":
        return run_capture(args)
    elif args.subcommand == "record":
        return run_record(args)
    elif args.subcommand == "compare":
        return run_compare(args)
    elif args.subcommand == "why":
        return run_why(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
