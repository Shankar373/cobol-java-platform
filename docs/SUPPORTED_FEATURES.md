# Supported COBOL Features

This document provides a matrix of COBOL grammar and batch statements supported by the compiler engine.

---

## Feature Matrix

| Feature / Statement | Support Tier | Description |
|---|---|---|
| **EVALUATE** | `VERIFIED` | Translated to standard Java `switch` or `if-else` blocks. |
| **PERFORM VARYING** | `VERIFIED` | Emitted as standard Java loops with break-guard indices. |
| **REDEFINES** | `VERIFIED` | Mapped to native Java getters/setters performing substring or ByteBuffer views over overlapping memory. |
| **OCCURS / OCCURS DEPENDING** | `VERIFIED` | Subscripted arrays backed by Java lists or arrays. |
| **CALL ... USING** | `VERIFIED` | Arguments passed by reference wrapping values inside custom `CobolRef` objects. |
| **SORT / MERGE** | `VERIFIED` | Executed using native JVM-based collection sorting utilities. |
| **VSAM Files (Indexed)** | `EMULATED` | Simulated locally using persistent SQLite indexed tables. |
| **Report Writer** | `PARTIAL` | Translates page formats but complex control breaks are bypassed. |
| **Embedded DB2 SQL** | `EMULATED` | Executed via JDBC / JPA bindings using an emulated local SQL database. |
| **CICS / BMS Maps** | `EMULATED` | Parses screens map coordinates and mocks transactions via standard I/O streams. |
| **POINTER / ADDRESS OF** | `UNSUPPORTED` | Unsupported; memory pointers are bypassed/ignored. |
