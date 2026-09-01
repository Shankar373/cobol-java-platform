# Implementation Plan: Mainframe JCL Modernization

This plan outlines the design and implementation of JCL Batch Workflow Orchestration (Phase 6 & 7):
1. **JCL Parser & JCL IR**: Standalone, independent parser supporting `JOB`, `EXEC`, `DD`, `PROC`/`PEND` expansion, `SET` symbol substitution, inline `SYSIN` datasets, and conditional executing routing (`COND` and `IF-THEN-ELSE`).
2. **JCL to Spring Batch Java Code Generation**: Automatically transpiled parsed JCL workflows into Spring Batch Job configurations using the legacy-free Spring/Java framework.

## User Review Required

> [!IMPORTANT]
> - **Mainframe COND Condition Inversion**: In mainframe JCL, the `COND` parameter specifies when a step should be **BYPASSED** (skipped), rather than executed. For example, `COND=(4,LT,STEP1)` means "if 4 is less than STEP1's return code, bypass this step". We will implement this standard conditional logic.
> - **SYSIN File Emulation**: Inline SYSIN datasets will be written to temporary files at step execution time, and their paths registered dynamically in `JclExecutionContext` so that sequential file reads map seamlessly.
> - **JclExecutionContext Isolation**: Step return codes, SYSIN paths, and DD assignments will be stored in `ThreadLocal` storage, ensuring full isolation during concurrent job execution.

## Proposed Changes

### Component: JCL Parser & JCL IR

#### [NEW] [`modernize/jcl_parser.py`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/modernize/jcl_parser.py)
- Implement `JclParser` to read and parse JCL files line-by-line.
- Track JCL continuation lines (joining lines ending in commas followed by spaces).
- Identify and store JCL Procedures (`PROC` / `PEND`).
- Support symbol definition (`SET` / `PROC` parameters) and substitution (`&SYM` / `&SYM.`).
- Parse conditions:
  - `EXEC COND` parameter: support bypass operator logic (`EQ`, `NE`, `GT`, `LT`, `GE`, `LE`).
  - `IF-THEN-ELSE-ENDIF` JCL structures.
- Detect diagnostics errors:
  - `JCL_INVALID_STEP`: `EXEC` card has neither `PGM` nor `PROC`.
  - `JCL_UNRESOLVED_PROC`: referenced PROC definition not found.
  - `JCL_UNRESOLVED_SYMBOL`: symbol starts with `&` but is unresolved.
  - `JCL_UNSUPPORTED_CONDITION`: condition syntax is malformed.
  - `JCL_DATASET_NOT_FOUND`: dataset does not exist on disk when `DISP=SHR` or `DISP=OLD` is specified.

---

### Component: Java Spring Batch Generation

#### [MODIFY] [`modernize/native_pipeline.py`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/modernize/native_pipeline.py)
- Update `stage_discover()` to search for files with `.jcl` extensions.
- Generate standard runtime helper [`JclExecutionContext.java`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/generated/src/main/java/com/systema/modernized/JclExecutionContext.java) inside the helpers directory.
- Generate JCL job executers that construct a Spring Batch `Job` configuration matching JCL steps, transitions, and conditional step execution.
- Map step execution to Java classes (executing the corresponding COBOL modernized program `execute()` method).

#### [MODIFY] [`modernize/native_generator.py`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/modernize/native_generator.py)
- Modify file path resolution inside generated program file I/O methods to query `com.systema.modernized.JclExecutionContext.getDdAssignment(...)` before falling back to static default paths.

---

### Component: JCL Test Infrastructure

#### [NEW] [`tests/test_jcl_modernization.py`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/tests/test_jcl_modernization.py)
- E2E tests validating JOB run execution, PROC symbol resolution, SYSIN inline data consumption, and conditional bypass logic.
- Negative tests validating unregistered symbols, missing datasets, and invalid step execution.

---

## Verification Plan


### Differential Testing and Boundary Verification
- Build and run the previously failing mainframe legacy repository:
  ```powershell
  python cobol_migrate.py --repo legacy --out target
  ```
  Ensure compile, package, and execution outcomes all succeed.
- Create a new COBOL test application [`tests/repos/CUSTOMER01/src/CUSTOMER01.cob`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/tests/repos/CUSTOMER01/src/CUSTOMER01.cob) simulating `CUSTOMER-NAME`, `CUSTOMER-ADDRESS`, and multiple reference modifications with expressions. Check for differential byte-for-byte equivalence of output files.
