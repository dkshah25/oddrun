"""Security and sensitive credential redaction utilities for OddRun."""

from __future__ import annotations

REDACTED_VALUE = "<present>"

# Substrings in environment variable names that indicate sensitive contents
SENSITIVE_SUBSTRINGS = (
    "KEY",
    "SECRET",
    "PASS",
    "PWD",
    "TOKEN",
    "CREDENTIAL",
    "AUTH",
    "PRIVATE",
    "SIGNATURE",
    "CERT",
    "COOKIE",
    "SESSION",
    "JWT",
    "SALT",
    "HASH",
    "BEARER",
    "CONN_STR",
    "DATABASE_URL",
    "DB_URI",
    "PEM",
)


def is_sensitive_key(key: str) -> bool:
    """Determine whether an environment variable key should be considered sensitive.

    Checks key against sensitive keyword patterns (case-insensitive).
    Returns True if the variable is deemed sensitive, False otherwise.
    """
    key_upper = key.upper()
    for substring in SENSITIVE_SUBSTRINGS:
        if substring in key_upper:
            return True
    return False


def redact_environment(env: dict[str, str]) -> dict[str, str]:
    """Return a new dictionary with sensitive environment variables redacted.

    Sensitive variables have their values replaced with `<present>`.
    Keys are preserved. Non-sensitive variables retain their original string values.
    """
    redacted: dict[str, str] = {}
    for key, value in env.items():
        if is_sensitive_key(key):
            redacted[key] = REDACTED_VALUE
        else:
            redacted[key] = str(value)
    return redacted


def sanitize_error_message(message: str, sensitive_values: list[str]) -> str:
    """Sanitize error messages to prevent accidental credential leakage."""
    sanitized = message
    for val in sensitive_values:
        if val and len(val) > 2:
            sanitized = sanitized.replace(val, REDACTED_VALUE)
    return sanitized
