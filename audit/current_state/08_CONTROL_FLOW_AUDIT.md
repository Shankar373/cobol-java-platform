# 08. Control Flow Audit

This document presents the detailed architectural and correctness audit of the Control Flow Graph (CFG) generation.

---

## 1. Component Location
- **Source File**: [`modernize/control_flow.py`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/modernize/control_flow.py)
- **Tests**: [`tests/test_control_flow.py`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/tests/test_control_flow.py)

---

## 2. CFG Construction & Structure

- **Nodes & Edges**: Maps sequential instructions, conditional branch jumps, and exits.
- **PERFORM / PERFORM THRU**: Tracks dynamic execution loops and paragraph returns.
- **Exit Bounds**: Unsupported looping constructs are mapped to standard statement nodes with exit bounds.
- **Traceability**: Every control flow edge and node stores line coordinates to map traceably back to the original source.
