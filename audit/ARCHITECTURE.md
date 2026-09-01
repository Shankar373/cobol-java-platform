# Phase 5: Reconstructed Pipeline Architecture

This document describes the flow and component interactions of the SystemaOps pipeline.

## 1. High-Level Pipeline Workflow
```mermaid
graph TD
    Ingest[0. Ingest: hashing/immutability] --> Discover[1. Discover: inventory/entrypoint]
    Discover --> Analyze[2. Analyze: static call graph]
    Analyze --> Baseline[3. Baseline: GnuCOBOL Docker golden run]
    Baseline --> Transpile[4. Transpile: cobj Docker Java source gen]
    Transpile --> Collect[5. Collect: gather sources/check stubs]
    Collect --> Generate[6. Generate: assemble target jar structure]
    Generate --> Execute[7. Execute: compile and execute Java]
    Execute --> Compare[8. Compare: Gate 1 physical/logical output parity]
    Compare --> Refactor[9. Refactor: Spring Boot/Batch scaffolding]
    Refactor --> Validate[10. Validate: compile refactored/Gate 2 comparison]
    Validate --> Report[11. Report: write migration report]
    Report --> Package[12. Package: create zip package]
```

## 2. Interactive Execution Sequence
```mermaid
sequenceDiagram
    participant Web as Browser Dashboard
    participant Backend as ui.py / cobol_migrate.py
    participant Baseline as GnuCOBOL Docker
    participant Exec as Java target Docker

    Web->>Backend: Post run_id and start stage
    Backend->>Backend: Check Interactivity (bare ACCEPT)
    Backend->>Backend: Extract inputs from test/run_smoke_test.sh
    Backend->>Baseline: Execute legacy binary with inputs
    Baseline-->>Backend: Snapshot data/out and stdout
    Backend->>Exec: Run Java entry class with identical inputs
    Exec-->>Backend: Snapshot data/out and stdout
    Backend->>Backend: Logical Indexed Parity Check (SQLite comparisons)
    Backend-->>Web: Event log-stream update (SSE)
```
