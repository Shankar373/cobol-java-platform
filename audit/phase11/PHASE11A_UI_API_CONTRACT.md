# PHASE 11A — SYSTEMAOPS UI API CONTRACT SPECIFICATION
**System:** SystemaOps Enterprise Application Modernization Platform  
**Document Version:** 1.0  
**Effective Date:** 2026-08-22  

---

## 1. Overview
The SystemaOps UI communicates with the backend HTTP API server (`ui.py`) using REST JSON requests and Server-Sent Events (SSE) streaming. All endpoints are hosted locally under the active ThreadingHTTPServer.

---

## 2. API Endpoints Contract

### 2.1. GET `/api/state`
Returns the status, parameters, stages progress, final verdicts, and metadata of all workspaces.

* **Method**: `GET`
* **Query Parameters**: None
* **Success Response (200 OK)**:
  ```json
  {
    "runs": [
      {
        "run_id": "run-name-uuid",
        "status": "ready | running | done | error | interrupted",
        "source": "zip | git",
        "name": "Human Readable Name",
        "last_stage": 4,
        "error": null,
        "verdict": "PRODUCTION_READY | PRODUCTION_CANDIDATE | FAILED | VERIFIED_WITH_LIMITATIONS | UNVERIFIED | PARTIAL | EQUIVALENCE_UNVERIFIED | BASELINE_UNPRODUCIBLE",
        "log": ["log line 1", "log line 2"],
        "stages": [
          {
            "index": 0,
            "label": "Ingest",
            "desc": "Upload repository...",
            "status": "done | running | error | pending",
            "at": "2026-08-22T21:30:00Z",
            "detail": "Ingestion successful",
            "started_at": "2026-08-22T21:30:00Z",
            "completed_at": "2026-08-22T21:31:00Z",
            "duration_seconds": 60.0,
            "warnings": [],
            "errors": []
          }
        ],
        "compare_data": {},
        "package_size": 125432,
        "execution_scenario": {},
        "legacy": {},
        "execute": {},
        "manifest_exists": true,
        "data": {}
      }
    ],
    "active": false,
    "git_available": true
  }
  ```

---

### 2.2. POST `/api/ingest`
Ingests legacy COBOL assets from a Base64-encoded ZIP upload or clones from a Git repository URL.

* **Method**: `POST`
* **Payload (JSON - ZIP upload)**:
  ```json
  {
    "source": "zip",
    "name": "filename.zip",
    "data": "Base64EncodedStringData..."
  }
  ```
* **Payload (JSON - Git clone)**:
  ```json
  {
    "source": "git",
    "name": "git-run",
    "url": "https://github.com/org/repo.git",
    "branch": "main"
  }
  ```
* **Success Response (200 OK)**:
  ```json
  {
    "ok": true,
    "run_id": "run-name-uuid"
  }
  ```
* **Error Response (400 Bad Request / 500 Server Error)**:
  ```json
  {
    "ok": false,
    "error": "Detailed reason why ingestion failed"
  }
  ```

---

### 2.3. POST `/api/run`
Triggers or resumes pipeline execution for a specific workspace.

* **Method**: `POST`
* **Payload (JSON)**:
  ```json
  {
    "run_id": "run-name-uuid",
    "restart_from": 0
  }
  ```
* **Success Response (200 OK)**:
  ```json
  {
    "ok": true,
    "error": null
  }
  ```
* **Error Response (400 Bad Request)**:
  ```json
  {
    "ok": false,
    "error": "another run is in progress | unknown run"
  }
  ```

---

### 2.4. POST `/api/reset`
Resets a workspace, deleting target outputs and cleaning state metadata.

* **Method**: `POST`
* **Payload (JSON)**:
  ```json
  {
    "run_id": "run-name-uuid"
  }
  ```
* **Success Response (200 OK)**:
  ```json
  {
    "ok": true
  }
  ```

---

### 2.5. GET `/api/log-stream`
Initiates a Server-Sent Events (SSE) connection to stream log output in real-time.

* **Method**: `GET`
* **Query Parameters**:
  * `run_id`: The target workspace run identifier.
* **Headers**:
  * `Content-Type`: `text/event-stream`
  * `Cache-Control`: `no-cache`
  * `Connection`: `keep-alive`
* **Payload**: Streams text messages containing log statements as JSON strings.

---

### 2.6. GET `/api/artifacts`
Scans and lists files under reports, generated, execution, and modernized subfolders in the workspace.

* **Method**: `GET`
* **Query Parameters**:
  * `run_id`: The target workspace run identifier.
* **Success Response (200 OK)**:
  ```json
  {
    "ok": true,
    "artifacts": [
      {
        "name": "migration-report.md",
        "path": "migration-report.md",
        "type": "report"
      },
      {
        "name": "App.java",
        "path": "modernized/App.java",
        "type": "modernized"
      }
    ]
  }
  ```

---

### 2.7. GET `/api/artifact-content`
Securely retrieves the file contents of an allowed artifact path inside the target folder.

* **Method**: `GET`
* **Query Parameters**:
  * `run_id`: The target workspace run identifier.
  * `name`: Relative file path within the run target output directory.
* **Success Response (200 OK)**:
  ```json
  {
    "ok": true,
    "content": "File string content here..."
  }
  ```
* **Error Response (400 Bad Request / 404 Not Found)**:
  ```json
  {
    "ok": false,
    "error": "Artifact not available for this run."
  }
  ```

---

### 2.8. GET `/api/modernized-file`
Securely retrieves Java source code artifacts. Binds directly to target modernized folder.

* **Method**: `GET`
* **Query Parameters**:
  * `run_id`: The target workspace run identifier.
  * `path`: Relative path inside `/modernized/` folder.
* **Success Response (200 OK)**: Same structure as `/api/artifact-content`.

---

### 2.9. GET `/report`
Returns the migration verification markdown report.

* **Method**: `GET`
* **Query Parameters**:
  * `run_id`: Target run identifier.
* **Success Response (200 OK)**: Serves Markdown file directly as `text/markdown; charset=utf-8`.

---

### 2.10. GET `/package`
Downloads the deployed modernized ZIP package.

* **Method**: `GET`
* **Query Parameters**:
  * `run_id`: Target run identifier.
* **Success Response (200 OK)**: Serves ZIP file directly as `application/zip`.

---

## 3. Path Security Restrictions
1. **No relative path traversal (`../`)**: Relative segment patterns are rejected.
2. **Absolute paths rejected**: Any path starting with `/` or drive letters is rejected.
3. **Workspace Isolation constraint**: All resolved file paths are checked using `os.path.realpath` to confirm they start with the workspace root directories. Escaping base targets throws a `400 Bad Request` containing the standard message: `"Artifact not available for this run."`
