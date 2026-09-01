# Phase 2: Repository-Agnostic Comparison Contract & Observables Model

This document defines the generic model for behavior validation:

## 1. ExecutionObservation Model Layout
The container records the observable state of a process execution and must include `"schema_version": "1.0"`:

```json
{
  "schema_version": "1.0",
  "scenario_id": "SC-1002",
  "execution_status": "normal",
  "exit_code": 0,
  "stdout": "Processing complete.",
  "stderr": "",
  "files": {
    "data/out/records.csv": "PRESENT_NONEMPTY"
  },
  "file_contents": {
    "data/out/records.csv": "10001,ACTIVE,95000.00"
  },
  "file_sizes": {
    "data/out/records.csv": 22
  },
  "record_counts": {
    "data/out/records.csv": 1
  },
  "database_observations": {},
  "structured_output": {},
  "duration": 0.45,
  "normalization_metadata": {}
}
```

## 2. Validator State Machine
The equivalence engine resolves validation into one of six distinct states:
- **Case A**: Expected no output + actual no output -> **PASS**
- **Case B**: Expected output + actual output matching -> **PASS**
- **Case C**: Expected output + actual output different -> **FAIL**
- **Case D**: Expected output + output missing -> **FAIL**
- **Case E**: Expected no output + unexpected output -> **FAIL**
- **Case F**: Expected behavior unknown -> **UNVERIFIED** (UNKNOWN = UNVERIFIED; never defaults to pass or fail).
- **Case G**: Expected file exists but is empty + empty expected -> **PASS**
- **Case H**: Expected non-empty file + actual empty file -> **FAIL**
- **Case I**: Extra unexpected output file -> **FAIL**
- **Case J**: Missing expected output file -> **FAIL**

## 3. Exit Code Parity Contract
Default behavior: `EXIT_CODE_MISMATCH = FAIL`.
If different exit codes are equivalent, the contract must explicitly record the exception with an auditable justification.

## 4. Strict Normalization Rules
Every normalization rule must declare:
- **pattern**: Regex string.
- **artifact**: Filename.
- **field**: Field position/index.
- **reason**: Justification (e.g. `nondeterministic transaction timestamp`).
- **scope**: Mapped lines or fields.
- **original_value**: Value before translation.
- **normalized_value**: Translated value.
