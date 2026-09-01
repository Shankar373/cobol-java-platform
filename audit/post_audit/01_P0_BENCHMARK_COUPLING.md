# 01. P0 Benchmark Coupling Diagnostic Report

This report documents the diagnostic findings and verification of P0 Benchmark Coupling in the SystemaOps pipeline.

---

## 1. Verified Coupling Instances

We scanned the codebase for references to the benchmarks (`BCMAIN`, `CCPROC01`, etc.) and mapped their execution paths.

### A. Spring Boot Configuration Selection
- **File**: [`cobol_migrate.py`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/cobol_migrate.py)
- **Line(s)**: 3315, 3453, 5582, 5709, 6113
- **Condition**: `if "BCMAIN" in entry:` / `is_bank = "BCMAIN" in d.get("entry", "")`
- **Caller**: `stage_refactor`, `write_modern_business_services`, `write_data_seed_runner`
- **Execution Path**: If `BCMAIN` is present in the discovered entry point name, the refactoring engine switches context to seed and generate classes for the BankCore benchmark. Otherwise, it defaults to Claims PAS structures.
- **Impact**: Non-benchmark repositories fail to compile because the generator seeds benchmark-specific entities (such as `Policy` or `Customer`) that are not defined by the repository's own parsed copybooks.

### B. Validation Gateway Bypass
- **File**: [`cobol_migrate.py`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/cobol_migrate.py)
- **Line(s)**: 3411
- **Condition**: `if d.get("entry") not in ("CCMAIN01", "BCMAIN01"):`
- **Caller**: `stage_validate`
- **Execution Path**: Skips Gate 2 validation entirely for any generic repository, returning `True` (passed).
- **Impact**: Prevents compilation and execution validation of the refactored Spring Boot code for any generic repositories.

---

## 2. Genericity Diagnostic Test (INVOICE01)

To prove this behavior, we ran a temporary synthetic repository (`INVOICE01.cob`, `TAXCALC99.cob`, `INVREC01.cpy`):

- **First Component Failure**: `stage_refactor`
- **Reproduction Log/Trace**:
```
[ERROR] DataSeedRunner.java:[54,84] cannot find symbol
  symbol:   class Policy
  location: package com.systema.modernized.domain
[ERROR] DataSeedRunner.java:[63,38] cannot find symbol
  symbol:   class Policy
  location: package com.systema.modernized.domain
```
- **Reason**: The engine assumed `INVOICE01` was a Claims PAS project because it did not contain `BCMAIN`, thus trying to seed `Policy` objects which were never generated.

---

## 3. Recommended Architectural Fix

1. **Remove hardcoded template switches**: Replace templated Java class writes with metadata-driven entity/service generators.
2. **Derive domain fields from parser outcomes**: Use the variable mappings in the Semantic IR `DATA_ITEM` list to generate entities and item readers dynamically.
