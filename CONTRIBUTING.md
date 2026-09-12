# Contributing to OddRun

Thank you for your interest in contributing to OddRun!

## Development Setup

OddRun requires Python 3.10 or higher.

1. Clone the repository:
   ```bash
   git clone https://github.com/oddrun/oddrun.git
   cd oddrun
   ```

2. Install in editable mode with development dependencies:
   ```bash
   python -m pip install -e ".[dev]"
   ```

3. Run the test suite:
   ```bash
   pytest
   ```

4. Run code linting:
   ```bash
   ruff check .
   ```

## Development Guidelines

- **Zero Runtime Dependencies**: Keep the v0.1 core dependent only on the Python standard library.
- **Security First**: Ensure secret redaction logic is maintained and tested for any environment inspection changes.
- **Tests**: Write deterministic unit tests for all new features.
- **Code Style**: Follow standard Python conventions enforced by Ruff.
