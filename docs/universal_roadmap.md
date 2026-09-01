# Universal COBOL to Java/Spring Modernization Roadmap

> This document maps the phased plan from the current state to the North-Star vision.
> All phases directly address bugs and gaps documented in limitations_and_gaps.md.
> Current state summary references pipeline_execution_limits.md and transformation-coverage.md.

---

## Current State Summary (Phase A Complete)

### What We Can Claim Today (End-to-End Verified)

The pipeline achieves full E2E success (Stages 0-12, Gate 1 and Gate 2) for:

- Plain batch COBOL programs with file I/O (SEQUENTIAL, LINE SEQUENTIAL, RELATIVE, INDEXED/VSAM emulation)
- Standard arithmetic with COMP-3 packed decimal, ROUNDED, ON SIZE ERROR
- PERFORM VARYING / PERFORM THRU / out-of-line paragraphs (differentially verified as of Phase 3)
- CALL BY REFERENCE and CALL BY CONTENT parameter passing (differentially verified as of Phase 3)
- REDEFINES scalar and group views with shared backing buffers (differentially verified as of Phase 3)
- OCCURS fixed tables with subscripted access
- EVALUATE (single-subject), IF/ELSE, GO TO
- STRING / UNSTRING / INSPECT
- JPA/Spring Boot scaffolding for simple file-based apps (Gate 2 passes for SIMPLEBASELINE01 pattern)

Evidence: 50/50 parity tests passing, 516+ unit/integration tests passing in CI.

### What Is Partial (Gate 1 Only)

- Enterprise apps with DB2/CICS/IMS/MQ: Stage 3 baseline is blocked; Stage 9 (Refactor) scaffolds Spring Boot but Stages 10-11 fail
- Complex JPA mappings with COBOL numeric types: Maven compilation fails due to BUG-G006 and BUG-G007
- Spring Batch step generation: Framework-only stubs (BUG-G008)

### What Is Unsupported (with Planned Path)

| Pattern | Blocker | Planned Phase |
|---|---|---|
| EXEC SQL / DB2 | No mock-baseline path; H2 wiring incomplete | Phase C |
| EXEC CICS | No precompiler; BMS parsing absent | Phase C |
| EXEC DLI / IMS | No DL/I precompiler; no mock service | Phase C |
| IBM MQ (MQPUT/MQGET) | Missing copybooks; no JMS bridge | Phase C |
| EBCDIC file I/O | No charset codec | Phase D |
| Variable-length records (RDW) | No RECORDING MODE V/U parser | Phase D |
| REDEFINES of OCCURS-containing group | Code-gen fails | Phase B |
| Multi-subject EVALUATE | IR only; no Java generated | Phase B |
| GO TO DEPENDING ON | No code generation | Phase B |

---

## Target State Description (North-Star Vision)

Input: Any realistic mainframe COBOL application (batch and online) including:
- DB2 SQL (EXEC SQL), CICS transactions (EXEC CICS), IMS DL/I (EXEC DLI), IBM MQ calls
- VSAM (KSDS/ESDS/RRDS), sequential, EBCDIC, variable-length records
- Complex data structures (REDEFINES, OCCURS, nested groups)

Output:
- A native Java 17+ application using Spring Boot runtime, Spring Batch for batch jobs, Spring Data JPA for DB2/relational persistence, and REST controllers for online/CICS-like interactions
- Behavioral equivalence: Gate 1 (COBOL vs transpiled Java outputs match) and Gate 2 (refactored Spring app vs legacy behavior match)
- Deployment-ready artifacts: JARs, Docker image, migration report

---

## Phase B - Close Core COBOL Semantic Gaps

**Goal**: Extend differential (GnuCOBOL vs Java) coverage to remaining COBOL constructs. Fix P0/P1 generator bugs that block correct business logic.

**Estimated Duration**: 2-3 weeks  
**Complexity**: Medium

### Technical Tasks

