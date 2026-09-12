"""Deterministic comparison engine for OddRun environment snapshots."""

from __future__ import annotations

from typing import Any

from oddrun.models import DiffItem, EnvironmentSnapshot, SnapshotDiff


def _compare_dicts(
    category: str, left: dict[str, Any], right: dict[str, Any]
) -> list[DiffItem]:
    """Compare two dictionaries deterministically and produce a list of DiffItems."""
    diffs: list[DiffItem] = []
    all_keys = sorted(set(left.keys()) | set(right.keys()))

    for key in all_keys:
        in_left = key in left
        in_right = key in right

        left_val = str(left[key]) if (in_left and left[key] is not None) else None
        right_val = str(right[key]) if (in_right and right[key] is not None) else None

        if in_left and not in_right:
            diffs.append(
                DiffItem(
                    category=category,
                    key=key,
                    left_value=left_val,
                    right_value=None,
                    change_type="removed",
                )
            )
        elif not in_left and in_right:
            diffs.append(
                DiffItem(
                    category=category,
                    key=key,
                    left_value=None,
                    right_value=right_val,
                    change_type="added",
                )
            )
        elif left_val != right_val:
            diffs.append(
                DiffItem(
                    category=category,
                    key=key,
                    left_value=left_val,
                    right_value=right_val,
                    change_type="changed",
                )
            )

    return diffs


def compare_snapshots(
    left: EnvironmentSnapshot,
    right: EnvironmentSnapshot,
    left_label: str = "left",
    right_label: str = "right",
) -> SnapshotDiff:
    """Compare two EnvironmentSnapshots and return a SnapshotDiff."""
    differences: list[DiffItem] = []

    # Category 1: Python
    differences.extend(
        _compare_dicts("python", left.python.to_dict(), right.python.to_dict())
    )

    # Category 2: System
    differences.extend(
        _compare_dicts("system", left.system.to_dict(), right.system.to_dict())
    )

    # Category 3: Environment
    differences.extend(
        _compare_dicts("environment", left.environment, right.environment)
    )

    # Category 4: Packages
    differences.extend(_compare_dicts("packages", left.packages, right.packages))

    # Guarantee deterministic final ordering by category and key
    category_order = {"python": 0, "system": 1, "environment": 2, "packages": 3}
    differences.sort(key=lambda d: (category_order.get(d.category, 99), d.key))

    return SnapshotDiff(
        left_label=left_label,
        right_label=right_label,
        differences=differences,
    )
