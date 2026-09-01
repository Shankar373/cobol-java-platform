# Phase 2 Summary — Numeric Semantics & Evidence Hardening

## 1. Scope and Objectives
Phase 2 establishes strict numeric semantics and evidence hardening across the modernization platform:
1. Eradicate double-precision floating-point contamination in exponentiation (`**`).
2. Add explicit COBOL scope terminators (`END-ADD`, `END-SUBTRACT`, `END-MULTIPLY`, `END-DIVIDE`, `END-COMPUTE`) to ensure clean statement boundaries.
3. Formally prove that the normalization layer cannot mask business-significant differences (leading zeroes, signs, field widths, decimal precision).
4. Conduct a rigorous audit of all skipped and deferred parity tests to ensure unexecuted capabilities cannot contribute to `DIFFERENTIALLY_VERIFIED` or `PRODUCTION_READY` verdicts.

---

## 2. Evidence-Backed Implementation Changes

### A. Exponentiation (`**` / `CobolArithmetic.power`)
* **Root cause**: `CobolArithmetic.power()` previously fell back to `Math.pow(double, double)` for fractional exponents, violating the strict `BigDecimal` no-double rule and introducing IEEE 754 precision loss.
* **Source/Function**:
  - [`runtime/CobolArithmetic.java:power(BigDecimal, BigDecimal)`](file:///c:/Users/bandi/Desktop/ai-workspace/Cobol-to-java-modernization/modernize/java_helpers/src/main/java/com/systema/modernized/runtime/CobolArithmetic.java#L98-L109)
  - [`modernize/native_generator.py:parse_power`](file:///c:/Users/bandi/Desktop/ai-workspace/Cobol-to-java-modernization/modernize/native_generator.py#L488)
* **Implementation Details**:
  - Positive integer exponents: Computes exact `BigDecimal.pow(exponent, MC)`.
  - Zero exponent: `X ** 0` returns `BigDecimal.ONE` (1).
  - Negative integer exponents: Computes reciprocal `BigDecimal.ONE.divide(a.pow(-exponent, MC), MC)`.
  - Negative base: Correctly differentiates odd power (negative result) from even power (positive result).
  - Fractional or out-of-range exponents: Throws fail-fast `ArithmeticException("COBOL_UNSUPPORTED_NUMERIC_FEATURE: Fractional or out-of-range exponentiation...")`.
* **Tests Added**: [`tests/component/arithmetic/test_power_differential.py`](file:///c:/Users/bandi/Desktop/ai-workspace/Cobol-to-java-modernization/tests/component/arithmetic/test_power_differential.py)
* **Real Execution Evidence**: `javac` compiled and `java` executed under OpenJDK 25 LTS:
  - `2 ** 3 = 8` (PASS)
  - `10 ** 4 = 10000` (PASS)
  - `5 ** 0 = 1` (PASS)
  - `0 ** 0 = 1` (PASS)
  - `2 ** -2 = 0.25` (PASS)
  - `10 ** -3 = 0.001` (PASS)
  - `(-3) ** 3 = -27` (PASS)
  - `(-2) ** 2 = 4` (PASS)
  - `2 ** 0.5` raises `COBOL_UNSUPPORTED_NUMERIC_FEATURE` fail-fast (PASS)

---

### B. Output Normalization Safety Proof
* **Root cause**: Normalization in differential gates must only eliminate harmless transport-level differences (e.g. CRLF vs LF, trailing line spaces), and must never mask business data mismatches.
* **Source/Function**:
  - [`cobol_migrate.py:_normalize_text`](file:///c:/Users/bandi/Desktop/ai-workspace/Cobol-to-java-modernization/cobol_migrate.py#L5265)
  - [`modernize/native_pipeline.py:conservative_stdout`](file:///c:/Users/bandi/Desktop/ai-workspace/Cobol-to-java-modernization/modernize/native_pipeline.py#L1420)
  - [`tests/utils/parity_harness.py:normalize_display`](file:///c:/Users/bandi/Desktop/ai-workspace/Cobol-to-java-modernization/tests/utils/parity_harness.py#L102)
* **Safety Assertions Proven in Tests**:
  - **Leading Zeroes**: `00012345` vs `12345` evaluated as `MISMATCH` across all normalization layers.
  - **Signed Values**: `+123.45` vs `-123.45` vs `123.45` evaluated as `MISMATCH`.
  - **Decimal Precision**: `12.34` vs `12.340` vs `12.35` evaluated as `MISMATCH`.
  - **Off-by-one Numeric Digits**: `25864` vs `258648` evaluated as `MISMATCH`.
  - **Output File Records**: Binary and fixed-length data files are compared byte-for-byte with zero normalization.
* **Tests**: [`tests/test_normalization_safety.py`](file:///c:/Users/bandi/Desktop/ai-workspace/Cobol-to-java-modernization/tests/test_normalization_safety.py) (6/6 tests passing).

---

### C. `END-` Scope Terminators
* **Root cause**: COBOL programs using inline `ON SIZE ERROR` blocks require explicit scope terminators (`END-ADD`, `END-SUBTRACT`, `END-MULTIPLY`, `END-DIVIDE`, `END-COMPUTE`) to avoid leaking subsequent statements into the exception handler.
* **Source/Function**:
  - [`modernize/lexer.py:COBOL_KEYWORDS`](file:///c:/Users/bandi/Desktop/ai-workspace/Cobol-to-java-modernization/modernize/lexer.py#L12)
  - [`modernize/parser.py:STATEMENT_START_VERBS`](file:///c:/Users/bandi/Desktop/ai-workspace/Cobol-to-java-modernization/modernize/parser.py#L96)
  - [`modernize/native_generator.py:_generate_compute_block`](file:///c:/Users/bandi/Desktop/ai-workspace/Cobol-to-java-modernization/modernize/native_generator.py#L488)
* **Real Execution Evidence**:
  - Lexer and parser extract 11 separate statements without syntax errors or statement leakage.
  - Transpiled Java compiles cleanly and executes: size error blocks execute only on overflow; subsequent statements execute unconditionally.
* **Tests Added**: [`tests/component/parser/test_end_scope_terminators.py`](file:///c:/Users/bandi/Desktop/ai-workspace/Cobol-to-java-modernization/tests/component/parser/test_end_scope_terminators.py) (2/2 tests passing).

---

## 3. Audit of Deferred and Skipped Parity Tests

The test suite in [`tests/test_parity_fixtures.py`](file:///c:/Users/bandi/Desktop/ai-workspace/Cobol-to-java-modernization/tests/test_parity_fixtures.py) contains exactly **4 explicitly deferred parity tests**:

| Test Name | Line | Stated Reason | Architectural Limitation vs Defect Proof | Target Phase |
|---|---|---|---|---|
| `test_parity_ebcdic_records` | 944 | EBCDIC file I/O is UNSUPPORTED | **Architectural Limitation**: Requires dedicated EBCDIC charset transcoding layer (`CP037`/`IBM-1047`) in file stream handlers. | Phase D |
| `test_parity_relative_file_random_access` | 952 | RELATIVE file storage emulation | **Architectural Limitation**: Random record access by RRN requires keyed persistence (SQL/database backing in runtime). | Phase 4 / Phase C |
| `test_parity_indexed_file_missing_key` | 1006 | INDEXED file storage emulation | **Architectural Limitation**: B-Tree / SQL index lookup and FILE STATUS return codes require DB2/H2 schema integration. | Phase 4 / Phase C |
| `test_parity_jcl_conditional` | 1053 | JCL conditional parity | **Architectural Limitation**: Mainframe JCL `COND` parameter step routing requires multi-step job runner in Docker harness. | Phase 6 / Phase 7 |

> [!CAUTION]
> **Strict Verdict Guard**:
> - `PARITY_ALLOW_SKIP=true` is strictly a developer convenience flag for fast-lane offline testing when Docker is down.
> - Skipped and deferred tests **never** grant `DIFFERENTIALLY_VERIFIED` capability status.
> - All 4 deferred capabilities remain explicitly classified as `UNSUPPORTED` or `PARTIAL` in [`modernize/capability_matrix.py`](file:///c:/Users/bandi/Desktop/ai-workspace/Cobol-to-java-modernization/modernize/capability_matrix.py).

---

## 4. Capabilities Explicitly Classified as UNPROVEN / PARTIAL

Until differential execution evidence against GnuCOBOL/Mainframe baselines is established, the following capabilities remain strictly classified as `UNPROVEN` or `PARTIAL`:
1. **EBCDIC File I/O**: `UNSUPPORTED` (no codec in runtime).
2. **OCCURS DEPENDING ON**: `PARTIAL` (bounds generated; runtime dynamic reallocation unverified).
3. **REDEFINES Shared Backing Storage**: `PARTIAL` (basic chains verified in Phase 3; complex multidimensional arrays unverified).
4. **CALL BY CONTENT**: `PARTIAL` (scalar snapshot cloning verified in Phase 3; deep nested structures unverified).
5. **PERFORM VARYING AFTER**: `PARTIAL` (single-variable varying verified in Phase 3; multi-varying `AFTER` loops pending Phase B).
6. **VSAM / Database Persistence**: `PARTIAL / EMULATED` (H2 SQL mapping exists; real IBM DB2/CICS middleware unproven).
7. **Fractional Exponents**: `UNSUPPORTED` (fail-fast with `COBOL_UNSUPPORTED_NUMERIC_FEATURE` under no-double rule).
