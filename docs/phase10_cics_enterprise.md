# Phase 10 — CICS Enterprise Runtime & Online Transaction Boundary
## Zero-Assumption Audit, Transaction Isolation, Flow Control & Compatibility Verification

**Classification Standard**: Evidence-Driven Mainframe Modernization Taxonomy  
**Date**: September 2026  
**Status**: `PARTIAL` (`COMPATIBILITY_PROVEN` for documented CICS/BMS subset | `REAL_CICS_MIDDLEWARE = UNPROVEN`)

---

## 1. Executive Summary

Phase 10 audits, hardens, and verifies the online transaction processing boundary for mainframe Enterprise COBOL programs utilizing IBM CICS (Customer Information Control System) and BMS (Basic Mapping Support) 3270 screens.

### Core Certification Principles
- **`CICS COMPATIBILITY != REAL CICS ON z/OS`**: Modernized Java services run on top of an in-process thread-safe semantic compatibility runtime (`CicsTransactionContext`, `CicsProgramRegistry`). Real IBM CICS region internals (MVS dispatching, VTAM/SNA terminal networks, CICS system tables FCT/PCT/PPT, CICS mirror transactions CSMI) are classified as **`UNPROVEN`**.
- **`BMS PARSING != 3270 HARDWARE EQUIVALENCE`**: BMS macros (`DFHMSD`, `DFHMDI`, `DFHMDF`) compile into typed Java DTOs. Real IBM 3270 hardware data streams (EBCDIC attribute bytes, write control characters, field outline attributes) are classified as **`UNPROVEN`**.
- **`FAIL-CLOSED DIAGNOSTICS`**: Unsupported CICS commands (such as direct CICS dataset I/O or distributed two-phase commit syncpoints) emit `ParserDiagnostic: CICS_UNSUPPORTED_COMMAND` at parse time, halting compilation before code generation.

---

## 2. Architecture & Transaction Model

```
                    Enterprise COBOL + EXEC CICS / BMS Macro
                                      │
                                      ▼
                      Deterministic Lexer & Parser
              (Tokens: EXEC_CICS, BMS Macros: DFHMSD/DFHMDI/DFHMDF)
                                      │
                                      ▼
                             Semantic IR Model
           (STATEMENT[EXEC_CICS], PROGRAM, VARIABLE, COMMAREA, DTOs)
                                      │
                                      ▼
                         Native Java / Spring Generator
        (Spring REST Services, DTOs, CicsTransactionContext, CicsProgramRegistry)
                                      │
                                      ▼
                 ThreadLocal CicsTransactionContext Runtime
         (TransactionState: transId, commarea, channels, containers, EIB, RESP)
                                      │
                                      ▼
                    8+ Concurrent Multithreaded Execution
             (Strict Request/Thread Isolation & Zero Cross-Talk)
                                      │
                                      ▼
                       Negative Mutation Verification
            (Invalid program PGMIDERR, Length mismatch LENGERR, MAPFAIL)
```

---

## 3. Comprehensive CICS Command Inventory & Implementation Status

