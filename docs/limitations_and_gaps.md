# COBOL to Java Modernization: Limitations and Gaps

> Status: Current as of Phase 3 (August 2026).
> Scope: All stages 0-12, all COBOL features, all enterprise middleware.
> See also: pipeline_execution_limits.md, transformation-coverage.md, baseline_limits.md

---

## 1. Pipeline-Stage Limitations

### Stage 0 - Ingest

| Issue | Type | Severity |
|---|---|---|
| ZIP archives with non-UTF-8 filenames silently drop files | Gap | P1 |
| Very large repositories (>500 MB) time out in hashing | Bug | P2 |
| No detection of EBCDIC-encoded source files - treated as Latin-1 | Gap | P1 |

### Stage 1 - Discover

| Issue | Type | Severity |
|---|---|---|
| Copybook resolution is path-based only; COPY IN library cross-library references not followed | Gap | P1 |
| Nested copybooks (copybook that COPYs another) are partially resolved; third-level nesting fails silently | Bug | P1 |
| Multiple PROGRAM-ID in a single source file (nested programs) can cause the wrong entry point to be detected | Bug | P1 |
| VSAM KSDS ALTERNATE RECORD KEY clauses discovered but not used to drive alternate-index emulation | Gap | P2 |
| BMS map files (.bms) are indexed by file extension but no content is parsed or mapped | Gap | P1 |
| JCL files catalogued but PROC libraries and INCLUDE groups not expanded | Gap | P1 |

### Stage 2 - Analyze

| Issue | Type | Severity |
|---|---|---|
| Parser crashes on multi-subject EVALUATE (EVALUATE A ALSO B) with more than two subjects | Bug | P1 |
| GO TO DEPENDING ON parsed but immediately raises ParserDiagnostic; no IR node generated | Known Gap | P1 |
| ADD CORRESPONDING / SUBTRACT CORRESPONDING / MOVE CORRESPONDING are parsed but no field-matching IR generated | Gap | P1 |
| Reference modification on group-level items (GROUP-VAR(2:4)) parsed but treated as scalar string slicing | Bug | P1 |
| Complex REDEFINES of an OCCURS-containing group - IR generated but group expansion fails in code-gen | Bug | P0 |
| OCCURS DEPENDING ON bounds computed at parse time rather than runtime; subscript validation is static | Bug | P1 |
| CICS RESP / RESP2 field reads from EIB are stubbed to 0; no mock-programmable response | Gap | P1 |
| Very long PROCEDURE DIVISION sections (>10,000 lines) cause O(n^2) paragraph lookup performance | Bug | P2 |
| COPY REPLACING with partial word replacement (==:TAG:==) not handled | Bug | P1 |

### Stage 3 - Baseline

| Issue | Type | Severity |
|---|---|---|
| EXEC SQL, EXEC CICS, EXEC DLI - baseline is entirely blocked; no mock-baseline path exists | Known Gap | P0 |
| IBM MQ copybooks (CMQV, CMQODV) not included - compilation fails with No such file | Known Gap | P1 |
| GnuCOBOL 3.1 COMP-5 (native-endian binary) semantics differ from IBM z/Architecture big-endian | Gap | P1 |
| Signed EBCDIC overpunch (SIGN IS SEPARATE CHARACTER) behavior differs from GnuCOBOL defaults | Bug | P2 |
| Programs using SORT with INPUT PROCEDURE / OUTPUT PROCEDURE produce incorrect sort file paths on Windows | Bug | P2 |

### Stage 4 - Transpile

| Issue | Type | Severity |
|---|---|---|
| cobj transpiler path is optional/external; if absent pipeline falls back to native generator only | Gap | P1 |
| Transpile stage does not pass copybook directories to cobj; nested copybooks fail | Bug | P1 |

### Stage 5 - Collect

| Issue | Type | Severity |
|---|---|---|
| Spring/JPA runtime JARs not on classpath during native-generator execution path | Gap | P2 |

### Stage 6 - Generate

