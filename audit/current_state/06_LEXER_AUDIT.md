# 06. COBOL Lexer Audit

This document presents the detailed architectural and correctness audit of the COBOL Lexer implementation.

---

## 1. Component Location
- **Source File**: [`modernize/lexer.py`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/modernize/lexer.py)
- **Tests**: [`tests/test_lexer.py`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/tests/test_lexer.py)

---

## 2. Capabilities Audited

- **Fixed Format Mode**: Skips indicator area (column 7) and scans from column 8 to 72.
- **Free Format Mode**: Scans complete lines without column bounds.
- **Line/Column/Offset Tracking**: Correctly records 1-based line numbers, 1-based columns (relative to Area A), and absolute character offsets in source files.
- **Comments Handling**: Supports standard indicators (asterisk `*` or slash `/` in column 7) and free-format floating inline comments (`*>`).
- **Continuation Lines**: Merges continued literal strings when indicator column contains hyphen `-`.
- **Diagnostics**: Triggers malformed diagnostic records for unknown lexical characters instead of crashing.
