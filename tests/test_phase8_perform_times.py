import sys
import os
import subprocess
import tempfile
import shutil
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.utils.cobol_runner import run_cobol_code

def test_perform_times_zero():
    code = """
        IDENTIFICATION DIVISION.
        PROGRAM-ID. PERFTIMES0.
        PROCEDURE DIVISION.
        MAIN-PARA.
            PERFORM 0 TIMES
                DISPLAY "LOOPED"
            END-PERFORM.
            DISPLAY "DONE".
            STOP RUN.
    """
    code_val, output = run_cobol_code("PERFTIMES0", code)
    assert code_val == 0
    assert output == ["DONE"]

def test_perform_times_one():
    code = """
        IDENTIFICATION DIVISION.
        PROGRAM-ID. PERFTIMES1.
        PROCEDURE DIVISION.
        MAIN-PARA.
            PERFORM 1 TIMES
                DISPLAY "ONCE"
            END-PERFORM.
            STOP RUN.
    """
    code_val, output = run_cobol_code("PERFTIMES1", code)
    assert code_val == 0
    assert output == ["ONCE"]

def test_perform_times_multiple():
    code = """
        IDENTIFICATION DIVISION.
        PROGRAM-ID. PERFTIMESM.
        PROCEDURE DIVISION.
        MAIN-PARA.
            PERFORM 3 TIMES
                DISPLAY "HELLO"
            END-PERFORM.
            STOP RUN.
    """
    code_val, output = run_cobol_code("PERFTIMESM", code)
    assert code_val == 0
    assert output == ["HELLO", "HELLO", "HELLO"]

def test_perform_times_nested():
    code = """
        IDENTIFICATION DIVISION.
        PROGRAM-ID. PERFTIMESN.
        PROCEDURE DIVISION.
        MAIN-PARA.
            PERFORM 2 TIMES
                PERFORM 3 TIMES
                    DISPLAY "NEST"
                END-PERFORM
            END-PERFORM.
            STOP RUN.
    """
    code_val, output = run_cobol_code("PERFTIMESN", code)
    assert code_val == 0
    assert len(output) == 6
    assert output == ["NEST"] * 6

def test_perform_times_exit_perform():
    code = """
        IDENTIFICATION DIVISION.
        PROGRAM-ID. PERFTIMESEX.
        PROCEDURE DIVISION.
        MAIN-PARA.
            PERFORM 5 TIMES
                DISPLAY "LOOP"
                EXIT PERFORM
            END-PERFORM.
            STOP RUN.
    """
    code_val, output = run_cobol_code("PERFTIMESEX", code)
    assert code_val == 0
    assert output == ["LOOP"]

def test_perform_times_conditional():
    code = """
        IDENTIFICATION DIVISION.
        PROGRAM-ID. PERFTIMESCOND.
        DATA DIVISION.
        WORKING-STORAGE SECTION.
        01  WS-VAL  PIC 9 VALUE 1.
        PROCEDURE DIVISION.
        MAIN-PARA.
            PERFORM 3 TIMES
                IF WS-VAL = 1
                    DISPLAY "RUN"
                END-IF
            END-PERFORM.
            STOP RUN.
    """
    code_val, output = run_cobol_code("PERFTIMESCOND", code)
    assert code_val == 0
    assert output == ["RUN", "RUN", "RUN"]

def test_perform_times_out_of_line():
    code = """
        IDENTIFICATION DIVISION.
        PROGRAM-ID. PERFTIMESOUT.
        PROCEDURE DIVISION.
        MAIN-PARA.
            PERFORM SUB-PARA 3 TIMES.
            STOP RUN.
        SUB-PARA.
            DISPLAY "SUB".
    """
    code_val, output = run_cobol_code("PERFTIMESOUT", code)
    assert code_val == 0
    assert output == ["SUB", "SUB", "SUB"]
