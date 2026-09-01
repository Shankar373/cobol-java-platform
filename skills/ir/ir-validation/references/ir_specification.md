# Semantic IR Node Graph Specification

## Node Kinds
- `PROGRAM`: Root node defining `program_id`, author, format mode.
- `VARIABLE` / `DATA_ITEM`: Represents variable declarations with level number, name, picture string, usage, occurs count, redefines target, and initial values.
- `SECTION`: Represents a procedural section.
- `PARAGRAPH`: Represents a procedure division paragraph.
- `STATEMENT`: Represents an executable COBOL statement with `statement_type` (e.g. `MOVE`, `ADD`, `PERFORM`, `CALL`, `EXEC_SQL`, `EXEC_CICS`).

## Structural Invariants
1. Node IDs must be unique across the IR graph.
2. Every statement node must specify a valid `statement_type`.
3. Every variable node must have a `name` and level number >= 1.
4. Source location (`file`, `line`, `column`) must be recorded for traceability.
