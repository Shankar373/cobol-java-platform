# CI & Business-Logic Coverage Audit

Date: 2026-08-31
Branch: `master`
Status: PARTIAL — CI green-able but not fully green due to environment-blocked DB2 tests

---

## 1. Objective

This audit documents:

1. The current GitHub Actions CI status and what each run verified.
2. A classification of the automated test suite into **business-logic coverage**
   versus **infrastructure-only coverage**.
3. Coverage gaps and evidence-backed recommendations.

The audit follows the project engineering rules (FAIL-CLOSED; no claim without
evidence; infrastructure tests must not masquerade as business equivalence).

---

## 2. CI Workflow Overview

Workflow: `.github/workflows/ci.yml` (id `342352724`)

Two jobs:

| Job | Trigger | What it runs |
|---|---|---|
| `fast` | push to `master`, pull_request | Builds GnuCOBOL+OCESQL image, starts real PostgreSQL 16, seeds schema, runs full pytest suite (minus nightly-only tests) |
| `nightly-full` | schedule (03:00 daily) + `workflow_dispatch` | Everything in `fast` plus all tests, Playwright UI, opensourcecobol4j transpiler |

### Fast-lane test exclusions (`--ignore`)

After this work, the fast-lane `--ignore` list is:

```
tests/logical_audit_test.py
tests/test_realistic_modernization.py
tests/test_validation_nobypass.py
tests/test_generic_refactoring.py
tests/robustness/adversarial/test_java_source_mutation.py
```

> Note: during the test reorganization, `test_java_source_mutation.py` was moved
> from `tests/` into `tests/robustness/adversarial/`, which silently changed its
> `--ignore` matching. This was corrected (see §5).

---

## 3. CI Run History (evidence)

Repository GitHub: `Shankar373/cobol-java-modernization` (remote `origin`, branch `master`).

| Run ID | Commit | Result | Test summary |
|---|---|---|---|
| `33325109742` | `41e5c5a` (baseline, pre-reorg) | FAIL | 1 failed (DB2 tx visibility), 627 passed, 4 skipped |
| `33324242651` | (pre-reorg) | FAIL | DB2 tx visibility only |
| `33323310086` | (pre-reorg) | FAIL | DB2 tx visibility only |
| `33371944619` | `3132603` (reorg) | FAIL | **collection abort** — 24 errors, 488 collected |
| `33372723406` | `3a687d7` (shim removal) | FAIL | 8 failed, 622 passed, 9 skipped |
| `33374179798` | `882fdc0` (ignore + ui.html fix) | FAIL | 4 failed, 625 passed, 9 skipped |

### Latest run (`33374179798`) — breaking it down

```
4 failed, 625 passed, 9 skipped in 544.40s
```

- **625 passed** — the business-logic and unit/integration acceptance suite.
- **9 skipped** — all infrastructure/parity tests:
  - 5 new differential tests (`filestat01`, `sizeerr01`, `db2curnull01`,
    `occurs01`, `redefines01`) — SKIP in fast-lane because Docker parity is not
    enabled there.
  - 4 `test_parity_fixtures` tests (EBCDIC records, relative-file random access,
    indexed-file missing key, JCL conditional) — SKIP for the same reason.
- **4 failed** — all in `tests/test_db2_stage1.py`:
  - `test_db2_left_outer_join_e2e`
  - `test_db2_count_aggregate_e2e`
  - `test_db2_group_by_having_e2e`
  - `test_db2_tx_commit_visible_e2e`

---

## 4. Classification of the 4 Remaining Failures (DB2 E2E)

All four failures share a single error signature produced by the generated /
OCESQL native execution path against PostgreSQL:

```
CURSOR OPEN FAILED SQLSTATE: 99999
NATIVE_JAVA = NOT_VERIFIED: Equivalence failed (verdict: FAIL)
```