| Issue | Type | Severity |
|---|---|---|
| SpringContextHelper.jdbcTemplate is initialized to null; no H2 DataSource is wired at startup for native-execution path | Bug | P0 |
| Db2ErrorMapper.getSqlCode() returns generic -1 for non-SQLException; error classification incomplete | Bug | P2 |
| Generated VSAM KSDS table DDL uses VARCHAR(255) for key column; truncates keys longer than 255 bytes | Bug | P1 |
| Cursor variables (e.g. cursor_c1) declared at method scope but referenced across paragraph methods - Java compile errors | Bug | P0 |
| Programs with multiple EXEC SQL DECLARE CURSOR for the same cursor name produce duplicate variable declarations | Bug | P1 |
| BY CONTENT snapshot type inference falls back to String for BigDecimal fields when var_types lookup misses | Bug | P1 |

### Stage 7 - Execute

| Issue | Type | Severity |
|---|---|---|
| Java class compilation classpath does not include runtime helpers from java_helpers/ when running outside parity harness | Bug | P0 |
| Programs using STOP RUN inside PERFORM loop do not propagate exit through nested perform() calls in all cases | Bug | P1 |
| Division-by-zero produces ArithmeticException (exit code 1); GnuCOBOL exits with SIGFPE (exit code 136) | Known Gap | P2 |

### Stage 8 - Compare (Gate 1)

| Issue | Type | Severity |
|---|---|---|
| Trailing-space normalization applied to text but not binary output; COMP-3 byte sequences may differ | Bug | P1 |
| SQLite database state comparison is not performed - only text/file output is Gate-1 compared | Gap | P1 |
| File output comparison is byte-for-byte; EBCDIC vs ASCII encoding differences cause false-positive mismatches | Known Gap | P1 |

### Stage 9 - Refactor (Enterprise Generator)

| Issue | Type | Severity |
|---|---|---|
| EnterpriseApplicationGenerator._write_jpa_entity() maps all COBOL numeric fields to BigDecimal; COMP/BINARY fields should map to Integer/Long | Bug | P0 |
| JPA @Column(name=...) annotation uses raw COBOL field name with hyphens, causing Hibernate schema creation failure | Bug | P0 |
| Spring Batch ItemReader uses a hardcoded file path data/in/transactions.dat not derived from discovered file assigns | Bug | P1 |
| Generated pom.xml declares spring-boot-starter-data-jpa but native-gen programs still reference SpringContextHelper (not a Spring bean) | Bug | P1 |
| CICS to REST controller is a stub; no BMS field-JSON payload mapping is generated | Gap | P1 |
| JCL step to Spring Batch step mapping is framework-only; step readers/writers/processors contain placeholder TODO bodies | Gap | P1 |
| REPORT SECTION programs produce no batch step equivalent; report lines are discarded | Gap | P2 |

### Stage 10 - Validate (Gate 2)

| Issue | Type | Severity |
|---|---|---|
| Maven compilation fails when @Entity class has hyphenated @Column(name=...) (Hibernate validation rejects it) | Bug | P0 |
| Gate 2 waits up to 120 s for Spring Boot startup; complex JPA schema creation on H2 can exceed this timeout | Bug | P1 |
| Gate 2 only compares files listed in baseline_files; DB state (H2 rows) is not compared | Gap | P1 |
| validate_port selection logic can collide between concurrent pipeline runs | Bug | P2 |
| batch.input path resolution falls back to data/in/transactions.dat even when discovered assigns point elsewhere | Bug | P1 |
| Gate 2 semantic comparator (pipe_records) assumes pipe-delimited format; programs producing other formats fail | Gap | P1 |

### Stage 11 - Report

| Issue | Type | Severity |
|---|---|---|
| Report references db2_status but only classifies from env vars; H2-executed programs show REAL_DB2_NOT_CONFIGURED not H2_VERIFIED | Bug | P2 |

### Stage 12 - Package

