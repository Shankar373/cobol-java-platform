# Phase 1 Pipeline Audit & Gap Analysis

## 1. What is Real Today
These capabilities compile and execute successfully on both the COBOL (baseline) and Java (modernized) sides, with differential verification of stdout/files in our test suite:
- **Data Types**: USAGE DISPLAY (character), PIC 9/S9 DISPLAY numeric, USAGE COMP-3 (packed decimal), alphanumeric slicing.
- **Arithmetic**: ADD, SUBTRACT, MULTIPLY, DIVIDE (with REMAINDER), COMPUTE (scalar expressions), ROUNDED (HALF_UP mode), and ON SIZE ERROR handling.
- **Control Flow**: Paragraph PERFORM, PERFORM THRU range, basic IF/ELSE, STOP RUN and GOBACK propagation, basic single/dual-subject EVALUATE switches.
- **File I/O**: LINE SEQUENTIAL sequential read/write operations.
- **JCL Structure**: JOB statement parsing, EXEC PGM program invocation routing, step return code tracking, and simple DD assignments.

## 2. What is Stubbed, Mocked, or Skipped
These capabilities are either bypassed during verification or emulated via local stubs:
- **Embedded SQL (DB2)**:
  - *COBOL Baseline*: Previously completely blocked because GnuCOBOL lacked an SQL precompiler.
  - *Java Side*: JDBC/JPA calls are mapped to local H2 in-memory structures or mocked using `mock_db.yaml`. No live Postgres compilation/run check occurred.
- **EXEC CICS**:
  - *All Commands*: SEND MAP, RECEIVE MAP, LINK, and RETURN generate stub outputs or debug messages.
  - *BMS Maps*: BMS files (`.bms`) are registered in discovery but fields are not parsed or mapped to layout models.
  - *EIB Fields*: Transaction context fields (EIBTRNID, EIBCALEN, EIBRESP) are stub constants returning 0 or placeholder strings.
- **VSAM KSDS / Indexed Access**:
  - emulated using a local SQLite/H2 JDBC table or raw key-value store structure, lacking scalable database-backed alternate index mapping or transaction boundaries.
- **Hierarchical/Messaging Middleware**:
  - *IMS/DLI*: `EXEC DLI` and `CBLTDLI` calls are parsed as unsupported diagnostics.
  - *IBM MQ*: `MQPUT`/`MQGET` calls are stubbed; missing MQ copybooks (CMQV) prevent baseline compilation.

## 3. What is Broken or Unproven
These issues or edge cases fail to compile, fail to execute, or are not differentially compared:
- **Parser/Generator Diagnostics**:
  - `EVALUATE ALSO` (multi-subject) with >2 subjects crashes parser.
  - `REDEFINES` of an `OCCURS`-containing group causes layout expansion failures.
  - `PERFORM VARYING ... AFTER` drops the inner loop body during code-gen.
- **Database Mapping**:
  - Modernized JPA entities map COMP/BINARY to `BigDecimal` (should be `Integer`/`Long` for Spring Batch performance).
  - Raw hyphenated column names are emitted in `@Column` annotations, causing Hibernate schema creation failures.
- **Execution & Orchestration**:
  - Modernized program compilation fails to find runtime helpers (like `JclExecutionContext`) when compiled standalone outside the parity harness.
  - Trailing space normalization is skipped for binary outputs, leading to false mismatches on packed decimal sequences.

## 4. Priority List for Phase-1
The following high-priority capabilities will be modernized and verified during Phase 1:
1. **Real Embedded SQL Baseline (ocesql + Postgres)**: Preprocess COBOL using ocesql and run baseline matches directly against PostgreSQL.
2. **Real Java Build & Execution (Maven)**: Ensure all generated classes compile, package, and run as standalone Maven projects against PostgreSQL.
3. **Database-Backed KSDS Emulation**: Model VSAM KSDS key-value structures onto Postgres tables with full sequential positioning (`START KEY IS`).
4. **Spring Boot CICS/BMS MVC Layer**: Parse BMS map files to Java models and wire `EXEC CICS` to Spring REST MVC controllers.
5. **Sanitize JPA Mapping**: Automate column name hyphen sanitization and map binary numeric fields to Java `Integer`/`Long`.