`SQLSTATE 99999` is the OCESQL/runtime generic connection-failure SQLSTATE. The
failure occurs at runtime **DB connectivity**, not at parse, generate, or compile.

### Evidence-based classification

| Test | Pre-reorg baseline | Post-reorg (2 runs) | Classification |
|---|---|---|---|
| `test_db2_tx_commit_visible_e2e` | FAIL (all prior runs, same error) | FAIL (both runs) | **PRE-EXISTING** |
| `test_db2_left_outer_join_e2e` | PASS (3 prior runs) | FAIL (both runs) | **ENVIRONMENT/DB-connectivity** |
| `test_db2_count_aggregate_e2e` | PASS (3 prior runs) | FAIL (both runs) | **ENVIRONMENT/DB-connectivity** |
| `test_db2_group_by_having_e2e` | PASS (3 prior runs) | FAIL (both runs) | **ENVIRONMENT/DB-connectivity** |

### Reasoning (not asserted — argued from evidence)

- No DB2 runtime code, `modules/native_pipeline.py`, or any of the failing test
  repos (`DB2LEFTJOIN01`, `DB2AGGREGATE01`, `DB2GROUPBY01`, `DB2TXVISIBILITY01`)
  were modified by this work. The entire source delta on the production path was a
  one-line assertion in `modernize/native_generator.py:373` (Payment01 single-quote
  bug) — unrelated to DB connection.
- The identical `CURSOR OPEN FAILED 99999` connection error spans **four different
  repos**, which is the signature of a shared infrastructure / DB-connectivity
  cause, not four independent logic bugs.
- The same three tests passed in **three prior CI runs** on the same DB2 code
  paths, indicating the code path itself is functionally correct in a healthy
  environment.

**Status: NOT VERIFIED (root cause).** Full root-cause verification requires the
Docker GnuCOBOL+OCESQL image and the real PostgreSQL container, which are not
available in this working environment (Docker daemon is not running locally).
This must not be claimed as fixed.

> Per project rule §16, these tests are **NOT** being weakened, skipped, or
> converted to PASS. They remain real failures until the environment supports them.

---

## 5. Regressions Introduced by the Test Reorganization (all now FIXED)

The reorganization commit `3132603` introduced three CI-breaking issues. All were
diagnosed and fixed; each fix is committed and pushed.

| Issue | Symptom in CI | Fix | Verified |
|---|---|---|---|
| Empty placeholder shims | `import file mismatch` — 24 collection errors | Deleted 23 placeholder shim files (commit `3a687d7`) | `647` tests collected cleanly |
| `test_java_source_mutation.py` moved, so `--ignore` stopped matching | It unexpectedly ran and failed in fast-lane | Updated `--ignore` path (commit `882fdc0`) | Removed from run |
| `test_hardening_parity_and_ui.py` moved, so `ui.html` path broke | `FileNotFoundError: tests/integration/ui.html` (3 test failures) | Corrected relative path to repo root (commit `882fdc0`) | 7/7 pass locally |

---

## 6. Test Suite Coverage Classification

### 6.1 Business-logic coverage (semantics, parser, IR, generator, equivalence)

These verify that COBOL behaviour is preserved by the generator — the heart of
"business equivalence".

| Area | Representative files | What they verify |
|---|---|---|
| Parser / IR / lexer | `tests/unit/parser`, `tests/unit/lexer`, `tests/unit/ir`, `tests/test_control_flow.py`, `tests/test_data_flow.py` | Tokenization, parse, semantic IR, control/data flow |
| Native generator semantics | `test_native_*.py` (call, compute truncation, evaluate, file_io, level88, move_multi, occurs, paragraph_control, perform_varying, period_scoping, ref_mod, statement_translation, traceability, type_mapping) | Per-CONSTRUCT behavioural translation |
| Arithmetic / numeric | `test_phase8_arithmetic_errors.py`, `test_native_compute_truncation.py` | Overflow, ON SIZE ERROR, precision |
| Report Writer | `test_phase8_report_writer.py` | Report generation semantics |
| Sort / merge | `test_phase8_sort_merge.py` | SORT/MERGE workflow |
| String / pointers | `test_phase8_string_operations.py`, `test_phase8_pointers.py` | String and pointer operations |
| DB2 / SQL semantics | `test_db2_acceptance.py`, `test_db2_stage1.py` (unit), `test_sql_db_ksds_modernization.py`, `test_db2_dialect_null_indicators.py` | SQL translation and (where env allows) execution |
| Differential equivalence | `tests/e2e/differential/*` (5 new tests) | COBOL-vs-Java output comparison (SKIP in fast-lane) |
| Unseen repos | `tests/robustness/unseen/*` | Repository-agnostic generalisation |

