# Security Policy

## OddRun Security Guarantees

OddRun is designed to inspect environment configurations safely. Security is a primary design goal.

### Secret Redaction Policy

Environment variables often contain sensitive credentials (API keys, database passwords, OAuth tokens, private keys).

OddRun enforces **conservative secret redaction**:
- Any environment variable matching sensitive keywords (such as `KEY`, `SECRET`, `PASSWORD`, `PASSWD`, `TOKEN`, `CREDENTIAL`, `AUTH`, `PRIVATE`, `SIGNATURE`, `CONN`, `DATABASE`, `URI`, `CERT`, `COOKIE`, `JWT`, `SALT`, `HASH`, `ID`) is automatically replaced with `"<present>"` or `"<absent>"`.
- Raw secret values are **never** logged, **never** written to snapshot JSON files, and **never** included in exception error messages.

### Local-First Guarantee

- No remote network requests are made by OddRun.
- No telemetry or analytics exist.
- No data is uploaded anywhere.

## Reporting a Vulnerability

If you discover a potential security issue or secret leak bug in OddRun, please open a issue on GitHub or contact the maintainers directly.
