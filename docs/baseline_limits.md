# Baseline Execution Limits & Success Criteria

### Executive Summary: Up to what limit does our project have baseline?

* **Plain COBOL and File I/O (Works)**: Standard COBOL programs using sequential, line-sequential, relative, and indexed (VSAM-equivalent) files compile and run successfully to capture golden master output files.
* **CICS Transactions (Blocked)**: Programs containing `EXEC CICS` are explicitly detected and blocked from GnuCOBOL compilation due to the absence of proprietary CICS transaction runtimes/precompilers.
* **DB2 SQL Queries (Blocked)**: Programs containing `EXEC SQL` are blocked from baseline compilation due to the absence of DB2/SQL precompilers (`esqlOC` / `cobsql`) in the GnuCOBOL builder image.
* **IMS Database Access (Blocked)**: Programs containing `EXEC DLI` are blocked from baseline compilation due to the absence of DL/I IMS precompilation libraries.
* **IBM MQ Series (Partial / Build Errors)**: Programs referencing IBM MQ copybooks (e.g., `CMQODV`, `CMQV`) but containing no `EXEC` blocks are not blocked, but fail compilation with `partial (build errors)` because the proprietary MQ SDK copybooks are missing.
* **The Exact Boundary**:
  - **Successful**: Zero `EXEC` blocks and all copybooks/runtimes present.
  - **Blocked**: Presence of `EXEC CICS`, `EXEC SQL`, or `EXEC DLI` in any repository source file.
  - **Partial (Build Errors)**: Zero `EXEC` blocks, but GnuCOBOL compilation fails due to missing files/unsupported dialect syntax.
* **No Preprocessing in Baseline**: Unlike the transpilation stage which stubs out CICS, SQL, and IMS statements, the Baseline stage compiles legacy source files in their unmodified form. Therefore, any precompiler-dependent statements or missing SDK copybooks will prevent baseline success.

---

## 1. Baseline Success Criteria

The Baseline stage (Stage 3 in `cobol_migrate.py`) classifies legacy COBOL repository status into three distinct categories:

### A. Blocked (Explicitly Prevented)
* **Conditions**: Any legacy source file contains the substring `EXEC SQL`, `EXEC CICS`, or `EXEC DLI` (case-insensitive).
* **Behavior**: Pipeline logs the blocked reason and sets the legacy status to `"blocked"`. No compilation is attempted in the GnuCOBOL Docker image.
* **Logs Excerpt**:
  ```
  [BASELINE] GnuCOBOL baseline compilation BLOCKED: missing proprietary DB2/CICS/DLI precompilation environment
  ```

### B. Partial / Build Errors (Attempted but Failed)
* **Conditions**: No `EXEC SQL/CICS/DLI` statements are present, but GnuCOBOL compilation (`cobc -m` or `cobc -x`) returns a non-zero exit code.
* **Behavior**: The build failure is logged, and the status is marked as `"partial (build errors)"` with `0` output files captured.
* **Common Causes**: Missing copybook dependencies (e.g., MQ Series SDK headers), syntactic dialects unsupported by GnuCOBOL, or missing compiler dependencies.

### C. Successful (Fully Verified)
* **Conditions**: Legacy sources compile with exit code `0` and run to completion (exit code `0`) under GnuCOBOL in the Docker container (`hurriedreformist/gnucobol:3.1-builder`).
* **Behavior**: Captures console output (`stdout.txt`, `stderr.txt`), logical output files (sequential, indexed/VSAM), and SQLite database states, storing them as the golden reference.

---

## 2. What Baseline Works for Today

Baseline execution succeeds for standard batch COBOL programs that do not rely on mainframe middleware runtimes. 

### Supported Language Features
* **Standard Control Flow**: `PERFORM`, `EVALUATE`, nested program structures, paragraph slices.
* **Data Representation**: Numeric, alphanumeric, picture editing, `COMP-3`/packed decimal processing.
* **File System Operations**: 
  - Sequential read/write (`ORGANIZATION IS SEQUENTIAL`).
  - Line-sequential flat files (`ORGANIZATION IS LINE SEQUENTIAL`).
  - Indexed files representing VSAM KSDS files (`ORGANIZATION IS INDEXED`).
