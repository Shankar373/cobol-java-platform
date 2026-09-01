# Phase 3 Baseline Inventory

This document establishes the baseline capability status of SystemaOps prior to initiating Phase 3.

---

## 1. Capabilities Matrix

| Component | Baseline Status | Technical Justification |
| :--- | :---: | :--- |
| **Generic COBOL Semantic IR** | `PARTIAL` | The model schemas are defined in `modernize/semantic_ir.py`, but they are not dynamically populated from COBOL parser AST nodes yet. |
| **Data Semantics** | `NOT_IMPLEMENTED` | Generic PIC, COMP-3, REDEFINES, and USAGE mapping logic is not active; domain type mapping is currently tailored to hardcoded copybooks. |
| **Control Flow** | `PARTIAL` | `ControlFlowModel` containers exist in `modernize/control_flow.py` but no actual AST CFG graph building is integrated. |
| **Data Flow** | `PARTIAL` | `DataFlowModel` containers are defined but they are not populated from source statement expressions yet. |
| **Call Graph + Migration Status** | `PARTIAL` | Scaffolding classes exist in `modernize/dependencies.py` but dynamic calls mapping is not fully populated in Stage 2. |
| **Source -> Java Traceability** | `PARTIAL` | Record classes defined in `modernize/traceability.py` but no dynamic target mapping generation is connected to the pipeline. |
| **Business Rule Coverage** | `PARTIAL` | Scaffolding classes defined in `modernize/coverage.py` but coverage statistics calculation is not implemented. |
| **Native Java Vertical Slice** | `PARTIAL` | Native project structure is generated during Stage 9 (Refactor) but it does not compile or run decoupled from `libcobj.jar` on a generic program slice. |
| **Native Java Dependency Gate** | `NOT_IMPLEMENTED` | No automated checking exists to verify target class files do not import `libcobj.jar` or `jp.osscons` classes. |
| **Equivalence Engine** | `VERIFIED` | Full dynamic state comparison machine implemented in `execution/equivalence.py` and regression verified. |
| **Deterministic Execution** | `VERIFIED` | Dynamic scenario replay engine is implemented and verifies exit codes, stdout, and files outputs. |
| **Native Java Build Pipeline** | `PARTIAL` | Build stages compile Spring Boot target, but dynamic output classification is not active. |
| **Regression Safety** | `VERIFIED` | Test suite with 26 unit tests (including logical records audit test) runs and passes via pytest. |
| **Security Audit** | `UNVERIFIED` | Process execution and Docker execution flows have not been audited for input safety. |
| **Frontend Observability** | `VERIFIED` | Frontend dashboard is active and displays pipeline logs and validation stage execution outcomes. |

---

## 2. Evidence Registry

- **Existing Tests**: 26 unit tests in the workspace under `tests/` folder. All pass.
- **Golden Comparison Runs**: Stage 8 comparison outcome (Gate 1 PASS, Gate 2 PASS) for ClaimsCore sample application.
- **Scaffold files**: Initializer blocks in `modernize/__init__.py`.