| Command | COBOL Syntax Example | Modernized Java / Runtime Action | Classification |
| :--- | :--- | :--- | :--- |
| **`LINK`** | `EXEC CICS LINK PROGRAM('PROG') COMMAREA(WS-COM) LENGTH(10) RESP(RC) END-EXEC.` | `CicsProgramRegistry.invoke("PROG", ws_com)` with in/out reflection | `COMPATIBILITY_PROVEN` |
| **`XCTL`** | `EXEC CICS XCTL PROGRAM('PROG') COMMAREA(WS-COM) RESP(RC) END-EXEC.` | `CicsProgramRegistry.invoke(...)` followed by `programExited = true; return;` | `COMPATIBILITY_PROVEN` |
| **`RETURN`** | `EXEC CICS RETURN TRANSID('TRN2') COMMAREA(WS-COM) END-EXEC.` | `CicsTransactionContext.cicsReturn("TRN2", ws_com); return;` | `COMPATIBILITY_PROVEN` |
| **`PUT CONTAINER`**| `EXEC CICS PUT CONTAINER('REQ') CHANNEL('CHAN') FROM(WS-VAR) END-EXEC.` | `CicsTransactionContext.putStringContainer("CHAN", "REQ", ws_var)` | `COMPATIBILITY_PROVEN` |
| **`GET CONTAINER`**| `EXEC CICS GET CONTAINER('REQ') CHANNEL('CHAN') INTO(WS-VAR) END-EXEC.` | `CicsTransactionContext.getStringContainer("CHAN", "REQ")` | `COMPATIBILITY_PROVEN` |
| **`DELETE CONTAINER`**| `EXEC CICS DELETE CONTAINER('REQ') CHANNEL('CHAN') END-EXEC.` | `CicsTransactionContext.deleteContainer("CHAN", "REQ")` | `COMPATIBILITY_PROVEN` |
| **`SEND MAP`** | `EXEC CICS SEND MAP('M1') MAPSET('S1') FROM(WS-OUT) ERASE FREEKB END-EXEC.` | `CicsTransactionContext.send("M1", "S1", ws_out, sendOpts)` | `COMPATIBILITY_PROVEN` |
| **`RECEIVE MAP`** | `EXEC CICS RECEIVE MAP('M1') MAPSET('S1') INTO(WS-IN) RESP(RC) END-EXEC.` | `CicsTransactionContext.receive("M1", "S1", recvOpts)` | `COMPATIBILITY_PROVEN` |
| **`ABEND`** | `EXEC CICS ABEND ABCODE('AB01') END-EXEC.` | `CicsTransactionContext.cicsAbend("AB01")` (throws `CicsAbendException`) | `COMPATIBILITY_PROVEN` |
| **`ASKTIME`** | `EXEC CICS ASKTIME ABSTIME(WS-TIME) END-EXEC.` | `ws_time = System.currentTimeMillis();` | `COMPATIBILITY_PROVEN` |
| **`FORMATTIME`**| `EXEC CICS FORMATTIME ABSTIME(WS-T) YYYYMMDD(WS-D) TIME(WS-TM) END-EXEC.` | `DateTimeFormatter.ofPattern("yyyyMMdd")` & `("HHmmss")` | `COMPATIBILITY_PROVEN` |
| **`READ` (File)** | `EXEC CICS READ DATASET('FILE') INTO(REC) RIDFLD(KEY) END-EXEC.` | Emits `ParserDiagnostic: CICS_UNSUPPORTED_COMMAND` (Fail-Closed) | `UNSUPPORTED` |
| **`STARTBR/ENDBR`**| `EXEC CICS STARTBR DATASET('FILE') RIDFLD(KEY) END-EXEC.` | Emits `ParserDiagnostic: CICS_UNSUPPORTED_COMMAND` (Fail-Closed) | `UNSUPPORTED` |
| **`SYNCPOINT`** | `EXEC CICS SYNCPOINT END-EXEC.` | Emits `ParserDiagnostic: CICS_UNSUPPORTED_COMMAND` (Fail-Closed) | `UNSUPPORTED` |
| **`TSQ / TDQ`** | `EXEC CICS WRITEQ TS / TD ... END-EXEC.` | Emits `ParserDiagnostic: CICS_UNSUPPORTED_COMMAND` (Fail-Closed) | `UNSUPPORTED` |

---

## 4. COMMAREA & Channel/Container Semantics

1. **`DFHCOMMAREA` & `EIBCALEN` Binding**:
   - In callee subprograms, `LINKAGE SECTION` declarations of `01 DFHCOMMAREA` automatically bind to incoming transaction payload.
   - `EIBCALEN` is set to `commarea.length()`.
2. **Length Validation**:
   - Explicit `LENGTH(n)` in `EXEC CICS LINK` is checked against declared Working-Storage variable length at parse time. Mismatches trigger `CICS_COMMAREA_MISMATCH`.
3. **Channels & Containers**:
   - Channels act as named collections of typed byte / string containers stored within `TransactionState`.
   - Missing channels or containers set `DFHRESP_CHANNELERR` (122) and `DFHRESP_CONTAINERERR` (123).

---

## 5. CICS Response (EIBRESP / EIBRESP2) & Error Handling

All CICS operations update `EIBRESP` and `EIBRESP2` in `TransactionState` and copy results to explicit `RESP(var)` and `RESP2(var)` variables:

| Symbolic Response | Numeric Code | Trigger Condition |
| :--- | :--- | :--- |
| `DFHRESP_NORMAL` | `0` | Successful command execution |
| `DFHRESP_NOTFND` | `13` | Record or resource not found |
| `DFHRESP_INVREQ` | `16` | Invalid request / invalid options |
| `DFHRESP_LENGERR` | `22` | COMMAREA or container length error |
| `DFHRESP_PGMIDERR` | `27` | Target program not registered in `CicsProgramRegistry` |
| `DFHRESP_MAPFAIL` | `36` | Map receive failure / unmapped screen |
| `DFHRESP_CHANNELERR`| `122` | Channel not found or invalid |
| `DFHRESP_CONTAINERERR`| `123` | Container not found or invalid |
| `DFHRESP_ERROR` | `999` | Transaction ABEND |

