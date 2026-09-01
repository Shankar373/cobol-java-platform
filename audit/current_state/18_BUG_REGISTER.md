# 18. Bug Register

This document registers verified code defects in the repository.

---

## Bug ID: BUG-001
- **Severity**: `P1` (Major functional defect)
- **Component**: Audit Engine CLI
- **File**: [`audit_engine.py`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/audit_engine.py)
- **Line(s)**: `argparse.ArgumentParser` / CLI Print help
- **Reproduction**: Run `python audit_engine.py --help` on Windows Command Prompt or PowerShell (CP1252 console).
- **Expected**: Prints help documentation successfully.
- **Actual**: Crashes with `UnicodeEncodeError: 'charmap' codec can't encode character '\u2192'`.
- **Root Cause**: The module's docstring and help messages contain the unicode arrow symbol `→` (`\u2192`), which is not present in CP1252 character maps.
- **Impact**: Prevents users from querying help options or executing the audit engine on Windows standard terminal configurations.
- **Recommended Fix**: Replace all instances of `→` with `->` in the command line docs.
- **Regression Test Required**: Yes.
