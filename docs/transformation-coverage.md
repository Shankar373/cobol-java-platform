# COBOL → Java Transformation Coverage

> **Auto-generated** from `modernize/capability_matrix.py`. Do not edit manually.

## Evidence Taxonomy

| Level | Meaning |
|---|---|
| `UNSUPPORTED` | No detection, no parsing, no generation |
| `PARSED_ONLY` | Parsed into IR but no Java generated (or stub/comment only) |
| `GENERATED_ONLY` | Java generated but never executed in a differential test |
| `UNIT_TESTED` | Unit-tested in isolation (Java compile + run) without GnuCOBOL comparison |
| `DIFFERENTIALLY_VERIFIED` | GnuCOBOL and Java both ran, relevant outputs compared, reproducible in CI |
| `PRODUCTION_QUALIFIED` | Reserved — not claimed for any feature yet |

> [!IMPORTANT]
> A feature may only be marked `DIFFERENTIALLY_VERIFIED` if there is a passing `run_parity()` test in `tests/test_parity_fixtures.py` that compares GnuCOBOL and generated Java output.

---

## PIC / USAGE

| Construct | Evidence Level | Notes / Known Limitations |
|---|---|---|
| PIC 9 / S9 DISPLAY numeric | `DIFFERENTIALLY_VERIFIED` | |
| PIC X alphanumeric | `DIFFERENTIALLY_VERIFIED` | |
| PIC edited numeric (Z, *, $, CR, DB) | `UNIT_TESTED` | CR/DB suffix editing not fully tested |
| PIC edited alpha | `UNIT_TESTED` | |
| USAGE DISPLAY | `DIFFERENTIALLY_VERIFIED` | |
| USAGE COMP / COMP-4 / BINARY | `UNIT_TESTED` | COMP-1 (float) and COMP-2 (double) **unsupported** |
| USAGE COMP-3 / PACKED-DECIMAL | `DIFFERENTIALLY_VERIFIED` | Negative zero not separately tested |
| USAGE COMP-5 | `GENERATED_ONLY` | Native-endian binary not verified differentially |
| USAGE INDEX | `UNSUPPORTED` | Produces no numeric semantics |

---

## Arithmetic

| Construct | Evidence Level | Notes / Known Limitations |
|---|---|---|
| ADD | `DIFFERENTIALLY_VERIFIED` | ADD CORRESPONDING **unsupported** |
| SUBTRACT | `DIFFERENTIALLY_VERIFIED` | SUBTRACT CORRESPONDING **unsupported** |
| MULTIPLY | `DIFFERENTIALLY_VERIFIED` | MULTIPLY CORRESPONDING **unsupported** |
| DIVIDE / DIVIDE … REMAINDER | `DIFFERENTIALLY_VERIFIED` | Recurring decimal truncated to target PIC scale |
| COMPUTE (expression) | `DIFFERENTIALLY_VERIFIED` | Fractional exponents are unsupported and fail-fast with a clear diagnostic (no double math) |
| ROUNDED | `DIFFERENTIALLY_VERIFIED` | Only `NEAREST_AWAY_FROM_ZERO` (HALF_UP) emitted; `ROUNDED MODE IS` clause not supported |
| ON SIZE ERROR / NOT ON SIZE ERROR | `DIFFERENTIALLY_VERIFIED` | NOT ON SIZE ERROR path has limited test coverage |

---

## MOVE

| Construct | Evidence Level | Notes / Known Limitations |
|---|---|---|
| MOVE alpha → alpha | `DIFFERENTIALLY_VERIFIED` | |
| MOVE numeric → numeric | `DIFFERENTIALLY_VERIFIED` | MOVE CORRESPONDING **unsupported** |
| MOVE group → group | `UNIT_TESTED` | Byte-exact differential not verified |

---

## REDEFINES / OCCURS

