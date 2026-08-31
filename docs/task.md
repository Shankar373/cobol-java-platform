# Task Tracking — Mainframe COBOL Modernization Platform

## Phase 0: Foundation & Environment Readiness
- [x] Environment readiness audit (docs/environment_readiness_report.md)
- [x] Repository bootstrap & Git push (cobol-java-platform)
- [x] Architecture & pipeline setup

## Phase 1: Core Vertical Slice (PAYMAIN.cob)
- [x] COBOL Lexer & Parser
- [x] SemanticIR (v2.0) language-agnostic representation
- [x] Track B Native Java Generator
- [x] GnuCOBOL Docker Baseline Verifier
- [x] Java Build & Execution Verifier
- [x] Equivalence Comparator & Evidence Verdict Generator
- [x] E2E Differential Verification (PAYMAIN.cob)

## Phase 2: SQL / PostgreSQL Track
- [x] EXEC SQL statement extractor (	ransformation/sql/extractor.py)
- [x] Native Java JDBC SQL generator (generators/native_java/sql.py)
- [x] DB2SELECT01 fixture integration & precompiler fixes
- [x] GnuCOBOL + OCESQL baseline compilation & PostgreSQL connection
- [x] E2E Differential SQL Verification (DB2SELECT01)

## Phase 3: Sequential File I/O Track
- [ ] SELECT ... ASSIGN TO clause parsing
- [ ] FD record layout & buffer mapping
- [ ] OPEN / CLOSE / READ / WRITE / REWRITE statement translators
- [ ] Sequential file fixture (SEQNFILE01)
- [ ] E2E Differential File I/O Verification

## Phase 4: VSAM & Indexed File Track
- [ ] Indexed file IR representation (KSDS/ESDS/RRDS)
- [ ] Key definition & START/READ NEXT syntax
- [ ] Java Map/Key-Value store adapter
- [ ] E2E Differential VSAM Verification

## Phase 5: Spring Boot & Batch Packaging
- [ ] Spring Boot application configuration generator
- [ ] Spring Batch Tasklet & ItemReader/ItemWriter generator
- [ ] Maven Spring Boot build verification