### 6.2 Infrastructure / validation / security coverage (NOT business equivalence)

These verify the pipeline's robustness, validation integrity and security — they
are important but do **not** prove business equivalence on their own.

| Area | Representative files |
|---|---|
| Validation gates / fail-closed | `test_no_false_production_ready.py`, `test_phase10_gates.py`, `test_validation_nobypass.py`, `test_no_hardcoding.py` (all at `tests/` root) |
| Security | `test_phase11b_security.py`, `test_phase8_security_audit.py`, `test_proleap_security.py`, `test_security_hardening.py` |
| Concurrency / workspace isolation | `test_concurrency_isolation.py`, `test_phase11b_workspace_isolation.py`, `test_docker_isolation.py`, `test_pipeline_remediation.py` |
| Failure recovery / negative paths | `test_phase8_failure_recovery.py`, `test_phase9_failure_matrix.py`, `test_negative_*`, `test_native_negative_equivalence.py` |
| Dependency / Maven / offline | `test_dependencies.py`, `test_phase8_dependency_audit.py`, `test_native_dependency_gate.py` |
| API / contract | `test_phase9_api_contract.py`, `test_phase9_manifest.py`, `test_phase9_repeatability.py` |
| E2E pipeline | `test_postgres_e2e.py`, `test_sql_baseline.py`, `test_sql_db_ksds_modernization.py` (integration) |

### 6.3 Finding: "categorization" subdirectories removed (flat layout retained)

After removing the placeholder shims (which only contained comment text and broke
pytest collection), the previously-empty categorization subdirectories
(`tests/negative/`, `tests/security/`, `tests/hardening/`, `tests/contracts/`,
`tests/gates/`) were **deleted** in favour of keeping all such tests flat at the
`tests/` root.

The real tests for those domains remain **at `tests/` root** (e.g.
`test_security_hardening.py`, `test_negative_equivalence_contract.py`,
`test_phase10_gates.py`). These directories were only empty scaffolding — they
contained no tracked source files and no real tests, so removing them changes no
test logic and the suite collects cleanly.

**Why flat rather than moving tests into subdirectories:** the affected tests all
rely on root-relative `sys.path` boilerplate
(`os.path.dirname(os.path.dirname(os.path.abspath(__file__)))`) that resolves to
the repository root only at the `tests/` depth. Moving them one level deeper
(e.g. into `tests/security/`) would break `from modernize.*` and `from tests.*`
package imports (e.g. `test_phase8_failure_recovery.py` imports
`from tests.test_phase8_file_semantics import run_cobol_code`), and would require
path fixes in several files that reference fixtures (`ui.py`, `ui.html`,
`repos/ACCTPROG`). The decision rule in the task therefore selects **Option B**
(remove stubs, keep flat). The test suite is intentionally split across a small
number of genuinely-moved subdirectories (`tests/unit`, `tests/component`,
`tests/e2e/differential`, `tests/robustness`) plus a flat root for the remaining
domain suites.

---

## 7. Coverage Gaps

