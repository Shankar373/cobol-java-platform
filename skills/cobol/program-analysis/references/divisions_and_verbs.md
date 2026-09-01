# COBOL Divisions, Sections, and Verbs Analysis Reference

## COBOL Structure Hierarchy
1. **IDENTIFICATION DIVISION**: `PROGRAM-ID` definition.
2. **ENVIRONMENT DIVISION**: `CONFIGURATION SECTION` and `INPUT-OUTPUT SECTION` (`FILE-CONTROL`, `SELECT ... ASSIGN`).
3. **DATA DIVISION**:
   - `FILE SECTION`: `FD` records and buffer definitions.
   - `WORKING-STORAGE SECTION`: Variables, structures, level 01-49, 77, 88, REDEFINES, OCCURS.
   - `LOCAL-STORAGE SECTION`: Thread-local / recursion variables.
   - `LINKAGE SECTION`: Parameter passing for `CALL` and `DFHCOMMAREA`.
4. **PROCEDURE DIVISION**: `USING` parameters, sections, paragraphs, statements.

## Supported Verbs and Statements
- **Data Movement**: `MOVE`, `MOVE CORRESPONDING`, `INITIALIZE`, `SET`.
- **Arithmetic**: `ADD`, `SUBTRACT`, `MULTIPLY`, `DIVIDE`, `COMPUTE`.
- **Control Flow**: `PERFORM`, `PERFORM THRU`, `PERFORM UNTIL`, `PERFORM VARYING`, `GO TO`, `IF/ELSE`, `EVALUATE/WHEN`, `EXIT`, `CONTINUE`, `GOBACK`, `STOP RUN`.
- **File I/O**: `OPEN`, `CLOSE`, `READ`, `WRITE`, `REWRITE`, `DELETE`, `START`.
- **Inter-Program**: `CALL ... USING BY REFERENCE / CONTENT / VALUE`.
- **String Operations**: `STRING`, `UNSTRING`, `INSPECT`.