| Construct | Evidence Level | Notes / Known Limitations |
|---|---|---|
| REDEFINES scalar view | `DIFFERENTIALLY_VERIFIED` | |
| REDEFINES group view | `DIFFERENTIALLY_VERIFIED` | |
| REDEFINES COMP-3 byte view | `DIFFERENTIALLY_VERIFIED` | |
| REDEFINES nested complex | `PARSED_ONLY` | REDEFINES of OCCURS-containing group **not generated** |
| OCCURS fixed | `UNIT_TESTED` | OCCURS inside REDEFINES not differentially verified |
| OCCURS DEPENDING ON | `GENERATED_ONLY` | Runtime bounds not differentially verified |

---

## Procedure Division / Control Flow

| Construct | Evidence Level | Notes / Known Limitations |
|---|---|---|
| PERFORM paragraph | `UNIT_TESTED` | |
| PERFORM THRU | `UNIT_TESTED` | EXIT PARAGRAPH inside range not differentially verified |
| PERFORM VARYING | `DIFFERENTIALLY_VERIFIED` | Multi-varying loops (AFTER clause) not fully supported |
| GO TO | `UNIT_TESTED` | GO TO DEPENDING ON **unsupported** |
| CALL static | `UNIT_TESTED` | BY VALUE, BY CONTENT isolation not differentially verified |
| CALL dynamic | `GENERATED_ONLY` | Unknown registry targets produce diagnostic |
| CALL BY REFERENCE | `UNIT_TESTED` | Caller-visible mutation not differentially verified |
| CALL BY CONTENT | `DIFFERENTIALLY_VERIFIED` | |
| GOBACK | `UNIT_TESTED` | |
| STOP RUN | `UNIT_TESTED` | |
| EVALUATE | `UNIT_TESTED` | Multi-subject EVALUATE TRUE ALSO TRUE not differentially verified |
| IF / ELSE | `UNIT_TESTED` | |
| Sections / fall-through | `GENERATED_ONLY` | PERFORM THRU across sections not differentially verified |

---

## String Handling

| Construct | Evidence Level | Notes |
|---|---|---|
| STRING … INTO | `UNIT_TESTED` | |
| UNSTRING … INTO | `UNIT_TESTED` | |
| INSPECT … TALLYING / REPLACING | `UNIT_TESTED` | |

---

## File I/O

| Construct | Evidence Level | Notes / Known Limitations |
|---|---|---|
| LINE SEQUENTIAL (read/write) | `DIFFERENTIALLY_VERIFIED` | |
| SEQUENTIAL fixed-length | `UNIT_TESTED` | Record boundary enforced by newline internally — **not byte-safe for binary** |
| SEQUENTIAL EBCDIC | `UNSUPPORTED` | No EBCDIC charset codec in file path |
| RELATIVE files (random access) | `UNIT_TESTED` | Numeric RRN stored as string key |
| INDEXED KSDS (READ/WRITE/START) | `UNIT_TESTED` | Alternate indexes partial; duplicate keys tested |
| FILE STATUS after each op | `UNIT_TESTED` | Not captured in parity harness `ExecutionResult` |
| Variable-length / RDW records | `UNSUPPORTED` | RECORDING MODE V/U not supported |

---

## Embedded SQL (DB2)

| Construct | Evidence Level | Notes / Known Limitations |
|---|---|---|
| SELECT INTO | `UNIT_TESTED` | Not differentially verified vs GnuCOBOL (blocked at baseline) |
| INSERT | `UNIT_TESTED` | |
| UPDATE | `UNIT_TESTED` | |
| DELETE | `UNIT_TESTED` | |
| DECLARE/OPEN/FETCH/CLOSE CURSOR | `UNIT_TESTED` | Cursor paging not differentially verified |
| NULL indicators | `UNIT_TESTED` | |
| COMMIT / ROLLBACK | `UNIT_TESTED` | Transaction boundary behavior not differentially verified |
| SQLCODE / SQLSTATE | `UNIT_TESTED` | Not captured in parity harness `ExecutionResult` |
| Host variables | `UNIT_TESTED` | |

