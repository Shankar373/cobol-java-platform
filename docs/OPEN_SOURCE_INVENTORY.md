# Open Source Dependency & Software Bill of Materials (SBOM)
## Phase 12 Unified Modernization Platform Compliance Audit

**Classification Standard**: Track B Pure Open-Source Standard  
**Audit Date**: September 2026  
**Status**: `COMPLIANT` (Zero proprietary mainframe runtimes, zero commercial SDKs)

---

## 1. Overview & Licensing Policy

The modernization platform adheres to the strict **Track B Open-Source Architecture**:
- All generated Java applications execute on standard Java 17+ and Spring Boot 3 without proprietary mainframe emulation libraries (e.g. `libcobj`, `jp.osscons`, `COBOL4J`, `Micro Focus`, `IBM JCC driver`).
- All tools and test harnesses utilize standard open-source licenses (Apache 2.0, MIT, BSD 3-Clause, PostgreSQL License).

---

## 2. Dependency Inventory

### 2.1 Modernized Java Runtime Dependencies (Shipped in Generated `pom.xml`)

| Dependency Coordinate | Version | License | Usage & Role | Production Status |
| :--- | :--- | :--- | :--- | :--- |
| `org.springframework.boot:spring-boot-starter-web` | `3.2.3` | Apache 2.0 | REST Controllers, Microservice HTTP endpoints | Production Runtime |
| `org.springframework.boot:spring-boot-starter-jdbc` | `3.2.3` | Apache 2.0 | Spring `JdbcTemplate`, `PlatformTransactionManager`, DataSource | Production Runtime |
| `org.postgresql:postgresql` | `42.7.2` | PostgreSQL License | JDBC Driver for PostgreSQL relational database target | Production Runtime |
| `org.springframework.boot:spring-boot-starter-test` | `3.2.3` | Apache 2.0 | JUnit 5, Spring Test Context for component testing | Test Scope Only |

### 2.2 Modernization Engine Dependencies (Python Toolchain)

| Package | Version | License | Usage & Role | Scope |
| :--- | :--- | :--- | :--- | :--- |
| `Python` | `3.14.x` | PSF License | Runtime environment for lexer, parser, IR, and generator | Engine Toolchain |
| `pytest` | `9.1.x` | MIT | Automated test framework for unit, component, and differential suites | Test Harness |
| `psycopg2` / PostgreSQL Client | `2.9.x` | LGPL / BSD | PostgreSQL database connectivity for test data verification | Test Harness |

---

## 3. Prohibited Mainframe Dependencies Audit

| Prohibited Component | Detection Status | Audit Result |
| :--- | :--- | :--- |
| `libcobj` (GnuCOBOL C Runtime) | None in generated Java | **PASS** (`VERIFIED_ABSENT`) |
| `jp.osscons.cobol` (OSS COBOL JNI) | None in generated Java | **PASS** (`VERIFIED_ABSENT`) |
| `com.microfocus.*` (Enterprise Server) | None in generated Java | **PASS** (`VERIFIED_ABSENT`) |
| `com.ibm.db2.jcc.*` (IBM DB2 Driver) | None in generated Java | **PASS** (`VERIFIED_ABSENT`) |
| `com.ibm.mq.*` (IBM MQ Client JARs) | None in generated Java | **PASS** (`VERIFIED_ABSENT`) |
| `com.ibm.cics.*` (IBM JCICS Client JARs)| None in generated Java | **PASS** (`VERIFIED_ABSENT`) |
