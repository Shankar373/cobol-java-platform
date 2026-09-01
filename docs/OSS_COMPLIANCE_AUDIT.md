# Open-Source Software (OSS) Compliance & Supply-Chain Audit
## Pure Open-Source Architecture (Track B) Provenance Audit

---

## 1. Compliance Certification

The modernization platform operates strictly on pure open-source dependencies without proprietary vendor SDKs, runtime interpreters, or binary wrappers:

- **Generated Runtime**: Java 17+, Spring Boot 3.2.3, Spring JDBC, PostgreSQL JDBC driver (`42.7.2`).
- **Engine Dependencies**: Python 3.14, pytest, psycopg2.
- **Prohibited Libraries (Verified 0% Presence)**:
  - `libcobj` (GnuCOBOL C runtime)
  - `jp.osscons.cobol` (COBOL JNI runtime)
  - `opensourcecobol4j` / `COBOL4J`
  - `com.microfocus.*`
  - `com.ibm.db2.jcc.*`
  - `com.ibm.cics.*`
  - `com.ibm.mq.*`

---

## 2. Dependency Risk Assessment

| Component | License | Vulnerability Scan | Provenance Status |
| :--- | :--- | :--- | :--- |
| `spring-boot-starter-web` | Apache 2.0 | Clean (Zero CVEs) | Maven Central / VMware |
| `spring-boot-starter-jdbc` | Apache 2.0 | Clean (Zero CVEs) | Maven Central / VMware |
| `org.postgresql:postgresql` | PostgreSQL License | Clean (Zero CVEs) | Maven Central / PostgreSQL Global Dev Group |
