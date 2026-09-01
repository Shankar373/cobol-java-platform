# Changes Made Compared With the Uploaded Repository

This document records only the changes made in this session on top of the uploaded ZIP.
It does **not** claim that the project is universally production-ready.

## Source/runtime changes

### `modernize/native_pipeline.py`
- Added explicit `baseline_verified` run state.
- Removed automatic reuse of an existing `baseline/legacy/stdout.txt` as evidence for a new run.
- A non-zero COBOL baseline execution now stops native verification instead of allowing a failed baseline to become equivalence evidence.
- Hardened PostgreSQL fixture seeding:
  - Detect table existence with PostgreSQL's `to_regclass()` boolean query instead of parsing human-readable `psql` output.
  - Use `ON_ERROR_STOP=1` for seed/truncate commands.
  - Validate SQL-derived table identifiers before constructing TRUNCATE statements.
  - Propagate seed/read/timeout errors instead of silently swallowing them.
- Reworked the native equivalence gate to compare the **union** of baseline and native output files, so Java-only files cannot be missed.
- Removed broad leading-zero/sign normalization from stdout comparison. Only line-ending and trailing-horizontal-whitespace differences are normalized.
- Empty observable output now produces `UNVERIFIED` rather than a synthetic pass.

### `cobol_migrate.py`
- `docker_available()` now handles an unavailable Docker CLI as an explicit unavailable environment instead of raising `FileNotFoundError` during caller execution.
- Certification report construction now uses an explicit equivalence-gate status after actual compare evidence has been established, rather than scattering unconditional `"PASS"` literals through the later certification tiers.

### `modernize/jcl_generator.py`
- Parenthesized JCL return-code conditions are normalized safely.
- Compound step names are supported in the supported pattern.
- Unsupported conditions now fail closed with a `ValueError` instead of silently compiling to `true`.

### `modernize/java_helpers/src/main/java/com/systema/modernized/MockSqlService.java`
- Initialization is a no-op when no embedded mock resources are present and a real database is not being used.
- Existing embedded mock behavior is retained when mock resources are actually packaged.

### `scratch/test_sign_file.py`
- Docker test execution is now inside `main()` and guarded by `if __name__ == "__main__"` so importing the scratch file cannot execute Docker during pytest collection.
- Added a finite timeout to the scratch Docker invocation.

## Tests added

### `tests/test_strict_equivalence_guards.py`
New regression tests for:
- stale/current baseline evidence handling;
- symmetric baseline/native file-set comparison;
- protection against stripping business-significant leading zeroes.

### `tests/test_jcl_generator_fail_closed.py`
New regression tests for:
- parenthesized JCL return-code expressions;
- fail-closed behavior for unsupported JCL conditions.

## Verification performed in this session

- Python syntax compilation of changed Python modules: **PASS**
- New strict-equivalence + JCL tests: **5 passed**
- Additional verdict/equivalence tests: **22 passed**
- Repository pytest collection: **653 tests collected**
- Full end-to-end project suite: **NOT PROVEN in this environment** because Docker and Maven are not installed/available in the audit runtime.

## Important limitation

The fixes above improve correctness and fail-closed behavior, but they do not turn an arbitrary IBM Enterprise COBOL + DB2 + CICS + VSAM + JCL application into a universally proven native Spring application. Full mainframe semantic coverage still requires additional implementation and real differential verification.
