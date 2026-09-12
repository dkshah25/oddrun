# OddRun Architecture & Design Document (v0.1)

## Overview

OddRun is designed around the core principle: **"When the same code doesn't behave the same."**

While traditional tools focus on environment inventory, OddRun's long-term goal is **causal behavioral diagnosis**:
isolating which environment difference actually changes a Python program's behavior.

---

## v0.1 Core Components

OddRun v0.1 establishes a zero-dependency foundation with three primary architectural layers:

```
+-------------------------------------------------------------+
|                          CLI Layer                          |
|                  (oddrun capture, oddrun compare)            |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
|                          Python API                         |
|    capture_environment(), compare_snapshots(), io module    |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
|                      Data Models & Security                 |
|      EnvironmentSnapshot, SnapshotDiff, Secret Redaction    |
+-------------------------------------------------------------+
```

### 1. Data Models (`oddrun.models`)
- `PythonInfo`: Immutable snapshot of Python interpreter metadata (`version`, `executable`, `sys_prefix`, `platform`, `cache_tag`).
- `SystemInfo`: Host platform metadata (`os_name`, `os_release`, `architecture`, `cwd`, `timezone`).
- `EnvironmentSnapshot`: Root model holding `PythonInfo`, `SystemInfo`, redacted `environment` key-value pairs, and `packages` distribution versions.
- `DiffItem`: Single structural difference item (`category`, `key`, `left_value`, `right_value`, `change_type`).
- `SnapshotDiff`: Container holding the complete list of differences.

### 2. Security & Secret Redaction (`oddrun.security`)
- Conservative keyword matching (`KEY`, `SECRET`, `PASSWORD`, `PASSWD`, `TOKEN`, `CREDENTIAL`, `AUTH`, `PRIVATE`, `SIGNATURE`, `CERT`, `COOKIE`, `JWT`, `SALT`, `HASH`, `DATABASE_URL`, `DB_URI`).
- Secrets are replaced with `"<present>"` prior to serialization.
- Exception sanitization prevents raw secret strings from leaking into terminal outputs or logs.

### 3. Snapshot I/O & Determinism (`oddrun.io` & `oddrun.compare`)
- Snapshot JSON files are saved using UTF-8 with indented structure and sorted keys (`sort_keys=True`).
- Comparison ordering is strictly deterministic, sorted by category (`python` -> `system` -> `environment` -> `packages`) and key names.

---

## Future Architecture Boundary (`oddrun why`)

Version 0.1 provides the deterministic baseline required for future causal diagnosis engine (`oddrun why`):

```
EnvironmentSnapshot
       ↓
Runtime Observation
       ↓
Candidate Generation
       ↓
Controlled Perturbation
       ↓
Re-execution & Measurement
       ↓
Causal Ranking & Explanation
```

The future causal engine will build on `EnvironmentSnapshot` and `SnapshotDiff` to perturb candidate differences in an isolated subshell/environment and observe whether behavioral divergence disappears.
