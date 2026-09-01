# 03. P1 Windows CLI Diagnostic Report

This report documents the diagnostics and root cause of the Windows CLI encoding crash.

---

## 1. Offending Character & Line

- **Offending Character**: Unicode arrow `→` (`\u2192`)
- **Offending Line**: Line 2 in [`audit_engine.py`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/audit_engine.py):
  `"""Audit Engine — 22-point engineering audit for COBOL → Java migration.`
- **Trace**: When the user queries `--help`, `argparse` attempts to format the module's docstring `__doc__` and prints it to the terminal.
- **Root Cause**: Windows consoles in standard US locales default to `cp1252` encoding. The character `→` cannot be mapped by `cp1252`, causing a `UnicodeEncodeError`.

---

## 2. Impact & Scope

- **Affects**: Running `python audit_engine.py --help` crashes.
- **Normal Execution**: Report writing itself is unaffected because files are written using `open(..., encoding="utf-8")`.
- **Minimal Safe Fix**: Replace the unicode character `→` with `->` in the docstring of `audit_engine.py` (Line 2).