| Issue | Type | Severity |
|---|---|---|
| Large target/ directories (>100 MB) are excluded from ZIP silently; no warning emitted | Gap | P2 |

---

## 2. COBOL Feature Gaps

### 2.1 Numeric / Decimal Edge Cases

| Feature | Evidence Level | Gap |
|---|---|---|
| COMP-1 (single-precision float) | UNSUPPORTED | No IEEE-754 mapping; diagnostic only |
| COMP-2 (double-precision float) | UNSUPPORTED | No IEEE-754 mapping; diagnostic only |
| COMP-5 (native-endian binary) | GENERATED_ONLY | Endianness not corrected; values differ on x86 |
| Negative zero in packed decimal | UNIT_TESTED | Not differentially verified |
| ROUNDED MODE IS clause variants (HALF_EVEN, TRUNCATION, etc.) | Gap | Only HALF_UP emitted; other modes silently fall back |
| Very large packed fields (>18 digits) | Gap | Overflow to BigDecimal loses COBOL truncation semantics |
| SIGN IS SEPARATE CHARACTER | GENERATED_ONLY | Overpunch sign not correctly marshalled in file I/O |

### 2.2 REDEFINES / OCCURS Patterns

| Feature | Evidence Level | Gap |
|---|---|---|
| REDEFINES of OCCURS-containing group | PARSED_ONLY | Code generation fails; produces comment only |
| Multi-level REDEFINES chains (A REDEFINES B, C REDEFINES B) | DIFFERENTIALLY_VERIFIED | Phase 3 fixed shared backing buffer |
| OCCURS DEPENDING ON runtime bounds | GENERATED_ONLY | Bounds checked statically at generation time |
| OCCURS INDEXED BY with SET / SEARCH | UNIT_TESTED | SEARCH ALL (binary search) not generated |
| REDEFINES inside OCCURS (table redefine) | UNSUPPORTED | Not detected; produces wrong Java |

### 2.3 Control Flow Constructs

| Feature | Evidence Level | Gap |
|---|---|---|
| GO TO DEPENDING ON | UNSUPPORTED | No code generation; diagnostic only |
| EVALUATE with multiple subjects | PARSED_ONLY | IR created; Java switch not generated |
| PERFORM VARYING AFTER (nested varying) | GENERATED_ONLY | Only outer loop generated; AFTER clause dropped |
| Sections as PERFORM targets | GENERATED_ONLY | Section paragraphs not sequenced correctly |
| EXIT PARAGRAPH inside inline PERFORM | UNIT_TESTED | Not differentially verified for edge cases |
| ALTER TO PROCEED TO | UNSUPPORTED | Self-modifying code; not supportable |
| DECLARATIVES section | PARSED_ONLY | I/O error handlers not wired to file open/read exceptions |

### 2.4 String / Data Operations

| Feature | Evidence Level | Gap |
|---|---|---|
| ADD CORRESPONDING / SUBTRACT CORRESPONDING | PARSED_ONLY | No field-matching generation |
| MOVE CORRESPONDING | PARSED_ONLY | No field-matching generation |
| STRING DELIMITED BY SIZE (multi-source) | UNIT_TESTED | OVERFLOW clause not generated |
| UNSTRING DELIMITED BY ALL | UNIT_TESTED | OVERFLOW / TALLYING clauses partial |
| INSPECT CONVERTING | UNIT_TESTED | Not differentially verified |
| Reference modification on group items | Bug | Generates substring of group toString; semantically wrong |

### 2.5 File I/O

| Feature | Evidence Level | Gap |
|---|---|---|
| EBCDIC file encoding | UNSUPPORTED | No IBM037 charset path in file readers/writers |
| Variable-length records (RDW) | UNSUPPORTED | RECORDING MODE V / U not handled |
| WRITE AFTER ADVANCING (multiple lines) | UNIT_TESTED | Line count not differentially verified |
| READ INTO (read into working-storage) | UNIT_TESTED | Not differentially verified for group reads |
| START KEY IS (partial key positioning) | UNIT_TESTED | KEY IS GREATER THAN OR EQUAL TO partial |
| Relative files with random access | UNIT_TESTED | DELETE not differentially verified |
| Sequential files with BLOCK CONTAINS | GENERATED_ONLY | Block boundary ignored |
| Tape / unit record (UNIT=TAPE) | UNSUPPORTED | No content model |