#### B.1 Fix REDEFINES of OCCURS-containing group (BUG-G003) - P0

- File: modernize/native_generator.py ~4660
- Root cause: _analyze_redefines_and_layout exits early when a redefines target contains an OCCURS; the child fields are not expanded into the layout.
- Fix: When the redefines target record contains an OCCURS group, expand the OCCURS children using the occurs_max and compute offsets for each element (offset = base_offset + i * element_length).
- Add parity fixture: REDEFINES of an OCCURS group; write via array view, read via scalar redefinition.

#### B.2 Fix PERFORM VARYING AFTER (BUG-G005) - P1

- File: modernize/native_generator.py ~2400 (PERFORM VARYING code gen)
- Root cause: AFTER clause in multi-varying loop not consumed; only the primary VARYING variable's loop is emitted.
- Fix: Parse AFTER into nested loop(s); generate Java nested for() loops with correct UNTIL conditions.
- Add parity fixture: PERFORM VARYING WS-I FROM 1 BY 1 UNTIL WS-I > 3 AFTER WS-J FROM 1 BY 1 UNTIL WS-J > 3.

#### B.3 Fix STOP RUN propagation in nested PERFORM (BUG-R001) - P1

- File: Generated Java (perform() method scaffold in native_generator.py)
- Root cause: After programExited = true is set, the outer perform() loop does not re-check the flag before executing the next paragraph.
- Fix: Add if (programExited) return; guard as the first statement in every iteration of the perform() while loop.

#### B.4 Implement multi-subject EVALUATE (BUG-P001) - P1

- File: modernize/parser.py ~2340 and native_generator.py EVALUATE handling
- Root cause: EVALUATE A ALSO B with WHEN X ALSO Y multi-subject form is not generated.
- Fix: Parse each subject-when pair into IR as a tuple; generate if/else chains comparing each tuple component.
- Add parity fixture: EVALUATE WS-CODE ALSO WS-FLAG with multi-subject WHEN clauses.

#### B.5 ADD/SUBTRACT/MOVE CORRESPONDING generation (P1)

- File: modernize/native_generator.py and parser.py
- Root cause: IR nodes created but code-gen stub produces a comment.
- Fix: At code-gen time, look up the group_fields for both source and destination; emit one ADD/SUBTRACT/MOVE per matching field name.
- Add unit tests for common and non-common field sets.

#### B.6 Fix BY CONTENT type inference for BigDecimal (BUG-G004) - P1

- File: modernize/native_generator.py ~3015 (_generate_call_block)
- Root cause: c_type lookup falls back to String when the var_types dict key is present under a different case.
- Fix: Normalize var_types lookup to uppercase before fallback.

**Verification**: All Phase B changes must have a passing parity fixture in test_parity_fixtures.py before marking complete.

**Gaps Addressed**: BUG-G003, BUG-G004, BUG-G005, BUG-P001, BUG-R001, REDEFINES of OCCURS, Multi-subject EVALUATE, PERFORM VARYING AFTER.

---

## Phase C - Middleware Stubs and Mock Baselines

**Goal**: Enable end-to-end testing of COBOL programs with EXEC SQL, EXEC CICS, EXEC DLI, and MQ through a deterministic mock-middleware approach. Close the baseline gap (Stage 3) for SQL/CICS programs.

**Estimated Duration**: 4-6 weeks  
**Complexity**: Large  
**Dependency**: Phase B (cursor variable scope fix BUG-G001 and H2 wiring BUG-G002 must be resolved first)

### C.1 Mock SQL Service (EXEC SQL)

Design: An in-memory H2 database pre-seeded from a YAML/JSON fixture file.

Architecture:
- `modernize/mock_sql_service.py`: Python-side fixture loader; writes H2-compatible SQL DDL+DML to a seed script embedded in generated Java.
- `MockSqlService.java` (generated helper class): Initializes H2 DataSource, runs seed script, exposes `static JdbcTemplate getJdbcTemplate()`.
- SpringContextHelper.jdbcTemplate is wired to MockSqlService at program startup (fixes BUG-G002).
- Fixture format: tests/repos/DB2SELECT01/mock_db.yaml with tables, columns, rows.

