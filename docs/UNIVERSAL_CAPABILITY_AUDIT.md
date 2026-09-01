# Universal COBOL Modernization Capability Audit

## 1. Executive Summary
This document presents an independent forensic audit of the COBOL to Native Java/Spring modernization platform. The platform is designed to compile, modernize, and validate COBOL programs into Spring Boot/Spring Batch applications. This audit determines what features are genuinely implemented and verified by the codebase, versus what features are stubbed or emulated.

---

## 2. Universal Claim Verdict
**Can we honestly call this project a "Universal COBOL → Native Java/Spring Modernization Platform"?**

**Answer: NO**

**Reasoning**:
While the platform provides a working modernization path for simple file-based structured Batch COBOL programs, it does not support the vast majority of mainframe-specific subsystem dependencies (such as CICS, JCL, BMS, IMS, MQ, or real DB2 database servers) in an end-to-end verified capacity. Subsystems are either emulated using stubs, mapped to lightweight local emulators (like H2 for DB2), or require manual review (such as dynamic CALLs). Labeling it a "Universal" platform would be highly misleading; it is currently a **working batch COBOL prototype / MVP with serious architectural limitations**.

---

## 3. Capability Matrix

| Capability | Classification | Evidence | Real Execution? | End-to-End? | Limitations | What Is Needed to Become PROVEN |
|---|---|---|---|---|---|---|
| **Batch COBOL** | `PROVEN` | `PAYMAIN.cob`, `INVMGR.cob` (fixtures) | Yes | Yes | Limited to simple sequential control flow. | Support complex nested PERFORM statements. |
| **Sequential Files** | `PROVEN` | `PAYMAIN.cob` / `INVMGR.cob` read/write files | Yes | Yes | Limited to standard text records. | Support binary and custom record delimiters. |
| **VSAM** | `PARTIAL` | `tests/test_vsam.py` checking sequential FD. | Yes (Sequential only) | No | Indexed/Relative VSAM files are unsupported. | Add VBISAM/BDB file system library support. |
| **DB2** | `EMULATED` | `tests/test_db2_real_vs_emulated.py` H2 path. | No | No | Emulated via local H2 database. | Execute against a real, live IBM DB2 server. |
| **CICS** | `EMULATED` | CICS stubs in `preprocess_cobol_for_cobj`. | No | No | Transaction context/terminal links stubbed. | Implement full CICS API context handlers. |
| **BMS** | `UNSUPPORTED` | No parser or compiler code for BMS map definition. | No | No | Screen layouts are completely ignored. | Add a parser to map BMS definitions to HTML. |
| **JCL** | `FRAMEWORK_ONLY` | JCL structures in `discover` stage. | No | No | JCL steps are cataloged but not executed. | Implement JCL translation to Spring Batch XML/Java. |
| **Dynamic CALL** | `UNSUPPORTED` | `DYNAMIC_CALL_REQUIRES_REVIEW` classification. | No | No | Statements require manual code rewrite. | Build a dynamic registry / DI provider at runtime. |
| **IMS** | `UNSUPPORTED` | No implementation or test cases exist. | No | No | None. | Implement IMS DB/DC API compatibility. |
| **MQ** | `UNSUPPORTED` | No implementation or test cases exist. | No | No | None. | Implement JMS/Spring AMQP bridge for MQ APIs. |
| **Mainframe Data Types** | `PARTIAL` | `CobolFormatHelper.java` parsing COMP/COMP-3. | Yes | Yes | Precision limits on high-precision floats. | Add unit tests for boundary/overflow conditions. |
| **Legacy Baseline** | `PROVEN` | Containerised GnuCOBOL run of `A-PAYONLY` and `INVMGR`. | Yes | Yes | Executables named `.exe` even on Linux. | Rename binaries based on OS environments. |
| **Native Java Gen** | `PROVEN` | `ModernizedApplication.java` generated. | Yes | Yes | Basic transpilation only. | Handle complex pointer/redefines mapping. |
| **Spring Boot** | `PROVEN` | `ModernizedApplication.java` using Spring. | Yes | Yes | Simple REST/batch runners. | Add complete multi-service orchestration. |
| **Spring Batch** | `FRAMEWORK_ONLY` | `SpringBatchConfig.java` structure generated. | No | No | Batch steps are not dynamically generated. | Implement complete JCL step-to-Step mapping. |
| **Equivalence Verify**| `PROVEN` | `EquivalenceEngine` comparing `.dat` files. | Yes | Yes | Checks only console, files, and emulated DB. | Add support for real DB and MQ queues. |

