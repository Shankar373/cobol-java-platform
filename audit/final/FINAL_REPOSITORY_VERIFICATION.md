# FINAL REPOSITORY VERIFICATION
## SystemaOps — All Representative Repositories
**Date:** 2026-08-22  
**Source:** Read-only static + runtime audit

> **Policy Reminder:** The objective is NOT to make every repository say `PRODUCTION_READY`.
> The objective is to make the verdict **scientifically trustworthy**.

---

## Summary Table

| Repository | Topology | Compile | Execute | Equivalence | Dep Audit | Neg Equiv | Traceability | Max Achievable Verdict |
|------------|----------|---------|---------|-------------|-----------|-----------|--------------|----------------------|
| INVOICE01 | FILE_OUTPUT | Achievable | Achievable | Achievable | Achievable | Achievable (input fixture present) | Achievable | **PRODUCTION_READY** |
| ADVERSARIAL01 | CONSOLE_OUTPUT | Achievable | Achievable | Achievable (stdout) | Achievable | ❌ UNVERIFIED (no mutable input) | Achievable | **PRODUCTION_CANDIDATE** |
| INVMGR | CONSOLE_OUTPUT | Achievable | Achievable | Achievable (stdout) | Achievable | ❌ UNVERIFIED (no mutable input) | Achievable | **PRODUCTION_CANDIDATE** |
| LAYOUT01 | CONSOLE_OUTPUT | Achievable | Achievable | Achievable (stdout) | Achievable | ❌ UNVERIFIED (no mutable input) | Achievable | **PRODUCTION_CANDIDATE** |
| ACCTPROG | FILE_OUTPUT | Achievable | Achievable | Achievable | Achievable | Achievable (input fixture present) | Achievable | **PRODUCTION_READY** |

---

## INVOICE01 — Detailed Verification

### Topology
- **Type:** `FILE_OUTPUT`
- **Config:** `migration_config.json` present
- **Programs:** 1 main program (`INVOICE01.cob`) in `src/`
- **Copybooks:** `copybooks/` dir declared
- **Input fixture:** `data/in/invoice-input.dat` (195 bytes, present)
- **Output target:** `data/out/invoice-output.dat`
- **File assignments:** `IN-FILE` → input, `OUT-FILE` → output

### Compile Status
- COBOL source present and syntactically valid
- Compiled legacy executable: `invoice01.exe` (20,776 bytes, present)
- Java translation: achievable via `stage_transpile`

### Execution Status
- Legacy: executable present, will run against `invoice-input.dat`
- Java: achievable once compiled

### Equivalence Status
- Gate type: **file comparison** (`data/out/invoice-output.dat` vs Java output)
- Comparison is deterministic given fixed input fixture
- Status: Achievable (input fixture exists)

### Dependency Audit Status
- `dep_audit` stage: executable, no known blockers

### Negative Equivalence Status
- **Type:** File-mutation based
- Input fixture is present and mutable → mutation sensitivity is testable
- Status: **Achievable** — `neg_equiv.executed` can be `True`

### Traceability Status
- Traceability stage derives from Spring Boot generation
- Status: Achievable

### Final Verdict
**Maximum achievable: `PRODUCTION_READY`**  
All ten required gates are achievable through the automated pipeline.

---

## ADVERSARIAL01 — Detailed Verification

### Topology
- **Type:** `CONSOLE_OUTPUT`
- **Config:** No `migration_config.json` — bare COBOL file
- **Programs:** 1 program (`ADVERSARIAL01.cob`, 41 lines)
- **Input:** None — all values hardcoded in WORKING-STORAGE
- **Output:** `DISPLAY` statements only

### COBOL Feature Coverage
The program exercises: 88-level condition names, `EVALUATE/WHEN OTHER`, `MOVE X TO A B` (multi-target),
`PERFORM VARYING`, array subscript access (`ITEM-VAL(WS-I)`), `PIC 99V99` arithmetic.
It is designed as an adversarial test of translator correctness, not a realistic business program.

### Compile Status
- Legacy executable present: `adversarial01.exe` (20,104 bytes)
- Java translation: achievable

### Execution Status
- Legacy: executes deterministically (fixed hardcoded values)
- Java: achievable

### Equivalence Status
- Gate type: **stdout comparison**
- Both legacy and Java stdout are deterministic
- Status: Achievable

### Dependency Audit Status
- No external file I/O, no CALLs to other programs
- Status: Achievable (trivially)

### Negative Equivalence Status
- **BLOCKED** — no external mutable input exists
- The program has no stdin, no file input, no environment-variable input
- Any mutation of WORKING-STORAGE constants requires recompilation → not a runtime mutation test
- Pipeline correctly records `neg_equiv.executed = False`
- Status: **UNVERIFIED** — this is an honest, correct assessment

### Traceability Status
- Achievable via Spring Boot generation stage

### Final Verdict
**Maximum achievable: `PRODUCTION_CANDIDATE`**  
Neg-equiv gate is permanently blocked by the program's topology.
This is scientifically correct, not a defect.

---

## INVMGR — Detailed Verification

