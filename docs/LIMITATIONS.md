# Known Limitations & Unsupported Constructs

---

## 1. Supported vs Unsupported Summary

The platform supports modernizing batch, file-oriented, relational SQL (DB2/PostgreSQL), online transaction (CICS/BMS), and advanced language features (REDEFINES, ODO, SORT/MERGE, PIC editing, INSPECT/UNSTRING). The following boundaries define current operational limits.

---

## 2. Unsupported Subsystems & Features (Fail-Closed)

1. **Unsupported CICS Commands**:
   - `EXEC CICS READ`, `WRITE`, `REWRITE`, `DELETE` (Dataset direct I/O via CICS)
   - `EXEC CICS START`, `SYNCPOINT`
   - *Diagnostic*: Emits `CICS_UNSUPPORTED_COMMAND` at parse time.
2. **IMS / DL/I Databases**:
   - `EXEC DLI` / `CBLTDLI` calls for hierarchical IMS databases are unsupported.
3. **EBCDIC Collating Sequences**:
   - Custom mainframe EBCDIC collation sort tables (`PROGRAM COLLATING SEQUENCE IS EBCDIC`) are classified as `UNSUPPORTED`. Standard ASCII/UTF-8 collation is used in modernized Java.
4. **Hardware / Middleware Architecture Limits**:
   - Real IBM z/OS CICS middleware regions, 3270 SNA terminal hardware, and native DB2 for z/OS subsystems are not executed. Modernized applications run on standard JVM and PostgreSQL/Spring infrastructure.
5. **Report Writer Section**:
   - Programs utilizing `REPORT SECTION` (`GENERATE`, `INITIATE`, `TERMINATE`) are parsed and handled via Java stream generation; native mainframe layout formatting without procedural logic is classified as `COMPATIBILITY_PROVEN`.
6. **DB2 / Relational SQL Boundaries**:
   - `REAL_DB2_ZOS = UNPROVEN`: Validated on PostgreSQL target container. Real IBM DB2 for z/OS (DRDA, EBCDIC catalog tables, DSN commands) requires z/OS infrastructure.
   - `Distributed / XA Transactions`: Multi-resource two-phase commit is `UNSUPPORTED`.
   - `DB2 XML / JSON SQL Data Types`: `XMLPARSE`, `JSON_OBJECT` are not parsed.
   - `Dynamic SQL Package Calling`: Dynamic `CALL DSNUTILS` or DB2 catalog packages are `UNSUPPORTED`.
7. **IMS & IBM MQ Integration Boundaries**:
   - `REAL_IMS = UNPROVEN` & `REAL_MQ = UNPROVEN`: Real IBM IMS DB/TM and IBM MQ queue manager subsystems on z/OS are unexecuted.
   - `IMS DL/I Calls`: Calls to `CBLTDLI`, `ASMTDLI`, `PLITDLI`, `EXEC DLI` emit `NATIVE_TRANSLATION_BLOCKED` diagnostics and are `UNSUPPORTED`.
   - `IBM MQ Calls`: Calls to `MQCONN`, `MQOPEN`, `MQPUT`, `MQGET`, `MQCLOSE`, `MQDISC` emit `NATIVE_TRANSLATION_BLOCKED` diagnostics and are `UNSUPPORTED`.
