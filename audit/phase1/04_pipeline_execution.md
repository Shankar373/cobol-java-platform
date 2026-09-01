# Phase 1: Pipeline Stage Orchestration Execution

The 13-stage pipeline executed end-to-end for the benchmark repositories:

## Active Stage Names & Ordering:
0. **ingest** - Computes source file hashes to establish immutability baseline.
1. **discover** - Discovers COBOL program files, entrypoints, and copies.
2. **analyze** - Constructs dependency call graphs and physical-logical file maps.
3. **baseline** - Executes legacy COBOL via GnuCOBOL Docker to capture outputs.
4. **transpile** - Translates COBOL to Java sources using cobj toolchain.
5. **collect** - Locates and verifies generated Java files.
6. **generate** - Packages intermediate Java maven project structure.
7. **execute** - Compiles and runs target Java programs using Docker.
8. **compare** - Structural parity checks on output directories.
12. **package** (mapped to Stage 13) - Compiles final modernized project archive.

*(Note: Stages 9, 10, and 11 are placeholder steps in the core orchestrator).*
