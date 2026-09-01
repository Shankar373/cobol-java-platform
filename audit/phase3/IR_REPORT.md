# Phase 3.2 Semantic IR Validation Report

This report documents the structure, schema, and actual output representation of the Semantic IR model.

---

## 1. Validation Verdict & Status

| Component | Status | Verification Evidence |
| :--- | :---: | :--- |
| **Semantic IR** | `VERIFIED` | Custom Semantic IR schema mapping parsed nodes directly from actual COBOL source. Preserves exact line, column, offsets, kind, status, and custom properties. Checked by `tests/test_semantic_ir.py`. |

---

## 2. Evidence Registry

### Created Files
- **[`tests/test_semantic_ir.py`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/tests/test_semantic_ir.py)**: Serialization validation.

### Executed Tests
```powershell
python -m pytest tests/test_semantic_ir.py -v
```
**Outcome**:
```
tests/test_semantic_ir.py::test_semantic_ir_serialization_and_persistence PASSED [100%]
```

---

## 3. IR Node Statistics (from test_prog.cob parse)

- **Total Programs**: 1
- **Total Divisions**: 4
- **Total Sections**: 3
- **Total Paragraphs**: 1
- **Total Data Items / Variables**: 7 (including level 01, 05, and 88)
- **Total Statements**: 11 (including MOVE, COMPUTE, IF, ELSE, PERFORM, CALL, END-IF, READ, WRITE, STOP RUN)

---

## 4. Example Generated IR JSON

Excerpts from the parsed model showing exact source location preserves:
```json
{
  "schema_version": "1.0",
  "nodes": {
    "node_00008": {
      "node_id": "node_00008",
      "kind": "DATA_ITEM",
      "status": "PARSED",
      "properties": {
        "name": "WS-SUB-VAR",
        "level": 5,
        "picture": "X(10)",
        "usage": null,
        "value": "HELLO",
        "redefines": null,
        "occurs": null,
        "signed": false,
        "digits": 0,
        "scale": 0,
        "is_group": false,
        "condition_values": []
      },
      "source_location": {
        "file": "test_prog.cob",
        "line": 8,
        "column": 12,
        "start_offset": 236,
        "end_offset": 288
      }
    },
    "node_00017": {
      "node_id": "node_00017",
      "kind": "STATEMENT",
      "status": "PARSED",
      "properties": {
        "statement_type": "COMPUTE",
        "target": "WS-NUMERIC-VAR",
        "expression": "12.34 + 5.0"
      },
      "source_location": {
        "file": "test_prog.cob",
        "line": 17,
        "column": 12,
        "start_offset": 622,
        "end_offset": 665
      }
    }
  }
}
```
---

## 5. Known Limitations
- **Declaratives Section**: Structure inside declaratives blocks is parsed as generic division code blocks rather than custom Declarative scopes.
