# 11. Equivalence Audit

This document presents the detailed architectural and correctness audit of the Equivalence Engine.

---

## 1. Component Location
- **Source File**: [`execution/equivalence.py`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/execution/equivalence.py)
- **Tests**: [`tests/test_equivalence.py`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/tests/test_equivalence.py)

---

## 2. Validation & Parity Modes

The Equivalence Engine compares legacy GnuCOBOL observations against Java observations using the following rules:

- **Scenario Parity**: If scenario IDs differ, status is flagged as `UNVERIFIED` (Case Scenario Mismatch).
- **Exit Code Parity**: Validates exit code match unless explicit parities are mapped (e.g., mapping code 0 to 1).
- **File Set Parity**: Checks that all expected non-empty/empty files are matching, capturing missing/unexpected file differences.
- **File Contents Parity**: Performs content hash matching, and applies regex normalization patterns.
- **Database Parity**: Checks that database states match (context ID, db type, affected tables, row counts).
