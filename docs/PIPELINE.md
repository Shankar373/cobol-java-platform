# Modernization Pipeline Execution

This document details the stages of the 13-step modernization orchestrator managed by `cobol_migrate.py`.

---

## 1. Pipeline Stages

The platform runs the following lifecycle stages sequentially:

| Step | Stage Name | Description | Output Artifacts |
|---|---|---|---|
| **0** | **ingest** | Receives inputs (ZIP or git) and hashes original sources. | `source_hashes.json` |
| **1** | **discover** | Scans margins, entry points, JCLs, copybooks, and CALL targets. | `discovery.json` |
| **2** | **analyze** | Resolves variables, layout structures, and dependency graphs. | `call_graph.json` |
| **3** | **baseline** | Compiles and executes legacy COBOL via GnuCOBOL in Docker. | `golden_outputs/` |
| **4** | **transpile** | Translates COBOL to emulated Java classes via `cobj`. | `transpiled_sources/` |
| **5** | **collect** | Verifies generated transpiled classes and checks for stubs. | `classes/` |
| **6** | **generate** | Emits Track-B Spring Boot classes and JPA database mappings. | `modernized_sources/` |
| **7** | **execute** | Compiles and runs generated Java targets locally. | `results/` |
| **8** | **compare** | Gate 1 Parity check (stdout, files, database). | `comparison_results.json` |
| **9** | **refactor** | Generates Spring Batch JCL overrides and database tasks. | `modernized_scaffolding/` |
| **10** | **validate** | Gate 2 Parity check (native execution vs baseline). | `validation_results.json` |
| **11** | **report** | Generates parities summaries and provenance documents. | `migration-report.md` |
| **12** | **package** | Bundles all stages and outputs into a portable zip. | `modernized-package.zip` |

---

## 2. Checkpoint & Resume

*   **State Persistence**: Stage execution statuses and output files are recorded in `state.json`.
*   **Resume Feature**: If a run fails at stage 7 (execute), the pipeline can be restarted directly from stage 7 without re-running stages 0-6.
*   **Cancellation**: Runs can be stopped asynchronously by calling the `/api/stop` route, which signals `process.kill()` on Popen wrappers.
