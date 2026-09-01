# Mainframe Integration Boundaries Specification
## External Programs, Character Encodings & Subsystem Classifications

---

## 1. External Program Boundary (`CALL`)

### 1.1 Local & Dynamically Resolved Programs
- Programs present in the source repository are linked directly as Java class instances or registered via `CicsProgramRegistry`.
- Dynamic calls using identifier variables (`CALL WS-PROG-NAME`) are looked up dynamically at runtime.

### 1.2 Unresolved External Targets
- If a target program is neither present in the local codebase nor registered, the generator emits an explicit diagnostic comment and records `DYNAMIC_TARGET_UNRESOLVED` to prevent silent no-ops.

---

## 2. Character Encodings & Mainframe Data Types

- **Modernized Target**: Standard ASCII / UTF-8 string encoding on standard JVM.
- **EBCDIC Collating Sequences**: Custom mainframe EBCDIC collation sort tables (`PROGRAM COLLATING SEQUENCE IS EBCDIC`) are classified as `UNSUPPORTED`.
- **Binary Data**: Packed decimal (`COMP-3`), binary (`COMP`/`COMP-4`/`COMP-5`), and raw byte streams are translated to `BigDecimal`, `int`/`long`, and `byte[]`.
