# Phase 1: Equivalence Comparison Audit (Stage 8)

We audited the behavioral equivalence check logic inside `stage_compare`:

## 1. Comparison Cases Matrix
- **CASE A (Parity matches)**: **PASS** (exact physical or normalized match).
- **CASE B (Parity differs)**: **FAIL** (verdict: `differ`).
- **CASE C (Both outputs empty)**: **PASS** (false-positive loophole). If both baseline and execute fail without creating files and exit code 0, it reports a success.
- **CASE D (COBOL empty, Java has output)**: **FAIL** (verdict: `java-only`).
- **CASE E (COBOL has output, Java empty)**: **FAIL** (verdict: `baseline-only`).
- **CASE F (Same output, differing exit codes)**: **FAIL** (verdict: `differ`).
- **CASE G (Same exit code, differing output)**: **FAIL** (verdict: `differ`).
- **CASE H (Same file count, differing contents)**: **FAIL** (verdict: `differ`).

## 2. Identified Loophole
- **File**: `cobol_migrate.py` (Line 3057, `stage_compare()`)
- **Loophole**: `set(baseline) | set(results)` yields an empty set if neither execution produced output files. The loop is skipped, and since no errors are thrown, it reports a PASS.
- **Severity**: **Medium**.
- **Fix**: Check that the count of comparison files is $>0$ before verifying parity, or assert that stdout is not empty.