---

## 3. Middleware and Enterprise Gaps

### 3.1 DB2 / EXEC SQL

| Area | Status | Gap |
|---|---|---|
| Baseline execution | BLOCKED | GnuCOBOL has no SQL precompiler; mock-baseline path not yet implemented |
| H2 emulation (SELECT/INSERT/UPDATE/DELETE) | UNIT_TESTED | Verified against pre-seeded mock baseline; not differentially verified vs GnuCOBOL |
| Cursor paging | UNIT_TESTED | Multi-page FETCH loops not differentially verified |
| SQLCODE / SQLSTATE propagation | UNIT_TESTED | Verified against H2 error codes; real DB2 code mapping incomplete |
| Stored procedures (CALL proc) | UNSUPPORTED | No generation; produces diagnostic comment |
| Dynamic SQL (PREPARE / EXECUTE) | UNSUPPORTED | Not parsed; produces diagnostic |
| WHENEVER error handling | PARSED_ONLY | Parsed but no Java exception routing generated |
| Multi-row SELECT INTO (array fetch) | UNSUPPORTED | Only single-row INTO supported |
| DB2 data types (DECFLOAT, ROWID, BLOB, CLOB) | UNSUPPORTED | No mapping; diagnostic |
| Real DB2 server execution | NOT_VERIFIED | Requires REAL_DB2_MODE=1 + DB2_URL; never executed |

### 3.2 CICS / EXEC CICS

| Area | Status | Gap |
|---|---|---|
| Baseline execution | BLOCKED | No CICS precompiler / transaction monitor |
| EXEC CICS SEND MAP | PARSED_ONLY | Stubbed; no BMS screen-to-HTML/JSON generation |
| EXEC CICS RECEIVE MAP | PARSED_ONLY | Stubbed; input binding not generated |
| EXEC CICS LINK (program call) | PARSED_ONLY | Stub; no Spring controller dispatch |
| EXEC CICS RETURN | PARSED_ONLY | Stub; no transaction context lifecycle |
| EXEC CICS READ / WRITE (VSAM via CICS) | PARSED_ONLY | Stub; no VSAM bridge |
| EXEC CICS GETMAIN / FREEMAIN | UNSUPPORTED | Memory management; diagnostic |
| EIB fields (EIBTRNID, EIBCALEN) | GENERATED_ONLY | Stub constants; not wired to session context |
| RESP / RESP2 error handling | GENERATED_ONLY | Set to 0 always; no mock-programmable responses |
| BMS map parsing | UNSUPPORTED | .bms files detected but not parsed |
| CICS to REST controller scaffold | FRAMEWORK_ONLY | Generates empty controller; no endpoint mapping |
| CICS transaction isolation | UNSUPPORTED | No Spring @Transactional boundary mapping |

### 3.3 IMS / EXEC DLI

| Area | Status | Gap |
|---|---|---|
| Baseline execution | BLOCKED | No DL/I precompiler |
| CALL CBLTDLI / CALL ASMTDLI | PARSED_ONLY | Produces diagnostic IMS_MQ: NATIVE_TRANSLATION_BLOCKED |
| DL/I function codes (GU, GN, GNP, GHU, ISRT, DLET, REPL) | UNSUPPORTED | No Java equivalents |
| PCB / DBD structures | UNSUPPORTED | Not parsed as data structures |
| IMS segment hierarchy mapping | UNSUPPORTED | No JPA nested-entity generation |
| IMS mock service | UNSUPPORTED | Not designed or prototyped |

### 3.4 IBM MQ