> [!NOTE]
> SQL features cannot reach `DIFFERENTIALLY_VERIFIED` via GnuCOBOL (DB2/CICS blocked at baseline). Differential verification requires a separate SQL-mock baseline approach.

---

## EXEC CICS

| Construct | Evidence Level | Notes / Known Limitations |
|---|---|---|
| SEND MAP | `PARSED_ONLY` | Stubbed; no BMS map semantics |
| RECEIVE MAP | `PARSED_ONLY` | Stubbed |
| LINK | `PARSED_ONLY` | Stubbed |
| RETURN | `PARSED_ONLY` | Stubbed |
| RESP / RESP2 fields | `PARSED_ONLY` | Set to 0 by stub; not behaviorally verified |
| All other CICS commands | `PARSED_ONLY` | Stubbed with diagnostic comment; complete list in capability_matrix.py |

---

## JCL

| Construct | Evidence Level | Notes / Known Limitations |
|---|---|---|
| JOB card | `UNIT_TESTED` | Parameters not fully mapped |
| EXEC PGM= | `UNIT_TESTED` | COND parameter routing partial |
| DD statement | `UNIT_TESTED` | DISP disposition not modeled; UNIT=TAPE **unsupported** |
| COND= parameter | `UNIT_TESTED` | COND=ONLY and COND=EVEN **not verified** |
| IF/THEN/ELSE block | `GENERATED_ONLY` | Step routing generated but not differentially verified |
| Symbolic parameters | `UNIT_TESTED` | |

---

## Unsupported / Blocked Areas

| Area | Evidence Level | Action Required |
|---|---|---|
| IMS DL/I (`EXEC DLI`, `CBLTDLI`) | `UNSUPPORTED` | Blocked at baseline; stubbed in transpile preprocessing. Diagnostic: `COBOL_UNSUPPORTED_IMS_CALL` |
| IBM MQ Series (`CALL 'MQPUT'`, `COPY CMQV`) | `UNSUPPORTED` | MQ copybooks missing; compilation fails. Diagnostic: `COBOL_UNSUPPORTED_MQ_CALL` |
| Report Writer | `PARSED_ONLY` | Section parsed, not generated. Diagnostic: `COBOL_UNSUPPORTED_REPORT_WRITER` |
| EBCDIC file I/O | `UNSUPPORTED` | No codec. Diagnostic: `COBOL_UNSUPPORTED_RECORD_FORMAT` |
| Variable-length records (RDW) | `UNSUPPORTED` | No RDW. Diagnostic: `COBOL_UNSUPPORTED_RECORD_FORMAT` |
| COMP-1 / COMP-2 (float/double) | `UNSUPPORTED` | Produces diagnostic; never maps to Java float/double |
| GO TO DEPENDING ON | `UNSUPPORTED` | Produces diagnostic |
| OCCURS DEPENDING ON (runtime) | `GENERATED_ONLY` | Generated but bounds not verified |
| SORT with INPUT/OUTPUT PROCEDURE | `UNIT_TESTED` | Partially; complex PROCEDURE not verified |
| SET ADDRESS OF linkage | `UNSUPPORTED` | |
| Non-integer COMPUTE ** exponent | `GENERATED_ONLY` | Fractional exponents are unsupported and fail-fast with a clear diagnostic (no double math) |
| COND=ONLY / COND=EVEN (JCL) | `GENERATED_ONLY` | Not verified |

---

## Summary Counts

| Evidence Level | Count |
|---|---|
| DIFFERENTIALLY_VERIFIED | 19 |
| UNIT_TESTED | 38 |
| GENERATED_ONLY | 5 |
| PARSED_ONLY | 8 |
| UNSUPPORTED | 5 |
| **Total** | **75** |