Implementation steps:
1. Fix BUG-G002: wire H2 DataSource into SpringContextHelper at native-execution startup.
2. Fix BUG-G001: move cursor variables from method scope to class field scope.
3. Design mock_db.yaml schema (see Phase C in mock_middleware_architecture.md).
4. Implement MockSqlService.java generation in native_pipeline.py.
5. Pre-seed existing DB2 test repos (DB2SELECT01, DB2INSERT01, etc.) with mock_db.yaml fixtures.
6. Add differential test: run same fixture through mock-COBOL baseline (H2-seeded GnuCOBOL wrapper) and Java transpiled code; compare outputs.

### C.2 Fix Cursor Variable Scope (BUG-G001) - P0

- File: modernize/native_generator.py ~2500
- Fix: Move cursor declarations from paragraph method body to class field level (like other WORKING-STORAGE vars).
- Emit: `private org.springframework.jdbc.support.rowset.SqlRowSet cursor_c1 = null;` as a class field.

### C.3 Fix H2 DataSource Wiring (BUG-G002) - P0

- File: modernize/native_generator.py ~5610 and native_pipeline.py ~720
- Fix: Generate an H2 DataSource initialization block in the program class that runs before execute(); wire it to SpringContextHelper.jdbcTemplate.
- This is gated behind an `has_sql` check that already exists.

### C.4 Mock CICS Service (EXEC CICS)

Design: CicsMockService with configurable map layouts and responses.

Implementation steps:
1. Parse BMS map files (Phase C.4a): extract field names, lengths, positions from .bms DFHMDF macros.
2. Design CICS mock config: tests/repos/CICSREST01/mock_cics.yaml with map definitions and scripted responses.
3. Generate CicsTransactionContext.java with pre-loaded map data from mock config.
4. Wire EXEC CICS SEND MAP / RECEIVE MAP stubs to CicsTransactionContext.
5. Add parity test using mock-CICS baseline vs transpiled Java.

### C.5 Mock IMS / DL/I Service (EXEC DLI)

Design: ImsSegmentMock with configurable segment trees.

Implementation steps:
1. Design IMS mock config: mock_ims.yaml with DBD/segment tree definitions.
2. Generate ImsMockService.java that maps CBLTDLI function codes (GU, GN, ISRT, DLET) to in-memory segment tree operations.
3. Replace NATIVE_TRANSLATION_BLOCKED diagnostic with actual generated Java calls to ImsMockService.
4. Add parity test using mock-IMS baseline vs transpiled Java.

### C.6 Mock MQ Service

Design: MqMockService backed by an in-memory java.util.Deque.

Implementation steps:
1. Generate stub MQ copybooks (CMQV.cpy, CMQODV.cpy) with minimal constant definitions.
2. Generate MqMockService.java with MQPUT/MQGET operations on an in-memory queue.
3. Replace NATIVE_TRANSLATION_BLOCKED diagnostic with generated Java calls to MqMockService.
4. Add parity test using mock-MQ baseline vs transpiled Java.

### C.7 Fix javac classpath (BUG-R003) - P0

- File: tests/utils/cobol_runner.py ~229
- Fix: Add java_helpers/src/main/java to javac -cp argument; or copy pre-compiled runtime helper .class files to temp dir before javac.

**Verification**: At minimum one end-to-end demo app for each middleware type (SQL, CICS, IMS, MQ) must pass Gate 1 with the mock baseline before Phase C is marked complete.

**Gaps Addressed**: BUG-G001, BUG-G002, BUG-R003, Stage 3 baseline blocked for SQL/CICS/IMS/MQ.

---

## Phase D - File I/O and Record Format Extensions

**Goal**: Add EBCDIC codec support and variable-length record (RDW) handling to the file I/O path.

