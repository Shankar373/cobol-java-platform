# Mainframe Modernization Capability Matrix

**Classification Standard**: Evidence-Driven Taxonomy  
**Date**: September 2026

---

## 1. Evidence Level Definitions

- `E2E_PROVEN`: Verified via end-to-end execution of legacy COBOL baseline against modernized Java on real infrastructure producing identical business behavior.
- `COMPATIBILITY_PROVEN`: Modernized Java runtime semantics verified through deterministic component/unit suites (e.g. ThreadLocal transaction contexts, local indexed file navigation, batch step evaluation).
- `UNIT_PROVEN`: Parser, semantic IR, or generator unit tests pass with explicit assertions.
- `MOCK_PROVEN`: Verified only against simulated in-memory databases or synthetic mock responses.
- `UNPROVEN`: Middleware/infrastructure that is not executed in local/CI environments.

---

## 2. Comprehensive Construct Matrix

### A. Core COBOL Verbs & Data Types
| Feature Area | Construct | Parser Status | Generator Status | Runtime Status | Evidence Classification |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Numeric** | `PIC 9(n)`, `COMP`, `COMP-3`, `COMP-5` | Implemented | Implemented | `CobolNumeric` | `E2E_PROVEN` |
| **Numeric** | `ROUNDED`, `ON SIZE ERROR` | Implemented | Implemented | `CobolNumeric` | `E2E_PROVEN` |
| **Data Movement** | `MOVE`, `MOVE CORRESPONDING`, `INITIALIZE` | Implemented | Implemented | Plain Java | `E2E_PROVEN` |
| **Arithmetic** | `ADD`, `SUBTRACT`, `MULTIPLY`, `DIVIDE`, `COMPUTE` | Implemented | Implemented | `CobolNumeric` | `E2E_PROVEN` |
| **Tables** | `OCCURS`, `OCCURS DEPENDING ON`, `REDEFINES` | Implemented | Implemented | Plain Java / Layout | `E2E_PROVEN` |
| **Control Flow** | `PERFORM`, `PERFORM THRU`, `PERFORM VARYING` | Implemented | Implemented | Plain Java methods | `E2E_PROVEN` |
| **Control Flow** | `EVALUATE / WHEN`, `IF / ELSE`, `GO TO` | Implemented | Implemented | Switch / If / Loop | `E2E_PROVEN` |
| **Inter-Program** | `CALL ... USING BY REFERENCE / CONTENT / VALUE` | Implemented | Implemented | Java Method / Static | `E2E_PROVEN` |
| **Strings** | `STRING`, `UNSTRING`, `INSPECT`, Reference Mod | Implemented | Implemented | Java String / `CobolFormatHelper` | `E2E_PROVEN` |
| **File I/O** | `OPEN`, `CLOSE`, `READ`, `WRITE`, `REWRITE`, `FILE STATUS` | Implemented | Implemented | `CobolSequentialFile` | `E2E_PROVEN` |
| **Sorting / Merging** | `SORT`, `MERGE` (`USING` ... `GIVING`) | Implemented | Implemented | Collections / Streams | `E2E_PROVEN` |
| **Edited Output** | `PIC $$,$$9.99`, `ZZ,ZZ9.99`, `**,**9.99`, `CR`, `DB` | Implemented | Implemented | `CobolFormatHelper` | `E2E_PROVEN` |
| **VSAM KSDS** | `ORGANIZATION IS INDEXED`, `START`, `READ NEXT` | Implemented | Implemented | `CobolIndexedFile` | `COMPATIBILITY_PROVEN` |
| **Report Writer** | `REPORT SECTION`, `RD`, `INITIATE`, `GENERATE`, `TERMINATE` | Implemented | Implemented | Plain Java Stream | `COMPATIBILITY_PROVEN` |
| **Pointers** | `USAGE IS POINTER`, `SET ADDRESS OF` | Implemented | Implemented | Plain Java References | `COMPATIBILITY_PROVEN` |

