# Phase 28: Benchmark Audit Results

- **Benchmark 1 (Accounting)**: Fixed input alignment in run_smoke_test.sh (removed redundant 1000000001 menu offset). Pipeline run: **PASS**.
- **Benchmark 2 (BankCore)**: Added missing `DATA DIVISION.`, renamed `EVENT` keyword collision, aligned parameter sizes (`OP` 8b -> 4b, `INTEREST` 13b -> 11b). Pipeline run: **PASS**.
- **Benchmark 3 (Insurance PAS)**: Added `DATA DIVISION.`, renamed `FINAL` keyword, aligned parameter sizes (`COVERAGE`, `REFUND`). Pipeline run: **PASS**.
- **Benchmark 4 (Mainframe)**: Renamed `STATUS` keyword collision, ignored `ACCOUNT_DML.sql` from compilation list. Pipeline run: **PASS**.