**Estimated Duration**: 2-3 weeks  
**Complexity**: Medium  
**Dependency**: Phase B complete

### D.1 EBCDIC Codec

Implementation:
1. Add EbcdicCodec.java to java_helpers runtime: wraps java.nio.charset.Charset.forName("IBM037") with COBOL-compatible normalization.
2. In native_generator.py file I/O generation: detect when FD has RECORDING MODE BINARY or EBCDIC indicator in migration_config.json.
3. Apply EbcdicCodec.decode() on file read and EbcdicCodec.encode() on file write.
4. Add parity fixture: write EBCDIC-encoded sequential file under GnuCOBOL; read back and verify under Java.

### D.2 Variable-Length Records (RDW)

Implementation:
1. Add RdwFileReader.java to java_helpers runtime: reads 4-byte RDW prefix, then payload of RDW-specified length.
2. Add RdwFileWriter.java: writes 4-byte RDW header before each record.
3. In native_generator.py file I/O generation: detect RECORDING MODE V; generate RdwFileReader/Writer instead of standard BufferedReader/Writer.
4. Add parity fixture: write variable-length records under GnuCOBOL; read back and verify field values under Java.

**Verification**: Two new parity fixtures (EBCDIC sequential, RDW sequential) must pass differentially.

**Gaps Addressed**: EBCDIC file encoding (UNSUPPORTED), Variable-length records/RDW (UNSUPPORTED).

---

## Phase E - Enterprise Refactor Hardening (Spring/JPA/Batch/REST)

**Goal**: Fix all P0/P1 Validate-stage failures. Make Gate 2 pass for enterprise apps with DB2 and file-based batch logic.

**Estimated Duration**: 3-4 weeks  
**Complexity**: Large  
**Dependency**: Phase C (mock SQL service must be working)

### E.1 Fix JPA Column Name Mapping (BUG-G007) - P0

- File: modernize/enterprise_generator.py ~100
- Fix: Apply to_java_var() sanitization to all @Column(name=...) values; convert hyphens to underscores.
- Add test: verify generated @Entity has no hyphens in any annotation.

### E.2 Fix JPA Type Mapping for COMP/BINARY (BUG-G006) - P0

- File: modernize/enterprise_generator.py ~92
- Fix: In _write_jpa_entity(), check the COBOL usage clause; map COMP/BINARY/COMP-4 to Integer or Long based on field length (<=4 digits: Integer, <=9: Long, else BigDecimal).
- Add test: verify generated @Entity field types for COMP fields.

### E.3 Fix Spring Batch ItemReader Path (BUG-G008) - P1

- File: modernize/enterprise_generator.py ~195
- Fix: Accept file_assigns parameter in _write_spring_batch_config(); use the first input file assign path as the FlatFileItemReader resource.
- Add test: verify generated BatchConfig references the discovered input path.

### E.4 Fix h2_verified Flag (BUG-O001) - P1

- File: cobol_migrate.py ~5574
- Fix: After Stage 10 (validate) completes with job_completed=True, set validate.h2_executed = True in the state dict before reporting.
- Add test: verify report shows H2_VERIFIED=true after successful Gate 2 run.

### E.5 Gate 2 DB State Comparison - P1

- File: cobol_migrate.py ~5105 (Gate 2 comparison logic)
- Add: After job_completed=True, execute H2 JDBC query to read row counts / key rows from generated tables; compare against expected counts from migration_config.json.
- Config format addition: compare.db_state_checks: [{table: CUSTOMER, expected_count: 3}, ...]
- Add integration test: verify Gate 2 DB state check passes for DB2SELECT01 after Phase C mock wiring.

### E.6 Fix Gate 2 Completion Detection (BUG-O003) - P1

- File: cobol_migrate.py ~5099
- Fix: Also check for Spring Batch `EXIT_CODE:COMPLETED` log pattern as an alternative completion marker; make detection configurable.

