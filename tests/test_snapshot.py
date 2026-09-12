"""Unit tests for environment snapshot capture."""

from oddrun.security import REDACTED_VALUE
from oddrun.snapshot import (
    capture_environment,
    capture_packages,
    capture_python_info,
    capture_system_info,
)


def test_capture_python_info():
    info = capture_python_info()
    assert info.version != ""
    assert info.implementation != ""
    assert info.executable != ""
    assert info.platform != ""


def test_capture_system_info():
    sys_info = capture_system_info()
    assert sys_info.os_name != ""
    assert sys_info.architecture != ""
    assert sys_info.cwd != ""


def test_capture_packages():
    pkgs = capture_packages()
    assert isinstance(pkgs, dict)


def test_capture_environment_with_monkeypatch(monkeypatch):
    monkeypatch.setenv("PATH", "/usr/bin")
    monkeypatch.setenv("SECRET_API_KEY", "super-secret-12345")

    snapshot = capture_environment()

    assert snapshot.environment["PATH"] == "/usr/bin"
    assert snapshot.environment["SECRET_API_KEY"] == REDACTED_VALUE
    assert "super-secret-12345" not in snapshot.environment.values()
    assert snapshot.captured_at != ""
