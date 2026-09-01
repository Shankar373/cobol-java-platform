# Modernization Pipeline: Stage 3 (Baseline) Technical Analysis

### Executive Summary

* **Stage 3 Baseline Role**: Compiles legacy COBOL programs via GnuCOBOL and runs them to capture stdout, stderr, files, and DB state to serve as the golden-master reference for downstream parity verification.
* **Baseline Status**: Completed with `baseline partial (build errors); 0 output files captured` due to compilation failures inside the GnuCOBOL compiler container.
* **Transpile Status**: Errored with `transpilation produced no Java files` due to syntax errors in `cobj` compilation.
* **Bug 1 (Pathing Bug)**: `stage_baseline` attempted to inspect sources for CICS/DB2 blockers using raw repository-relative paths (`s`) instead of prepending the repository path (`os.path.join(self.repo, s)`). This raised `FileNotFoundError`, which was silently swallowed, causing the compiler check to proceed instead of gracefully blocking.
* **Bug 2 (EXEC DLI)**: The preprocessor did not recognize or comment-stub IMS Database (`EXEC DLI`) statements, causing `cobj` compilation to crash.
* **Bug 3 (COPY Regex Period)**: The copybook matching pattern included `.` in its unquoted path group, capturing trailing statement periods (e.g., matching `CMQODV.` instead of `CMQODV`), resulting in failed copybook resolution and compilation errors.
* **Bug 4 (Bogus Comment Copybook)**: `extract_copy_deps` parsed COPY statements inside comment blocks, resulting in bogus copybooks like `of`.
* **Bug 5 (Indicator Area Collision)**: Comment-stubbing produced `     CONTINUE` lines with 5 spaces of indentation, placing the letter `'O'` in column 7 (indicator area) and causing compiler syntax errors.

---

## 1. Purpose of the Baseline Stage

The **Baseline** stage (Stage 3 in the 13-stage pipeline defined in [cobol_migrate.py](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/cobol_migrate.py)) establishes the **golden-master behavior** of the legacy COBOL application. 

### Role in the Parity validation Lifecycle
1. **Source Capture**: Executes the original COBOL programs under a standard emulator environment (GnuCOBOL) using the exact same inputs (flat files, database scripts, database queries).
2. **Snapshot Creation**: Records all logical side effects of legacy execution, including:
   - Command-line standard output (`stdout.txt`) and standard error (`stderr.txt`).
   - File output writes (sequential files, line-sequential files, indexed files).
   - SQL state changes and return codes.
3. **Parity Comparison Gate**: Downstream validation gates (specifically Stage 8 `compare`) utilize these captured outputs to perform record-level and field-level differential comparison against the transpiled Java execution outputs.

---

## 2. Expected Inputs and Outputs

```
+--------------------+        +------------------------+        +------------------------+
| Discovered Sources | -----> |   Stage 3 (Baseline)   | -----> | Baseline Output files  |
|   & Copybook Dirs  |        |  (GnuCOBOL Execution)  |        | (stdout, stderr, .dat) |
+--------------------+        +------------------------+        +------------------------+
```

### Expected Inputs
* **Discovery Metadata**: A structural model containing the list of source files, copybook search paths, entry point configuration, and dataset mappings.
* **Source Trees**: Unmodified COBOL codebases containing programs and copybooks.
* **Input Datasets**: Seeds containing input records (e.g., flat files in `data/in/` or database fixtures).

### Expected Outputs
* **Compiled Binary Artifacts**: stand-alone executables (`.exe`) and dynamic link libraries (`.so`).
* **Legacy Run Logs**:
  - `stdout.txt`: Logged console display messages.
  - `stderr.txt`: Logged system messages/errors.
* **Output Datasets**: Written output files captured via directory snapshots (`data/out/*`, `data/work/*`, etc.) and SQLite database snapshots.

---

## 3. Implementation Overview

