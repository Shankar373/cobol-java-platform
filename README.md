# COBOL-to-Java Modernization Pipeline & Audit Portal

Repository-agnostic, automated COBOL to Java modernization pipeline and validation suite, including a standalone audit verification engine, an interactive portal dashboard, and a native Java Enterprise refactoring layer (Spring Boot + Spring Batch + REST APIs).

---

## Production Architecture & Stages

The pipeline (`cobol_migrate.py`) automates the full modernization lifecycle through **13 distinct execution stages (0 to 12)**:

- **Stage 0 - Ingest**: Extract repositories, calculate SHA-256 signatures, and establish source immutability boundaries.
- **Stage 1 - Discover**: Parse directory trees to discover COBOL source files (`.cob`/`.cbl`) and copybooks (`.cpy`). Map file linkages and compile the initial dependency call-graph.
- **Stage 2 - Analyze**: Discover embeddable CICS/SQL commands, calculate scopes, and perform legacy feature categorization.
- **Stage 3 - Baseline**: Compile and execute source COBOL code against a pinned GnuCOBOL compiler in a Docker container to record golden baselines.
- **Stage 4 - Transpile**: Transpile raw COBOL to Java classes via opensourcecobol4j Docker (Track A).
- **Stage 5 - Collect**: Collect Track-A Java source components and identify legacy stub imports.
- **Stage 6 - Preserve**: Vendor runtime libraries (`libcobj.jar`) into compile directories.
- **Stage 7 - Generate**: Assemble target native Spring Boot Project directories and provenance manifests (Track B).
- **Stage 8 - Execute**: Run the compiled Java classes against equivalent input scopes.
- **Stage 9 - Compare**: Run the Equivalence Engine to compare stdout/stderr and file streams byte-for-byte.
- **Stage 10 - Refactor**: Generate clean, native Spring Boot REST APIs, Spring Batch tasklets, and JPA relational schemas (Track B).
- **Stage 11 - Validate**: Boot up the modernized Spring Batch application against H2 and compile using Maven.
- **Stage 12 - Package**: Build a distributable ZIP package containing the generated Spring Boot projects, baselines, and execution logs.

---

## Key Documentation & Architecture Matrix

