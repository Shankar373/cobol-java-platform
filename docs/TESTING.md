# Testing Guide

This document explains how to execute the platform's test suite and verification checks.

---

## 1. Running Tests

To run the complete suite of tests:

```powershell
python -m pytest
```

### Skipped Tests
If Docker is not active on your host machine, the testing framework will automatically bypass the containerized baseline verification tests (e.g. `test_validation_nobypass.py`).

---

## 2. Test Structure

*   `tests/`:
    *   `test_lexer.py`: Lexer unit tests.
    *   `test_parser.py`: Parser grammar validations.
    *   `test_native_*.py`: Target code generation parities.
    *   `test_jcl_*.py`: JCL workflow parser validations.
    *   `test_phase10_gates.py`: Lifecycle verification audits.
    *   `utils/cobol_runner.py`: Helper class that compiles and runs translated Java on-the-fly.

---

## 3. Writing Parity Tests

When adding a feature, add a corresponding test inside `tests/` that:
1.  Defines a raw COBOL snippet.
2.  Passes it to `run_cobol_code`.
3.  Asserts that the compiled Java returns the expected output state.