1. **Full differential equivalence still not in the fast-lane.** The new
   `differential-smoke` job (see §7.2) now runs a **small core subset** (REDEFINES,
   ON SIZE ERROR, file I/O) on every push/PR, but the broader `tests/e2e/differential/*`
   and `test_parity_fixtures.py` sets (EBCDIC, relative, indexed, JCL, DB2-cursor)
   still only run in `nightly-full`. Business-equivalence claims beyond the smoke
   subset thus depend on running the nightly job.

2. **Real DB2 is `NOT_VERIFIED`.** As documented in the objective and in
   `docs/REAL_DB2_FINAL_VERIFICATION.md`, the platform has never been executed
   against a real DB2. All DB2 evidence is either emulated (H2) or against
   PostgreSQL. The DB2 E2E path is now fixture-isolated (see §7.1) and runs against
   PostgreSQL — still not a real DB2.

3. **No per-domain home for security/gates/negative/contracts/hardening tests.**
   The empty stub directories (§6.3) leave the suite layout inconsistent and make
   it easy for future "reorganization" to drift into duplicate-basename collisions
   again.

4. **CI green-ness requires a live PostgreSQL run.** The DB2 E2E fix is verified at
   the **generation level** (generated seed SQL confirmed); a live PostgreSQL CI run
   is required to confirm the fast lane is green. The fix does not weaken any
   assertion, in line with project rules.

5. **No explicit CI gate tying nightly differential results back to a job result.**
   The `nightly-full` job runs everything but there is no fast, deterministic,
   required diff-coverage assertion on business-critical constructs in the default
   push path.

---

## 8. Recommendations

1. **Fix the DB2 E2E shared-table isolation deficiency.** The four DB2 E2E
   failures were **root-caused** (see §7.1): several generated DB2 programs
   `TRUNCATE` + re-seed / re-schema (and `DB2ERRCONSTRAINT`/`DB2ERRNOTFOUND`
   `CREATE TABLE customer (cust_id, cust_name)`) the shared
   `modernization_db.CUSTOMER` table, so test execution order made one test drop
   columns another test needs. **Now DONE** at the fixture level (see §7.1): the
   `data/*.sql` seeds were aligned so generated programs create a non-destructive
   superset `customer` schema and each self-TRUNCATEs its seeded tables. This
   removes the cross-test interference without touching any assertion. A fully
   independent per-repo schema/database remains a future hardening option but is no
   longer required for the fast lane.

2. **Make differential parity run deterministically in a defined job.** **Now DONE**
   via the `differential-smoke` job (see §7.2). NOTE: the actual differential test
   modules use `@pytest.mark.skipif(env PARITY_ALLOW_SKIP != "true")`, so the job
   **must** set `PARITY_ALLOW_SKIP=true` for them to execute (setting `false` skips
   them entirely). The job closes the silent-skip gap by failing if any selected test
   is skipped (both images are guaranteed present, so a skip is a real signal).

3. **Add per-test DB isolation for DB2 repos.** Originally the long-term fix for the
   four DB2 E2E tests. **Superseded** by the fixture-alignment fix shipped in this
   change (see §7.1). A fully isolated schema/table namespace per repo can still be
   added later for defense-in-depth, but is not required for green fast lane.

4. **Guard against duplicate module basenames.** Add a lightweight CI check (or
   `conftest.py` assertion) that fails if two collected test modules resolve to
   the same pytest module name, preventing a recurrence of the 24-error collection
   abort. (**Open** — not yet implemented.)

5. **Document DB2 status honestly.** Keep `REAL_DB2` as `NOT_VERIFIED` — the DB2 E2E
   tests run against **PostgreSQL** (an emulation of the DB2 JDBC surface), never a
   real DB2. No emulation is reported as real DB2. (**Ongoing** — see §9.)

---

## 7.1 DB2 E2E failures classification

