# 04. Pipeline Audit

This document details the exact stage structure of the modernization pipeline orchestrator.

---

## 1. Actual Executed Stages in `cobol_migrate.py`

The pipeline execution matches the canonical **13-stage order** defined in the `STAGES` list of `cobol_migrate.py`:

| Index | Stage Name | Purpose / Function | Input | Output |
| :---: | :--- | :--- | :--- | :--- |
| **0** | `ingest` | Calculates SHA-256 baseline hashes of source files. | COBOL programs | `state.json` hashes |
| **1** | `discover` | Walks repo directories to identify files and technology stacks. | Source directory | Files list |
| **2** | `analyze` | Constructs call graphs and physical-logical file maps. | Sources list | Call graph metadata |
| **3** | `baseline` | Executes original legacy COBOL under GnuCOBOL container. | Golden inputs | Output binary `.dat` files |
| **4** | `transpile` | Invokes the COBOL 4J transpiler compiler in Docker. | COBOL sources | Transpiled Java files |
| **5** | `collect` | Gathers Java sources and checks for missing stubs. | Java output | Stubs checklist |
| **6** | `generate` | Assembles the intermediate transpiled target maven project. | Java sources | Maven project, `libcobj.jar` |
| **7** | `execute` | Runs transpiled Java bytecode batch execution. | SQLite DB, files | Java stdout/stderr logs |
| **8** | `compare` | Gate 1 validation comparing GnuCOBOL vs Java outcomes. | GnuCOBOL + Java outputs | Comparison results |
| **9** | `refactor` | Refactors Java code structures. | Transpiled project | target/modernized/ Spring Batch |
| **10** | `validate` | Gate 2 validation compiling refactored code and run REST DB tests. | Maven project | REST endpoint test logs |
| **11** | `report` | Emits final markdown and JSON audit report. | Comparison metadata | `migration-report.md` |
| **12** | `package` | Archives legacy, analyses, transpiled, modernized, and reports. | All target files | `migration_package.zip` |
