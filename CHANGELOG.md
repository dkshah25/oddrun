# Changelog

All notable changes to OddRun will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-09-12

### Added
- **Privacy-Aware Environment Snapshotting (`oddrun capture`)**: Captures Python, OS, safe environment variables, and package metadata.
- **Deterministic Comparison (`oddrun compare`)**: Compares two snapshots with sorted differences.
- **Target Execution Observation (`oddrun record`)**: Executes commands 1x on target environments and captures `ExecutionRecord` with `BehaviorSignature`.
- **Causal Behavior Diagnosis (`oddrun why`)**: Controlled baseline perturbation testing with layered behavior signature matching (`exit_code`, `exception_type`, normalized diagnostics).
- **Conservative Secret Redaction**: Replaces sensitive environment variables (`API_KEY`, `SECRET`, `TOKEN`, `PASSWORD`, `AUTH`, etc.) with `"<present>"`.
- **Zero External Dependencies**: Operates 100% offline using Python standard library native tools.