| Area | Status | Gap |
|---|---|---|
| CALL MQPUT / CALL MQGET | PARSED_ONLY | Diagnostic: IMS_MQ: NATIVE_TRANSLATION_BLOCKED |
| MQ copybooks (CMQV, CMQODV) | UNSUPPORTED | Missing; GnuCOBOL compilation fails |
| JMS / Spring AMQP bridge | UNSUPPORTED | No generation; architectural gap |
| MQ mock service | UNSUPPORTED | Not designed |

### 3.5 Spring / JPA / Batch / REST Generation

| Area | Status | Gap |
|---|---|---|
| JPA @Entity hyphenated column names | Bug | Hibernate rejects hyphens - Maven compile fails |
| JPA type mapping for COMP (BINARY) fields | Bug | Maps to BigDecimal instead of Integer/Long |
| JPA @Id generation strategy | Gap | Uses @GeneratedValue(AUTO) always; COBOL record keys often natural keys |
| Spring Batch FlatFileItemReader path | Bug | Hardcoded; not derived from discovered file assigns |
| Spring Batch step processor | Gap | Placeholder TODO body; no COBOL procedure logic injected |
| Spring Batch chunk-oriented vs tasklet | Gap | All steps generated as tasklets; multi-step chunk jobs not modeled |
| REST controller payload mapping | Gap | Stub controller; no BMS field to JSON mapping |
| Spring Batch job restart / skippable items | Unsupported | Not generated |
| H2 schema auto-creation | Bug | spring.jpa.hibernate.ddl-auto=create can fail on COBOL column names |
| DB2 dialect configuration | Gap | H2 dialect used in dev; switching to real DB2 dialect not scripted |
| application.properties datasource | Gap | H2 in-memory; no configurable external DB profile |
| Gate 2 DB state comparison | Gap | Only file outputs compared; H2 row counts not verified |

---

## 4. Bug List

### Parser Bugs

| ID | File | Lines | Description |
|---|---|---|---|
| BUG-P001 | modernize/parser.py | ~2340 | Multi-subject EVALUATE TRUE ALSO TRUE raises ParserDiagnostic instead of generating IR |
| BUG-P002 | modernize/parser.py | ~2730 | COPY REPLACING ==:TAG:== partial-word replacement not parsed; silently dropped |
| BUG-P003 | modernize/parser.py | ~147 | Nested copybook at 3rd level silently fails; no diagnostic emitted |
| BUG-P004 | modernize/parser.py | ~2934 | WHENEVER SQL clause parsed but no IR node created |
| BUG-P005 | modernize/lexer.py | Various | EBCDIC-encoded files tokenized as Latin-1; produces garbage tokens |

### Generator Bugs

| ID | File | Lines | Description |
|---|---|---|---|
| BUG-G001 | modernize/native_generator.py | ~2500 | cursor_c1 declared in wrong scope - Java compile error for cursors used across paragraphs |
| BUG-G002 | modernize/native_generator.py | ~5610 | SpringContextHelper.jdbcTemplate = null at execution time; H2 DataSource never wired |
| BUG-G003 | modernize/native_generator.py | ~4660 | REDEFINES of OCCURS-containing group - _analyze_redefines_and_layout skips group expansion |
| BUG-G004 | modernize/native_generator.py | ~3015 | BY CONTENT snapshot type defaults to String when var_types lookup misses; COMP-3 loses precision |
| BUG-G005 | modernize/native_generator.py | ~2400 | PERFORM VARYING AFTER - only outer loop generated; AFTER clause body silently dropped |
| BUG-G006 | modernize/enterprise_generator.py | ~92 | _write_jpa_entity() maps COBOL COMP/BINARY to BigDecimal; should be Integer/Long |
| BUG-G007 | modernize/enterprise_generator.py | ~100 | JPA @Column(name=...) contains raw hyphenated COBOL name; Hibernate rejects it |
| BUG-G008 | modernize/enterprise_generator.py | ~195 | Spring Batch ItemReader hardcodes data/in/transactions.dat regardless of file assigns |

