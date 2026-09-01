# 02. Repository Inventory

This document inventory details the layout, files, and modules present in the current repository.

---

## 1. Directory Structure

```
├── .gemini/                 - App configurations and IDE storage
├── audit/                   - Validation reports and state baseline audits
│   ├── phase3/              - Individual phase results reports
│   └── current_state/       - Current repository baseline audits
├── execution/               - Scenario parser, interactive execution runner, and equivalence engine
├── legacy/                  - Legacy benchmark repositories containing COBOL programs
├── modernize/               - Lexer, Parser, SemanticIR, CFG, DataFlow, and Dependency analysis modules
├── scratch/                 - Scratchpad scripts and utilities
├── target/                  - Output folder containing transpiled and refactored codes and SQLite databases
├── tests/                   - Complete testing suite for execution, lexer, parser, CFG, DataFlow, and dependencies
├── cobol_migrate.py         - Main migration pipeline runner orchestrating stages 0 to 12
├── audit_engine.py          - 22-point validation analyzer
├── modernize_and_verify.py  - Transpilation and outcomes validation runner
├── slicer.py                - COBOL paragraph slicing utility
├── ui.py / ui.html          - Interactive dashboard server and HTML frontend
└── requirements.txt         - Python dependencies file
```

---

## 2. Core Python Components

- **[`cobol_migrate.py`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/cobol_migrate.py)**: The 13-stage migration orchestrator.
- **[`audit_engine.py`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/audit_engine.py)**: The 22-point validator which parses `state.json` and runs checks.
- **[`modernize_and_verify.py`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/modernize_and_verify.py)**: Verification script.
- **[`modernize/lexer.py`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/modernize/lexer.py)**: Lexical scanner.
- **[`modernize/parser.py`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/modernize/parser.py)**: Structural parser.
- **[`modernize/control_flow.py`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/modernize/control_flow.py)**: CFG builder.
- **[`modernize/data_flow.py`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/modernize/data_flow.py)**: Data flow builder.
- **[`modernize/dependencies.py`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/modernize/dependencies.py)**: Call & COPY dependency builder.
