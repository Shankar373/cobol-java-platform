# 04. Security Verification Report

This report documents the security audit verification of the SystemaOps interactive UI dashboard.

---

## 1. UI Server Configuration

- **Bind Address**: `127.0.0.1` (localhost)
- **Port**: `8787`
- **Exposed Routes**:
  - `/api/runs`, `/api/run/<id>`, `/api/run-log`
  - `/api/file` (exposes workspace source file contents, generated Java classes, target reports, and metadata configurations)
- **Authentication**: `NONE`. Anyone who has access to the local port can invoke and view all data.
- **Authorization**: `NONE`. Exposes full command control.

---

## 2. Git Branch Argument Option Injection

Inside [`ui.py`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/ui.py):
- **Implementation**:
  ```python
  branch = (payload.get("branch") or "").strip()
  if branch:
      cmd += ["--branch", branch]
  cmd += [url, repo]
  r = subprocess.run(cmd, capture_output=True, text=True)
  ```
- **Option Injection Analysis**: If a user submits a payload containing option flags (like `-u` or `--help`), the branch payload is appended directly into `cmd`. Because `cmd` is parsed as a list to `subprocess.run` (without `shell=True`), arbitrary shell injection is blocked. However, git command options can still be injected, leading to option hijacking.
- **Remedy**: Sanitize input, validating that the branch name matches a strict alphanumeric regex pattern before appending.
