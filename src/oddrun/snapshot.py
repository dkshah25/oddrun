"""Environment snapshot capture logic for OddRun."""

from __future__ import annotations

import importlib.metadata
import os
import pathlib
import platform
import sys
import time
from datetime import datetime, timezone

from oddrun.models import EnvironmentSnapshot, PythonInfo, SystemInfo
from oddrun.security import redact_environment


def capture_python_info() -> PythonInfo:
    """Capture details about the running Python interpreter."""
    cache_tag = getattr(sys.implementation, "cache_tag", None)
    return PythonInfo(
        version=platform.python_version(),
        implementation=platform.python_implementation(),
        executable=sys.executable,
        sys_prefix=sys.prefix,
        base_prefix=getattr(sys, "base_prefix", sys.prefix),
        platform=sys.platform,
        cache_tag=cache_tag,
    )


def capture_system_info() -> SystemInfo:
    """Capture host operating system and environment execution context."""
    try:
        current_cwd = str(pathlib.Path.cwd())
    except Exception:
        current_cwd = os.getcwd()

    # Timezone detection
    tz_str = ""
    try:
        tz_name = time.tzname
        if tz_name and len(tz_name) > 0:
            tz_str = tz_name[0]
    except Exception:
        tz_str = "UNKNOWN"

    return SystemInfo(
        os_name=platform.system(),
        os_release=platform.release(),
        architecture=platform.machine(),
        processor=platform.processor() or "unknown",
        cwd=current_cwd,
        timezone=tz_str or "UNKNOWN",
    )


def capture_packages() -> dict[str, str]:
    """Discover installed Python distributions using importlib.metadata."""
    pkgs: dict[str, str] = {}
    try:
        for dist in importlib.metadata.distributions():
            name = dist.metadata.get("Name") or dist.name
            version = dist.version
            if name and version:
                pkgs[name] = version
    except Exception:
        # Fallback gracefully if distribution inspection fails
        pass

    return dict(sorted(pkgs.items()))


def capture_environment() -> EnvironmentSnapshot:
    """Capture a privacy-aware EnvironmentSnapshot of current environment."""
    python_info = capture_python_info()
    system_info = capture_system_info()

    # Environment variables with sensitive values redacted
    raw_env = dict(os.environ)
    redacted_env = redact_environment(raw_env)

    # Installed packages
    packages = capture_packages()

    captured_at = datetime.now(timezone.utc).isoformat()

    return EnvironmentSnapshot(
        python=python_info,
        system=system_info,
        environment=redacted_env,
        packages=packages,
        captured_at=captured_at,
    )
