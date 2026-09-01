import pytest
import os
import shutil
from modernize.lexer import CobolLexer
from modernize.parser import CobolParser
from modernize.native_generator import NativeProgramGenerator
from tests.test_phase8_file_semantics import run_cobol_code

def test_unstring_basic_and_delimiters():
    code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. UNSTR1.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-SOURCE PIC X(20) VALUE "A,B,,C".
       01 WS-TGT1   PIC X(5) VALUE "     ".
       01 WS-TGT2   PIC X(5) VALUE "     ".
       01 WS-TGT3   PIC X(5) VALUE "     ".
       01 WS-TGT4   PIC X(5) VALUE "     ".
       01 WS-PTR    PIC 9(2) VALUE 1.
       01 WS-TALLY  PIC 9(2) VALUE 0.
       PROCEDURE DIVISION.
           UNSTRING WS-SOURCE
               DELIMITED BY ","
               INTO WS-TGT1 WS-TGT2 WS-TGT3 WS-TGT4
               WITH POINTER WS-PTR
               TALLYING IN WS-TALLY
               ON OVERFLOW DISPLAY "OVERFLOW OCCURRED"
               NOT ON OVERFLOW DISPLAY "NO OVERFLOW".
           DISPLAY "T1:" WS-TGT1 ":T2:" WS-TGT2 ":T3:" WS-TGT3 ":T4:" WS-TGT4.
           DISPLAY "PTR:" WS-PTR " TALLY:" WS-TALLY.
           GOBACK.
    """
    ret, stdout, stderr, java_src, outputs = run_cobol_code("UNSTR1", code)
    assert ret == 0
    lines = [l.strip() for l in stdout.strip().splitlines()]
    # Check NO OVERFLOW was executed
    assert "NO OVERFLOW" in lines
    # Check fields (empty field WS-TGT3 should remain empty)
    assert "T1:A    :T2:B    :T3:     :T4:C" in lines
    # WS-PTR should be source length + 2 (A,B,,C padded to 20 -> ptr becomes 22)
    # WS-TALLY should count how many target fields were processed (4 fields)
    assert "PTR:22 TALLY:04" in lines

def test_unstring_overflow():
    code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. UNSTR2.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-SOURCE PIC X(10) VALUE "A,B".
       01 WS-TGT1   PIC X(5) VALUE "     ".
       01 WS-PTR    PIC 9(2) VALUE 99.
       PROCEDURE DIVISION.
           UNSTRING WS-SOURCE
               DELIMITED BY ","
               INTO WS-TGT1
               WITH POINTER WS-PTR
               ON OVERFLOW DISPLAY "OVERFLOW OCCURRED".
           GOBACK.
    """
    ret, stdout, stderr, java_src, outputs = run_cobol_code("UNSTR2", code)
    assert ret == 0
    lines = [l.strip() for l in stdout.strip().splitlines()]
    assert "OVERFLOW OCCURRED" in lines

def test_inspect_tallying():
    code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. INSP1.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-STR   PIC X(20) VALUE "ABAAACA".
       01 WS-C1    PIC 9(2) VALUE 0.
       01 WS-C2    PIC 9(2) VALUE 0.
       01 WS-C3    PIC 9(2) VALUE 0.
       PROCEDURE DIVISION.
           INSPECT WS-STR TALLYING WS-C1 FOR ALL "A".
           INSPECT WS-STR TALLYING WS-C2 FOR LEADING "A".
           INSPECT WS-STR TALLYING WS-C3 FOR CHARACTERS.
           DISPLAY "C1:" WS-C1 " C2:" WS-C2 " C3:" WS-C3.
           GOBACK.
    """
    ret, stdout, stderr, java_src, outputs = run_cobol_code("INSP1", code)
    assert ret == 0
    lines = [l.strip() for l in stdout.strip().splitlines()]
    assert "C1:05 C2:01 C3:20" in lines

def test_inspect_replacing():
    code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. INSP2.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-STR   PIC X(10) VALUE "ABAAACA".
       PROCEDURE DIVISION.
           INSPECT WS-STR REPLACING ALL "A" BY "X".
           DISPLAY "ALL:" WS-STR.
           MOVE "ABAAACA" TO WS-STR.
           INSPECT WS-STR REPLACING FIRST "A" BY "Y".
           DISPLAY "FIRST:" WS-STR.
           MOVE "ABAAACA" TO WS-STR.
           INSPECT WS-STR REPLACING LEADING "A" BY "Z".
           DISPLAY "LEAD:" WS-STR.
           GOBACK.
    """
    ret, stdout, stderr, java_src, outputs = run_cobol_code("INSP2", code)
    assert ret == 0
    lines = [l.strip() for l in stdout.strip().splitlines()]
    assert "ALL:XBXXXCX" in lines
    assert "FIRST:YBAAACA" in lines
    assert "LEAD:ZBAAACA" in lines

def test_inspect_converting():
    code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. INSP3.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-STR   PIC X(10) VALUE "ABCDEFG".
       PROCEDURE DIVISION.
           INSPECT WS-STR CONVERTING "ACE" TO "XYZ".
           DISPLAY "CONV:" WS-STR.
           GOBACK.
    """
    ret, stdout, stderr, java_src, outputs = run_cobol_code("INSP3", code)
    assert ret == 0
    lines = [l.strip() for l in stdout.strip().splitlines()]
    assert "CONV:XBYDZFG" in lines

def test_initialize_statement():
    code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. INIT1.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-GROUP.
          05 WS-STR  PIC X(5) VALUE "HELLO".
          05 WS-NUM  PIC 9(3) VALUE 123.
       PROCEDURE DIVISION.
           INITIALIZE WS-GROUP.
           DISPLAY "STR:" WS-STR ":NUM:" WS-NUM.
           GOBACK.
    """
    ret, stdout, stderr, java_src, outputs = run_cobol_code("INIT1", code)
    assert ret == 0
    lines = [l.strip() for l in stdout.strip().splitlines()]
    assert "STR:     :NUM:000" in lines

def test_exit_program_statement():
    code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. MAINPROG.
       PROCEDURE DIVISION.
           DISPLAY "BEFORE CALL".
           CALL "SUBPROG".
           DISPLAY "AFTER CALL".
           GOBACK.
       END PROGRAM MAINPROG.

       IDENTIFICATION DIVISION.
       PROGRAM-ID. SUBPROG.
       PROCEDURE DIVISION.
       MAIN-SUB.
           DISPLAY "BEFORE EXIT".
           PERFORM EXIT-PARA.
           DISPLAY "AFTER EXIT".
           GOBACK.
       EXIT-PARA.
           EXIT PROGRAM.
       END PROGRAM SUBPROG.
    """
    ret, stdout, stderr, java_src, outputs = run_cobol_code("MAINPROG", code)
    assert ret == 0
    lines = [l.strip() for l in stdout.strip().splitlines()]
    assert "BEFORE CALL" in lines
    assert "BEFORE EXIT" in lines
    assert "AFTER CALL" in lines
    assert "AFTER EXIT" not in lines
