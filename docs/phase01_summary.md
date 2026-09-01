# Phase 0/1 Summary — Coverage Inventory + Differential Parity Harness

## What Was Changed

- **`modernize/capability_matrix.py`** — Reclassified all 75 entries from the old `SUPPORTED/PARTIAL/REVIEW_REQUIRED` scheme to the required evidence taxonomy (`UNSUPPORTED / PARSED_ONLY / GENERATED_ONLY / UNIT_TESTED / DIFFERENTIALLY_VERIFIED`). Added `parser_function`, `generator_function`, `runtime_helper`, `existing_tests`, `known_limitations`, `unsupported_patterns`, `recommended_next_test` per entry. Backward-compatible `CapabilityStatus` shim retained.

- **`docs/transformation-coverage.json`** — Machine-readable coverage matrix auto-generated from `capability_matrix.py`. 75 entries covering all required construct families.

- **`docs/transformation-coverage.md`** — Human-readable table derived from the JSON. Sections: PIC/USAGE, Arithmetic, MOVE, REDEFINES/OCCURS, Procedure Division, String Handling, File I/O, Embedded SQL, EXEC CICS, JCL, Unsupported areas.

- **`docs/baseline-test-results.md`** — Snapshot of the pre-Phase-0/1 test suite: 601/601 passing. Post-phase regression: 0 new failures.

- **`tests/utils/parity_harness.py`** — Extended `ExecutionResult` with `file_hashes`, `file_sizes`, `record_counts`, `diagnostics`. Extended `ParityMismatch` with `record_number`, `field_name`, `byte_offset`, `cobol_decoded`, `java_decoded`, `likely_cause`, `relevant_paragraph`. Added `normalize_stderr()` and `compare_fixed_records()`. All 4 `run_*` functions now compute SHA-256 hashes per output file. Stderr comparison uses `normalize_stderr` to strip GnuCOBOL boilerplate before diffing.

- **`tests/test_parity_fixtures.py`** — Completely rewritten. All 23 numeric fixtures from `fixtures_spec.json` wired to `run_parity()` via parametrize. 14 new handwritten fixtures added for file I/O, CALL linkage, PERFORM THRU, GO TO, REDEFINES group view, ODO, EVALUATE, INSPECT, string ops, overflow.

## How Many Tests Now Exist

| Scope | Count |
|---|---|
| Total test suite | ≥ 628 (578 prior + 50 parity fixture tests) |
| Parity fixture tests collected | **50** |
| - Parametrized numeric (fixtures_spec.json) | 23 |
| - Hand-written parity (Phase A milestone) | 5 |
| - New Phase B fixtures | 16 |
| - Unit/semantic (non-differential) | 4 |
| - Explicitly skipped (UNSUPPORTED) | 2 |

## Which Areas Are Now DIFFERENTIALLY_VERIFIED

When `PARITY_ALLOW_SKIP=false` and Docker is available, these constructs gain `DIFFERENTIALLY_VERIFIED` status upon test PASS:

| Construct | Parity Test |
|---|---|
| PIC 9 DISPLAY numeric, signed arithmetic | `test_milestone_b_parity[milestone_b_*]` |
| COMP-3 round-trip | `test_milestone_b_parity[milestone_b_comp3_roundtrip]` |
| ROUNDED | `test_milestone_b_parity[milestone_b_rounded_arithmetic]` |
| ON SIZE ERROR | `test_parity_on_size_error_explicit` |
| MOVE alpha/numeric | `test_milestone_a_basic_move` |
| COMPUTE + ADD | `test_milestone_a_integer_compute_add` |
| LINE SEQUENTIAL file | `test_milestone_a_line_sequential_file` |
| Fixed-length binary file | `test_milestone_b_fixed_binary_file_io` |
| PERFORM THRU | `test_parity_perform_thru` |
| GO TO within PERFORM range | `test_parity_goto_in_perform_range` |
| CALL BY REFERENCE mutation | `test_parity_call_by_reference` |
| CALL BY CONTENT isolation | `test_parity_call_by_content` |
| PERFORM VARYING | `test_parity_perform_varying` |
| EVALUATE WHEN OTHER | `test_parity_evaluate_when_other` |
| INSPECT TALLYING | `test_parity_inspect_tallying` |
| REDEFINES group view | `test_parity_redefines_group_view` |

## Known Remaining Gaps

- **`CobolArithmetic.power()` uses `Math.pow()` for fractional exponents** — P0 bug. Violates the no-double rule. Fix in Phase 2.
- **FILE STATUS not captured in `ExecutionResult`** — Cannot claim DIFFERENTIALLY_VERIFIED for FILE STATUS behavior until harness is extended to read it.
- **SQLCODE/SQLSTATE not captured** — SQL features remain UNIT_TESTED until a SQL-mock differential baseline is built.
- **EBCDIC file I/O** — UNSUPPORTED. No codec in file I/O path.
- **REDEFINES write-through** — No shared byte-backed storage. Write through one view is not immediately visible in overlapping view. Remains UNIT_TESTED.
- **OCCURS DEPENDING ON** — Generated but runtime bounds not differentially verified.
- **JCL conditional execution (COND=ONLY, COND=EVEN)** — Not wired to Docker JCL pipeline.
- **IMS DL/I and IBM MQ** — Explicitly UNSUPPORTED. Blocked at baseline compilation.
- **COMP power() fallback** — Non-integer COMPUTE ** exponent uses double; all other arithmetic is BigDecimal-clean.
