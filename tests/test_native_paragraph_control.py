import sys
import os
import subprocess
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.utils.cobol_runner import run_cobol_code

def test_natural_sequential_fallthrough_non_alpha():
    code = """
        IDENTIFICATION DIVISION.
        PROGRAM-ID. FALLTHRU.
        PROCEDURE DIVISION.
        Z-PARA.
            DISPLAY "Z".
        A-PARA.
            DISPLAY "A".
        M-PARA.
            DISPLAY "M".
    """
    code_val, output = run_cobol_code("FALLTHRU", code)
    assert code_val == 0
    assert output == ["Z", "A", "M"]

def test_perform_paragraph():
    code = """
        IDENTIFICATION DIVISION.
        PROGRAM-ID. PERFTEST.
        PROCEDURE DIVISION.
        MAIN-PARA.
            DISPLAY "START".
            PERFORM SUB-PARA.
            DISPLAY "END".
            STOP RUN.
        SUB-PARA.
            DISPLAY "SUB".
    """
    code_val, output = run_cobol_code("PERFTEST", code)
    assert code_val == 0
    assert output == ["START", "SUB", "END"]

def test_perform_thru_source_order():
    code = """
        IDENTIFICATION DIVISION.
        PROGRAM-ID. THRUTEST.
        PROCEDURE DIVISION.
        MAIN-PARA.
            PERFORM Z-PARA THRU M-PARA.
            STOP RUN.
        Z-PARA.
            DISPLAY "Z".
        A-PARA.
            DISPLAY "A".
        M-PARA.
            DISPLAY "M".
        OTHER-PARA.
            DISPLAY "O".
    """
    code_val, output = run_cobol_code("THRUTEST", code)
    assert code_val == 0
    assert output == ["Z", "A", "M"]

def test_nested_performs():
    code = """
        IDENTIFICATION DIVISION.
        PROGRAM-ID. NESTTEST.
        PROCEDURE DIVISION.
        MAIN-PARA.
            PERFORM OUTER-PARA.
            STOP RUN.
        OUTER-PARA.
            DISPLAY "OUTER-START".
            PERFORM INNER-PARA.
            DISPLAY "OUTER-END".
        INNER-PARA.
            DISPLAY "INNER".
    """
    code_val, output = run_cobol_code("NESTTEST", code)
    assert code_val == 0
    assert output == ["OUTER-START", "INNER", "OUTER-END"]

def test_stop_run_semantics():
    code = """
        IDENTIFICATION DIVISION.
        PROGRAM-ID. STOPTEST.
        PROCEDURE DIVISION.
        MAIN-PARA.
            DISPLAY "START".
            STOP RUN.
            DISPLAY "UNREACHABLE".
    """
    code_val, output = run_cobol_code("STOPTEST", code)
    assert code_val == 0
    assert output == ["START"]
