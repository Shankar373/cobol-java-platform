# PHASE 11A — SYSTEMAOPS UI FUNCTIONAL INTEGRATION GAP ANALYSIS
**System:** SystemaOps Enterprise Application Modernization Platform  
**Audit Date:** 2026-08-22  
**Auditor:** Antigravity (Inspection-Only Audit)  

---

## 1. Reference UI Observations
The reference repository (`Shankar373/modernization-platform`) provides a modern React 19 + TypeScript + Vite frontend that maps dynamic application migrations asynchronously via FastAPI/Uvicorn, PostgreSQL, and Celery workers.
* **Layout Design**: Utilizes an enterprise-grade responsive layout with a side navigation panel and structured main dashboards.
* **Component Hierarchies**: Features clear separations between active repositories, progress pipelines, final verdicts, structured verification evidence grids, and a multi-folder artifact inspector.
* **Visual Theme**: Uses an enterprise color palette (Primary Teal `#1d7f8a`, Warning Gold `#f2bd22`) with clean cards, minimal decorations, and high-readability fonts.

---

## 2. Current UI Capabilities
The current SystemaOps dashboard uses a single-page HTML layout (`ui.html`) served via Python's standard library `BaseHTTPRequestHandler` (`ui.py`).
* **Ingestion**: Supports uploading project ZIP files or cloning Git repositories.
* **Pipeline Tracking**: Displays the progress of 13 backend stages via a sidebar and a vertical stepper.
* **Logs & Files**: Streams execution logs using Server-Sent Events (SSE) and displays output files for physical/logical parity.
* **Modernized Source Explorer**: Lists generated files and serves code previews for files in the `/modernized/` folder.

---

## 3. Current Backend API Capabilities
The `ui.py` backend handles pipeline execution asynchronously via Python standard threading.
* **`/api/state`**: Reads and returns lists of workspaces and their `state.json` execution metrics.
* **`/api/log-stream`**: Streams live stdout logs during pipeline execution.
* **`/api/artifacts`**: Lists baseline/execute artifacts for the current interactive scenario.
* **`/api/artifact-content`**: Retrieves files from the baseline execution directory.
* **`/api/modernized` & `/api/modernized-file`**: Retrieves lists and contents of the Spring Boot refactored project.
* **`/api/deps`**: Exposes discovered program dependencies, copybook coverage, and call graphs.
* **`/api/report-json`**: Exposes JSON report details (provenance manifest, execution manifest).
* **`/report` & `/package`**: Returns markdown reports and downloads final modernized packages.

---

## 4. UI ➔ API Mapping

Every frontend action maps directly to one or more backend API endpoints:
* **Ingest Project**: `POST /api/ingest`
* **Trigger/Resume Pipeline**: `POST /api/run`
* **Workspace Reset**: `POST /api/reset`
* **Dashboard State Poll**: `GET /api/state`
* **Live Log Stream**: `GET /api/log-stream`
* **Dependency Tree / Call Graph**: `GET /api/deps`
* **Modernized Files Explorer**: `GET /api/modernized`
* **Source Preview**: `GET /api/modernized-file`
* **Interactive Scenario Artifacts**: `GET /api/artifacts` and `GET /api/artifact-content`
* **Manifest View**: `GET /api/report-json`
* **Report View**: `GET /report`
* **Modernized Zip Package Download**: `GET /package`

---

## 5. API ➔ Pipeline-State Mapping

All dynamic values exposed by the APIs are derived strictly from evidence stored in `state.json` and the target output directory:
* **Run Meta & Status**: `state.json -> stages -> {stage} -> status`
* **Timeline Metrics**: `state.json -> stages -> {stage} -> started_at / completed_at / duration_seconds`
* **Warnings & Errors**: `state.json -> stages -> {stage} -> warnings / errors`
* **Discovered Source Metrics**: `state.json -> data -> discover`
* **Architecture Mappings**: `state.json -> data -> analyze`
* **Equivalence File Lists**: `state.json -> data -> compare`
* **Spring Boot Validation (Gate 2)**: `state.json -> data -> validate`
* **Dependency Audit**: `state.json -> data -> collect -> dependency_audit`
* **Negative Equivalence**: `state.json -> data -> neg_equiv`

---

## 6. Pipeline-Stage Mapping
The authoritative SystemaOps backend model defines **13 distinct stages** in `cobol_migrate.py` (lines 32-46):

