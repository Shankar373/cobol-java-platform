# IMS / DL/I Database Semantics & Modernization Boundary
## Hierarchical Architecture, Status Codes & Fail-Closed Strategy

---

## 1. Mainframe IMS / DL/I Architecture

Information Management System (IMS) Database Manager (DB) is a hierarchical database management system:
- **Hierarchical Paths**: Root segments, parent-child relationships, twin segments.
- **Program Specification Block (PSB)** & **Program Communication Block (PCB)**: Define application database view.
- **Segment Search Arguments (SSA)**: Qualify segment selection criteria (`GU`, `GN`, `GNP`, `GHU`, `GHN`, `ISRT`, `DLET`, `REPL`).

---

## 2. Modernization Boundary & Fail-Closed Enforcement

- **Current Status**: `UNSUPPORTED / UNPROVEN`.
- **Enforcement**: Any call to `CBLTDLI`, `ASMTDLI`, `PLITDLI`, `AIBTDLI`, or `DFSRRC00` emits:
  `diagnostic: construct="IMS_MQ", status="NATIVE_TRANSLATION_BLOCKED"`
- **Production Guidance**: For enterprise modernizations requiring IMS data migration, transform hierarchical structures into relational models (PostgreSQL with foreign key parent-child relationships or document stores) prior to application logic transpilation.