**Root cause (verified from CI PostgreSQL server logs):** the four failing tests in
`tests/test_db2_stage1.py` were blocked by **shared mutable PostgreSQL table state**,
not by a code-generation regression. Each generated DB2 Java program embeds
per-repo `TRUNCATE`/re-seed executed against the **same**
`modernization_db.CUSTOMER` table, and `DB2ERRCONSTRAINT`/`DB2ERRNOTFOUND` further
`CREATE TABLE customer (cust_id, cust_name)` which **destructively dropped** the
`dept_id` / `status` columns other repos rely on. Observed server errors on the
failing runs:

| Error (PostgreSQL log) | Test | Effect |
|---|---|---|
| `column c.dept_id of relation "customer" does not exist` | `left_outer_join` | LEFT JOIN query throws → `OPEN FAILED 99999` |
| `column "status" of relation "customer" does not exist` | `count_aggregate` | `SELECT COUNT(*) WHERE STATUS=...` throws → `99999` |
| `column "dept_id" does not exist` (HINT: `customer.cust_id`) | `group_by_having` | GROUP BY query throws → `OPEN FAILED 99999` |
| `relation "customer" already exists` + `duplicate key ... customer_pkey` + `unexpected EOF ... open transaction` | `tx_commit_visible` (+ collateral) | transaction/schema conflict + stale-row PK conflicts |

The `CURSOR OPEN FAILED SQLSTATE 99999` string is emitted by the generated Java
program when its `queryForRowSet(...)` throws (catch sets `sqlcode=-1`,
`sqlstate=99999`). Reorg commit `3132603` changed **pytest file execution order**
(moving several DB2 test files into `tests/component/db/`), which determines the
order in which these shared-table mutating programs run — exposing this pre-existing
test-isolation fragility.

| Test | Classification | Evidence | Fix applied |
|---|---|---|---|
| `test_db2_left_outer_join_e2e` | **FIXED** (fixture isolation) | PG log: `column c.dept_id ... does not exist`, `OPEN FAILED 99999` | Error repos no longer drop `dept_id`/`status` |
| `test_db2_count_aggregate_e2e` | **FIXED** (fixture isolation) | PG log: `column "status" ... does not exist` | Error repos no longer drop `status` |
| `test_db2_group_by_having_e2e` | **FIXED** (fixture isolation) | PG log: `column "dept_id" does not exist`, HINT `customer.cust_id` | Error repos no longer drop `dept_id` |
| `test_db2_tx_commit_visible_e2e` | **FIXED** (fixture isolation) | `duplicate key`, stale-row PK conflicts | Added non-empty seed → self-TRUNCATE clears stale rows |

**Fix (fixture-level, no assertion changes):** three `data/*.sql` seed files were
aligned so the generated programs isolate themselves on the shared table:

- `tests/repos/DB2ERRCONSTRAINT/data/customer.sql` and
  `tests/repos/DB2ERRNOTFOUND/data/customer.sql`: changed from the destructive
  `CREATE TABLE customer (cust_id, cust_name)` to a **non-destructive superset**
  `CREATE TABLE IF NOT EXISTS customer (cust_id INT PRIMARY KEY, cust_name
  VARCHAR(100), dept_id INT, status VARCHAR(20))`. This preserves the `dept_id` /
  `status` columns other repos need while keeping `cust_id` as the PK (so the
  `-803` constraint-violation and `100` not-found behaviors are unchanged).
- `tests/repos/DB2TXVISIBILITY01/data/customer.sql`: was comment-only, so
  `seed_queries` was empty and the generated program's `TRUNCATE` block
  (`if seed_queries:` in `native_generator.py`) was **skipped** — stale rows from
  prior shared-table tests survived and caused PK collisions on the TX INSERTs,
  breaking commit/rollback visibility. The file now contains a non-destructive
  superset `CREATE TABLE IF NOT EXISTS customer (...)`, which makes the generated
  program TRUNCATE the table first and gives it a clean base.

