# Phase 2: Architecture Review

This document contains a complete review of the pipeline flow for SystemaOps, analyzing its components and identifying coupling.

## 1. Pipeline Stages Flow
```mermaid
graph TD
    Ingest[Ingest: SHA-256 fingerprinting] --> Discover[Discover: Entry point & copybook search]
    Discover --> Analyze[Analyze: Static call graph parsing]
    Analyze --> Baseline[Baseline: GnuCOBOL Docker golden execution]
    Baseline --> Transpile[Transpile: cobj Docker Java translation]
    Transpile --> Collect[Collect: Java file search & check stubs]
    Collect --> Generate[Generate: Assembly Maven layout]
    Generate --> Execute[Execute: Compile and run target Java]
    Execute --> Compare[Compare: Parity outputs check]
    Compare --> Refactor[Refactor: Placeholder]
    Refactor --> Validate[Validate: Placeholder]
    Validate --> Report[Report: Write pipeline report]
    Report --> Package[Package: Zip modernized artifacts]
```

## 2. In-Depth Component Assessment
- **Ingestion**: Verifies file immutability using SHA-256. Fully generic.
- **Discovery**: Resolves `.cob`/`.cbl` files and entry points. Uses heuristic root detection.
- **Static Analysis & Dependency Graph**: Scans for static CALL dependency nodes. Dynamic calls are marked.
- **Scenario Discovery**: Resolves test shell scripts and stdin fixtures.
- **Baseline Run**: Compiles via GnuCOBOL Docker and runs with watchdogs.
- **Transformation (Transpile)**: Uses cobj Docker image to produce Java code.
- **Java Execution**: Compiles and runs the translated classes.
- **Validator (Compare)**: Structural file comparisons.
- **Report & Package**: Compiles summaries and zips the results.
