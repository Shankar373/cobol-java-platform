# Baseline Test Results

> **Snapshot recorded**: 2026-08-29 after Phase 0/1 implementation.
> Prior commit: `9b81eee` — 601/601 tests passing.

---

## Pre-Phase-0/1 Baseline (commit 9b81eee)

| Metric | Value |
|---|---|
| Total tests | 601 |
| Passed | 601 |
| Failed | 0 |
| Errors | 0 |
| Skipped | (Docker-gated parity tests skipped when Docker unavailable) |

---

## Test Category Breakdown

| Category | File(s) | Status |
|---|---|---|
| Lexer | `test_lexer.py` | ✅ All passing |
| Parser | `test_parser.py` | ✅ All passing |
| Numeric type mapping | `test_native_type_mapping.py` | ✅ All passing |
| Arithmetic / truncation | `test_native_compute_truncation.py` | ✅ All passing |
| Arithmetic errors (COMP-3, size) | `test_phase8_arithmetic_errors.py` | ✅ All passing |
| Statement translation | `test_native_statement_translation.py` | ✅ All passing |
| EVALUATE | `test_native_evaluate.py` | ✅ All passing |
| PERFORM VARYING | `test_native_perform_varying.py` | ✅ All passing |
| OCCURS | `test_native_occurs.py` | ✅ All passing |
| CALL translation | `test_native_call_translation.py` | ✅ All passing |
| File I/O | `test_native_file_io.py` | ✅ All passing |
| Adversarial / edge cases | `test_native_adversarial.py` | ✅ All passing |
| PIC formatting | `test_phase8_pic_formatting.py` | ✅ All passing |
| Redefines | `test_phase8_redefines.py` | ✅ All passing |
| String operations | `test_phase8_string_operations.py` | ✅ All passing |
| File semantics | `test_phase8_file_semantics.py` | ✅ All passing |
| Pointers | `test_phase8_pointers.py` | ✅ All passing |
| Layout integration | `test_phase8_layout_integration.py` | ✅ All passing |
| Nested programs | `test_phase8_nested_programs.py` | ✅ All passing |
| DB2 acceptance | `test_db2_acceptance.py` | ✅ All passing |
| DB2 JCC driver | `test_db2_jcc_driver.py` | ✅ All passing |
| DB2 modernization | `test_db2_modernization.py` | ✅ All passing |
| DB2 stage 1 | `test_db2_stage1.py` | ✅ All passing |
| DB2 null indicators | `test_db2_dialect_null_indicators.py` | ✅ All passing |
| DB2 error mapper | `test_db2_error_mapper.py` | ✅ All passing |
| SQL literals | `test_sql_literals_translation.py` | ✅ All passing |
| SQL DB KSDS modernization | `test_sql_db_ksds_modernization.py` | ✅ All passing |
| VSAM KSDS stage 2 | `test_vsam_ksds_stage2.py` | ✅ All passing |
| VSAM RRDS | `test_vsam_rrds.py` | ✅ All passing |
| JCL modernization | `test_jcl_modernization.py` | ✅ All passing |
| JCL symbols | `test_jcl_symbols_complete.py` | ✅ All passing |
| BMS mapping | `test_bms_mapping.py` | ✅ All passing |
| Security hardening | `test_security_hardening.py` | ✅ All passing |
| Docker isolation | `test_docker_isolation.py` | ✅ All passing (Docker-gated) |
| Postgres E2E | `test_postgres_e2e.py` | ✅ All passing (Docker-gated) |
| Certification hardening | `test_certification_hardening.py` | ✅ All passing |
| Java source mutation | `test_java_source_mutation.py` | ✅ All passing |
| Parity fixtures | `test_parity_fixtures.py` | ✅ Collected/skipped (Docker-gated) |
| Equivalence negative gates | `test_equivalence_negative_gates.py` | ✅ All passing |
| Final equivalence contract | `test_final_equivalence_contract.py` | ✅ All passing |
| Pipeline remediation | `test_pipeline_remediation.py` | ✅ All passing |
| Phase 9 verdict | `test_phase9_verdict.py` | ✅ All passing |
| Phase 9 manifest | `test_phase9_manifest.py` | ✅ All passing |
| Phase 10 gates | `test_phase10_gates.py` | ✅ All passing |
| Phase 11 UI integration | `test_phase11_ui_integration.py` | ✅ All passing |

---

## Post-Phase-0/1 Regression Check

After implementing Phase 0 (capability matrix reclassification, coverage docs) and Phase 1 (parity harness extension, fixture suite), the non-parity test suite was re-run:

| Metric | Value |
|---|---|
| Tests collected (excl. parity_fixtures) | ≥ 578 |
| Regressions introduced | **0** |
| New failures | **0** |

---

## Known Skipped Tests

| Test | Reason |
|---|---|
| `test_parity_fixtures.py::test_parity_ebcdic_records` | EBCDIC file I/O **UNSUPPORTED** — no codec |
| `test_parity_fixtures.py::test_parity_jcl_conditional` | JCL Docker integration not yet wired |
| All `run_parity()` tests | Skipped when `PARITY_ALLOW_SKIP=true` and Docker is unavailable |
| `test_compiler_fingerprint_drift` | Skipped when Docker is unavailable |

---

## Known Gaps at Baseline

| Gap | Impact |
|---|---|
| `CobolArithmetic.power()` uses `Math.pow()` for fractional exponents | **P0** — violates no-double rule for COMPUTE ** |
| FILE STATUS not captured in `ExecutionResult` | DIFFERENTIALLY_VERIFIED status cannot be claimed for FILE STATUS behavior |
| SQLCODE/SQLSTATE not captured in `ExecutionResult` | SQL differential evidence limited |
| EBCDIC file I/O not implemented | SEQUENTIAL_EBCDIC remains UNSUPPORTED |
| REDEFINES write-through not byte-backed | REDEFINES capped at UNIT_TESTED |
| OCCURS DEPENDING ON runtime bounds not verified | ODO remains GENERATED_ONLY |
