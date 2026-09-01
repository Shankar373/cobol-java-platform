# 05. Audit Findings Revalidation Report

This report documents the verification and revalidation of the findings reported in the previous repository audit.

---

## 1. Revalidation Verdicts

| Finding ID | Finding Description | Severity | Revalidation Status |
| :--- | :--- | :---: | :--- |
| **P0-001** | Spring Boot Refactoring benchmark coupling. | `P0` | **CONFIRMED**. Verified that running on generic repositories (like `INVOICE01`) fails compilation due to hardcoded templates seeding `Policy` classes. |
| **P1-001** | Classpath dependency on `libcobj.jar`. | `P1` | **CONFIRMED**. Verified that generated Java imports namespaces from `jp.osscons.opensourcecobol.libcobj` and fails compilation and execution when the jar is omitted. |
| **P1-002** | Windows CLI Unicode arrow crash. | `P1` | **CONFIRMED**. Verified that running `python audit_engine.py --help` crashes on CP1252 consoles due to unicode arrow `→` in the docstring. |
| **SEC-001** | Web dashboard lacks authentication. | `High` | **CONFIRMED**. Exposes routes on localhost port 8787 without authentication. |
| **SEC-002** | Git branch option injection. | `Medium` | **CONFIRMED**. Git options can be injected via the branch string parameter. |
