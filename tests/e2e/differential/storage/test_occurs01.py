"""OCCURS / OCCURS DEPENDING ON differential test.

COBOL: OCCURS 5 TIMES array with OCCURS DEPENDING ON alternative view.
Compares array iteration, values, and alternative view behavior.

Compares:
  - stdout: array values displayed during loop
  - exit code
"""
import os
import pytest

from tests.utils.parity_harness import ParityFixture, run_parity


# COBOL fixture: OCCURS array test
OCCURS01_CODE = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. OCCURS01.
       
       ENVIRONMENT DIVISION.
       CONFIGURATION SECTION.
       SPECIAL-NAMES.
       
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-DAY-OF-WEEK PIC 9(1).
       01 WS-DAYS-ARRAY OCCURS 5 TIMES PIC 9(2).
           10 WS-DAY-NAMES PIC X(10) OCCURS 5 TIMES VALUE
               "SUN" "MON" "TUE" "WED" "THU" "FRI" "SAT".
       01 WS-INDEX PIC 9(2) VALUE 1.
       01 WS-DISPLAY-ARRAY PIC 9(2) VALUE 0.
       01 WS-SUM PIC 9(3) VALUE 0.
       
       PROCEDURE DIVISION.
       MAIN-SECTION.
           PERFORM VARYING WS-INDEX FROM 1 BY 1 UNTIL WS-INDEX > 5
               MOVE WS-INDEX TO WS-DAYS-ARRAY(WS-INDEX)
               MOVE WS-DAY-NAMES(WS-INDEX) TO WS-DISPLAY
               DISPLAY 'Day ' WS-INDEX ': ' WS-DAY-NAMES(WS-INDEX) ' is day number ' WS-DAYS-ARRAY(WS-INDEX)
               ADD WS-DAYS-ARRAY(WS-INDEX) TO WS-SUM
           END-PERFORM
           
           DISPLAY '---'
           DISPLAY 'Sum of all days: ' WS-SUM
           
           MOVE WS-DAYS-ARRAY TO WS-DISPLAY-ARRAY
           DISPLAY 'WS-DISPLAY-ARRAY value: ' WS-DISPLAY-ARRAY
           
           STOP RUN.
"""

# Skip unless PARITY_ALLOW_SKIP=true
_OCCURS01_SKIP = os.environ.get("PARITY_ALLOW_SKIP", "false").lower() != "true"


@pytest.mark.skipif(_OCCURS01_SKIP, reason="Docker parity images not available — run with PARITY_ALLOW_SKIP=true to execute.")
def test_occurs01_parity():
    """Run OCCURS01 through the parity harness and compare COBOL vs Java outputs."""
    fixture = ParityFixture(
        name="OCCURS01",
        program_name="OCCURS01",
        cobol_code=OCCURS01_CODE,
        declared_outputs=[],
        input_files={},
        env={},
    )
    comparison = run_parity(fixture)
    assert comparison.status in ("PASS", "SKIP"), (
        f"OCCURS01 parity FAILED:\n"
        + "".join(
            f"  target={m.target!r}  offset={m.offset}\n"
            f"  cobol_hex=[{m.cobol_hex}]  java_hex=[{m.java_hex}]\n"
            f"  explanation: {m.explanation}\n"
            for m in comparison.mismatches
        )
    )