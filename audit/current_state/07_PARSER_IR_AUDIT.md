# 07. COBOL Parser / Semantic IR Audit

This document presents the detailed architectural and correctness audit of the COBOL Parser and Semantic IR generation.

---

## 1. Component Location
- **Source File**: [`modernize/parser.py`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/modernize/parser.py)
- **Tests**: [`tests/test_parser.py`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/tests/test_parser.py)

---

## 2. Structural Parsing Capabilities

- **Divisions**: Parses `IDENTIFICATION DIVISION`, `DATA DIVISION`, and `PROCEDURE DIVISION`.
- **Data Declarations**: Correctly maps 01-88 levels data items, `PIC` specifications, `USAGE` clauses (`COMP`, `COMP-3`, `DISPLAY`), `REDEFINES` and `OCCURS` hierarchies.
- **Statement Support**:
  - `MOVE`, `COMPUTE`, `ADD`, `SUBTRACT`, `MULTIPLY`, `DIVIDE`
  - Conditional: `IF` / `ELSE` / `END-IF`, `EVALUATE`
  - Control Jumps: `PERFORM`, `PERFORM THRU`, `CALL`, `GOBACK`, `STOP RUN`
  - File I/O: `OPEN`, `CLOSE`, `READ`, `WRITE`
- **Error Handling & Trailing Periods**: Contains optional consuming rules for trailing periods to prevent parser failures inside nested conditional blocks.
- **Unsupported Constructs**: Maps unsupported tokens to `STATEMENT` nodes with status `UNSUPPORTED` and type `UNKNOWN` traceably, preventing silent drop.
