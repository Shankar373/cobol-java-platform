# Phase 8 — Advanced Enterprise COBOL Language Semantics

**Status**: Verified & Differential Execution Proven  
**Date**: September 2026

---

## 1. Overview & Objectives

Phase 8 expands Enterprise COBOL semantic coverage to support advanced language constructs and enterprise data structures:
- **`EVALUATE` / Multi-Subject Decision Tables** (`EVALUATE TRUE`, `ALSO`, ranges, `WHEN OTHER`)
- **Dynamic Array Sizing & OCCURS DEPENDING ON (ODO)** (`checkBounds` runtime verification)
- **Nested & Multi-Level Overlays / REDEFINES** (Shared backing storage via `char[]` buffer and `CobolLayout`)
- **String Manipulations** (`INSPECT TALLYING`, `REPLACING`, `CONVERTING`, `STRING`, `UNSTRING`)
- **Initialization & Memory Semantics** (`INITIALIZE ... REPLACING`, alphanumeric/numeric defaults)
- **Sorting & Merging** (`SORT ... USING ... GIVING`, `MERGE ... USING ... GIVING`)
- **Report Writer Extensions** (`RD`, `INITIATE`, `GENERATE`, `TERMINATE`)
- **Pointer & Address Arithmetic** (`USAGE IS POINTER`, `SET ADDRESS OF`)
- **Nested Programs & Scope Delimiters** (`PROGRAM-ID`, `END PROGRAM`, `GLOBAL` data items)
- **Formatted Picture Output** (`PIC $$,$$9.99`, `ZZ,ZZ9.99`, `**,**9.99`, `CR`, `DB`, zero-suppression and leftmost integer truncation)

---

## 2. Detailed Construct Audit & Implementation

### A. REDEFINES & Shared Backing Storage
- **COBOL Semantic Requirement**: When multiple fields redefine the same storage area, modifications through one view must immediately reflect in all overlapping views.
- **Java Implementation**: `NativeProgramGenerator` computes byte offsets and emits a single contiguous `char[] backing_store` with accessor methods (`get_fieldName()` / `set_fieldName()`) that read and write at the calculated offsets.
- **Evidence**: Verified in `tests/test_phase8_redefines.py` and `tests/test_phase8_layout_integration.py`.

### B. OCCURS DEPENDING ON (ODO)
- **COBOL Semantic Requirement**: The effective size of an array depends dynamically on an integer control field. Out-of-bounds access beyond the current control value or configured bounds is illegal.
- **Java Implementation**: The generator emits `checkBounds(index, min_val, dep_var_name, dep_val_expr)`.
- **Evidence**: Verified in `tests/test_phase8_redefines.py`.

### C. Picture Editing & Numeric Formatting
- **COBOL Semantic Requirement**: Numeric editing (`$`, `+`, `-`, `Z`, `*`, `CR`, `DB`) formats numbers with floating currency/sign symbols, suppression, and standard high-order digit truncation on overflow.
- **Java Implementation**: `CobolFormatHelper.format(value, pattern)` formats `BigDecimal` numbers deterministically. Leftmost integer overflow truncates according to ISO/IEC 1989 COBOL rules.
- **Evidence**: Verified against GnuCOBOL baseline in `tests/test_phase8_pic_formatting.py`.

### D. SORT and MERGE Verbs
- **COBOL Semantic Requirement**: `SORT workfile ON ASCENDING/DESCENDING KEY ... USING infile GIVING outfile` and `MERGE workfile ... USING in1 in2 GIVING outfile` sort/merge input datasets into output datasets using record key slices.
- **Java Implementation**: `NativeProgramGenerator` generates comparator lambdas and stream/collection sort pipelines that process file records sequentially.
- **Evidence**: Verified end-to-end in `tests/test_phase8_sort_merge.py`.

### E. String Operations (INSPECT / UNSTRING / STRING)
- **COBOL Semantic Requirement**:
  - `INSPECT ... TALLYING` counts character occurrences.
  - `INSPECT ... REPLACING` substitutes character patterns.
  - `INSPECT ... CONVERTING` maps character sets.
  - `UNSTRING` splits fields with multiple delimiters, pointer tracking, and overflow flags.
- **Java Implementation**: `CobolFormatHelper` helper methods and native Java regex/tokenizers.
- **Evidence**: Verified in `tests/test_phase8_string_operations.py`.

---

## 3. Evidence & Verification Summary

| Construct Area | Parser Node | Generator Output | Runtime Class | Tests | Evidence Classification |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **REDEFINES (Overlay)** | `DATA_ITEM` (`redefines`) | `backing_store` / Getters/Setters | Native Array Storage | `test_phase8_redefines.py` | `E2E_PROVEN` |
| **OCCURS DEPENDING ON** | `DATA_ITEM` (`depending_on`) | `checkBounds()` | `CobolLayout` | `test_phase8_redefines.py` | `E2E_PROVEN` |
| **PIC Formatting** | `DATA_ITEM` (`is_edited`) | `CobolFormatHelper.format()` | `CobolFormatHelper` | `test_phase8_pic_formatting.py` | `E2E_PROVEN` |
| **SORT / MERGE** | `STATEMENT` (`SORT`/`MERGE`) | `Collections.sort()` | Standard Java 17 | `test_phase8_sort_merge.py` | `E2E_PROVEN` |
| **INSPECT / UNSTRING** | `STATEMENT` (`INSPECT`/`UNSTRING`)| `CobolFormatHelper` | `CobolFormatHelper` | `test_phase8_string_operations.py`| `E2E_PROVEN` |
| **Nested Programs** | `PROGRAM` / `END PROGRAM` | Inner Static Classes | Standalone JVM | `test_phase8_nested_programs.py` | `E2E_PROVEN` |
| **Report Writer** | `RD` / `GENERATE` | Screen/Report Stream | Standalone JVM | `test_phase8_report_writer.py` | `COMPATIBILITY_PROVEN`|
| **Pointers & Addresses**| `USAGE IS POINTER` | Typed References | Standalone JVM | `test_phase8_pointers.py` | `COMPATIBILITY_PROVEN`|
