# Development Environment & Execution Guide

This document describes the environment specifications, Docker-first execution patterns, and testing configuration for the COBOL-to-Java transformation project.

---

## 1. Required Tools & Image Specifications

### Docker Images (Docker-first strategy)
For Milestone A, only two Docker images are required:
*   **GnuCOBOL Execution**: `hurriedreformist/gnucobol:3.1-builder` (or by digest: `hurriedreformist/gnucobol:3.1-builder@sha256:e06b8478988cf8628045d4ea54bf69d6718d799015c6329486c75955627ef671`)
*   **Java Parity Execution**: `eclipse-temurin:17-jdk-noble` (or by digest: `eclipse-temurin:17-jdk-noble@sha256:61a94244559f518e32c86d8b5eb54a2a4663c0a525d804868e1a1215bf321fb4`)

> [!NOTE]
> Do not use `opensourcecobol/opensourcecobol4j:2.0.0` for Milestones A or B. Transpilation is handled exclusively by our Python-based lexer/parser/semantic_ir/native_generator engine.

### Local Host Fallbacks
*   **Java Development Kit (JDK)**: Optional host Java (LTS version 17 or higher) can be used only when `PARITY_JAVA_RUNTIME=local` is configured.
*   **GnuCOBOL (`cobc`)**: Optional local override (requires `PARITY_RUNTIME=local`).

---

## 2. Configuration Parameters

The parity validation harness uses the following environment variables to configure run behaviors:

*   `PARITY_RUNTIME`: Set to `docker` (default canonical runtime for COBOL baseline) or `local` (local developer override fallback).
*   `PARITY_JAVA_RUNTIME`: Set to `docker` (default canonical runtime for transpiled Java execution) or `local` (local developer override fallback).
*   `PARITY_GNUCOBOL_IMAGE`: Pinned GnuCOBOL container image (default: `hurriedreformist/gnucobol:3.1-builder`).
*   `PARITY_JDK_IMAGE`: Pinned Java SDK container image (default: `eclipse-temurin:17-jdk-noble`).
*   `PARITY_ALLOW_SKIP`: Set to `false` (default for CI/release mode; skips are blocked). Set to `true` only for local development scenarios when Docker is unavailable.
*   `PARITY_KEEP_ARTIFACTS_ON_FAILURE`: Set to `true` (default) to persist temporary files when comparisons mismatch.
*   `PARITY_ARTIFACT_DIR`: Path to write diagnostics output on mismatch (default: `artifacts/parity-failures`).

---

## 3. How to Run Parity & Differential Tests

Run focused parity tests using pytest:
```powershell
# Run all initial parity harness tests
python -m pytest tests/test_parity_fixtures.py

# Run standard pipeline unit checks
python -m pytest tests/test_native_type_mapping.py
```

To run heavyweight database or real DB2 integration tests, use opt-in markers:
```powershell
# Opt into live PostgreSQL database integration tests
python -m pytest -m db_integration

# Opt into real DB2 database query tests
python -m pytest -m real_db2
```

---

## 4. Docker Disk Space & Storage Hygiene

### Inspect Docker Disk Space Usage
Check system resource utilization regularly:
```powershell
docker system df
```

### Temporary Artifact Cleanup
All temporary runs generate files in isolated system folders. To clean up stale failures and free storage:
```powershell
# Remove all failure logs
Remove-Item -Recurse -Force artifacts/parity-failures/*
```
To prune stopped containers and unused caching structures:
```powershell
docker container prune
docker builder prune
```

> [!CAUTION]
> **Strict Rule**: Do not run `docker system prune -a --volumes` under any circumstances without explicit approval from the lead architect. Doing so will clean up cached compiler environments and database seed volumes.

---

## 5. Storage Impact Assessment

*   **Docker Images**: Total size is approximately `9.647 GB`.
*   **Build Cache**: Approximately `2.577 GB`.
*   **Cumulative Disk Usage**: Total `~12.224 GB` before additional test run artifacts.
*   **Compilation Workspaces**: Ephemeral storage capped under 50 MB per run, reclaimed automatically on test completions.
