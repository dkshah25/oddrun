"""Basic usage example for the OddRun Python API."""

import tempfile
from pathlib import Path

from oddrun import capture_environment, compare_snapshots, load_snapshot, save_snapshot


def main():
    print("1. Capturing current environment snapshot...")
    snapshot = capture_environment()
    print(f"   Python Version : {snapshot.python.version}")
    arch = snapshot.system.architecture
    print(f"   OS Name        : {snapshot.system.os_name} ({arch})")
    print(f"   Packages Count : {len(snapshot.packages)}")
    print(f"   Env Vars Count : {len(snapshot.environment)}")

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_a = Path(tmp_dir) / "snapshot_a.json"
        file_b = Path(tmp_dir) / "snapshot_b.json"

        print(f"\n2. Saving snapshot to {file_a.name}...")
        save_snapshot(snapshot, file_a)

        # Simulate loading snapshots
        snap_a = load_snapshot(file_a)
        save_snapshot(snap_a, file_b)
        snap_b = load_snapshot(file_b)

        print("\n3. Comparing identical snapshots...")
        diff = compare_snapshots(snap_a, snap_b, left_label="local", right_label="ci")
        print(f"   Has Differences? {diff.has_differences}")
        print(f"   Difference Count: {len(diff.differences)}")

        print("\n4. Verification completed successfully!")


if __name__ == "__main__":
    main()
