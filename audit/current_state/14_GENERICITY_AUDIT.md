# 14. Genericity Audit

This document examines the genericity vs benchmark-specific hardcoding of the codebase.

---

## 1. Genericity Findings

### A. Generic Components
- **Lexer (`modernize/lexer.py`)**: Generic scanner, parameterizable for fixed/free format modes.
- **Parser (`modernize/parser.py`)**: Generic parser mapping standard COBOL constructs to node sequences.
- **CFG Builder (`modernize/control_flow.py`)**: Generic builder mapping conditional blocks and perform returns.
- **Data Flow Builder (`modernize/data_flow.py`)**: Generic builder mapping redefinitions and transitions.
- **Dependency Analyzer (`modernize/dependencies.py`)**: Generic call-graph and copybook resolver.

### B. Benchmark-Specific Hardcoding (Non-Generic)
- **Spring Scaffolding (`cobol_migrate.py`)**:
  - Checks `if "BCMAIN" in entry` to switch between BankCore transaction structures and Claim PAS structures.
  - Seeds hardcoded customer data for BankCore.
  - Hardcodes the `fallback_layout` definitions matching BankCore (`id`, `date`, `accountId`, `type`, `amount`) and Claims PAS (`id`, `date`, `policyId`, `type`, `lossAmount`).
- **Logical Verification (`cobol_migrate.py`)**:
  - SQLite tables and fields layouts are verified using rules that map to the specific tables of the target benchmarks.