---

## 6. Concurrency & Transaction Isolation Evidence

Tested via [`tests/component/cics/test_cics_transaction_isolation.py`](file:///c:/Users/bandi/Desktop/ai-workspace/Cobol-to-java-modernization/tests/component/cics/test_cics_transaction_isolation.py):
- **Concurrency**: 8 concurrent worker threads executed simultaneously via `ExecutorService`.
- **Payloads**: Each thread was assigned a unique transaction ID (`TRN0` through `TRN7`) and distinct container data (`THREAD-xx-PAYLOAD`).
- **Isolation Result**: 100% verified. Zero cross-thread state leakage or container collision.

---

## 7. BMS / 3270 Macro Parsing & Screen DTO Generation

- Parsed by [`modernize/bms_parser.py`](file:///c:/Users/bandi/Desktop/ai-workspace/Cobol-to-java-modernization/modernize/bms_parser.py):
  - `DFHMSD`: Mapset name, mode (`INOUT`), lang (`COBOL`), terminal type (`3270`).
  - `DFHMDI`: Map name, screen dimensions (`(24, 80)`), control options (`FREEKB`, `ALARM`, `ERASE`).
  - `DFHMDF`: Field name, position `(row, col)`, length, initial value, attributes (`PROT`, `ASKIP`, `NUM`, `FSET`, `BRT`, `NORM`, `DRK`), color, highlight.
- Generates strongly-typed Java DTO classes representing screen input and output structures.

---

## 8. Comprehensive Test & Verification Summary

| Test Suite | Test File | Test Count | Result |
| :--- | :--- | :--- | :--- |
| **BMS Parsing & DTO Generation** | `tests/component/cics/test_bms_mapping.py` | 2 | **PASS** |
| **COMMAREA & Channels** | `tests/component/cics/test_cics_commarea_channels.py` | 1 | **PASS** |
| **RESP Codes & ABEND** | `tests/component/cics/test_cics_error_resp.py` | 1 | **PASS** |
| **LINK / XCTL / RETURN Flow** | `tests/component/cics/test_cics_flow_control.py` | 2 | **PASS** |
| **Map Semantics & Options** | `tests/component/cics/test_cics_map_semantics.py` | 1 | **PASS** |
| **CICS Lexer & Parser Valid** | `tests/component/cics/test_cics_modernization.py` | 4 | **PASS** |
| **CICS Parser Comprehensive** | `tests/component/cics/test_cics_parser_comprehensive.py` | 6 | **PASS** |
| **Screen SEND/RECEIVE MAP** | `tests/component/cics/test_cics_screen_io.py` | 1 | **PASS** |
| **Multithreaded Isolation** | `tests/component/cics/test_cics_transaction_isolation.py` | 1 | **PASS** |
| **Phase 10 Production Gates** | `tests/test_phase10_gates.py` | 22 | **PASS** |
| **Total** | | **41** | **100% PASS** |

---

## 9. Final Phase 10 Classification Verdict

```
================================================================================
                   PHASE 10 FINAL CLASSIFICATION VERDICT
================================================================================

Overall Phase 10 Verdict: PARTIAL

Breakdown:
  1. CICS Parser & Lexer:                             UNIT_PROVEN
  2. CICS Semantic IR Model:                          UNIT_PROVEN
  3. BMS Macro Parser & Screen DTO Generation:        COMPATIBILITY_PROVEN
  4. LINK / XCTL / RETURN Flow Control:               COMPATIBILITY_PROVEN
  5. DFHCOMMAREA & EIBCALEN Binding:                  COMPATIBILITY_PROVEN
  6. Channels & Containers (PUT/GET/DELETE):          COMPATIBILITY_PROVEN
  7. EIB & Response Engine (RESP/RESP2):              COMPATIBILITY_PROVEN
  8. Multithreaded Transaction Isolation (8+ Threads):COMPATIBILITY_PROVEN
  9. Real IBM z/OS CICS Middleware:                   UNPROVEN
 10. Real 3270 / SNA Hardware Data Stream:            UNPROVEN
 11. CICS Dataset File Control (READ/WRITE/STARTBR):  UNSUPPORTED

Justification:
  The platform provides a proven, verified native Java/Spring compatibility
  runtime for online transaction processing across the documented CICS and BMS
  subset with 100% passing tests and verified multithreaded transaction isolation.
  However, because real IBM z/OS CICS middleware regions and physical 3270
  terminals were not executed, the honest and accurate verdict remains PARTIAL.
================================================================================
```
