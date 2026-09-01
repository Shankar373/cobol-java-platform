# 05. Test Results

This document presents the detailed execution outcomes of the Pytest suite.

---

## 1. Test Execution Metrics

- **Execution Command**: `python -m pytest -v`
- **Total Tests Collected**: 37
- **Passed**: 37
- **Failed**: 0
- **Skipped**: 0
- **Errors**: 0
- **Duration**: ~13.44 seconds
- **Regression Verdict**: `PASS` (100% success rate, 0 regressions)

---

## 2. Test File Inventory

- **[`tests/logical_audit_test.py`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/tests/logical_audit_test.py)**: Checks logical db schema differences.
- **[`tests/test_control_flow.py`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/tests/test_control_flow.py)**: Checks CFG paragraph nesting and branches.
- **[`tests/test_data_flow.py`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/tests/test_data_flow.py)**: Checks Data Flow definitions and properties.
- **[`tests/test_dependencies.py`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/tests/test_dependencies.py)**: Checks Call & COPY dependencies resolution.
- **[`tests/test_equivalence.py`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/tests/test_equivalence.py)**: Checks output equivalence engine checks.
- **[`tests/test_interactive_execution.py`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/tests/test_interactive_execution.py)**: Checks watchdog timers, scenario discovery, and interactive ACCEPT execution.
- **[`tests/test_lexer.py`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/tests/test_lexer.py)**: Checks lexer tokens formatting.
- **[`tests/test_parser.py`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/tests/test_parser.py)**: Checks COBOL syntax structural parsing.
- **[`tests/test_semantic_ir.py`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/tests/test_semantic_ir.py)**: Checks Semantic IR serialization.
- **[`tests/test_slicer.py`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/tests/test_slicer.py)**: Checks paragraph extraction slicing.
