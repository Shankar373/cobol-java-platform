# Phase 2: Business Logic Preservation & Verification

We design a generic business rule extractor tracking mechanism:

## 1. Business Verification Reporting Layout
The final report must list verification test coverage for all discovered business rules:

| Program | Rule ID | COBOL Location | Java Location | Test Case | Status | Evidence |
| :--- | :--- | :--- | :--- | :--- | :---: | :--- |
| `BCPROC01` | BR-01 | Line 159 (ACCT-STATUS NOT = 'A') | `BCPROC01.java:120` | `test_inactive_rejection` | **VERIFIED** | Reject logs match |
| `BCPROC01` | BR-02 | Line 179 (Balance < Overdraft) | `BCPROC01.java:145` | `test_insufficient_debit` | **VERIFIED** | Balance matches |

## 2. Automated Rule Discoveries:
The parser scans for conditional statements (`IF`, `EVALUATE`) and compute blocks (`COMPUTE`), registering them as candidate business rules.