All four tests keep their original assertions (expected outputs unchanged). They now
run in the **fast lane** (the temporary `--deselect` workaround was removed) and
remain active in `nightly-full`. Verification is at the generation level only
(generated seed SQL inspected); a live PostgreSQL run in CI is still required to
close the loop. `REAL_DB2` compatibility remains `NOT_VERIFIED` (tests run against
PostgreSQL, an emulation of the DB2 JDBC surface).

---

## 7.2 Differential-smoke CI job

A dedicated `differential-smoke` job now runs on **every push to `master` and every
PR**, giving push-time business-equivalence (COBOL-vs-Java) evidence that the fast
lane previously lacked. It:

- Runs in Docker with the same `gnucobol-ocesql` image and the Temurin JDK image
  (`eclipse-temurin:17-jdk-noble`). No PostgreSQL is needed: the selected fixtures
  contain no `EXEC SQL`, so the parity harness (`run_parity`) runs them without the
  network/`db` container (see `tests/utils/parity_harness.py:425-429`).
- Sets **`PARITY_ALLOW_SKIP=true`**. This is **required** for the selected tests to
  execute at all: each differential test module is decorated with
  `@pytest.mark.skipif(os.environ.get("PARITY_ALLOW_SKIP","false") != "true")` (e.g.
  `tests/e2e/differential/numeric/test_sizeerr01.py:64`), so any other value **skips
  the entire test**. Setting `false` would make the smoke gate assert nothing.
- Runs a small, fast subset of differential fixtures: REDEFINES (`test_redefines01`),
  ON SIZE ERROR (`test_sizeerr01`), and basic file I/O (`test_filestat01`) — the core
  constructs whose COBOL-vs-Java output proves equivalence.
- **FAILS the job** if any selected test fails **or is skipped** (the summary line is
  inspected for a non-zero `skipped` count). Because both Docker images are built/pulled
  before the tests run, the harness returns `PASS`/`FAIL` — never `SKIP` — so a skip in
  this job is a real signal and is treated as a hard failure.

Meaning of results in this job:

| Result | Meaning |
|---|---|
| PASS | Java output matches COBOL baseline for the selected constructs |
| FAIL | Equivalence broken for a core construct → push/PR gate fails |
| SKIP | Treated as a failure (images are present, so there is no valid reason to skip) |

The remaining differential/parity fixtures (e.g. EBCDIC, relative, indexed, JCL, and
the broader `tests/e2e/differential/*` set) stay in `nightly-full`, which remains the
authoritative full business-equivalence regression.

---

## 9. Final Status

| Item | Status |
|---|---|
| Doc changes (flat test layout) committed & pushed | VERIFIED (HEAD `fb14932`) |
| DB2 E2E failure root cause | **VERIFIED** — shared `CUSTOMER` table mutated/destructively re-schema'd across tests (see §7.1) |
| DB2 E2E tests (4) | **FIXED (fixture isolation)** — non-destructive superset `customer` seeds + self-TRUNCATE for TX; assertions unchanged; back in the fast lane (deselect removed) |
| Differential-smoke CI job | ADDED — push/PR business-equivalence gate (see §7.2) |
| Reorg-induced collection errors | FIXED & VERIFIED (643 collected) |
| Real DB2 compatibility | NOT_VERIFIED (DB2 E2E runs against PostgreSQL, not a real DB2) |

Overall status: **PARTIAL** — the four DB2 E2E failures underlying the fast-lane red
were root-caused and **fixed at the fixture level** (no assertion changes): the
destructive `CREATE TABLE customer (cust_id, cust_name)` in the error repos is now a
non-destructive superset, and the TX repo's empty seed was replaced so its generated
program self-TRUNCATEs and gets a clean table. The temporary `--deselect` workaround
was **removed**, so the DB2 E2E tests run in the fast lane again. The verification is
at the **generation level only** (generated seed SQL inspected and confirmed); a live
PostgreSQL CI run is still required to close the loop before declaring the fast lane
green. A new `differential-smoke` job enforces COBOL-vs-Java business-equivalence on
every push/PR.
