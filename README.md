# OddRun

> When the same code doesn't behave the same.

Find what actually causes your Python code to behave differently across environments.

## Why OddRun?

Traditional environment tools answer:
> *"What is different between these environments?"*

OddRun experimentally investigates:
> *"Which difference actually changed the program's behavior?"*

### Environment Diff vs. Causal Investigation

- **Environment Diff**: *"TZ differs between local machine and server."*
- **OddRun**: *"Changing `TZ` from the baseline value (`Asia/Kolkata`) to the target value (`UTC`) consistently reproduced the observed failure."*

## Quickstart

```bash
pip install oddrun
```

OddRun operates locally using Python standard library native tools with zero external runtime dependencies.

## Hero Demo: `record` → `why` Workflow

### 1. On Target Environment (e.g., CI / Remote Server where code fails)

Execute the command once under observation to record host environment metadata and the failure signature:

```bash
oddrun record -o target-run.json -- python target_program.py
```
*(Generates `target-run.json` containing safe environment snapshot data and the observed `BehaviorSignature`)*

### 2. On Baseline Environment (e.g., Developer Machine where code passes)

Diagnose which environmental difference reproduces the target failure:

```bash
oddrun why target-run.json -- python target_program.py
```

#### Output Demonstration

```text
OddRun Causal Diagnosis
============================================================
Command         : python target_program.py
Target Record   : target-run.json
Differences     : 1 total (1 candidates tested)

[1/3] Baseline Stability ... PASS (3/3 identical runs)
[2/3] Testing Candidates...
  TZ=UTC .................... REPRODUCED FAILURE (3/3)

[3/3] Evaluating Causal Evidence...

EXPERIMENTALLY SUPPORTED CAUSAL FACTOR
============================================================
Factor       : TZ
Baseline     : Asia/Kolkata (PASS)
Target       : UTC (FAIL)
Forward Test : 3/3
Reverse Test : UNAVAILABLE (Static Snapshot Mode)
Evidence     : MODERATE (Forward Verified)

Interpretation:
  Changing factor 'TZ' from baseline value ('Asia/Kolkata') to target value ('UTC') consistently reproduced target failure.

Recommendation:
  Avoid relying on system timezone. Use explicit timezone-aware datetimes.
------------------------------------------------------------

Note: This is strong causal evidence, not proof that these are the unique possible causes.
```

## How It Works

OddRun follows a controlled 6-stage lifecycle:

```text
OBSERVE → COMPARE → PERTURB → RE-RUN → MEASURE → EXPLAIN
```

1. **OBSERVE**: `oddrun record` captures host environment metadata and a structural `BehaviorSignature` (exit code, exception type, normalized diagnostic output).
2. **COMPARE**: Identifies environmental differences between baseline and target snapshots.
3. **PERTURB**: Safely applies isolated environment variable modifications without altering global system state.
4. **RE-RUN**: Executes the command under controlled perturbations in subprocess isolation (`shell=False`).
5. **MEASURE**: Compares structural behavior signatures (requires 3x multi-run confirmation for stability).
6. **EXPLAIN**: Reports forward-verified **Experimentally Supported Causal Factors**.

## Evidence & Causal Reasoning

OddRun classifies findings using conservative evidence standards rather than claiming absolute certainty:

- **`EXPERIMENTALLY SUPPORTED CAUSAL FACTOR`**: Changing a single candidate factor reproduces the target failure signature across 3/3 identical runs.
- **Evidence Rating (`MODERATE`)**: Indicates forward verification. OddRun explicitly avoids claiming "Guaranteed Root Cause" or "Unique Cause" because un-tested environmental variables or system dependencies may also contribute.

## Commands

| Command | Question / Action | Input / Artifact |
| :--- | :--- | :--- |
| `oddrun capture` | **What's different?** Captures environment state | `EnvironmentSnapshot` JSON |
| `oddrun compare` | **What changed?** Compares two environment snapshots | Two `EnvironmentSnapshot` JSONs |
| `oddrun record` | **What actually happened here?** Executes command 1x on target | `ExecutionRecord` JSON |
| `oddrun why` | **Which difference explains target behavior?** | `ExecutionRecord` JSON + `<command>` |

## Security & Privacy

OddRun is strictly **local-first**:
- **Local-First & Zero Telemetry**: OddRun runs locally and does not require a cloud service or send telemetry. Uses standard-library native runtime dependencies.
- **Subprocess Isolation**: Spawns isolated process trees (`shell=False`) without mutating parent `os.environ`.
- **Automatic Secret Redaction**: Sensitive environment keys (`API_KEY`, `SECRET`, `PASSWORD`, `TOKEN`, `CREDENTIAL`, `AUTH`, etc.) are automatically replaced with `"<present>"` before saving snapshots or records to disk.

## Limitations

- **Perturbation Scope**: Only perturbable environment variables (Tier 1 safe variables, Tier 2 PATH/PYTHONPATH with opt-in) are tested. System architecture, OS kernel, and Python C-extensions are observed but not perturbed.
- **Reverse Verification**: Static snapshot mode tests forward causality (`baseline + target_value`). Reverse testing (`target + baseline_value`) is marked `UNAVAILABLE` when the target environment cannot be executed locally.
- **Multi-Factor Interactions**: Evaluates candidate factors independently; multi-variable combinatorial interactions are not tested in v0.1.0.

## Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run test suite
python -m pytest

# Run linter
python -m ruff check .

# Build package
python -m build
```

## License

[MIT License](https://github.com/dkshah25/oddrun/blob/main/LICENSE)
