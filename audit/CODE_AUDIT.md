# Phase 2: Line-by-Line Code Audit Report

This document records the exact control flow, resource usage, and security checks.

## 1. Watchdog Process Tree Cleanup
- **File**: `execution/scenario_runner.py` (Lines 166-190, `_kill_tree()`)
- **Findings**: Terminating processes inside containers requires signaling PGID groups. On Linux, `os.killpg(os.getpgid(proc.pid), signal.SIGTERM)` is called, falling back to standard `proc.terminate()` on Windows. This handles process termination cleanly across both systems.

## 2. Command Injection Vulnerabilities
- **File**: `cobol_migrate.py` (Line 595, `docker_run()`)
- **Findings**: The orchestrator wraps docker execution by calling shell wrappers:
  ```python
  subprocess.run(["docker", "run", "--rm", ..., image, "sh", "-c", cmd])
  ```
  Since `cmd` is interpolating path variables without strict sanitization, this introduces command injection vulnerabilities if directory structures contain command separators.

## 3. Broad Exception Catches
- **File**: `ui.py` (Lines 76-130, `restore_workspaces()`)
- **Findings**: Catches broad exceptions when reading `state.json` which could mask corrupt file structures and trigger silent crashes.
