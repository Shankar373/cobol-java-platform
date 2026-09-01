# Phase 2: Codebase Security Audit

We audited all execution paths for code vulnerability risks:

## 1. Security Flaws Matrix
- **Vulnerability 1: Command Injection via shell=True**
  - **Location**: `cobol_migrate.py` (Line 61) and `scenario_runner.py` (Line 70).
  - **Risk**: Process instantiation uses string formatting with `shell=True`, allowing arbitrary code execution if folder structures or arguments contain command terminators.
  - **Mitigation**: Refactor to list-based arguments with `shell=False`.
- **Vulnerability 2: ZIP Path Traversal**
  - **Location**: `ui.py` (Line 147, `safe_extract_zip()`).
  - **Mitigation**: Validates relative prefixes and checks canonical path starting bounds. Verified as secure.
