# Test Charter and Needs Analysis: COBOL-to-Java Modernization Platform

This document presents a comprehensive test-needs analysis and a structured test charter for the COBOL-to-Java modernization platform. The analysis is based strictly on the source code, runtime library components, and the test suite available in the repository.

---

## 1. Map the Implementation Landscape

The platform is designed to transpile COBOL legacy codebase artifacts (programs, copybooks, JCL scripts, BMS screen maps) into equivalent Java source code and Spring Boot applications, supporting emulated mainframe behavior.

### Core Transformation Logic
*   **Lexer (`modernize/lexer.py`)**: 
    *   *What it does*: Lexes raw COBOL source code text into tokens. Handles fixed-format column limits, comment stripping, copybook preprocessing, and string literal continuation across lines.
    *   *Main Inputs/Outputs*: Inputs raw COBOL strings. Outputs a list of `CobolToken` structures.
    *   *Dependencies*: Relies on python's `re` and `os` libraries.
    *   *Usage*: Utilized by CLI scripts and the pipeline.
*   **Parser (`modernize/parser.py`)**: 
    *   *What it does*: Parses token lists to build a structured AST representation of variables (DATA DIVISION) and execution statements (PROCEDURE DIVISION).
    *   *Main Inputs/Outputs*: Inputs list of `CobolToken`. Outputs `SemanticIR` containing parsed program nodes.
    *   *Dependencies*: Relies on `lexer.py` and `semantic_ir.py`.
    *   *Usage*: Core entry point for semantic analysis and control flow mapping.
*   **Semantic IR (`modernize/semantic_ir.py`)**: 
    *   *What it does*: Defines nodes for variables (`DATA_ITEM`), statements (`STATEMENT`), and logic structures (`PARAGRAPH`) with their metadata.
    *   *Main Inputs/Outputs*: Inputs node properties. Outputs structured JSON-serializable AST metadata.
    *   *Dependencies*: None.
*   **Native Code Generator (`modernize/native_generator.py`)**: 
    *   *What it does*: Transpiles parsed Semantic IR nodes into standalone Java classes matching the structure, execution logic, and database schemas of COBOL source.
    *   *Main Inputs/Outputs*: Inputs `SemanticIR` AST. Outputs Java class code (`.java` files).
    *   *Dependencies*: Relies on `parser.py` and `semantic_ir.py`.
*   **Enterprise Generator (`modernize/enterprise_generator.py`)**: 
    *   *What it does*: Transpiles parsed COBOL/CICS batch logic to modern Spring Boot REST endpoints.
    *   *Main Inputs/Outputs*: Inputs `SemanticIR` AST. Outputs Spring Boot controllers, repositories, and entities.
    *   *Dependencies*: Relies on `parser.py` and `semantic_ir.py`.
*   **JCL Parser & Generator (`modernize/jcl_parser.py`, `modernize/jcl_generator.py`)**: 
    *   *What it does*: Parses JCL batch scripts to map steps, conditional executions, and DD data assignments, generating equivalent Java orchestration launcher classes.
    *   *Main Inputs/Outputs*: Inputs `.jcl` text. Outputs orchestration Java launcher code.
*   **BMS Parser (`modernize/bms_parser.py`)**: 
    *   *What it does*: Parses CICS BMS screen map definitions to generate equivalent JSON map metadata.
    *   *Main Inputs/Outputs*: Inputs BMS `.bms` text. Outputs JSON screen metadata.

### Runtime/Emulation Logic
*   **CobolNumeric Helper (`modernize/java_helpers/src/main/java/com/systema/modernized/runtime/CobolNumeric.java`)**: 
    *   *What it does*: Emulates COBOL numeric types, decimal precision representation (COMP-3 packed decimal and DISPLAY zoned decimal), sign positions, and storage backing buffers.
*   **CobolArithmetic Helper (`modernize/java_helpers/src/main/java/com/systema/modernized/runtime/CobolArithmetic.java`)**: 
    *   *What it does*: Handles rounding modes (ROUNDED), sizing, ON SIZE ERROR overflows, division by zero, and precision truncation.
*   **CobolFormatHelper (`modernize/java_helpers/CobolFormatHelper.java`)**: 
    *   *What it does*: Emulates PICTURE clause formatted outputs (currency signs, decimal separator alignment, zero suppression, asterisks, signs).
