# 17. Test Quality Audit

This document reviews the coverage, depth, and quality of the test suite.

---

## 1. Test Coverage Overview

- **Unit Testing**: `HIGH`. Dedicated suites cover lexer formats, parser constructs, CFG paragraph loops, Data Flow REDEFINES overlaps, and Call/COPY dependency classifications.
- **Integration/Pipeline Testing**: `MEDIUM`. `tests/test_interactive_execution.py` verifies watchdog execution bounds, scenario parsers, and accept detection.
- **Transpiler & Code Generation testing**: `LOW`. No mock tests exist for `cobj` compiler translations or Maven Spring compilation pipelines, which are instead verified integrationally via physical checks during active repo runs.

---

## 2. Test Quality Gaps
- **Docker Dependency**: The regression suite relies on Docker being active on the test host to run baseline GnuCOBOL outputs and Java execution, which limits testing in standard CI environments.
- **Unverified Branches**: Lacks unit testing of the Spring Batch scaffolding writer or JPA entities writers.
