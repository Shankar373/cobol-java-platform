# Modernized Open Source Technology Stack

---

## 1. Zero Proprietary Runtime Dependency Standard (Track B)

Modernized Java applications produced by this platform contain zero proprietary runtime dependencies:
- **No** `libcobj.jar`
- **No** `jp.osscons`
- **No** `opensourcecobol4j` / `COBOL4J` runtime
- **No** proprietary CICS/DB2 jars

---

## 2. Core Open-Source Stack

| Component Area | Selected Open Source Technology | Version | Purpose |
| :--- | :--- | :--- | :--- |
| **Language & Runtime** | Eclipse Temurin OpenJDK | 17 (LTS) | Modern Java execution engine |
| **Application Framework** | Spring Boot | 3.2.5 | Modern enterprise web, REST, and DI services |
| **Database Access** | Spring JDBC (`JdbcTemplate`) | 6.1.3 | High-performance SQL queries & transactions |
| **Relational Database** | PostgreSQL | 16.x | Modern enterprise relational data storage |
| **Database Driver** | PostgreSQL JDBC Driver | 42.7.1 | Native connection pooling and execution |
| **In-Memory Test Database** | H2 Database | 2.2.224 | Local unit testing fallback |
| **JSON Serialization** | Jackson Databind | 2.15.2 | REST DTO serialization and schema mapping |
| **Build & Packaging** | Apache Maven | 3.9+ | Standalone dependency and artifact packaging |
