# Known Limitations

This document lists the architectural constraints and emulation limits of the current platform version.

---

## 1. Mainframe Interface Emulations

1.  **CICS Terminal Emulator**:
    *   *Limit*: Screen maps (`BMS` screens) are emulated in text format over standard console streams. The platform does not support real 3270 block-mode terminal drivers.
2.  **DB2 Host Environment**:
    *   *Limit*: SQL commands run against local JPA/Hibernate in-memory (H2) databases. Mainframe-specific features (such as DB2 plan bindings, transaction monitors, or explicit host variable isolation types) are emulated via standard JDBC.
3.  **JCL z/OS Parameter Mappings**:
    *   *Limit*: JCL step controls (e.g. `SPACE`, `UNIT`, and catalog flags) are ignored. Dataset dependencies are emulated via local directory paths.

---

## 2. Compiler Limits

1.  **Pointers & Direct Address Access**:
    *   COBOL constructs involving memory address updates (`SET ADDRESS OF var TO ptr`) are not supported and must be bypassed or rewritten.
2.  **Report Writer Breaks**:
    *   Complex control break headers and detail loops in `REPORT SECTION` are only partially parsed and require manual Spring Batch report generator stubs.
3.  **Dynamic CALL Resolution**:
    *   Program calls resolved at runtime (`CALL ws-program-name`) produce warnings and require explicit mapping dictionaries inside `migration_config.json`.
4.  **Integer/Long Fast-Path Limitations**:
    *   Variables without implied decimal points (`V`) or `COMP-3` usage are mapped to native Java `int` or `long` primitives. Size error checking (`ON SIZE ERROR`) relies on inlined absolute limits rather than precise zoned-decimal overflows. Direct binary serialization of these fields requires temporary conversions to avoid signed overpunch formatting discrepancies.
5.  **Divide-by-Zero Process Behavior Divergence**:
    *   Division by zero in GnuCOBOL crashes the program (triggering operating system signals like `SIGFPE` with exit code 136 and outputting platform-dependent crash messages). Modernized Java programs handle division by zero via inline checks or standard arithmetic exceptions, terminating with exit code 1 or logging to stderr, leading to minor process exit-code and stderr formatting divergence.