```text
0. ingest       - Ingest & Immutability Checkpoint
1. discover     - Tech & Source Inventory Discovery
2. analyze      - Data Model & Call Graph Analysis
3. baseline     - Golden-Fixture Legacy Execution
4. transpile    - Java AST Transpilation (cobj)
5. collect      - Stub Detection & Dependency Audit
6. generate     - Preservation & Classpath Generation
7. execute      - Modernized JRE Execution
8. compare      - Gate 1 Physical/Logical Parity Comparison
9. refactor     - Native Spring Boot Scaffolding
10. validate    - Gate 2 Enterprise Validation
11. report      - Verdict Ladder & Migration Report
12. package     - Package & Artifact Archive
```

**UI Layout Mapping**: The UI must display status information for all 13 stages. To match the reference visual style, stages may be grouped into parent blocks (e.g., *Ingest*, *Analyze*, *Transpile*, *Execute*, *Compare*, *Refactor*, *Validate*, *Report*, *Package*) but the underlying progress tracking must remain 13-stage accurate.

---

## 7. Evidence-Card Mapping
The UI must present **7 distinct Evidence Cards** mapped to backend data:

1. **Compilation** (Maven Compilation Validation):
   - *Source*: `state.json -> data -> generate` (compile status) or `refactor` stage status.
   - *Logic*: Check for a successful Maven clean compile inside `target/modernized`.
2. **Execution** (JRE Batch Run):
   - *Source*: `state.json -> data -> execute` or `execute` stage status.
   - *Logic*: Capture status code and console output logs.
3. **Equivalence** (Gate 1 Parity):
   - *Source*: `state.json -> data -> compare` (status and rows).
   - *Logic*: Ensure physical files and SQLite database tables match.
4. **Dependency Audit** (Forbidden Packages Scan):
   - *Source*: `state.json -> data -> collect -> dependency_audit` (executed and status).
   - *Logic*: Verify zero legacy references exist in the final codebase.
5. **Negative Equivalence** (Mutation Testing):
   - *Source*: `state.json -> data -> neg_equiv` (executed and status).
   - *Logic*: Confirm mutations were successfully caught.
6. **Traceability** (Gate 2 Enterprise Validation):
   - *Source*: `state.json -> data -> validate` (gate2_passed status).
   - *Logic*: Confirm Spring Boot REST H2 endpoints align with legacy calculations.
7. **Diagnostics** (Warning Inventory):
   - *Source*: `state.json -> data -> analyze` (diagnostics status).
   - *Logic*: Verify count of unsupported constructs and compiler stubs.

---

## 8. Artifact Mapping
The UI's **Unified Artifact Explorer** will allow previewing and downloading artifacts from three target locations. Access is mapped via `/api/artifact-content` and `/api/modernized-file`:

* **`/target/generated/`**:
  - `transpilation-provenance.json` (provenance manifest)
  - `native_translation_diagnostics.json` (diagnostics list)
  - `hardcoded-value-scan.json` (metadata scan)
* **`/target/reports/`**:
  - `migration-report.json`
  - `migration-report.md`
  - `business-rule-traceability.json`
  - `business-rule-traceability.md`
  - `pipeline_execution_manifest.json` (authoritative execution manifest)
* **`/modernized/`**:
  - Spring Boot code artifacts (`.java`, `.properties`, `.yml`)
  - Build descriptors (`pom.xml`)

---

## 9. Report Mapping
The dashboard will feature a **Report Center** linking to:
* **Migration Report**: Maps to `reports/migration-report.md` (markdown viewer).
* **Traceability Report**: Maps to `reports/business-rule-traceability.md`.
* **Provenance Manifest**: Maps to `transpilation-provenance.json`.
* **Diagnostics Report**: Maps to `native_translation_diagnostics.json`.

---

## 10. Verdict Mapping
The UI's **Verdict Panel** must display the exact string computed by `Pipeline._compute_verdict()` in `cobol_migrate.py` (lines 5229-5385). The 11 tiers must be represented with strict rules (no fabricated `PASS` values):

* `UNVERIFIED`: No stages completed.
* `PARTIAL`: Incomplete translation (`n_ok < n_total`).
* `EQUIVALENCE_UNVERIFIED`: Translation completed, but no baseline outputs generated.
* `FAILED`: Physical/logical mismatches or validation errors detected.
* `BASELINE_UNPRODUCIBLE`: Legacy program failed to execute.
* `VERIFIED_WITH_LIMITATIONS`: Core gates pass, but unresolved dynamic fields remain.
* `VERIFIED`: All core evidence gates pass (legacy path).
* `NATIVE_JAVA_VERIFIED`: Dependency audit passes.
* `NATIVE_SPRING_UNIFIED`: Refactored enterprise Spring project generated.
* `PRODUCTION_CANDIDATE`: Execution, equivalence, and traceability pass.
* `PRODUCTION_READY`: All gates pass (including negative equivalence and dependency audit).

