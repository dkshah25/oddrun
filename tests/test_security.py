"""Security and secret redaction unit tests for OddRun."""

from oddrun.security import (
    REDACTED_VALUE,
    is_sensitive_key,
    redact_environment,
    sanitize_error_message,
)


def test_sensitive_key_detection():
    sensitive_keys = [
        "API_KEY",
        "SECRET_KEY",
        "MY_PASSWORD",
        "PASSWD",
        "AUTH_TOKEN",
        "AWS_SECRET_ACCESS_KEY",
        "SSH_PRIVATE_KEY",
        "DB_CREDENTIAL",
        "OAUTH_AUTHORIZATION",
        "DIGITAL_SIGNATURE",
        "DATABASE_URL",
        "SESSION_COOKIE",
        "JWT_BEARER_TOKEN",
    ]
    for key in sensitive_keys:
        assert is_sensitive_key(key) is True, f"Expected {key} to be sensitive"


def test_non_sensitive_key_detection():
    safe_keys = [
        "PATH",
        "PYTHONPATH",
        "LANG",
        "LC_ALL",
        "TZ",
        "TERM",
        "SHELL",
        "HOME",
        "USER",
        "LOGNAME",
        "VIRTUAL_ENV",
        "PYTHONDONTWRITEBYTECODE",
        "PYTHONUNBUFFERED",
    ]
    for key in safe_keys:
        assert is_sensitive_key(key) is False, f"Expected {key} to be safe"


def test_redact_environment():
    raw_env = {
        "PATH": "/usr/local/bin:/usr/bin",
        "LANG": "en_US.UTF-8",
        "DATABASE_URL": "postgres://user:super_secret_password@localhost:5432/db",
        "AWS_SECRET_ACCESS_KEY": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        "API_KEY": "1234567890abcdef",
    }
    redacted = redact_environment(raw_env)

    assert redacted["PATH"] == "/usr/local/bin:/usr/bin"
    assert redacted["LANG"] == "en_US.UTF-8"
    assert redacted["DATABASE_URL"] == REDACTED_VALUE
    assert redacted["AWS_SECRET_ACCESS_KEY"] == REDACTED_VALUE
    assert redacted["API_KEY"] == REDACTED_VALUE

    # Ensure secret string values NEVER appear in the redacted dictionary values
    for secret in [
        "postgres://user:super_secret_password@localhost:5432/db",
        "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        "1234567890abcdef",
    ]:
        assert secret not in redacted.values()


def test_sanitize_error_message():
    secret = "my_super_secret_password"
    msg = f"Failed to connect using password {secret} at host localhost"
    sanitized = sanitize_error_message(msg, [secret])
    assert secret not in sanitized
    assert REDACTED_VALUE in sanitized