*   **KsdSDbService & VsamIndexedStore (`modernize/java_helpers/src/main/java/com/systema/modernized/KsdSDbService.java`, `runtime/VsamIndexedStore.java`)**: 
    *   *What it does*: Emulates mainframe VSAM KSDS database-backed indexed file indexing, record storage, and alternative index retrievals.
*   **MockSqlService (`modernize/mock_sql_service.py` / `MockSqlService.java`)**: 
    *   *What it does*: Mock database setup wrapper providing H2/PostgreSQL context initialization, table creation, and baseline data seeding.
*   **CICS & JCL Execution Emulators (`modernize/java_helpers/src/main/java/com/systema/modernized/CicsTransactionContext.java`, `JclExecutionContext.java`)**: 
    *   *What it does*: Simulates transaction COMMAREAs, linked programs, conditional steps, and DD/SYSIN files mapping.

### Test Harness / Infrastructure
*   **Cobol Runner (`tests/utils/cobol_runner.py`)**: 
    *   *What it does*: Transpiles COBOL to Java, compiles, and runs Java standalone programs dynamically (does *not* execute GnuCOBOL baseline, despite its name).
*   **Parity Harness (`tests/utils/parity_harness.py`)**: 
    *   *What it does*: Compiles and runs baseline COBOL under Docker/GnuCOBOL, compiles and runs generated Java class, and performs differential byte-exact, record count, and exit code comparisons.

---

## 2. Identify What "Business Equivalence" Means Here

Business equivalence guarantees that the transpiled Java execution produces output data, logs, database states, and program flows identical to the legacy COBOL execution.

Based on the runtime library and pipeline code, the following semantics must be strictly preserved:

