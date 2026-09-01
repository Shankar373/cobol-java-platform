# Phase 2: Execution Contract

This document defines the generic ExecutionContract model:

## 1. Contract Structure
The execution contract defines the expected observations layout:

- **Expected Output Modes**:
  - `EXPECTED_NO_OUTPUT`
  - `EXPECTED_FILES`
  - `EXPECTED_STDOUT`
  - `EXPECTED_DATABASE_STATE`
  - `EXPECTED_EXIT_STATUS`
  - `EXPECTED_STRUCTURED_OUTPUT`
- **Output Validation Attributes**:
  - Required output file keys.
  - Optional output file keys.
  - Expected empty files list.
  - Nondeterministic ignore regex patterns.
  - Record sorting rules.
  - Floating/fixed numeric tolerances.