### Runtime Bugs

| ID | File | Lines | Description |
|---|---|---|---|
| BUG-R001 | Generated Java | Various | STOP RUN inside nested perform() sets programExited=true but outer loop may continue one extra iteration |
| BUG-R002 | Generated Java | Various | Division-by-zero: Java throws ArithmeticException (exit 1); GnuCOBOL exits 136 - Gate 1 fails |
| BUG-R003 | tests/utils/cobol_runner.py | ~229 | javac classpath in runner does not include java_helpers/ runtime classes |

### Pipeline / Orchestration Bugs

| ID | File | Lines | Description |
|---|---|---|---|
| BUG-O001 | cobol_migrate.py | ~5574 | h2_verified flag never populated; report always shows H2_VERIFIED=false even after successful H2 run |
| BUG-O002 | cobol_migrate.py | ~4926 | validate_port selection can collide between concurrent pipeline runs on shared machines |
| BUG-O003 | cobol_migrate.py | ~5099 | Gate 2 completion detection looks for fixed string; Spring Boot log format changes break detection |
| BUG-O004 | modernize/native_pipeline.py | ~720 | SpringContextHelper generated only when has_sql=True; programs with VSAM JDBC emulation also need it |

---

## 5. Priority Ranking

### P0 - Blocks E2E or Produces Wrong Business Logic

| ID | Summary | Target Phase |
|---|---|---|
| BUG-G001 | Cursor variable declared in wrong scope - Java compile error | Phase C |
| BUG-G002 | H2 DataSource never wired - SQL programs produce no output | Phase C |
| BUG-G003 | REDEFINES of OCCURS group produces empty layout | Phase B |
| BUG-G006 | JPA entity maps COMP to BigDecimal - wrong Spring Batch logic | Phase E |
| BUG-G007 | Hyphenated JPA column names - Maven compile failure | Phase E |
| Stage 3 baseline blocked | No mock-baseline path for EXEC SQL / CICS / DLI | Phase C |

### P1 - Significant Limitation, Workaround Exists

| ID | Summary | Target Phase |
|---|---|---|
| BUG-G004 | BY CONTENT type inference falls back to String for BigDecimal | Phase B |
| BUG-G005 | PERFORM VARYING AFTER drops inner loop body | Phase B |
| BUG-G008 | Spring Batch ItemReader hardcoded path | Phase E |
| BUG-R001 | STOP RUN inside nested perform executes one extra iteration | Phase B |
| BUG-R003 | javac classpath misses runtime helpers | Phase C |
| BUG-O001 | h2_verified never set true in report | Phase E |
| CICS stub | EXEC CICS commands produce no Java logic | Phase C |
| IMS blocks | EXEC DLI blocked; no mock path | Phase C |
| MQ blocks | MQ copybooks missing; compile fails | Phase C |
| REDEFINES of OCCURS | Parsed only; code gen fails | Phase B |
| EBCDIC codec | No charset conversion in file I/O | Phase D |
| Multi-subject EVALUATE | IR only; no Java generated | Phase B |
| Gate 2 DB state | Only file output compared | Phase E |

### P2 - Nice-to-Have or Rare Pattern

| ID | Summary | Target Phase |
|---|---|---|
| BUG-O002 | Port collision in concurrent pipeline runs | Phase E |
| BUG-O003 | Gate 2 completion detection fragile | Phase E |
| BUG-R002 | Div-by-zero exit code mismatch | Phase B |
| BUG-P004 | WHENEVER SQL not wired | Phase C |
| COMP-1/COMP-2 | Float/double unsupported | Phase F |
| COMP-5 endianness | Not corrected | Phase B |
| RDW records | Variable-length not parsed | Phase D |
| SORT INPUT/OUTPUT PROCEDURE | Windows path bugs | Phase B |
| ALTER TO PROCEED TO | Self-modifying; not supportable | N/A |
| Report Writer | Section parsed, not generated | Phase F |
