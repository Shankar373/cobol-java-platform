# Repository Detection Rules & Technology Signatures

This document specifies the deterministic detection heuristics used by `repository-discovery`.

## File Extensions and Patterns
- **COBOL Programs**: Files matching `*.cob`, `*.cbl`, `*.pco` (case-insensitive).
- **Copybooks**: Files matching `*.cpy`, `*.cpb`, `*.copy`, `*.cblcopy` or files found within `copybooks/`, `cpy/`, `copylib/` directories.
- **JCL Scripts**: Files matching `*.jcl`, `*.job`, `*.cntl` or containing `//... JOB` statements in column 1-3.
- **BMS 3270 Maps**: Files matching `*.map`, `*.bms` or containing `DFHMSD`, `DFHMDI`, `DFHMDF` macro keywords.
- **SQL Schemas & Scripts**: Files matching `*.sql`, `*.ddl`, `*.dml` or files containing `EXEC SQL` blocks.

## Content-Based Technology Signatures
- **EXEC SQL / DB2**: Content contains `EXEC SQL` and `END-EXEC`.
- **EXEC CICS / Online**: Content contains `EXEC CICS` and `END-EXEC`.
- **VSAM Indexed / KSDS**: Environment or Data Division contains `ORGANIZATION IS INDEXED` or `ACCESS MODE IS RANDOM/DYNAMIC`.
- **Dynamic Program CALLs**: Procedure Division contains `CALL <identifier>` or `CALL 'literal'`.
- **Report Writer**: Data Division contains `REPORT SECTION` or `RD` entries.