The baseline execution logic is located in:
* **Entry Point**: [cobol_migrate.py:stage_baseline](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/cobol_migrate.py#L3348-L3556)
* **Emulation Environment**: Runs inside a Docker container using the image `hurriedreformist/gnucobol:3.1-builder`.

### Compilation and Linkage Flow
1. **Precompilation Check**: Scans COBOL source files for `EXEC SQL` and `EXEC CICS` instructions. If present, it checks for precompiler availability (`esqlOC` / `cobsql`). If missing, compilation is bypassed/blocked.
2. **Directory Cleanup**: Invokes `clean_outputs` to clean up old runtime state files.
3. **Module Compilation**: Compiles subprograms (non-entry sources) into shared modules (`.so`) using `cobc -m`.
4. **Binary Linkage**: Compiles the main entry point program into an executable binary (`.exe`) using `cobc -x`, linking it against the generated subprogram modules.
5. **Execution Run**:
   - **Interactive Programs**: Emulates keyboard inputs using scenario-driven tests (`execution/scenario_runner.py`).
   - **Non-Interactive Programs**: Runs the executable under a watchdog wrapper to intercept timeouts and memory leaks.
6. **Outputs Capture**: Takes directory snapshots of logical target directories to store in `baseline/legacy`.

---

## 4. Current Status (CardDemo Project)

### What is Working
- **Stage 0 (Ingest)**: Successfully fingerprinted 44 COBOL programs and 62 copybooks.
- **Stage 1 (Discover)**: Discovered 44 programs and their respective copybook paths.
- **Stage 2 (Analyze)**: Built the structural call graphs and physical-to-logical file maps.

### What is Failing
- **Stage 3 (Baseline)**: Reports `baseline partial (build errors); 0 output files captured`. The compiler failed to build any executable, producing 0 outputs.
- **Stage 4 (Transpile)**: Fails with `transpilation produced no Java files`. All 44 sources failed transpilation in `cobj`.

---

## 5. Root Cause Analysis

### Bug 1: File Pathing Error during Block Scan
In `stage_baseline` (lines 3403–3412), the script checks for SQL/CICS statements to block baseline compilation:
```python
3403:         for s in rm_legacy:
3404:             try:
3405:                 with open(s, "r", encoding="utf-8", errors="replace") as fh:
3406:                     content = fh.read().upper()
...
3411:             except Exception:
3412:                 pass
```
* **Failure Mechanism**: `s` is a repository-relative path (e.g. `app/app-authorization-ims-db2-mq/cbl/COPAUA0C.cbl`). However, the pipeline's current working directory is the tool root directory. Opening `s` directly throws `FileNotFoundError`. The `except Exception: pass` silently swallowed the error.
* **Consequence**: `has_sql` and `has_cics` were falsely evaluated as `False`. The pipeline proceeded to run GnuCOBOL compilation instead of blocking it.

### Bug 2: Missing EXEC DLI IMS Database Stubbing
The preprocessor in [cobol_migrate.py:preprocess_cobol_for_cobj](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/cobol_migrate.py#L1473-L1946) only handles `EXEC CICS` and `EXEC SQL`. It does not support `EXEC DLI` (IMS database statements).
* **Failure Evidence (Docker Compile Log)**:
  ```
  app/app-authorization-ims-db2-mq/cbl/CBPAUP0C.cbl:219: Error: Unknown statement 'EXEC'
  app/app-authorization-ims-db2-mq/cbl/CBPAUP0C.cbl:219: Error: Unknown statement 'DLI'
  ```
* **Consequence**: Preprocessed files still contained `EXEC DLI ... END-EXEC` blocks, causing `cobj` to crash during the transpile phase.

### Bug 3: Period Character Matching in `_RE_COPY`
The COPY statement regex matches periods as part of the unquoted file name:
```python
_RE_COPY = re.compile(
    r'(?i)\bCOPY\s+'
    r'(?:"([^"]+)"|\'([^\']+)\'|([A-Za-z0-9_\-./\\]+))'
)
```
* **Failure Mechanism**: For `COPY CMQODV.`, the trailing period was captured in the matched name (Group 3 matched `CMQODV.`).
* **Consequence**: The pipeline failed to resolve the copybooks and synthesized corrupted copybook stubs named `CMQODV..CPY`. When the compiler ran, the COPY statements could not be resolved, causing `PICTURE clause required` errors for variables under group items (e.g. `MQM-OD-REQUEST`).

### Bug 4: COPY Matching Inside Comments
The `extract_copy_deps` function ran on unstripped source text.
* **Failure Mechanism**: Comment strings like `* a copy of the License` were matched, extracting `of` as a missing copybook dependency.

### Bug 5: Indentation Indicator Collision for generated `CONTINUE` Statements
The preprocessor stubs block matches using the matched indent prefix.
* **Failure Mechanism**: If a line begins with a sequence number, e.g., `091000     EXEC`, the matched indent is 5 spaces. The preprocessor replaces the block with:
  `     CONTINUE`
* **Consequence**: The character `'O'` of `CONTINUE` is positioned at column 7. In fixed-format COBOL, column 7 is the indicator area. This caused the GnuCOBOL compiler to crash:
  ```
  app/app-transaction-type-db2/cbl/COTRTLIC.cbl:918: Error: Invalid indicator 'O' at column 7
  ```

---

## 6. Impact on Downstream Stages

1. **Stage 4 (Transpile) Correlation**: The transpile stage fails directly due to **Bugs 2, 3, 4, and 5**. Because the preprocessor did not handle `EXEC DLI` statements, mis-parsed copybooks with trailing periods, and output statements violating column-7 rules, `cobj` produced zero Java files.
2. **Parity Gate (Stage 8/10) Blockers**: Because Stage 3 produced no baseline outputs, downstream equivalence runs cannot verify equivalence, blocking the overall migration verdict.

---

## 7. Recommended Fixes

### 1. Fix Pathing inside block checks in `stage_baseline`
Modify [cobol_migrate.py:3405](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/cobol_migrate.py#L3405) to join the path with the repository base:
```python
with open(os.path.join(self.repo, s), "r", encoding="utf-8", errors="replace") as fh:
```

### 2. Implement EXEC DLI Preprocessing
Introduce `_RE_EXEC_DLI` pattern and comment out DLI blocks inside `preprocess_cobol_for_cobj`:
```python
_RE_EXEC_DLI = re.compile(r'([ \t]*)EXEC\s+DLI\b.*?END-EXEC\.?', re.IGNORECASE | re.DOTALL)
```
Add subn stubs for `EXEC DLI` inside both Data and Procedure divisions, logging count in `stats["dli_stubbed"]`.

### 3. Exclude Trailing Period from Copybook Matching
Modify `extract_copy_deps` to strip trailing periods from captured copybook references:
```python
raw = (m.group(1) or m.group(2) or m.group(3) or "").strip()
if raw.endswith("."):
    raw = raw[:-1].strip()
```

### 4. Strip Comments Prior to COPY Parsing
Filter comment lines in `extract_copy_deps` before matching regex:
```python
clean_lines = []
for line in text.splitlines():
    if len(line) > 6 and line[6] in ("*", "/"):
        continue
    idx = line.find("*>")
    if idx != -1:
        line = line[:idx]
    clean_lines.append(line)
clean_text = "\n".join(clean_lines)
```

### 5. Prevent Indicator Area Clash in stubbing
Modify `_comment_out_block` to ensure that indentations for code statements (like `CONTINUE`) are at least 11 spaces (so that they start in Area B):
```python
indent = match.group(1) if match.group(1) else '           '
if len(indent) < 11:
    indent = '           '
```

---

## 8. Open Questions

1. **IMS/DB2 Execution Mocking**: For CardDemo, since DB2 precompilation and IMS database environments are absent on standard execution hosts, is baseline execution meant to be bypassed, or should we mock IMS calls natively? (Recommended: Bypassing legacy execution via the `blocked` status is the correct intended path in the pipeline design).
2. **COBOL Standard mode**: Should CardDemo sources compile in fixed-format mode or free-format? (The sequence numbers at columns 1-6 suggest fixed-format mode is correct).
