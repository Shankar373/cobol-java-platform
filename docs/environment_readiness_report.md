# Toolchain & Environment Readiness Audit Report

> **Repository:** `cobol-java-platform`  
> **Audit Date:** 2026-09-01  
> **Status:** READINESS AUDIT COMPLETE — ALL TOOLCHAIN BLOCKERS RESOLVED — 100% E2E VERTICAL SLICE PASSING

---

## 1. Toolchain & Dependency Matrix

| TOOL | REQUIRED VERSION | DETECTED VERSION | AVAILABLE? | WHERE USED | PIPELINE STAGES BLOCKED | LOCAL INSTALL OPTION | DOCKER OPTION | CI OPTION | EXACT RESOLUTION |
|---|---|---|---|---|---|---|---|---|---|
| **Python** | `>= 3.10` | `3.14.3` | YES | Pipeline runner, engine, generators, verifiers | None | System PATH | `python:3.12-slim` | GitHub Actions `setup-python` | Already installed on system PATH. |
| **OpenJDK / JDK** | `JDK 17+` (target 17) | `25.0.3` (Temurin LTS) | YES | Java compilation and execution | `java_build` (was blocked by mvn lookup) | Temurin JDK 17/21/25 on PATH | `eclipse-temurin:17-jdk-noble` | GitHub Actions `setup-java@v4` | Local OpenJDK 25.0.3 used with target 17 in generated `pom.xml`. |
| **javac** | `17+` | `25.0.3` | YES | Java source compilation | `java_build` | Temurin JDK 17+ on PATH | `eclipse-temurin:17-jdk-noble` | GitHub Actions `setup-java@v4` | Available on system PATH (`C:\Program Files\Eclipse Adoptium\jdk-25.0.3.9-hotspot\bin\javac.exe`). |
| **Maven** | `3.8+ / 3.9+` | `3.9.16` | YES | Building generated Java project (`mvn compile`) | `java_build` (previously blocked by `mvn.cmd` vs `mvn` lookup on Windows) | Apache Maven 3.9.16 on PATH | `maven:3.9-eclipse-temurin-17` | GitHub Actions `setup-java` (with maven) | Fixed `java_build.py` to use `shutil.which("mvn") or "mvn"` to resolve `mvn.cmd` on Windows. |
| **Docker CLI** | `20.10+` | `29.6.2` | YES | Executing GnuCOBOL / PostgreSQL containers | `baseline`, `postgresql` | Docker Desktop / Engine | N/A | GitHub Actions runner Docker | Available on system PATH. |
| **Docker daemon** | Active daemon | `29.6.2` (WSL2 Linux) | YES | Container runtime for COBOL baseline & PostgreSQL | `baseline`, `postgresql` | Docker Desktop WSL2 | N/A | GitHub Actions Docker daemon | Active Docker Desktop daemon running on WSL2 engine. |
| **GnuCOBOL** | `3.1.2` | `3.1.2.0` | YES (in container) | Baseline COBOL compilation and execution | `baseline` | Isolated GnuCOBOL build | Repository image `gnucobol-ocesql:latest` | Docker in CI | Utilized repository-controlled `gnucobol-ocesql:latest` Docker image. |
| **OCESQL** | `v1.4` | `1.4` | YES (in container) | EXEC SQL / DB2 precompiler | `baseline` (SQL) | Isolated OCESQL build | Repository image `gnucobol-ocesql:latest` | Docker in CI | Utilized repository-controlled `gnucobol-ocesql:latest` Docker image. |
| **PostgreSQL** | `15` or `16` | `15-alpine` | YES (in container) | DB2 SQL & VSAM KSDS relational table emulation | `sql`, `vsam` | Local PostgreSQL service | Repository image `postgres:15-alpine` | PostgreSQL service container | Container `modernization-platform-db-1` active on port 5432. |
| **Git** | `2.x` | `2.54.0.windows.1` | YES | Version control & repository synchronization | None | Git for Windows | N/A | GitHub Actions git | Available on system PATH. |
| **pytest** | `>= 7.4` | `9.1.1` | YES | Test suite execution | None | `python -m pytest` | N/A | `pip install pytest` | Available via Python environment (`python -m pytest`). |
| **ProLeap** | `4.0.0` (optional) | Optional adapter | OPTIONAL | Optional parsing track | None | Local JAR copy | N/A | N/A | Custom recursive-descent parser active as primary; ProLeap adapter is an optional fallback. |

---

## 2. Environment Blockers Identified & Resolved

### Blocker 1: Windows Executable Resolution (`mvn` vs `mvn.cmd`)
- **Root Cause:** On Windows, `subprocess.run(["mvn", ...])` without `shell=True` looks strictly for `mvn.exe` or `mvn.com`, whereas Apache Maven on Windows is launcher script `mvn.cmd`.
- **Resolution:** Updated `verification/java_build/java_build.py` to use `shutil.which("mvn") or "mvn"`, allowing cross-platform resolution of `mvn.cmd` on Windows and `mvn` on Linux/macOS.
- **Status:** RESOLVED.

### Blocker 2: Missing Special Register in Native Java Generator
- **Root Cause:** COBOL programs containing `MOVE 0 TO RETURN-CODE` failed Maven compilation with `cannot find symbol: variable return_code` because `RETURN-CODE` is an implicit special register in COBOL but was missing as a field in generated Java.
- **Resolution:** Updated `generators/native_java/program.py` to automatically include `private int return_code = 0;` as a standard special register in generated program classes.
- **Status:** RESOLVED.

