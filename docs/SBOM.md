# Software Bill of Materials (SBOM)

This document provides a comprehensive list of all third-party libraries, engines, and utilities utilized by the COBOL-to-Java Modernization Platform.

---

## 1. Compiler Pipeline Dependencies (Build / Analysis Time Only)

These dependencies are used exclusively by the transpilation and code generation stages. **They are NOT packaged or inherited by the generated Track-B Java applications.**

| Component Name | Version | License | Source / Repository | Scope | Description |
|---|---|---|---|---|---|
| **Python** | 3.10+ | PSF License | [python.org](https://www.python.org/) | System Runtime | Host script execution environment |
| **pytest** | 9.x | MIT | [PyPI: pytest](https://pypi.org/project/pytest/) | Testing (Dev) | Local unit and regression tests |
| **GnuCOBOL** | 3.1.2 | GPL v3+ | [GNU COBOL Project](https://sourceforge.net/projects/open-cobol/) | Optional (Docker/Local) | Legacy golden baseline compiler |
| **Vite / React** | Latest | MIT | [NPM: vite](https://www.npmjs.com/) | UI Dashboard | Frontend dashboard components |

---

## 2. Modernized Java Target Dependencies (Production Runtime)

These dependencies are specified inside the generated Spring Boot `pom.xml` structures for target compilation. They utilize standard, secure enterprise licenses.

| Dependency Name | Version | License | Scope | Description |
|---|---|---|---|---|
| **Spring Boot Starter Batch** | 3.2.x | Apache 2.0 | Compile / Runtime | Core chunk-oriented execution scheduler |
| **Spring Boot Starter Data JPA**| 3.2.x | Apache 2.0 | Compile / Runtime | Data persistence and repository interfaces |
| **Spring Boot Starter Web** | 3.2.x | Apache 2.0 | Compile / Runtime | REST API controller endpoints |
| **H2 Database Engine** | 2.2.x | MPL 2.0 / EPL 1.0 | Test / Emulation | Local in-memory DB2 SQL emulation database |
| **SQLite JDBC Driver** | 3.42.x | Apache 2.0 | Runtime | Emulated VSAM indexed storage database driver |

---

## 3. Forbidden Runtime Dependencies (Verified Absent)

The following packages are **100% absent** from target modernized applications (Track-B):

*   `libcobj.jar` / `jp.osscons` (OpenSourceCOBOL4J emulation runtime)
*   `antlr` / `antlr4-runtime` (Parser components)
*   `proleap-cobol-parser` (ProLeap AST runtime)