1.  **Numeric Semantics**:
    *   *Implementation*: [`CobolNumeric.java`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/modernize/java_helpers/src/main/java/com/systema/modernized/runtime/CobolNumeric.java) (lines 65-151) and [`CobolArithmetic.java`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/modernize/java_helpers/src/main/java/com/systema/modernized/runtime/CobolArithmetic.java).
    *   *Behavior*: Absolute value coercion for unsigned receivers; explicit overflow trapping via `checkSizeError` (lines 125-129); `ON SIZE ERROR` branch execution; custom rounding modes (downward truncation by default vs bank's rounded); division-by-zero checks.
2.  **Storage Layout**:
    *   *Implementation*: [`CobolNumeric.java`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/modernize/java_helpers/src/main/java/com/systema/modernized/runtime/CobolNumeric.java) (lines 153-224, 282-340).
    *   *Behavior*: Backing shared byte arrays for `REDEFINES` variables, where edits to one field immediately reflect in overlapping byte segments of a redefined field; packed decimal (`COMP-3` BCD nibbles) encoding and ASCII zoned decimal overpunched signs decoding.
3.  **Control Flow**:
    *   *Implementation*: Generated Java code structures (`Db2tvs01.java` etc.) generated by [`native_generator.py`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/modernize/native_generator.py) (lines 2000-4000).
    *   *Behavior*: Section-level GOTO execution; PERFORM loops (UNTIL, TIMES, VARYING); dynamic program-to-program call passing LINKAGE SECTION reference arguments.
4.  **File I/O**:
    *   *Implementation*: [`VsamIndexedStore.java`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/modernize/java_helpers/src/main/java/com/systema/modernized/runtime/VsamIndexedStore.java) and [`KsdSDbService.java`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/modernize/KsdSDbService.java).
    *   *Behavior*: Line sequential, relative (RRDS), and indexed sequential (VSAM KSDS) file operations. Simulates return status codes (FILE STATUS `00` for OK, `10` for EOF, `35` for file not found).
5.  **Database / DB2 Behavior**:
    *   *Implementation*: Generated Java classes (`execute()` method DB2 branches) and [`Db2ErrorMapper.java`].
    *   *Behavior*: DB2 SQLCODE/SQLSTATE mapping (e.g., `-803` for constraint violation, `100` for not found); transaction commits/rollbacks; null indicator host variables.
6.  **CICS Emulation**:
    *   *Implementation*: [`CicsTransactionContext.java`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/modernize/java_helpers/src/main/java/com/systema/modernized/CicsTransactionContext.java) and [`CicsProgramRegistry.java`].
    *   *Behavior*: EXEC CICS LINK, COMMAREA state propagation, and screen map definitions.
7.  **JCL-like Orchestration**:
    *   *Implementation*: [`JclExecutionContext.java`] and step wrappers.
    *   *Behavior*: Orchestrates steps execution, updates execution status codes, handles logical condition branch triggers.

---

## 3. Test Charter (What MUST Be Tested and Why)

The test charter maps critical runtime behaviors to their requirements, failure consequences, and necessary evidence.

| Behavior Area | Why It Must Be Tested (Risk) | What Must Be Compared | Minimum Evidence Level |
| :--- | :--- | :--- | :--- |
| **Numeric Overflow (`ON SIZE ERROR`)** | Silent digit truncation or arithmetic crash would cause severe ledger imbalance. | Exit code, stdout, and state value. | `DIFFERENTIAL_COBOL_JAVA` |
| **REDEFINES Shared Buffer** | Non-shared memory layout would make updates to redefined variables invisible to the parent variables. | Raw byte array hashes and stdout. | `DIFFERENTIAL_COBOL_JAVA` |
| **COMP-3/Packed Decimal** | Incorrect BCD nibble encoding/decoding leads to corrupt file outputs and database failures. | Byte-exact file comparison. | `DIFFERENTIAL_COBOL_JAVA` |
| **GOTO / PERFORM Loops** | Incorrect loop branching leads to infinite loops, stack overflow, or dead paths in Java. | Output prints, loop counts. | `DIFFERENTIAL_COBOL_JAVA` or `RUNTIME_JAVA_ONLY` |
| **VSAM FILE STATUS** | Incorrect status codes (e.g. returning `00` on EOF instead of `10`) crash application control loops. | Standard error stream, status variable. | `DIFFERENTIAL_COBOL_JAVA` |
| **DB2 Transaction Isolation** | Rollback failures (autocommit = true by default) persist uncommitted records, corrupting DB integrity. | Live database state, stdout logs. | `RUNTIME_JAVA_ONLY` against real DB (PostgreSQL/DB2) |
| **CICS LINK COMMAREA** | Incorrect serialization of context maps crashes linked system state during transfers. | Java object context comparison. | `RUNTIME_JAVA_ONLY` with mocks |

---

## 4. Audit of Existing Tests

Each test suite within the repository has been analyzed and classified based on its execution methodology.

### 1. Differential Test Suite (True Parity Validation)
*   **`test_parity_fixtures.py`**:
    *   *Charter Targets*: Numeric types, implied decimals, COMP-3, REDEFINES, rounding, overflows, divisions.
    *   *Methodology*: Compiles/Runs COBOL (GnuCOBOL Docker), transpiles, runs Java, compares outputs differentially.
    *   *Classification*: **`DIFFERENTIAL_COBOL_JAVA`**
*   **`logical_audit_test.py`**:
    *   *Charter Targets*: Indexed files storage comparison and delta detection.
    *   *Methodology*: Compiles/Runs GnuCOBOL loader, transpiles and runs Java (opensourcecobol4j), compares SQLite database outputs.
    *   *Classification*: **`DIFFERENTIAL_COBOL_JAVA`** (ENVIRONMENT_BLOCKED if Docker is missing).

### 2. Runtime-Java-Only Suites (Pre-seeded Baseline / Static Verification)
*   **`test_db2_stage1.py`** & **`test_postgres_e2e.py`**:
    *   *Charter Targets*: SQL aggregate counts, joins, subqueries, database error mappings, transactional commits/rollbacks.
    *   *Methodology*: Pre-seeds static baseline `stdout.txt` files inside target temp directories. Runs the transpiler, compiles the generated Java classes, runs them against PostgreSQL/H2, and compares output with the pre-seeded files. Bypasses real GnuCOBOL baseline run.
    *   *Classification*: **`RUNTIME_JAVA_ONLY`** (against real PG or H2).
*   **`test_phase8_file_semantics.py`**:
    *   *Charter Targets*: Line sequential, relative (RRDS), and indexed sequential (VSAM) file read/write.
    *   *Methodology*: Executes Java program via `cobol_runner` and asserts output strings. Does not execute GnuCOBOL dynamically.
    *   *Classification*: **`RUNTIME_JAVA_ONLY`**
*   **`test_phase8_pic_formatting.py`**:
    *   *Charter Targets*: PICTURE formatting outputs and overflows.
    *   *Methodology*: Executes Java program and asserts stdout formats.
    *   *Classification*: **`RUNTIME_JAVA_ONLY`**
*   **`test_cics_modernization.py`**:
    *   *Charter Targets*: CICS map serialization, screen inputs, execution link context.
    *   *Methodology*: Mocks baseline run. Compiles and executes Java classes using Mock CICS Service inputs.
    *   *Classification*: **`RUNTIME_JAVA_ONLY`** (MOCK_BASED).
*   **`test_jcl_modernization.py`**:
    *   *Charter Targets*: JCL execution orchestration, file step allocations, condition checks.
    *   *Methodology*: Mocks baseline run. Executes Java JCL orchestrator class.
    *   *Classification*: **`RUNTIME_JAVA_ONLY`**

### 3. Static Verification Suites
*   **`test_phase8_redefines.py`**:
    *   *Charter Targets*: REDEFINES offset parsing and layout calculations.
    *   *Methodology*: Parses COBOL code and checks properties of nodes or content patterns in generated Java files.
    *   *Classification*: **`STATIC_ONLY`**
*   **`test_control_flow.py`** & **`test_data_flow.py`**:
    *   *Charter Targets*: Flow block logic.
    *   *Methodology*: Parses tokens and asserts AST structure.
    *   *Classification*: **`STATIC_ONLY`**
*   **`test_lexer.py`** & **`test_parser.py`**:
    *   *Charter Targets*: Lexing/parsing errors.
    *   *Methodology*: Run transpiler frontend components and assert syntax.
    *   *Classification*: **`STATIC_ONLY`**

### Critical Gaps and Risks Identified
1.  **Mocked Baseline Bypass**: Almost all end-to-end integration tests (VSAM, SQL/DB2, CICS, JCL) bypass legacy baseline execution by pre-seeding `stdout.txt` or stubbing `run_legacy_baseline = lambda: None`. If GnuCOBOL behaves differently (e.g. different trailing space handling or SQLCODE outputs), these tests will pass incorrectly.
2.  **No Real DB2 Verification**: DB2 tests execute against PostgreSQL or H2 databases. The dialect differences (such as null indicator evaluation, string casting, or default null orderings) are not differentially compared against a live DB2 database.
3.  **Missing Dynamic Call Parity**: Multi-program dynamic calls (passing arguments via LINKAGE SECTION) are not verified differentially with active stack mutations.

---

## 5. Ideal Test Topology

To establish high business equivalence, the test suite should adopt a three-tiered test topology:

1.  **Unit Tests (`STATIC_ONLY`)**:
    *   *Scope*: Lexer, Parser, IR logic.
    *   *Inputs*: Raw COBOL snippets.
    *   *Assertions*: AST structure matches specs.
2.  **Component Integration Tests (`RUNTIME_JAVA_ONLY` / Mock-Based)**:
    *   *Scope*: Live Spring Boot context, file operations, transactional commits.
    *   *Infrastructure*: Live PostgreSQL, H2, Mock CICS registries.
    *   *Assertions*: REST endpoint return statuses, database tables changes.
3.  **End-to-End Differential Parity Tests (`DIFFERENTIAL_COBOL_JAVA`)**:
    *   *Scope*: Compute logic, packed/zoned decimal conversions, REDEFINES buffer sharing, relative and indexed files.
    *   *Infrastructure*: Docker container with GnuCOBOL/OCESQL alongside Java runtime.
    *   *Assertions*: Byte-for-byte outputs matching, exact exit codes, matching stderr, record-by-record checks.

---

## 6. Recommended Next Steps

1.  **P0: Migrate VSAM Tests to Differential Harness**
    *   *Action*: Convert [`test_phase8_file_semantics.py`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/tests/test_phase8_file_semantics.py) to use `run_parity()`. Remove `p.run_legacy_baseline = lambda: None` to verify line sequential and indexed files against live GnuCOBOL.
2.  **P0: Strengthen Transaction Isolation Verification**
    *   *Action*: Ensure [`test_db2_stage1.py`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/tests/test_db2_stage1.py) does not pre-seed baseline stdout, but rather runs DB2 SQL statements differentially on PostgreSQL.
3.  **P1: Add Unaligned REDEFINES Parity Tests**
    *   *Action*: Write additional differential fixtures testing variable-length fields overlapping COMP-3 packed decimals.
4.  **P2: Integrate Real CICS Map Verification**
    *   *Action*: Create a differential map integration fixture verifying BMS map output fields alignment.
