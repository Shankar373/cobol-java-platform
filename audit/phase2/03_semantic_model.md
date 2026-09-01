# Phase 2: Semantic Intermediate Representation (IR) Specification

The Intermediate Representation maps COBOL declarations to structured semantic nodes:

## 1. Data Semantics Schema
For numeric declarations, the model preserves:
- **PIC / PICTURE**: The layout definition.
- **USAGE**: Mapped storage (COMP, COMP-3, DISPLAY, BINARY).
- **Implied Decimals**: Implied scale and precision bounds.
- **Sign**: Signed or unsigned declarations.
- **Groupings**: Level numbers, elementary items, occurs size, and redefines dependencies.

## 2. Control-Flow Semantics
The IR represents execution flow structures:
- Statement blocks (`IF`, `ELSE`, `EVALUATE`, `PERFORM`, `GO TO`, `CONTINUE`, `EXIT`).
- Loops, paragraph transitions, dynamic subprogram `CALL` targets, and returns.

## 3. Operations & Traceability
Traceability references map to exact file and line coordinates:

```json
{
  "node_id": "STMT_0017",
  "operation": "COMPUTE",
  "target": "WS-TOTAL",
  "expression": "WS-QTY * WS-RATE",
  "source_location": {
    "file": "PREMCALC.cob",
    "line": 120,
    "column": 12
  }
}
```
