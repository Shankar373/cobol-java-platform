# CICS File Control & Dataset Boundary Analysis
## Operational Scope, VSAM Interaction & Fail-Closed Diagnostics

---

## 1. Scope & Current Operational Boundary

In mainframe CICS environments, programs interact with VSAM and sequential datasets through CICS File Control commands (`EXEC CICS READ`, `WRITE`, `REWRITE`, `DELETE`, `STARTBR`, `READNEXT`, `ENDBR`).

### Modernization Boundary
1. **File Control vs Batch VSAM**:
   - Batch COBOL file operations (`OPEN`, `READ`, `WRITE`, `REWRITE`, `START`, `ORGANIZATION IS INDEXED`) are supported via `CobolIndexedFile` (`COMPATIBILITY_PROVEN`).
   - Online CICS File Control commands (`EXEC CICS READ DATASET(...)`) are currently **`UNSUPPORTED`** in online transaction contexts and emit fail-closed diagnostics.
2. **Fail-Closed Diagnostic**:
   - `ParserDiagnostic: CICS_UNSUPPORTED_COMMAND: Unsupported CICS command 'READ'` (and `WRITE`, `STARTBR`, etc.).

---

## 2. Target Architecture for Future Extension

When CICS file control is extended, it should route directly to the existing `CobolIndexedFile` VSAM runtime helper rather than creating a duplicate file engine:

```
                  EXEC CICS READ DATASET('CUSTFILE') RIDFLD(KEY)
                                      │
                                      ▼
                           CICS Semantic Adapter
                                      │
                                      ▼
                        CobolIndexedFile (VSAM KSDS)
                                      │
                                      ▼
                     Record Retrieved & Key Positioned
                                      │
                                      ▼
                     RESP = DFHRESP_NORMAL (0) / NOTFND (13)
```