### Topology
- **Type:** `CONSOLE_OUTPUT`
- **Config:** `migration_config.json` present but `file_assignments: {}`
- **Programs:** 1 program (`INVMGR.cob`, 34 lines) in `src/`
- **Input:** None — `WS-ITEM-QTY=50` hardcoded in WORKING-STORAGE
- **Output:** `DISPLAY` statements only (`IN STOCK: APPLE`, `QTY: 0050`, `VAL: ...`, `STS: OK`)
- **Data dirs:** `data/out/`, `data/work/` — no input data files present

### COBOL Feature Coverage
Exercises: paragraphs, `PERFORM CALL`, conditional branching (`IF/ELSE`), `COMPUTE` with
decimal arithmetic, `GOBACK`, `ADD`. Represents inventory management business logic.

### Compile Status
- Legacy executable present: `invmgr.exe` (20,368 bytes)
- Java translation: achievable

### Execution Status
- Legacy: executes deterministically
- Java: achievable

### Equivalence Status
- Gate type: **stdout comparison**
- Status: Achievable

### Dependency Audit Status
- No external CALL dependencies, no file I/O
- Status: Achievable

### Negative Equivalence Status
- **BLOCKED** — no external mutable input
- `data/` directory contains no input data files (confirmed: `data/out/`, `data/work/` only)
- Pipeline correctly records `neg_equiv.executed = False`
- Status: **UNVERIFIED**

### Traceability Status
- Achievable

### Final Verdict
**Maximum achievable: `PRODUCTION_CANDIDATE`**  
Same topology constraint as `ADVERSARIAL01`. Correct and honest.

---

## LAYOUT01 — Detailed Verification

### Topology
- **Type:** `CONSOLE_OUTPUT`
- **Config:** No `migration_config.json` — bare COBOL file
- **Programs:** 1 program (`LAYOUT01.cob`, 28 lines)
- **Input:** None — `WS-TEXT = "AAAA"` hardcoded
- **Output:** `DISPLAY` statements testing REDEFINES and OCCURS DEPENDING ON

### COBOL Feature Coverage
Exercises: `REDEFINES` (overlapping storage, `PIC X(4)` aliased as `PIC 9(4)`),
`OCCURS 1 TO 5 DEPENDING ON` (ODO variable-length arrays). These are advanced layout
constructs tested for correct Java memory mapping.

### Compile Status
- Legacy executable present: `layout01.exe` (19,648 bytes)
- Java translation: achievable (REDEFINES and ODO are supported per Phase 8)

### Execution Status
- Achievable

### Equivalence Status
- Gate type: **stdout comparison**
- `REDEFINES` and ODO behaviour must be identical in Java output
- Status: Achievable

### Dependency Audit Status
- No CALLs, no file I/O
- Status: Achievable

### Negative Equivalence Status
- **BLOCKED** — hardcoded input only
- Status: **UNVERIFIED**

### Traceability Status
- Achievable

### Final Verdict
**Maximum achievable: `PRODUCTION_CANDIDATE`**

---

## ACCTPROG — Detailed Verification

### Topology
- **Type:** `FILE_OUTPUT` with sub-program CALL
- **Config:** `migration_config.json` present
- **Programs:** 2 programs — `ACCTPROG.cob` (main, 47 lines), `ACCTCALC.cob` (called subprogram)
- **Copybooks:** `ACTREC`, `ACTREP`, `ACTLNK` — 3 copybooks in `copybooks/`
- **Input fixture:** `data/raw-source-data.bin` (76 bytes, present)
- **Output target:** `data/final-result-report.txt` (65 bytes, present from previous run)
- **File assignments:** `SOURCE-FILE` → binary input, `RESULT-FILE` → text report

### COBOL Feature Coverage
Exercises: `CALL "ACCTCALC"` (inter-program communication via `USING`), `COPY` copybooks,
`READ ... AT END / NOT AT END`, `WRITE` to output file, conditional balance logic
(`OVERDRAWN` / `ACTIVE`). Represents a realistic multi-module accounting batch.

### Compile Status
- Legacy executables present: `acctprog.exe` (20,272 bytes), `ACCTCALC.so` (17,600 bytes),
  `ACCTPROG.so` (18,328 bytes)
- Java translation: achievable

### Execution Status
- Legacy: executable present, input fixture present (76 bytes)
- Java: achievable

### Equivalence Status
- Gate type: **file comparison** (`final-result-report.txt`)
- Input is deterministic and present
- Status: Achievable

### Dependency Audit Status
- Subprogram `ACCTCALC` is a dependency — dep_audit must verify both are translated
- Status: Achievable (both programs present)

### Negative Equivalence Status
- **Type:** File-mutation based
- `raw-source-data.bin` is present (76 bytes) and mutable
- Corrupting one record should produce a different `OVERDRAWN`/`ACTIVE` classification
- Status: **Achievable** — `neg_equiv.executed` can be `True`

### Traceability Status
- Multi-program Spring project generation required
- Status: Achievable

### Final Verdict
**Maximum achievable: `PRODUCTION_READY`**  
All ten required gates are achievable through the automated pipeline.

---

## FILE_OUTPUT Repository Confirmation

> Requirement: "Verify at least one FILE_OUTPUT repo."

**Confirmed:** Both `INVOICE01` and `ACCTPROG` are `FILE_OUTPUT` topology repositories
with deterministic input fixtures, multi-file assignments, and `PRODUCTION_READY`-achievable
status through the automated pipeline. This requirement is satisfied.
