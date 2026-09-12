"""Data models for OddRun environment snapshots, execution records, and comparisons."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class PythonInfo:
    """Detailed information about the Python interpreter environment."""

    version: str
    implementation: str
    executable: str
    sys_prefix: str
    base_prefix: str
    platform: str
    cache_tag: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PythonInfo:
        return cls(
            version=str(data.get("version", "")),
            implementation=str(data.get("implementation", "")),
            executable=str(data.get("executable", "")),
            sys_prefix=str(data.get("sys_prefix", "")),
            base_prefix=str(data.get("base_prefix", "")),
            platform=str(data.get("platform", "")),
            cache_tag=data.get("cache_tag"),
        )


@dataclass(frozen=True)
class SystemInfo:
    """Detailed information about the host system."""

    os_name: str
    os_release: str
    architecture: str
    processor: str
    cwd: str
    timezone: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SystemInfo:
        return cls(
            os_name=str(data.get("os_name", "")),
            os_release=str(data.get("os_release", "")),
            architecture=str(data.get("architecture", "")),
            processor=str(data.get("processor", "")),
            cwd=str(data.get("cwd", "")),
            timezone=str(data.get("timezone", "")),
        )


@dataclass(frozen=True)
class EnvironmentSnapshot:
    """A captured snapshot of a Python execution environment."""

    python: PythonInfo
    system: SystemInfo
    environment: dict[str, str] = field(default_factory=dict)
    packages: dict[str, str] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION
    captured_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "captured_at": self.captured_at,
            "python": self.python.to_dict(),
            "system": self.system.to_dict(),
            "environment": dict(sorted(self.environment.items())),
            "packages": dict(sorted(self.packages.items())),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EnvironmentSnapshot:
        schema_version = str(data.get("schema_version", SCHEMA_VERSION))
        python_data = data.get("python", {})
        system_data = data.get("system", {})
        env_data = data.get("environment", {})
        packages_data = data.get("packages", {})

        py_dict = python_data if isinstance(python_data, dict) else {}
        sys_dict = system_data if isinstance(system_data, dict) else {}

        return cls(
            schema_version=schema_version,
            captured_at=str(data.get("captured_at", "")),
            python=PythonInfo.from_dict(py_dict),
            system=SystemInfo.from_dict(sys_dict),
            environment={
                str(k): str(v) for k, v in env_data.items()
            } if isinstance(env_data, dict) else {},
            packages={
                str(k): str(v) for k, v in packages_data.items()
            } if isinstance(packages_data, dict) else {},
        )


@dataclass(frozen=True)
class DiffItem:
    """Represents a single structural difference between two snapshots."""

    category: str
    key: str
    left_value: str | None
    right_value: str | None
    change_type: str  # 'added', 'removed', 'changed'

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SnapshotDiff:
    """Complete diff result between two EnvironmentSnapshot instances."""

    left_label: str
    right_label: str
    differences: list[DiffItem] = field(default_factory=list)

    @property
    def has_differences(self) -> bool:
        return len(self.differences) > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "left_label": self.left_label,
            "right_label": self.right_label,
            "has_differences": self.has_differences,
            "difference_count": len(self.differences),
            "differences": [item.to_dict() for item in self.differences],
        }
