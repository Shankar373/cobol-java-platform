# Modernization Verification Protocol & Evidence Standards

---

## 1. Differential Verification Protocol

For every modernizable construct, the platform requires an executable differential comparison:

```
          Initial State A (Input files, seeded DB)
                   ↓
        -----------------------
        |                     |
   Legacy COBOL          Modern Java
        ↓                     ↓
   State B (stdout,      State B' (stdout,
   out files, DB)        out files, DB)
        |                     |
        -----------------------
                   ↓
           Compare B == B'
```

### Strict Verification Rules
1. **Identical Initial Conditions**: Input datasets and database schemas must be reset before both legacy baseline and modern Java execution.
2. **Byte-Level File Comparison**: Record layouts, byte lengths, and numeric values in output datasets are compared byte-for-byte.
3. **Database Consistency**: Seeded records and mutated rows are queried and compared via deterministic ordering (`ORDER BY pk`).
4. **No Synthesized Verification**: Passing unit tests or mock tests do not grant `E2E_PROVEN` status.

---

## 2. Test Suite Architecture

1. **Skills Architecture Suite** (`tests/test_skills_architecture.py`):
   - 9 automated tests verifying skill specifications, validator negative cases, multi-fixture discovery, registry matching, and pipeline parity.
2. **Phase 8 Advanced Semantics Suite** (`tests/test_phase8_*.py`):
   - 119 automated tests covering REDEFINES shared storage, OCCURS DEPENDING ON bounds checking, SORT/MERGE pipeline execution, edited picture formatting, string operations (INSPECT, UNSTRING), nested programs, and pointer semantics.
3. **Component Test Suite** (`tests/component/`):
   - Unit and semantic tests for CICS (`tests/component/cics/`), JCL (`tests/component/jcl/`), DB/SQL (`tests/component/db/`), Arithmetic (`tests/component/arithmetic/`), and Parser (`tests/component/parser/`).
4. **Parity Fixture Suite** (`tests/test_parity_fixtures.py`):
   - 61 differential parity tests executed against GnuCOBOL baseline and PostgreSQL database.
5. **Phase 9 DB2 & Enterprise SQL Suite** (`tests/test_db2_acceptance.py`, `tests/test_db2_stage1.py`, `tests/component/db/*`, `tests/test_phase9_*.py`):
   - 128 automated tests verifying SELECT, INSERT, UPDATE, DELETE, Cursors, INNER/LEFT JOINs, Aggregates, GROUP BY, Subqueries, NULL indicators, Db2ErrorMapper SQLCODE/SQLSTATE translation, and transaction visibility against live PostgreSQL.
6. **Phase 10 CICS Enterprise Runtime Suite** (`tests/component/cics/*`, `tests/test_phase10_gates.py`):
   - 41 automated tests verifying LINK, XCTL, RETURN, COMMAREA in/out mutation, Channels & Containers, BMS screen DTOs, EIB & RESP codes, and 8-thread concurrent transaction isolation.
7. **Phase 11 IMS / MQ Boundary Suite** (`tests/test_phase11_ims_mq.py`, `tests/test_phase8_diagnostics.py`):
   - 5 automated tests asserting fail-closed NATIVE_TRANSLATION_BLOCKED diagnostics for CBLTDLI/ASMTDLI and MQCONN/MQPUT/MQGET/MQDISC calls.
8. **Certification Hardening Suite** (`tests/test_certification_hardening.py`):
   - Asserts capability matrix classifications and enforces that unproven middleware remains classified as `UNPROVEN`.