- **[Project Architecture & File Matrix](file:///C:/Users/bandi/.gemini/antigravity-ide/brain/4eb9e566-6b96-4279-b4ee-377cce30fdad/project_architecture_matrix.md)**: File-by-file mapping documenting role descriptions, achievements, and technical gaps.
- **[Transformation Coverage Matrix](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/docs/transformation-coverage.md)**: Feature-by-feature mapping listing parser locations, code generator classes, and verification levels.
- **[Test Charter & Needs Analysis](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/docs/test_charter_and_needs_analysis.md)**: Testing strategy outlining business equivalence definitions and existing test suite structure.
- **[Platform Limitations and Gaps](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/docs/limitations_and_gaps.md)**: Thorough stage-by-stage and construct-level limitations index.

---

## Toolchain & Requirements

- **Python 3.8+** (Standard Library only)
- **Docker** (Required on the host for GnuCOBOL/JDK isolation and parity testing)
- **Maven** (Used for final target application compilation checks)

---

## Quick Start Guide

### 1. Run the Portal Dashboard (Interactive UI)
Exposes an interactive dashboard to select repositories, execute pipelines, inspect files, and explore modernized Java code:
```bash
python ui.py
```
Open `http://localhost:8787` in your browser.

### 2. Run the Pipeline from the CLI
Run the entire 13-stage automated modernization pipeline against the local repository:
```bash
python cobol_migrate.py --repo legacy --out target --restart-from 0
```

### 3. Run the Standalone Audit Engine
Validate all 7 synthetic verification shape repositories (`A-PAYONLY` through `G-PAYMISSCP`) to prove correctness:
```bash
python audit_engine.py --run-synthetic
```

### 4. Run the Pytest Verification Suite
Run the full test suite comprising 36 verified tests (differential parity tests, unit tests, assignment logic):
```bash
python -m pytest tests/ -v
```
To run only differential container-parity tests:
```bash
python -m pytest tests/test_parity_fixtures.py -v
```

---

## Dockerizing & Running the Modernized App

The modernized Spring Boot batch application (generated inside `target/modernized/`) runs in a JRE container and mounts legacy files for processing:

### 1. Build the Docker Image
```bash
docker build -t modernized-app target/modernized/
```

### 2. Run the Container
Mount the legacy directory (where the `.dat` transaction files are located) and map port `8080`:
```bash
docker run -d -p 8080:8080 -v c:\Users\bandi\Desktop\SystemaOps\Cobol-to-java-test\legacy:/legacy --name modernized-container modernized-app
```

### 3. Query the REST Endpoints
Once the batch job completes (`Job: [FlowJob: [name=processClaimsJob]] completed ... status: [COMPLETED]`), query the H2 database results:
- **Query Processed Claims**:
  ```bash
  curl http://localhost:8080/api/process/claims
  ```
- **Query Processing Exceptions**:
  ```bash
  curl http://localhost:8080/api/process/exceptions
  ```

---

## Interactive Legacy Application Execution

The pipeline automatically detects COBOL entry points that contain user-facing
`ACCEPT` statements and executes them deterministically using discovered test
scenarios or input fixtures.

### How it works

1. **Detection** — The pipeline analyses every COBOL source reachable from the
   configured entry point and classifies the application:
   - `NON_INTERACTIVE` — no stdin-consuming `ACCEPT` found; existing batch path is used unchanged.
   - `INTERACTIVE` — one or more bare `ACCEPT` (without `FROM DATE/TIME/DAY-OF-WEEK`) found; scenario discovery runs.
   - `UNKNOWN` — dynamic `CALL` targets prevent full analysis; treated as interactive.

   > `ACCEPT WS-DATE FROM DATE` and `ACCEPT WS-T FROM TIME` are **not** treated
   > as interactive — they read the system clock, not stdin.

2. **Scenario discovery** (in priority order):
   1. Shell smoke/test scripts (`test/*.sh`, `test/*.bash`) — heredoc, echo pipe, printf pipe
   2. Stdin fixture files (`test/*.stdin`, `data/in/*.stdin`, etc.)
   3. Explicit path in `migration_config.json` under `execution.interactive_scenario`
   4. Code blocks in `README.md`
   5. **Fail fast** — `INTERACTIVE_INPUT_REQUIRED` — if no safe scenario exists

   Static analysis is used only for diagnostics (identifying which `ACCEPT` statements
   were found). It **never automatically generates business transactions**.

3. **Deterministic execution** — The discovered scenario is persisted in `state.json`
   with a content-hash `scenario_id`. The exact same scenario (not a re-discovered one)
   is used for both the GnuCOBOL baseline and the Java execution, guaranteeing a
   meaningful equivalence comparison.

4. **Watchdog protection** — Every execution is guarded by:
   - Configurable timeout (`execution.timeout_seconds`, default **120 s**)
   - Configurable output-size cap (`execution.max_output_bytes`, default **5 MB**)
   - Full process-tree cleanup on violation
   - Clear error codes: `BASELINE_EXECUTION_TIMEOUT`, `JAVA_EXECUTION_TIMEOUT`,
     `EXECUTION_OUTPUT_LIMIT_EXCEEDED`

5. **Audit artifacts** — Written to `target/execution/<scenario_id>/`:
   - `scenario.json` — what was discovered and used
   - `interactive_input.txt` — exact bytes sent to the program
   - `stdout_baseline.txt` / `stdout_execute.txt`
   - `execution_metadata_baseline.json` / `execution_metadata_execute.json`

### Configuration

Add an `execution` block to `migration_config.json` to override defaults or pin a scenario:

```json
{
  "execution": {
    "timeout_seconds": 120,
    "max_output_bytes": 5242880,
    "interactive_scenario": "test/run_smoke_test.sh"
  }
}
```

### BankCore regression example

> **Note**: BankCore (`BANKMAIN.cob`) is used below purely as a *regression example*
> of a real interactive program. The pipeline has **zero BankCore-specific code**.
> It works because the existing `test/run_smoke_test.sh` in the BankCore repository
> contains a heredoc with the correct menu selections — the generic discovery system
> finds and uses it automatically.

```text
== Stage 3: baseline ==
  interactivity: INTERACTIVE
  scenario discovered: test/run_smoke_test.sh (4 stdin lines, id=a3f2...)
  [GnuCOBOL baseline terminates normally — no infinite loop]

== Stage 7: execute ==
  reusing scenario id=a3f2... (source: test/run_smoke_test.sh)
  [Java execution uses identical input — comparison is valid]
```

### Fail-fast example

When no scenario exists:
```text
INTERACTIVE_INPUT_REQUIRED

The selected COBOL entry point 'MYMENU' requires stdin input,
but no deterministic test scenario was discovered.

Provide:
  - An existing test/smoke script (test/*.sh) with a heredoc or pipe
  - A stdin fixture file (test/*.stdin)
  - An explicit scenario path in migration_config.json:
      {"execution": {"interactive_scenario": "test/my_script.sh"}}
```

---

## Production Verdict Gates (Phase 10)

The pipeline integrates automated gates to enforce strict zero-dependency and mutation-sensitivity requirements:

### 1. Automatic Dependency Gate
- Scans all generated artifacts (`.java`, `.xml`, `.properties`, `.yml`, `.yaml`, `.sh`, `.bat`, `Dockerfile`, `Makefile`) to verify zero legacy runtime references (`libcobj`, `jp.osscons`, etc.).
- Failure to pass blocks the `PRODUCTION_READY` verdict.

### 2. Automatic Negative Equivalence Gate
- Automatically checks mutation sensitivity across 6 distinct mutation strategies during the comparison stage.
- Skipped or failing mutation runs block the `PRODUCTION_READY` verdict.

### 3. Verdict Ladder
Verdicts are strictly evidence-driven:
- `PRODUCTION_READY`: All gates complete and pass with positive evidence.
- `PRODUCTION_CANDIDATE`: Execution and physical equivalence pass, but one or more mandatory validation/negative equivalence gates were skipped or did not run.
- `FAILED`: Compilation or physical/logical output mismatches detected.
- `EQUIVALENCE_UNVERIFIED`: Translation and compilation succeeded, but no baseline files were produced to verify.
- `UNVERIFIED`: No execution evidence collected.
