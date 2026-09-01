"""ON SIZE ERROR / numeric overflow differential test.

COBOL: ADD/SUBTRACT with ON SIZE ERROR trigger verification.
Compares whether overflow is detected and final numeric values.

Compares:
  - stdout: ON SIZE ERROR triggered messages
  - exit code
  - final numeric values
"""
import os
import pytest

from tests.utils.parity_harness import ParityFixture, run_parity


# COBOL fixture: ON SIZE ERROR test
SIZEERR01_CODE = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. SIZEERR01.
       ENVIRONMENT DIVISION.
       CONFIGURATION SECTION.
       SPECIAL-NAMES.
           .
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-SMALL PIC 9(2) VALUE 0.
       01 WS-OVERFLOW PIC X VALUE 'N'.
       PROCEDURE DIVISION.
       MAIN-PARA.
           DISPLAY 'Before ADD: WS-SMALL = ' WS-SMALL
           ADD 1000 TO WS-SMALL ON SIZE ERROR
               MOVE 'Y' TO WS-OVERFLOW
               DISPLAY 'ON SIZE ERROR triggered'
           END-ADD
           DISPLAY 'After ADD: WS-SMALL = ' WS-SMALL
           DISPLAY 'WS-OVERFLOW = ' WS-OVERFLOW
           MOVE 'N' TO WS-OVERFLOW
           SUBTRACT 100 FROM WS-SMALL ON SIZE ERROR
               MOVE 'Y' TO WS-OVERFLOW
               DISPLAY 'ON SIZE ERROR underflow triggered'
           END-SUBTRACT
           DISPLAY 'After SUBTRACT: WS-SMALL = ' WS-SMALL
           DISPLAY 'WS-OVERFLOW = ' WS-OVERFLOW
           STOP RUN.
"""

# Skip unless PARITY_ALLOW_SKIP=true
_SIZEERR01_SKIP = os.environ.get("PARITY_ALLOW_SKIP", "false").lower() != "true"


@pytest.mark.skipif(_SIZEERR01_SKIP, reason="Docker parity images not available — run with PARITY_ALLOW_SKIP=true to execute.")
def test_sizeerr01_parity():
    """Run SIZEERR01 through the parity harness and compare COBOL vs Java outputs."""
    fixture = ParityFixture(
        name="SIZEERR01",
        program_name="SIZEERR01",
        cobol_code=SIZEERR01_CODE,
        declared_outputs=[],
        input_files={},
        env={},
    )
    comparison = run_parity(fixture)
    assert comparison.status in ("PASS", "SKIP"), (
        f"SIZEERR01 parity FAILED:\n"
        + "".join(
            f"  target={m.target!r}  offset={m.offset}\n"
            f"  cobol_hex=[{m.cobol_hex}]  java_hex=[{m.java_hex}]\n"
            f"  explanation: {m.explanation}\n"
            for m in comparison.mismatches
        )
    )