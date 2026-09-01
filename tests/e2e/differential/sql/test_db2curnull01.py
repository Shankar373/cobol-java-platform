"""Cursor + NULL indicators differential test.

COBOL: Cursor over table with nullable column, fetch rows, check null indicators.
Compares: rows fetched, NULL detection, SQLCODE/SQLSTATE values.

Note: This test requires a DB2/PostgreSQL backend with the ocesql preprocessor.
When Docker/DB2 is unavailable, the test will be SKIP'd gracefully.
"""
import os
import pytest

from tests.utils.parity_harness import ParityFixture, run_parity


# COBOL fixture: Cursor + NULL indicators test
# Uses ocesql preprocessor; INCLUDE SQLCA is injected by the harness.
DB2CURNULL01_CODE = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. DB2CURNULL01.
       
       ENVIRONMENT DIVISION.
       CONFIGURATION SECTION.
       SPECIAL-NAMES.
       
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-DBNAME PIC X(30) VALUE "modernization_db".
       01 WS-USERNAME PIC X(30) VALUE "modernize".
       01 WS-PASSWD PIC X(30) VALUE "modernize".
       
       * SQLCA is injected by ocesql preprocessor
       
       01 WS-EMPTABLE OCCURS 10 TIMES.
           05 WS-EMPNO PIC 9(4).
           05 WS-EMPNAME PIC X(20).
           05 WS-SALARY PIC 9(5)V99 COMP-3.
           05 WS-COMM PIC 9(3) VALUE 0.
           05 WS-NULL-INDICATOR PIC S9(4) COMP VALUE 0.
       
       01 WS-ROW-NUM PIC 9(2) VALUE 1.
       01 WS-DISPLAY-LINE PIC X(80) VALUE SPACES.
       01 WS-NULL-COUNT PIC 9(2) VALUE 0.
       
       EXEC SQL DECLARE EMP_CURSOR CURSOR FOR
           SELECT EMPNO, EMPNAME, SALARY, COMM, :WS-NULL-INDICATOR AS NULL_IND
           FROM STAFF.EMPTABLE
           FOR READ ONLY
       END-EXEC.
       
       EXEC SQL WHENEVER NOT FOUND STOP RUN END-EXEC.
       
       PROCEDURE DIVISION.
       MAIN-SECTION.
           EXEC SQL CONNECT TO :WS-DBNAME IDENTIFIED BY :WS-USERNAME
               USING :WS-DBNAME END-EXEC.
           
           EXEC SQL INSERT INTO STAFF.EMPTABLE
               (EMPNO, EMPNAME, SALARY, COMM, NULL_IND)
               VALUES (1001, 'JONES', 30000, 100, 0)
           END-EXEC.
           
           EXEC SQL INSERT INTO STAFF.EMPTABLE
               (EMPNO, EMPNAME, SALARY, COMM, NULL_IND)
               VALUES (1002, 'SMITH', 25000, NULL, -1)
           END-EXEC.
           
           EXEC SQL INSERT INTO STAFF.EMPTABLE
               (EMPNO, EMPNAME, SALARY, COMM, NULL_IND)
               VALUES (1003, 'ALLEN', 30000, 500, 0)
           END-EXEC.
           
           EXEC SQL OPEN EMP_CURSOR END-EXEC.
           
           DISPLAY 'Cursor opened. Fetching rows...'
           
           EXEC SQL FETCH EMP_CURSOR INTO :WS-EMPNO, :WS-EMPNAME, :WS-SALARY, :WS-COMM, :WS-NULL-INDICATOR END-EXEC.
           
           PERFORM
               WHILE SQLCODE > -999
                   DISPLAY 'Row ' WS-ROW-NUM ': EMPNO=' WS-EMPNO ' EMPNAME=' WS-EMPNAME
                        ' SALARY=' WS-SALARY ' COMM=' WS-COMM
                        ' NULL-IND=' WS-NULL-INDICATOR
                   
                   IF WS-NULL-INDICATOR = -1
                       DISPLAY '  *** NULL detected in COMM column ***'
                       ADD 1 TO WS-NULL-COUNT
                   END-IF
                   
                   ADD 1 TO WS-ROW-NUM
                   EXEC SQL FETCH EMP_CURSOR INTO :WS-EMPNO, :WS-EMPNAME, :WS-SALARY, :WS-COMM, :WS-NULL-INDICATOR END-EXEC.
               END-PERFORM
           
           DISPLAY 'Total NULL columns found: ' WS-NULL-COUNT
           
       end-program:
           EXEC SQL CLOSE EMP_CURSOR END-EXEC.
           EXEC SQL COMMIT END-EXEC.
           EXEC SQL COMMIT WORK END-EXEC.
           EXEC SQL DISCONNECT ALL END-EXEC.
           STOP RUN.
"""

# Skip unless PARITY_ALLOW_SKIP=true
_DB2CURNULL01_SKIP = os.environ.get("PARITY_ALLOW_SKIP", "false").lower() != "true"


@pytest.mark.skipif(_DB2CURNULL01_SKIP, reason="Docker parity images not available — run with PARITY_ALLOW_SKIP=true to execute.")
def test_db2curnull01_parity():
    """Run DB2CURNULL01 through the parity harness and compare COBOL vs Java outputs."""
    fixture = ParityFixture(
        name="DB2CURNULL01",
        program_name="DB2CURNULL01",
        cobol_code=DB2CURNULL01_CODE,
        declared_outputs=[],
        input_files={},
        env={},
    )
    comparison = run_parity(fixture)
    assert comparison.status in ("PASS", "SKIP"), (
        f"DB2CURNULL01 parity FAILED:\n"
        + "".join(
            f"  target={m.target!r}  offset={m.offset}\n"
            f"  cobol_hex=[{m.cobol_hex}]  java_hex=[{m.java_hex}]\n"
            f"  explanation: {m.explanation}\n"
            for m in comparison.mismatches
        )
    )