### Blocker 3: Statement Paragraph Association in Code Generator
- **Root Cause:** Statements following paragraph headers (e.g. `PROCESS-ITEMS.`) were being emitted into the top-level `run()` method after `return;`, causing `unreachable statement` Maven compilation errors.
- **Resolution:** Updated `generators/native_java/program.py` to track paragraph headers sequentially and attribute statements to their enclosing paragraph methods (`process_items()`).
- **Status:** RESOLVED.

### Blocker 4: Fixed-Width Zero-Padding for Numeric `DISPLAY`
- **Root Cause:** COBOL `PIC 9(05)` field `WS-COUNTER` printed `"00001"` in GnuCOBOL baseline, but native Java printed `"1"`, breaking strict equivalence.
- **Resolution:** Updated `generators/native_java/statements.py` to detect display-format numeric fields and format them with zero-padding (`String.format("%05d", ws_counter)`).
- **Status:** RESOLVED.

### Blocker 5: Trailing Whitespace Stripping in String Literals
- **Root Cause:** `literal_or_var` stripped trailing spaces from string literals (e.g. `"ITEMS PROCESSED: "`), producing `"ITEMS PROCESSED:"` in Java output.
- **Resolution:** Updated `literal_or_var` in `generators/native_java/statements.py` to preserve raw whitespace inside quoted string literals.
- **Status:** RESOLVED.

---

## 3. Before & After Environment Readiness Status

| Environment Probe | Initial State | Final State |
|---|---|---|
| GnuCOBOL Compiler | Not on host PATH | Available via Docker image `gnucobol-ocesql:latest` (EXECUTED) |
| OpenJDK Runtime | OpenJDK 25.0.3 on host PATH | OpenJDK 25.0.3 (target 17 in generated pom.xml) (EXECUTED) |
| Maven Build | BLOCKED (`WinError 2` file not found) | Executing Apache Maven 3.9.16 via `mvn.cmd` (COMPILED) |
| GnuCOBOL Baseline Execution | EXECUTED | EXECUTED (stdout captured) |
| Native Java Execution | BLOCKED / UNVERIFIED | EXECUTED (stdout captured) |
| COBOL-vs-Java Equivalence | FAILED / BLOCKED | **EQUIVALENT** (100% exact match) |

---

## 4. End-to-End Vertical Slice Execution Evidence (`PAYMAIN.cob`)

### Command Executed
```bash
python -m pytest tests/differential/test_paymain_slice.py -v
```

### Output Summary
```text
============================= test session starts =============================
platform win32 -- Python 3.14.3, pytest-9.1.1, pluggy-1.6.0 -- C:\Python314\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\bandi\Desktop\ai-workspace\cobol-java-platform
configfile: pyproject.toml

tests/differential/test_paymain_slice.py::test_paymain_end_to_end PASSED [ 33%]
tests/differential/test_paymain_slice.py::test_paymain_parse_generates_java PASSED [ 66%]
tests/differential/test_paymain_slice.py::test_equivalence_comparator_rules PASSED [100%]

============================= 3 passed in 13.15s ==============================
```

### Stage Evidence Records

1. **Ingest Stage:** `EXECUTED` — config loaded
2. **Discover Stage:** `EXECUTED` — discovered `PAYMAIN.cob`
3. **Parse Stage:** `EXECUTED` — parsed 17 SemanticIR nodes (v2.0)
4. **Generate Stage:** `EXECUTED` — generated `Paymain.java` & `pom.xml`
5. **Baseline Stage:** `EXECUTED` — GnuCOBOL 3.1.2 in `gnucobol-ocesql:latest` container
   - **Baseline STDOUT:**
     ```text
     PAYMENT PROCESSING BATCH STARTED
     ITEMS PROCESSED: 00001
     PAYMENT PROCESSING BATCH COMPLETED
     ```
6. **Java Build Stage:** `EXECUTED` — `mvn compile` + `java -cp target/classes com.platform.test.Paymain`
   - **Java STDOUT:**
     ```text
     PAYMENT PROCESSING BATCH STARTED
     ITEMS PROCESSED: 00001
     PAYMENT PROCESSING BATCH COMPLETED
     ```
7. **Equivalence Stage:** **`EQUIVALENT`** — symmetric comparator confirmed 100% exact match across all output lines and exit codes.

---

## 5. Full Test Suite Verification

Command executed:
```bash
python -m pytest tests/ -v
```

Result: **30 passed in 12.95s (0 failures, 0 errors, 0 skipped)**.

---

## 6. Remaining Project Defects & Next Steps

Now that the verification environment is 100% complete and trustworthy, we can proceed to subsequent application capabilities:

1. **Phase 2 — SQL / PostgreSQL Track:** Implement EXEC SQL extractor, DB2 -> PostgreSQL dialect translator, Spring JDBC generator, and differential test for `DB2SELECT01`.
2. **Phase 3 — File I/O Track:** Implement OPEN, CLOSE, READ, WRITE, REWRITE for sequential files.
3. **Phase 4 — VSAM KSDS Track:** Implement VSAM KSDS PostgreSQL indexed table mapping (`VsamIndexedStore.java`).
4. **Phase 5 — JCL Track:** Implement fail-closed JCL parsing and execution orchestration.
