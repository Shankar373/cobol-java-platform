import pytest
import os
import shutil
from tests.test_phase8_file_semantics import run_cobol_code

def test_add_size_error_unsigned():
    code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. MATH1.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-A PIC 9(2) VALUE 90.
       01 WS-B PIC 9(2) VALUE 15.
       PROCEDURE DIVISION.
           ADD WS-B TO WS-A
               ON SIZE ERROR DISPLAY "SIZE ERROR"
               NOT ON SIZE ERROR DISPLAY "OK:" WS-A.
           GOBACK.
    """
    ret, stdout, stderr, java_src, outputs = run_cobol_code("MATH1", code)
    assert ret == 0
    lines = [l.strip() for l in stdout.strip().splitlines()]
    # 90 + 15 = 105, which exceeds PIC 9(2) (max 99). WS-A should remain unchanged (90).
    assert "SIZE ERROR" in lines
    assert "OK:" not in "".join(lines)

def test_add_size_error_ok():
    code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. MATH2.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-A PIC 9(2) VALUE 80.
       01 WS-B PIC 9(2) VALUE 15.
       PROCEDURE DIVISION.
           ADD WS-B TO WS-A
               ON SIZE ERROR DISPLAY "SIZE ERROR"
               NOT ON SIZE ERROR DISPLAY "OK:" WS-A.
           GOBACK.
    """
    ret, stdout, stderr, java_src, outputs = run_cobol_code("MATH2", code)
    assert ret == 0
    lines = [l.strip() for l in stdout.strip().splitlines()]
    assert "OK:95" in lines

def test_divide_by_zero():
    code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. MATH3.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-A PIC 9(2) VALUE 10.
       01 WS-B PIC 9(2) VALUE 0.
       01 WS-C PIC 9(2) VALUE 50.
       PROCEDURE DIVISION.
           DIVIDE WS-B INTO WS-C
               ON SIZE ERROR DISPLAY "DIV ZERO"
               NOT ON SIZE ERROR DISPLAY "OK:" WS-C.
           GOBACK.
    """
    ret, stdout, stderr, java_src, outputs = run_cobol_code("MATH3", code)
    assert ret == 0
    lines = [l.strip() for l in stdout.strip().splitlines()]
    # Divide by zero is a size error. Target WS-C remains unchanged (50).
    assert "DIV ZERO" in lines
    assert "OK:" not in "".join(lines)

def test_compute_size_error():
    code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. MATH4.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-A PIC 9(2)V99 VALUE 99.99.
       PROCEDURE DIVISION.
           COMPUTE WS-A = WS-A + 0.01
               ON SIZE ERROR DISPLAY "SIZE ERROR"
               NOT ON SIZE ERROR DISPLAY "OK:" WS-A.
           GOBACK.
    """
    ret, stdout, stderr, java_src, outputs = run_cobol_code("MATH4", code)
    assert ret == 0
    lines = [l.strip() for l in stdout.strip().splitlines()]
    # 99.99 + 0.01 = 100.00, which exceeds PIC 9(2)V99 (max 99.99).
    assert "SIZE ERROR" in lines
