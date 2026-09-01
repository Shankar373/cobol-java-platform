# Security Architecture & Hardening

This document explains the security controls, validation rules, and threat defenses built into the platform.

---

## 1. Web Dashboard Hardening

1.  **Access Control**:
    *   The web dashboard started by `ui.py` can be secured by setting the `UI_AUTH_CREDENTIALS` environment variable (e.g. `admin:secretpass`). If configured, all requests must contain a valid HTTP Basic Auth header.
2.  **Path Traversal Prevention**:
    *   The `/api/artifacts` and `/api/artifact-content` endpoints resolve files via `secure_resolve_path(base_dir, relative_path)`. This function resolves paths using `os.path.realpath` and verifies that the target remains within the base directory, preventing `../` traversal attacks.
3.  **Payload Size Limits**:
    *   All POST payloads (such as ZIP uploads) are limited to a maximum of 30MB, protecting the server against memory exhaustion and Denial of Service (DoS) attacks.

---

## 2. Shell Injection Defense

*   **Subprocess Invocations**:
    *   Command executions in the pipeline (`sh()` wrapper) use Popen with list arguments (`cmd = [GIT, "clone", ...]`) instead of shell strings (`shell=True`), preventing command concatenation injections.
*   **Git Parameter Validation**:
    *   Branch parameters are matched against a strict alphanumeric pattern (`^[a-zA-Z0-9/._\-]+$`) before appending them to the Git command line arguments.
