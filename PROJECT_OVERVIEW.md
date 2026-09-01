# COBOL-to-Java Modernization Platform – Project Overview

> **Single source of truth** for architecture, implementation status, verification, and how to run tests.  
> Last updated: **2026-08-29** (Milestone B, Commit 2 complete).  
> Read this before opening any other document in the repo.

---

## Table of Contents

1. [What This Project Is](#1-what-this-project-is)
2. [High-Level Architecture](#2-high-level-architecture)
3. [Java Runtime Helpers](#3-java-runtime-helpers)
4. [Data Type Mapping](#4-data-type-mapping)
5. [Implementation Status by Milestone](#5-implementation-status-by-milestone)
6. [Verification Tiers](#6-verification-tiers)
7. [Known Limitations and Gaps](#7-known-limitations-and-gaps)
8. [How to Run Tests and Parity Checks](#8-how-to-run-tests-and-parity-checks)
9. [Key Documents](#9-key-documents)

---

## 1. What This Project Is

A **repository-agnostic, fully automated COBOL-to-Java modernization pipeline** that transforms
legacy mainframe COBOL programs into clean, runtime-independent Java (no emulation JARs, no
`libcobj`, no `jp.osscons` wrappers).

**Target environments**

| Layer | Technology |
|-------|-----------|
| Language target | Java 17+ |
| Batch framework | Spring Boot / Spring Batch |
| Database | Spring Data JPA (H2 for tests; DB2/Postgres for production) |
| REST APIs | Spring MVC |
| Legacy baseline | GnuCOBOL 3.1.2.0 (pinned Docker image) |
| CI parity harness | Docker two isolated containers per fixture |

**Key goals**

- Exact numeric behaviour (BigDecimal, explicit rounding modes matching COBOL `ROUNDED` clauses)
- Correct handling of `REDEFINES`, `OCCURS`, `OCCURS DEPENDING ON`, and record layouts
- Faithful file I/O (fixed-length records, VSAM/ISAM patterns)
- Equivalent control flow (`GO TO`, `PERFORM`, `CALL`, `LINKAGE SECTION`)
- Matching error handling (`FILE STATUS`, `ON SIZE ERROR`, `ON OVERFLOW`)
- Structured, actionable diagnostics for every unsupported construct

**How to use this document**

- New contributors: read Sections 1-5 and 8.
- Reviewers/auditors: focus on Sections 5-7 and 9.
- Maintainers: keep this file in sync with `docs/transformation-coverage.md` and the milestone docs.

---

## 2. High-Level Architecture

### 2.1 Transformation pipeline (compiler path)

```text
COBOL source
  |
  v
[Lexer]            modernize/lexer.py
  - Tokenises raw source
  - Expands COPY statements (copybook resolution)
  - Normalises continuation lines
  - Detects fixed/free margin format
  - Guards signed-literal vs binary-operator ambiguity
  |
  v
[Parser]           modernize/parser.py (~148 KB)
  - Builds a SemanticIR node graph
    (VARIABLE, STATEMENT, FILE_CONTROL, ...)
  - Emits structured diagnostics for unknown/unsupported constructs
  |
  v
[Semantic IR]      modernize/semantic_ir.py
  - Typed, immutable node graph passed between pipeline stages
  |
  v
[Native Generator] modernize/native_generator.py (~285 KB)
  - Emits a Java class per COBOL program
  - Handles all statement translation, arithmetic guards, size-error policies,
    DISPLAY byte emitter, CALL guard, and inline helpers
  |
  v
[Parity Harness]   tests/utils/parity_harness.py
  - Runs GnuCOBOL and generated Java in separate pinned Docker containers
  - Byte-compares stdout, stderr, exit code, and declared output files
```

### 2.2 Full pipeline orchestrator (13 stages)

The `cobol_migrate.py` orchestrator manages the end-to-end lifecycle:

| Stage | Name | Output |
|-------|------|--------|
| 0 | Ingest | `source_hashes.json` |
| 1 | Discover | `discovery.json`, call graph |
| 2 | Analyze | `call_graph.json`, file assignments |
| 3 | Baseline | GnuCOBOL golden outputs in `results/legacy/` |
| 4 | Transpile | Raw Java classes via `cobj` (Track A) |
| 5 | Collect | Compiled Track-A classes, stub detection |
| 6 | Preserve | `libcobj.jar` vendored |
| 7 | Generate | Track-B native Java project + provenance manifest |
| 8 | Execute | Track-B Java execution results |
| 9 | Compare | Physical + logical + semantic parity verdict |
| 10 | Refactor | Spring Boot / Spring Batch scaffolding |
| 11 | Validate | Maven compilation check on modernized project |
| 12 | Package | Distributable ZIP |

### 2.3 Two-track output model

| Track | Path | Purpose |
|-------|------|---------|
| A - Emulated | `target/transpiled/` | Legacy verification gate; uses `CobolRef` wrappers |
| B - Native | `target/modernized/` | Production target; pure Java primitives + BigDecimal |

---

## 3. Java Runtime Helpers

Located in `modernize/java_helpers/src/main/java/com/systema/modernized/runtime/`.
Copied into each generated project at transpile time.

| File | Role |
|------|------|
| `CobolNumericSpec.java` | Immutable PIC descriptor: digits, scale, signed, usage, signPosition, signSeparate |
| `CobolNumeric.java` | Mutable numeric field wrapper: `assign()`, `toStorageImage()`, `toDisplayString()` |
| `CobolArithmetic.java` | Static helpers: `checkPrecision()`, add/subtract/multiply/divide/remainder |
| `CobolRoundingMode.java` | 8-mode enum mapping every COBOL `ROUNDED` clause to `java.math.RoundingMode` |
| `AssignResult.java` | Result pair: `boolean sizeError` + `BigDecimal storedValue` |
| `UnsupportedPrecisionException.java` | Thrown when `totalDigits + 9 > 34` (34-digit `DECIMAL128` cap) |
| `SizeErrorPolicy.java` | `CHECKED` / `UNCHECKED` enum |
| `CobolUsage.java` | `DISPLAY` / `COMP_3` enum |
| `CobolSignPosition.java` | `LEADING` / `TRAILING` enum |

`CobolFormatHelper.java` (in `modernize/java_helpers/`) provides COBOL intrinsic functions:
`numval`, `mod`, `currentDate`, `dateOfInteger`, `integerOfDate`, and string helpers.

---

## 4. Data Type Mapping

| COBOL PIC | Java type | Notes |
|-----------|-----------|-------|
| `9(1-9)` (no `V`) | `Integer` | **Fast-path - no `CobolNumeric` wrapper** (see section 7.1) |
| `9(10-18)` (no `V`) | `Long` | **Fast-path - no `CobolNumeric` wrapper** (see section 7.1) |
| `9(n)V9(m)` | `CobolNumeric` | Full runtime path; BigDecimal backed |
| `S9(n)` | `CobolNumeric` (`signed=true`) | Full runtime path |
| `X(n)` | `String` | ISO-8859-1 bytes on `DISPLAY` |
| `9(n) COMP-3` | `CobolNumeric` (`COMP_3`) | BCD pack/unpack in `toStorageImage()` |

Arithmetic always uses `BigDecimal`. Division uses `MathContext.DECIMAL128` (34 digits).
No `double` or `float` is used anywhere for COBOL numeric values.

---

## 5. Implementation Status by Milestone

### Milestone A (complete, verified)

- Basic `MOVE` (PIC X, PIC 9)
- Basic integer `COMPUTE` and `ADD` (no fractions)
- Line-sequential file `OUTPUT` (text, ASCII, trailing-space trim)
- `DISPLAY` (single and multi-operand, byte-safe, no `println` mangling)

Differential parity: **3** GnuCOBOL-vs-Java fixtures, all green.

### Milestone B - Numeric Runtime & Storage Parity (Commit 2 complete)

A total of **36 passed tests** (comprising 31 parity/runtime tests, 4 parser unit tests, and 1 move-multi assignment test) are verified in pinned Docker containers and the local test suite:

- **24 differential parity fixtures** (spec-driven from [`tests/fixtures_spec.json`](tests/fixtures_spec.json))
- **2 Java unit tests** inside Docker (precision guard + `AssignResult` semantics)
- **3 Milestone A carry-forward fixtures**
- **5 Commit 2 storage & verification fixtures** (REDEFINES scalar and COMP-3 views, raw binary file I/O, fast-path audit, fingerprint drift)
- **2 additional parser unit tests** beyond the core parity suite (`test_parser_arithmetic_regression_parsing`, `test_parser_call_modifiers_parsing`)
- **1 move-multi target assignment test** (`test_move_multiple_targets`)

#### 5.1 Commit 2 differential test inventory

- `milestone_b_redefines_scalar_view`: Flat scalar redefines and type-union verification.
- `milestone_b_redefines_comp3_byte_view`: COMP-3 redefined as alphanumeric bytes.
- `milestone_b_fixed_binary_file_io`: Raw record-sequential binary file reads and writes using exact physical field widths.
- `milestone_b_integer_fast_path_audit`: Fast-path primitive Integer and Long variables parity.
- `test_compiler_fingerprint_drift`: Automatic fingerprint validation checks against the pinned GnuCOBOL docker baseline.

Key work completed:

| Item | Detail |
|------|--------|
| Precision cap | `totalDigits + 9 > 34` guard throws `UnsupportedPrecisionException`; uses `MathContext.DECIMAL128` |
| `AssignResult` | `sizeError` boolean; `UNCHECKED` = silent high-order truncation; `CHECKED` = target unchanged |
| Unsigned receivers | `abs(value)` applied before bounds check (`MOVE -5 TO PIC 9(3)` stores `005`, no error) |
| Lexer sign guard | Binary `-` after identifier/literal not misread as signed numeric literal |
| `DISPLAY` emitter | `writeBytes(byte[])` via `System.out.write`; no `println`; newline as `write(10)` |
| COMP-3 roundtrip | Hex-verified: GnuCOBOL and Java emit identical BCD bytes |
| Signed overpunch | Hex-verified: trailing zoned-overpunch bytes match GnuCOBOL `0x40` offset |
| `REDEFINES` overlay | Unified `byte[]` backing store with offset math and getters/setters for type-union parity |
| Raw binary file I/O | Switched sequential file handlers to raw byte stream filters (`BufferedInputStream` / `BufferedOutputStream`) and exact physical width offsets, supporting binary record structures |
| CALL modifiers | Parser fully extracts `BY REFERENCE`, `BY CONTENT`, and `BY VALUE` calling modifiers in USING arguments |
| Drift verification | Added automatic fingerprint validation checks against pinned GnuCOBOL docker image |
| Prohibited rounding | Distinct `ProhibitedRoundingException` for `PROHIBITED` mode; no longer conflated with precision-guard errors |

---

## 6. Verification Tiers

See [`docs/transformation-coverage.md`](docs/transformation-coverage.md) for the full
construct-level matrix with parser locations, generator locations, and test file links.

**Tier definitions:**

- `DIFFERENTIALLY_VERIFIED` - GnuCOBOL and Java outputs compared byte-for-byte in pinned Docker containers.
- `UNIT_TESTED` - behaviour tested in isolation; no GnuCOBOL baseline comparison.
- `UNSUPPORTED` - construct detected; transpile-time diagnostic emitted; no Java code generated.

| Construct | Tier | Verified subset |
|-----------|------|-----------------|
| PIC/USAGE - zero-fill, unsigned sign-drop | `DIFFERENTIALLY_VERIFIED` | Milestone B fixtures |
| COMP-3 - BCD pack/unpack roundtrip | `DIFFERENTIALLY_VERIFIED` | `milestone_b_comp3_roundtrip` |
| Arithmetic - add, divide, truncation, rounding | `DIFFERENTIALLY_VERIFIED` | All 17 Milestone B arithmetic fixtures |
| `COMPUTE` - basic integer | `DIFFERENTIALLY_VERIFIED` | Milestone A fixture only |
| File handling - binary & line-sequential output | `DIFFERENTIALLY_VERIFIED` | `milestone_a_line_sequential_file`, `milestone_b_fixed_binary_file_io` |
| `MOVE` | `DIFFERENTIALLY_VERIFIED` | Milestone A and B assignments (alphanumeric and numeric; integer fast-path subset documented in §7.1) |
| `REDEFINES` | `DIFFERENTIALLY_VERIFIED` | Flat scalar, single group-redefines-scalar, and COMP-3-to-alphanumeric byte views (complex layouts / OCCURS overlays remain PARTIAL) |
| `OCCURS` / `OCCURS DEPENDING ON` | `UNIT_TESTED` | No differential parity yet |
| `GO TO` | `UNIT_TESTED` | Simple targets only |
| `PERFORM` / `PERFORM VARYING` | `UNIT_TESTED` | Loop counts and sequential paragraphs |
| `CALL` and `LINKAGE` | `UNIT_TESTED` | Parser supports parameter modifiers; call runtime isolation pending |
| Embedded DB2 / `EXEC SQL` | `UNIT_TESTED` | H2 emulation only |
| `EXEC CICS` | `UNIT_TESTED` | Mock registry |
| JCL steps | `UNIT_TESTED` | Basic step sequencing |
| IMS / MQ | `UNSUPPORTED` | No parser, no generator, no stubs |
| Date / time intrinsics | `UNIT_TESTED` | No 2-digit century windowing |

---

## 7. Known Limitations and Gaps

### 7.1 Integer/Long fast-path bypasses `CobolNumeric` (Critical)

PIC `9(1-9)` without `V` maps directly to Java `Integer`; PIC `9(10-18)` to `Long`.
These paths have **no `CobolNumeric` wrapper**, which means:

- No zoned-decimal storage image
- No size-error tracking
- No `SizeErrorPolicy` enforcement
- No overpunch serialisation

Any program relying on overflow detection, zoned display output, or file I/O for
integer-only fields may silently diverge.

### 7.2 EBCDIC transcoding support (Documented)

While binary record-sequential file I/O has been modernized to use raw byte streams (`BufferedInputStream` / `BufferedOutputStream`) and exact physical width boundaries (fully resolving binary record layout corruption), EBCDIC-to-ASCII transcoding logic is not implemented natively. Source programs must run with ASCII-encoded datasets. Datasets must be provided in ASCII/ISO-8859-1; EBCDIC sources will not round-trip correctly.

### 7.3 REDEFINES storage overlay support (Partial)

REDEFINES groups are implemented with a shared `byte[]` backing store for:
- Flat scalar REDEFINES (e.g. WS-ALPHA / WS-NUM).
- One group-redefines-scalar case.
- COMP-3 redefined as alphanumeric bytes (tested in `milestone_b_redefines_comp3_byte_view`).

Nested REDEFINES, REDEFINES combined with OCCURS / OCCURS DEPENDING ON, and complex binary layouts are not yet differentially verified and remain PARTIAL.

### 7.4 Divide-by-zero without `ON SIZE ERROR`: exit-code divergence (Documented)

| | GnuCOBOL | Java |
|-|----------|------|
| Behaviour | Aborts with runtime error | Silently skips the divide; keeps prior value |
| stderr | `libcob: ... Arithmetic overflow` | (empty) |
| exit code | 1 | 0 |

The Milestone B fixture passes because stdout matches before the fault point.
The exit-code and stderr divergence is an accepted, documented limitation.

### 7.5 CICS path: catch-based control flow (C1 violation)

`EXEC CICS LINK`, `XCTL`, and `RETURN` are wrapped in `try/catch(Exception)` in generated Java.
Any Java runtime exception is silently caught and mapped to `eibresp = 1`, masking real bugs.
Outside Milestone B scope; fix planned for CICS milestone.

### 7.6 No 2-digit year century windowing

No Y2K century-window logic (`WHEN < 50 ADD 2000`) is implemented.
Programs using 2-digit year arithmetic will silently compute wrong dates.

---

## 8. How to Run Tests and Parity Checks

### Prerequisites

| Tool | Required version | Purpose |
|------|-----------------|---------|
| Python | 3.8+ | Pipeline and test runner |
| Docker | Any recent | Container execution for parity tests |
| GnuCOBOL image | `hurriedreformist/gnucobol:3.1-builder` | Pinned baseline compiler |
| JDK image | `eclipse-temurin:17-jdk-noble` | Pinned Java execution |

**GnuCOBOL version pinned:** 3.1.2.0 (built 2024-02-20, Alpine musl, GMP math, BDB indexed).
Fingerprint file: [`tests/utils/gnucobol_fingerprint.txt`](tests/utils/gnucobol_fingerprint.txt)
SHA-256: `4B4796423E607A4E0AFF9D68940AC5FF6545DDF8776C957C4B0525159BBAF31E`

**Why 3.1.2.0 and not 3.2.x?**
GnuCOBOL 3.2.x changed default `-fsign` behaviour and `BINARY-C-LONG` sizing.
Upgrading would invalidate all existing hex baselines.

### Run the full test suite

```powershell
python -m pytest tests/ -v
```

Expected: **36 passed** (31 parity/runtime tests + 4 parser unit tests + 1 move-multi target assignment test).

### Run only parity fixtures (requires Docker)

```powershell
python -m pytest tests/test_parity_fixtures.py -v
```

Expected: **31 passed** (23 spec-driven fixtures + 2 Java unit tests + 3 Milestone A carry-forward fixtures + 3 standalone Commit 2 verification tests).

### Run parity without Docker (skip mode)

```powershell
$env:PARITY_ALLOW_SKIP="true"; python -m pytest tests/test_parity_fixtures.py -v
```

### Run a single fixture

```powershell
python -m pytest "tests/test_parity_fixtures.py::test_milestone_b_parity[milestone_b_comp3_roundtrip]" -v
```

### Run the audit engine

```powershell
python audit_engine.py --run-synthetic
```

### Start the interactive portal UI

```powershell
python ui.py
```

Open `http://localhost:8787` in your browser.

### Parity harness environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PARITY_RUNTIME` | `docker` | `docker` or `local` for GnuCOBOL execution |
| `PARITY_JAVA_RUNTIME` | `docker` | `docker` or `local` for Java execution |
| `PARITY_GNUCOBOL_IMAGE` | `hurriedreformist/gnucobol:3.1-builder` | GnuCOBOL Docker image |
| `PARITY_JDK_IMAGE` | `eclipse-temurin:17-jdk-noble` | JDK Docker image |
| `PARITY_ALLOW_SKIP` | `false` | Skip parity tests when Docker unavailable |
| `PARITY_KEEP_ARTIFACTS_ON_FAILURE` | `true` | Retain temp dirs on failure for debugging |
| `PARITY_ARTIFACT_DIR` | `artifacts/parity-failures` | Where to copy failed fixture artifacts |

---

## 9. Key Documents

| Document | Location | What it covers |
|----------|----------|----------------|
| This file | `PROJECT_OVERVIEW.md` | Single source of truth |
| Transformation coverage matrix | [`docs/transformation-coverage.md`](docs/transformation-coverage.md) | Per-construct tiers, pipeline locations, evidence links |
| Coverage (machine-readable) | [`docs/transformation-coverage.json`](docs/transformation-coverage.json) | JSON schema for tooling |
| Architecture (two-track model) | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Track A vs Track B compiler diagram |
| Pipeline stages detail | [`docs/PIPELINE.md`](docs/PIPELINE.md) | 13-stage orchestrator |
| Testing guide | [`docs/TESTING.md`](docs/TESTING.md) | Test file inventory, writing parity tests |
| Known platform limitations | [`docs/KNOWN_LIMITATIONS.md`](docs/KNOWN_LIMITATIONS.md) | CICS/DB2/JCL emulation limits |
| Security policy | [`docs/SECURITY.md`](docs/SECURITY.md) | Responsible disclosure |
| GnuCOBOL compiler fingerprint | [`tests/utils/gnucobol_fingerprint.txt`](tests/utils/gnucobol_fingerprint.txt) | Full `cobc --info` output |
| Parity fixture spec | [`tests/fixtures_spec.json`](tests/fixtures_spec.json) | All Milestone B differential fixtures |
| Parity harness | [`tests/utils/parity_harness.py`](tests/utils/parity_harness.py) | Docker execution and byte comparison engine |
