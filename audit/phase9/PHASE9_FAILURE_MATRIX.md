# Phase 9 — Pipeline Failure Matrix

This matrix documents the verification results across the 13 designated failure scenarios. Each scenario verifies that a failure at any point in the pipeline triggers a clean termination, logs the appropriate stage error status, blocks dependent downstream stages, and prevents a false positive verdict.

## 13 Failure Matrix Scenarios

| Case | Scenario / Stage Failure | Trigger Condition / Mock | Stage Status | Downstream Status | Final Verdict |
|------|--------------------------|---------------------------|--------------|-------------------|---------------|
| 1    | Ingest Stage Fails       | Malformed workspace / files| `ingest`: `error` | `discover` onwards: `pending` | `FAILED` / `UNVERIFIED` |
| 2    | Discover Stage Fails     | Empty program catalog     | `discover`: `error` | `analyze` onwards: `pending` | `FAILED` / `UNVERIFIED` |
| 3    | Analyze Stage Fails      | Invalid call graph loop   | `analyze`: `error` | `baseline` onwards: `pending` | `FAILED` / `UNVERIFIED` |
| 4    | Baseline Unproducible    | Legacy binary crash       | `baseline`: `done` | `transpile` onwards: `blocked` | `BASELINE_UNPRODUCIBLE`|
| 5    | Transpile Stage Fails    | Lexer/Parser syntax error | `transpile`: `error` | `collect` onwards: `pending` | `PARTIAL` / `FAILED` |
| 6    | Collect Stage Fails      | Java compiler error       | `collect`: `error` | `generate` onwards: `pending` | `FAILED` |
| 7    | Generate Stage Fails     | Target directory locked   | `generate`: `error` | `execute` onwards: `pending` | `FAILED` |
| 8    | Execute Stage Fails      | JVM runtime crash         | `execute`: `error` | `compare` onwards: `pending` | `FAILED` |
| 9    | Compare Stage Fails      | File diffing failure      | `compare`: `error` | `refactor` onwards: `pending` | `FAILED` |
| 10   | Equivalence Mismatch     | Output content mismatch   | `compare`: `done`  | `refactor` onwards: `pending` | `FAILED` |
| 11   | Refactor Stage Fails     | Maven framework compile err| `refactor`: `error` | `validate` onwards: `pending` | `FAILED` |
| 12   | Validate Stage Fails     | Spring Boot boot-up fail  | `validate`: `error` | `report` onwards: `pending` | `FAILED` |
| 13   | Package Stage Fails      | Zip archiving error       | `package`: `error`  | None (terminal stage) | `FAILED` / `NATIVE_SPRING_UNIFIED` |

## Key Hardening Assurances

1. **Downstream Blockage**: When any stage raises an exception or returns a non-success flag, the pipeline runner immediately interrupts execution by throwing a `RuntimeError`. Downstream stages remain in `pending` or `blocked` and are never run.
2. **Deterministic Verdicts**: A pipeline run with failed or missing stages can never compute a `PRODUCTION_READY` or `PRODUCTION_CANDIDATE` verdict. The verdict ladder strictly requires evidence from preceding stages.
3. **No Phantom Success**: If compilation fails, the compare/validate stages cannot execute. Equivalence verification is completely blocked.
