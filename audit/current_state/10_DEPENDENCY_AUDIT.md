# 10. Dependency Audit

This document presents the detailed architectural and correctness audit of the Call & COPY Dependency Analyzer.

---

## 1. Component Location
- **Source File**: [`modernize/dependencies.py`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/modernize/dependencies.py)
- **Tests**: [`tests/test_dependencies.py`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/tests/test_dependencies.py)

---

## 2. Dependency Resolution Outcomes

- **Classification Mappings**:
  - `RESOLVED_STATIC`: Target source code exists in the repository.
  - `RESOLVED_DYNAMIC`: Variable is initialized to a constant string pointing to an existing program.
  - `UNRESOLVED_DYNAMIC`: Variable target name has no constant initialization value.
  - `MISSING_SOURCE`: Call target is not present in repository.
  - `EXTERNAL_SYSTEM`: Targets starting with CICS/DB2 keywords.
- **Copybooks**: Scans for copybooks and classifies them as `COPY_FOUND` or `COPY_MISSING` separately.
- **Reachability Calculations**: Tracks program entry points and maps reachability (`REACHABLE`/`UNREACHABLE`).
- **Arguments**: Stores parameters list count on CALL statements.
