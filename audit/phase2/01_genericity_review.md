# Phase 2: Genericity & Benchmark-Specific Coupling Review

An audit of the codebase to identify hardcoded, benchmark-specific dependencies:

## 1. Hardcoded Executable Output Name
- **File**: `cobol_migrate.py` (Line 2860 & 2929)
- **Coupling**: The compilation output name is hardcoded to `bin/claims_core.exe` and invoked as `./bin/claims_core.exe`.
- **Generic Design**: The GnuCOBOL compiler must output the binary using the dynamically discovered entrypoint program name (e.g. `bin/{entry}.exe`).

## 2. Interactive Testing Folder Assumptions
- **File**: `execution/scenario_discovery.py` (Line 34 & 61)
- **Coupling**: The search paths for scripts are constrained to hardcoded lists (`test/`, `tests/`, etc.).
- **Generic Design**: Recursively scan all subdirectory structures in the repository root.

## 3. Emulation Class Coupling
- **File**: `cobol_migrate.py` (Line 3013)
- **Coupling**: Executes target Java using hardcoded classpaths `java -cp /target/generated:/target/libcobj.jar {entry}`.
- **Generic Design**: The generation stage must compile target files into standalone modules or dynamically reference runtime libraries according to repository characteristics.
