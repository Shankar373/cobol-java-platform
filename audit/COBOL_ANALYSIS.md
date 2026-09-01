# Phase 8: COBOL Discovery Phase Analysis

The static call-graph discovery process is parsed in `cobol_migrate.py`:

## Key Capabilities:
- **Heuristic Entrypoint Detection**: `pick_entry()` analyzes program calls to find root nodes (programs with zero callers). If multiple roots are found, it triggers a warning.
- **Copybook Search Path**: Recursively scans `-I` search directories to match references.
- **Dynamic CALL Limitation**: `extract_call_deps()` (Line 143) searches for variables in `CALL` statements. Unresolved dynamic calls are logged as `DYNAMIC_CALL_REQUIRES_REVIEW`, forcing the pipeline to fall back to `UNKNOWN` interactivity.