---

## 4. Evidence Details

*   **Batch COBOL & Sequential Files**: Fully proven by `A-PAYONLY` and `INVMGR` runs in `blackbox_test.py`. They write to output data files (`out.dat`) which are verified to match 100% by the `EquivalenceEngine`.
*   **VSAM**: Checked by `tests/test_vsam.py` but verified only for sequential equivalents (`QSAM` behavior). No KSDS or RRDS files are executed or compared.
*   **DB2 / H2 Emulation**: In `cobol_migrate.py`, the `classify_db2_status()` function categorizes database access. When real DB2 is absent, H2 is initialized as a fallback. No real DB2 connection is established or tested.
*   **Dockerized Execution**: Verified by `blackbox_test.py` running inside the Docker container. All sibling compilers compile and run within the container filesystem using the shared volume.

---

## 5. Subsystem Assessments

### DB2 Assessment
The system has four levels of DB2 support:
1.  **DB2 code/framework**: Exists in `modernize/native_generator.py` (generating JDBC/SQL code).
2.  **H2 DB2 Emulation**: Fully working. It runs local H2 databases to emulate SQL tables.
3.  **DB2 Acceptance Tests**: Exists as stubs/mock tests.
4.  **REAL DB2 execution**: `NOT_VERIFIED` / `ENVIRONMENT_BLOCKED`.
The project has reached **Level 2 (H2 DB2 Emulation)**. No real DB2 validation has ever been performed.

### CICS Assessment
*   **CICS preprocessing**: Exists (removes CICS EXEC commands or wraps them).
*   **CICS runtime compatibility**: Stubbed.
*   **CICS → Spring/REST**: Framework only.
The system does not modernize CICS screens or transactions; it merely stubs them to make compilation pass.

### BMS Assessment
BMS layout files are completely ignored. The platform has **BMS detection** (indexing BMS map extensions) but lacks BMS parsing, BMS to Java, and BMS to modern Web UI translations.

### JCL Assessment
*   **JCL detection**: Implemented (catalogues JCL files).
*   **JCL parsing**: Stubbed.
*   **JCL execution**: Unsupported.
*   **JCL → Spring Batch**: Stubbed framework classes exist but generate no valid steps.

### VSAM Assessment
*   **VSAM detection**: Implemented.
*   **VSAM emulation**: Emulated as plain sequential files.
*   **VSAM semantic equivalence**: Only sequential file writes are checked. True keyed or relative access is unsupported.

### Dynamic CALL Assessment
Dynamic calls (`CALL identifier`) are detected, but the system cannot resolve their targets. They are flagged as `DYNAMIC_CALL_REQUIRES_REVIEW` and compile/execution will fail unless manually resolved by an engineer.

---

## 6. Real-World Repository Findings
The project contains several test logs and findings from previous dry-runs:
*   **SQLCA: No such file or directory**: Occurs because DB2 precompilation dependencies are missing in the base environment.
*   **MISSING COPYBOOK**: Indicates that ingestion was incomplete or copybooks were not provided in the source zip, causing GnuCOBOL compilation to fail.
*   **DYNAMIC_CALL_REQUIRES_REVIEW**: Encountered in complex systems where subprograms are dynamically invoked, blocking transformation.
*   **cics_stubbed / sql_stubbed**: Warnings logged when CICS or SQL queries are ignored/mocked during transpilation, indicating a transformation with partial semantics.

These failures represent **Genuin Capability Gaps (G)** in the engine's capability to support modern enterprise subsystems automatically.

---

## 7. Forensic Handoff Verdict
*   **CORE PLATFORM**: `PARTIAL` (Batch COBOL and sequential files work; other features do not).
*   **REAL DB2**: `ENVIRONMENT_BLOCKED` (No reachable DB2 server).
*   **DOCKER DEPLOYMENT**: `READY` (Volume mount and path translation blockers are fully resolved; E2E runs succeed).
*   **FRONTEND**: `READY` (API responds, path traversal checks pass, basic auth fail-closed works).
*   **TEST RESULTS**: 509 tests (508 passed, 1 xpassed on host; black-box verification succeeds in container).

**OVERALL HANDOFF STATUS**: `READY_FOR_HANDOFF_WITH_LIMITATIONS`. The next developer can safely begin working on the code, as the containerized runtime has been completely fixed and E2E verification is green.
