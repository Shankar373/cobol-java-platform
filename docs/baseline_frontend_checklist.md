# Baseline Verification via Frontend Checklist

This checklist provides the steps to verify the pipeline's Baseline execution stage using a simple, non-blocked COBOL repository (`SIMPLEBASELINE01`) in the modernization frontend interface.

---

## 1. Purpose
The `CardDemo` application uses DB2, CICS, and IMS database statements. Because the GnuCOBOL environment in the pipeline runner lacks proprietary precompilation tools, the pipeline is designed to **block** baseline compilation and execution for `CardDemo`. 

To verify that the Baseline stage actually executes and captures outputs successfully when the environment is valid, we run it against `SIMPLEBASELINE01` — a minimal repository containing standard COBOL with no proprietary syntax.

---

## 2. Prerequisites
* **Docker Daemon**: Must be running on the host system.
* **GnuCOBOL Docker Image**: The image `hurriedreformist/gnucobol:3.1-builder` must be pulled/available.
* **cobj Docker Image**: The image `opensourcecobol/opensourcecobol4j:2.0.0` must be pulled/available.
* **Frontend server**: Running on port `3000` (frontend UI) and port `8000` (backend API).

---

## 3. Steps to Verify Baseline Execution via Frontend

1. **Open Frontend UI**: Navigate to `http://localhost:3000` in the browser.
2. **Select/Upload Repository**:
   - Set the repository path to: `tests/repos/SIMPLEBASELINE01`
   - Set the target output path to: `target_simple`
3. **Configure Stages**:
   - In the pipeline configuration sidebar, select the target execution stage to run or restart from **Stage 3 (Baseline)**.
4. **Trigger Pipeline Execution**:
   - Click **Run Pipeline** or **Execute Stage**.
5. **Verify UI Baseline Outcomes (Stage 3)**:
   - **Status Text**: The baseline stage should display a green **SUCCESS** status (not "blocked").
   - **No Blocked Message**: Confirm there is no message saying `BLOCKED: missing proprietary DB2/CICS/DLI`.
   - **Output Logs**: Click the Baseline stage logs to verify that GnuCOBOL compiled the program and executed it, producing output files.
   - **Generated Artifacts**:
     - Check for `stdout.txt` and `stderr.txt` in the baseline target artifacts panel.
     - Verify the existence of the generated output dataset `data/out.dat`.

---

## 4. Steps to Verify Transpile via Frontend

1. **Trigger Transpilation**:
   - Select **Stage 4 (Transpile)** and click **Run**.
2. **Verify UI Transpile Outcomes (Stage 4)**:
   - **Status Text**: Displays **SUCCESS** status.
   - **Java Sources Generated**:
     - Confirm that `SIMPLEBASELINE01.java` (or case-insensitive equivalent) is listed in the transpiled artifacts panel.
     - Confirm there are no syntax error logs from EXEC DLI, COPY, or indicator area collisions.
3. **Verify Spring Boot Refactoring**:
   - Complete the rest of the stages through **Stage 11 (Validate)**.
   - Confirm that the Spring Boot Maven check builds successfully (`[PASS] Spring Boot Maven project compiled successfully`) and the equivalence check passes.

---

## 5. CLI Fallback Commands
If the frontend needs to be validated against CLI outputs, execute the following commands in the workspace root directory:

### Run Stage 3 (Baseline) Only
```powershell
python cobol_migrate.py --repo tests/repos/SIMPLEBASELINE01 --out target_simple --restart-from 3
```
*Expected Log Snippet*:
```
== [4/13] baseline ==
  interactivity: NON_INTERACTIVE
    - data/out.dat (21 bytes)
baseline done: baseline produced 1 output files
```

### Run Stage 4 (Transpile) Only
```powershell
python cobol_migrate.py --repo tests/repos/SIMPLEBASELINE01 --out target_simple --restart-from 4
```
*Expected Log Snippet*:
```
== [5/13] transpile ==
  cobj invocation: docker run --rm -v <repo>:/repo opensourcecobol/opensourcecobol4j:2.0.0 bash -c "cd /repo && cobj -free  -o generated -j generated src/SIMPLEBASELINE01.cob"
    [OK ] src/SIMPLEBASELINE01.cob
transpile done: 1 programs transpiled
```

### Run Full Pipeline
```powershell
python cobol_migrate.py --repo tests/repos/SIMPLEBASELINE01 --out target_simple
```
*Expected Log Snippet*:
```
validate done: Gate 2 PASS — output matched baseline
report done: verdict MVP_CERTIFIED
package done: modernized application packaged successfully
```