### E.7 Application Properties Profile Configuration - P1

- File: modernize/enterprise_generator.py _write_properties()
- Add: Generate application-h2.properties (H2 in-memory, default) and application-db2.properties (DB2 JDBC URL from env vars).
- Add: -Pdb2 Maven profile that activates db2 Spring profile.
- Add test: verify both property files are generated with correct datasource URLs.

**Verification**: ClaimsCore-style enterprise app must pass Gate 2 (Maven build success + Spring Boot batch completes + file output matches). Add integration test.

**Gaps Addressed**: BUG-G006, BUG-G007, BUG-G008, BUG-O001, BUG-O003, Gate 2 DB state gap.

---

## Phase F - CI/CD and Universal Coverage Claim

**Goal**: Define and measure the "universal" claim. Build a coverage corpus, run the full pipeline on each app, publish a matrix.

**Estimated Duration**: 4-6 weeks  
**Complexity**: Large  
**Dependency**: Phases C, D, E complete

### F.1 Universal Target Corpus

Define a representative set of COBOL application patterns:
1. Plain batch (file I/O only) - already covered
2. Batch with DB2 - Phase C/E
3. Online CICS transaction - Phase C/E
4. IMS hierarchical batch - Phase C
5. MQ message-driven batch - Phase C
6. EBCDIC file processing - Phase D
7. Variable-length record processing - Phase D
8. Mixed (DB2 + CICS + file) - Phase C/E
9. JCL multi-step job - Phase B/E

### F.2 Coverage Matrix Publication

For each pattern:
- Run full pipeline (Stages 0-12)
- Record which stages succeed / partial / fail
- Publish docs/universal_status.md matrix updated on each CI run

### F.3 COMP-1/COMP-2 Support (P2)

- Add IEEE-754 float/double mapping for COMP-1/COMP-2 fields in native_generator.py
- Emit float or double Java fields with appropriate precision loss warning

### F.4 Report Writer Support (P2)

- Implement REPORT SECTION generation as a Spring Batch ItemWriter that accumulates report lines
- Map control breaks to @BeforeStep / @AfterStep callbacks

### F.5 GO TO DEPENDING ON (P2)

- Implement as a Java switch statement where each case calls runParagraph(targetIndex)

---

## Risk Analysis

### Where Equivalence Is Hard

| Risk | Mitigation |
|---|---|
| CICS screen logic: BMS maps contain proprietary z/OS terminal semantics; HTML/JSON equivalence is semantic, not byte-exact | Define equivalence as JSON payload field match (not pixel/character exact); document semantic delta |
| IMS hierarchical data: segment hierarchies do not map cleanly to JPA entity relationships | Use JPA @Embeddable or Spring Data custom queries; document structural transformation |
| MQ delivery guarantees: IBM MQ has at-least-once / exactly-once semantics; in-memory mock is at-most-once | Mock is for testing only; production should use real JMS with IBM MQ JMS provider |
| COMP-3 precision: IBM z/Architecture packed decimal is 31-digit; Java BigDecimal is effectively unlimited but truncation semantics differ | Enforce explicit scale/precision in all BigDecimal operations; add truncation unit tests |
| EBCDIC character set: Code page 037/500/1047 differences cause subtle sort order and collation divergence | Use configurable charset mapping; default to IBM037; document known deviations |

### Where Performance May Be an Issue

| Risk | Mitigation |
|---|---|
| H2 in-memory database: large batch programs inserting millions of rows will hit H2 size limits | Use file-backed H2 (MODE=JDBC) for large batch tests; configure max memory |
| Paragraph dispatcher (runParagraph switch): O(1) but very large programs with 1000+ paragraphs generate huge switch statements | Consider replacing with Map<Integer, Runnable> dispatch for programs > 200 paragraphs |
| Gate 2 Spring Boot startup timeout: complex JPA schema creation can exceed 120 s | Increase timeout to 300 s; add progress polling; consider schema pre-generation |