### B. Enterprise Middleware & Extensions
| Subsystem | Construct | Parser Status | Generator Status | Runtime Status | Evidence Classification |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **EXEC SQL / DB2** | `SELECT`, `INSERT`, `UPDATE`, `DELETE` (Host Vars) | Implemented | Implemented | Spring `JdbcTemplate` (PostgreSQL) | `E2E_PROVEN` (PG) |
| **EXEC SQL / DB2** | `DECLARE`, `OPEN`, `FETCH`, `CLOSE` Cursors | Implemented | Implemented | Spring `SqlRowSet` Cursor Lifecycle | `E2E_PROVEN` (PG) |
| **EXEC SQL / DB2** | `INNER JOIN`, `LEFT OUTER JOIN`, Subqueries | Implemented | Implemented | ANSI SQL on PostgreSQL | `E2E_PROVEN` (PG) |
| **EXEC SQL / DB2** | Aggregates (`COUNT`, `SUM`, `AVG`), `GROUP BY` | Implemented | Implemented | ANSI SQL on PostgreSQL | `E2E_PROVEN` (PG) |
| **EXEC SQL / DB2** | NULL Indicators (`-1` / `0` `PIC S9(4) COMP`) | Implemented | Implemented | `rs.wasNull()` Indicator Logic | `E2E_PROVEN` (PG) |
| **EXEC SQL / DB2** | Dialect (`SYSDUMMY1`, `FETCH FIRST`, `WITH UR`) | Implemented | Implemented | AST Dialect Normalizer | `E2E_PROVEN` (PG) |
| **EXEC SQL / DB2** | `SQLCA` / `SQLCODE` / `SQLSTATE` Error Mapping | Implemented | Implemented | `Db2ErrorMapper` (Deterministic) | `E2E_PROVEN` (PG) |
| **EXEC SQL / DB2** | `COMMIT` & `ROLLBACK` Transaction Boundaries | Implemented | Implemented | `PlatformTransactionManager` | `E2E_PROVEN` (PG) |
| **EXEC SQL / DB2** | Parameterized Binding (`?` positional params) | Implemented | Implemented | Spring `JdbcTemplate` (Secure) | `E2E_PROVEN` (PG) |
| **JCL Batch** | `JOB`, `EXEC`, `DD`, `DISP`, `COND`, `IF/THEN/ELSE`, `SYMBOLS` | Implemented | Implemented | `JclStepContext` | `COMPATIBILITY_PROVEN` |
| **CICS Flow** | `LINK`, `XCTL`, `RETURN`, `TRANSID`, `COMMAREA`, `ABEND` | Implemented | Implemented | `CicsTransactionContext` | `COMPATIBILITY_PROVEN` |
| **CICS Channels** | `PUT CONTAINER`, `GET CONTAINER`, `DELETE CONTAINER` | Implemented | Implemented | `CicsTransactionContext` | `COMPATIBILITY_PROVEN` |
| **BMS 3270 Maps** | `DFHMSD`, `DFHMDI`, `DFHMDF`, `SEND MAP`, `RECEIVE MAP` | Implemented | Implemented | Typed Java Screen DTOs | `COMPATIBILITY_PROVEN` |
| **IMS / DL/I DB** | `CALL 'CBLTDLI'`, `EXEC DLI` (GU, GN, ISRT, DLET) | Fail-Closed | Blocked | N/A | `UNSUPPORTED` / `UNPROVEN` |
| **IMS TM** | Message GU/GN, Transaction Codes | Fail-Closed | Blocked | N/A | `UNSUPPORTED` / `UNPROVEN` |
| **IBM MQ Messaging** | `CALL 'MQCONN'`, `MQPUT`, `MQGET`, `MQCLOSE`, `MQDISC` | Fail-Closed | Blocked | N/A | `UNSUPPORTED` / `UNPROVEN` |
| **Real IBM z/OS CICS** | IBM CICS Region Subsystems, SNA/VTAM Terminals | N/A | N/A | N/A | `UNPROVEN` |
| **Real IBM z/OS DB2** | DB2 for z/OS Subsystems, EBCDIC Collations, DRDA | N/A | N/A | N/A | `UNPROVEN` |
| **Real IBM z/OS IMS** | IMS Database Engine, Hierarchical Buffer Pools | N/A | N/A | N/A | `UNPROVEN` |
| **Real IBM MQ Server** | IBM MQ Queue Manager Server on z/OS | N/A | N/A | N/A | `UNPROVEN` |
| **Distributed / XA** | Two-Phase Commit Distributed Transactions | N/A | N/A | N/A | `UNSUPPORTED` |