---

## 11. Missing Functionality
* **Repository Summary Card**: Visual overview card at the top of the workspace.
* **Evidence Cards Grid**: The grid displaying compilation, execution, equivalence, dependency, negative equivalence, traceability, and diagnostics.
* **Unified Artifact Explorer**: Dynamic file viewer for `/target/generated/`, `/target/reports/`, and `/modernized/` files.
* **Equivalence UI Section**: Detailed panel listing topology, exit codes, and mutation tests.
* **Report Center**: Dedicated dashboard area linking to markdown and JSON reports.
* **Stop Button**: Button mapping to cancellation, showing the unsupported warning if clicked.
* **Manifest View/Download buttons**: Clickable view/download controls for `pipeline_execution_manifest.json`.

---

## 12. Broken or Disconnected Functionality
* **File View Restraints**: The current UI file-preview is split into two disjointed components: `/api/artifact-content` (for legacy run outputs) and `/api/modernized-file` (for Java files). They must be unified behind a secure explorer.
* **Reset Flow**: Reset workspace removes files on disk but does not clear active logs from the frontend instantly.

---

## 13. Fake/Static Functionality
* **None**: The current SystemaOps application uses real state and pipeline data. We must ensure no simulated timers or hardcoded successes are introduced.

---

## 14. Security Risks
* **Path Traversal Vulnerability**: Endpoints that retrieve file content must be strictly validated. Users should not be able to bypass workspace constraints via relative parameters (`../`).
* **Shell Injection**: Ensure no execution of user input runs under `shell=True` or `os.system()`.

---

## 15. Repository-Isolation Risks
* **Log Bleeding**: If multiple workspaces run sequentially, logs of Run A must not bleed into Run B. 
* **State Pollution**: Workspace selection must clean up active variables and trigger state re-initialization.

---

## 16. UI/UX Gaps
* **Sidebar Layout**: Space and alignment issues in the runs list.
* **Stepper Styling**: Normalizing stage statuses to uppercase.
* **Log Viewer**: Missing auto-scroll toggle lock and color-highlighting of level-specific messages.

---

## 17. Priorities for Implementation

### P0 (Critical - Security & Parity Core)
- Enforce strict path traversal checks in `/api/artifact-content` and `/api/modernized-file`.
- Ensure clean state initialization on switching/resetting workspaces.
- Connect the Verdict Panel directly to the backend `_compute_verdict()` without overrides.

### P1 (High - Core Functional Views)
- Implement the **7 Evidence Cards** grid.
- Build the **Unified Artifact Explorer** tree layout.
- Build the **Equivalence UI** showing topology and mutation statistics.

### P2 (Medium - Dashboard Control & Reports)
- Implement the **Report Center** section.
- Add the **Stop/Cancel Button** (displaying the backend notice).
- Add `[View Manifest]` and `[Download Manifest]` buttons.

### P3 (Low - Polishing UX)
- Refine Log Viewer with auto-scroll toggles and error/warning styling.
- Align visual styles to the SystemaOps primary theme.

---

## 18. Implementation Status
All identified gaps have been completely resolved and implemented during Phase 11A Step 2:
- **Path Traversal Security**: Fully resolved using `secure_resolve_path` with `realpath` checks. (Status: **RESOLVED**)
- **State Isolation**: EventSource termination and variable clearance prevent state or log bleeding. (Status: **RESOLVED**)
- **Verdict Mapping**: Direct connection to `Pipeline._compute_verdict()` verified. (Status: **RESOLVED**)
- **7 Evidence Cards Grid**: Dynamically renders core validation check statuses from backend. (Status: **RESOLVED**)
- **Unified Artifact Explorer**: Provides dynamic folder tree browsing for reports, generated files, and modernized Spring Boot sources. (Status: **RESOLVED**)
- **Report Center & Manifest**: Download and View actions linked to manifest metrics. (Status: **RESOLVED**)
- **Log Viewer**: Implemented scroll locking, clearing, and warning/error text coloring. (Status: **RESOLVED**)
- **Stop Notice**: Gracefully handles threading limits. (Status: **RESOLVED**)
- **Automated Verification**: Integrated pytest assertions executed and passed. (Status: **VERIFIED**)