* **Absence of Middleware**: Must have zero `EXEC CICS`, `EXEC SQL`, or `EXEC DLI` blocks.

---

## 3. What Baseline does NOT Work for Today

### A. Middleware Blockers (EXEC statements)
The following precompiler-dependent blocks cause the pipeline to automatically **block** baseline execution:
* **EXEC CICS**: Transaction routing, map sends/receives, and system register access.
* **EXEC SQL**: Embedded SQL queries (DB2).
* **EXEC DLI**: IMS hierarchical database access.

### B. Compilation Blockers (Missing Runtimes / SDKs)
The following patterns are not blocked by the pre-scan checks but fail during GnuCOBOL compilation:
* **IBM MQ Series**: Statements like `COPY CMQODV.` fail because IBM MQ SDK headers are proprietary and not bundled with the application repository or standard GnuCOBOL images.
* **EXEC MQ**: Embedded MQSeries directives are not stubbed by GnuCOBOL, causing compiler syntax crashes.

---

## 4. Summary Table of Baseline Capabilities

| Technology / Pattern | Baseline Behavior | Reason | How to Enable |
| :--- | :--- | :--- | :--- |
| **Plain COBOL** | **SUCCESS** | Supported natively by GnuCOBOL 3.1. | Supported by default. |
| **VSAM (Sequential/Indexed)** | **SUCCESS** | GnuCOBOL supports indexed files via BDB/VBISAM. | Supported by default. |
| **DB2 (EXEC SQL)** | **BLOCKED** | Missing DB2/SQL precompilers (`cobsql`). | Install SQL precompiler in GnuCOBOL Docker image. |
| **CICS (EXEC CICS)** | **BLOCKED** | Missing CICS precompilation/transaction monitor. | Integrate CICS preprocessor (e.g. KIX/GnuCOBOL precompiler). |
| **IMS (EXEC DLI)** | **BLOCKED** | Missing DL/I IMS precompilation libraries. | Integrate IMS precompiler or stub DL/I statements. |
| **IBM MQ Series** | **PARTIAL (FAIL)** | Missing MQ copybooks (e.g. `CMQV.cpy`) in repo. | Supply MQ SDK copybooks or add mock copybook files. |

---

## 5. Examples from Our Test Suite

### Successful Repositories
* **`SIMPLEBASELINE01`**: Minimal test repo verifying sequential file writes and basic arithmetic. Compiles and executes cleanly E2E.
* **`A-PAYONLY`**: Standard batch payroll program. Baseline executes successfully, capturing output payroll reports.
* **`VSAMKSDS01`**: Indexed key-sequenced file simulator. Compiles and runs under GnuCOBOL, verifying key index start and read loops.

### Blocked / Partial Repositories
* **`CardDemo` (`aws-mainframe-modernization-carddemo-main`)**: **Blocked**. Contains CICS, SQL, and IMS DLI statements across core modules.
* **`DB2SELECT01` / `DB2JOIN01`**: **Blocked**. Contain embedded SQL statements.
* **`CICSREST01`**: **Blocked**. Contains CICS transaction calls.

---

## 6. How to Extend Baseline Coverage

If legacy baseline execution is ever desired for blocked/partial repositories, execute the following steps:

1. **Provide Mock SDK Copybooks**: Create stub versions of proprietary SDK copybooks (like `CMQV` for MQ Series) containing standard constants, allowing programs to compile cleanly in GnuCOBOL.
2. **Integrate Open Source Precompilers**: 
   - Bundle an open source precompiler like `esqlOC` for SQL databases in the builder container.
   - Incorporate CICS translators (like GnuCOBOL CICS preprocessors) into the GnuCOBOL build step.
3. **Mock Middleware Calls**: Modify GnuCOBOL linking options to link against mock shared libraries (`.so`) that intercept CICS/DB2/MQ calls and return simulated data fixtures.
