# AUDIT BASELINE BEFORE FIXES: COBOL-to-Java Modernization Pipeline

**Record Date**: August 22, 2026  
**Auditor**: Antigravity (AI Coding Assistant)  
**Baseline Release Code**: `RELEASE_1.0.0` (LOCKED/FROZEN)  

This document captures the baseline results of the audit before applying any fixes. These results will remain immutable for comparison after the fixes are completed.

---

## 1. Test Suite Baseline (Pytest)

- **Total Tests Collected**: 306 items (from 64 files).
- **Execution Mode**: `python -m pytest --ignore=tests/logical_audit_test.py` (due to Docker hang).
- **Execution Results**:
  - **Unit Tests (Parser, Lexer, Basic Control Flow)**: `VERIFIED WORKING` (passed when run individually or in clean environments).
  - **Phase 8/9/10/11 Tests**: `VERIFIED FAILED` (many tests failed during full suite run due to `OSError: [Errno 28] No space left on device` and Docker Desktop unresponsive daemon).
- **Docker-Dependent Tests**: `BLOCKED BY ENVIRONMENT` (crashed or hung due to unresponsive WSL2 VM and Docker Desktop named pipe socket).

---

## 2. Pipeline Execution Baseline

Running the orchestrator `cobol_migrate.py --repo legacy --out target --restart-from 0` yields:
- **Phase 0 (Ingest) - Phase 8 (Compare)**: `VERIFIED WORKING` for target ClaimsCore benchmark when Docker is active.
- **Phase 9 (Refactor)**: `VERIFIED FAILED` on generic repositories (e.g. `INVOICE01` shape) due to hardcoded reference injection.
- **Phase 10 (Validate)**: `PARTIALLY WORKING` (Gate 2 validation is bypassed for non-benchmark entry points, returning `True` (passed) instead of verifying code compilation).

---

## 3. Verified Audit Gaps & Issues (Baseline)

### P0-001: Benchmark Coupling in Spring Scaffolding
- **File**: `cobol_migrate.py`
- **Location**: `stage_refactor` (calls `EnterpriseApplicationGenerator` and benchmark-specific writes).
- **Observation**: Generates entities seeding `Policy` or `Customer` structures even if the repository represents a totally different concept (e.g. Invoices). Causes Maven compilation warnings or failures on generic repositories.
- **Status**: `VERIFIED FAILED`

### P0-002: Validation Gateway Bypass
- **File**: `cobol_migrate.py`
- **Location**: `stage_validate`
- **Observation**: If the entry point name is not `CCMAIN01` or `BCMAIN01`, validation skips execution entirely and returns `True` (passed).
- **Status**: `VERIFIED FAILED`

### P1-001: Adversarial Hardcoding Bypass
- **File**: `cobol_migrate.py`
- **Location**: `clean_benchmark_placeholders()`
- **Observation**: Uses string concatenation at runtime (e.g. `"Claim" + "Exception" + "Repository"`) to construct benchmark names, thereby evading the static scanner check in `tests/test_no_hardcoding.py`.
- **Status**: `VERIFIED FAILED`

### P1-002: Subprocess Execution Hangs
- **File**: `cobol_migrate.py`
- **Location**: `docker_available()` and various `sh()` / `subprocess.run()` calls.
- **Observation**: Subprocess execution commands lack timeouts, causing the execution threads to block indefinitely if the underlying process (e.g. `docker info`) hangs.
- **Status**: `VERIFIED FAILED`

### Native Java Modernization Gap
- **File**: Generated Java files (under `target/modernized/`).
- **Observation**: Mapped Java code depends completely on emulation wrappers (`libcobj.jar` classpath dependency). Control flow uses a switch statement index loop, and variables are stored as `CobolDataStorage` objects instead of native Java types.
- **Status**: `VERIFIED FAILED` (Is emulation, not native modernization).

### Duplicate Code
- **Observation**: The `run_cobol_code` helper function is duplicate-defined in **5 different test files**:
  - `tests/test_phase8_perform_times.py`
  - `tests/test_phase8_next_sentence.py`
  - `tests/test_phase8_file_semantics.py`
  - `tests/test_phase8_control_flow.py`
  - `tests/test_native_paragraph_control.py`
- **Status**: `VERIFIED FAILED`

### UI Security Posture
- **File**: `ui.py`
- **Observation**: Runs on port `8787` without authentication, allowing arbitrary access to workspace directories and command execution endpoints.
- **Status**: `VERIFIED FAILED`

---

## 4. Final Verdict Baseline
- **Modernization Platform Status**: **`FAILED / NOT READY`**
- **Justification**: Universal COBOL-to-Java translation cannot be claimed because the compiler generated code is emulated bytecode, and the Spring Boot refactorer layer is heavily coupled to specific benchmark templates and bypasses validation gates.
