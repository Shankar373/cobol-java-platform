import sys
import os
import subprocess
import tempfile
import shutil
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.utils.cobol_runner import run_cobol_code

def test_next_sentence_basic():
    code = """
        IDENTIFICATION DIVISION.
        PROGRAM-ID. NEXTSENT1.
        PROCEDURE DIVISION.
        MAIN-PARA.
            DISPLAY "HELLO".
            NEXT SENTENCE.
            DISPLAY "WORLD".
            DISPLAY "AFTER-PERIOD".
            STOP RUN.
    """
    code_val, output = run_cobol_code("NEXTSENT1", code)
    assert code_val == 0
    # Wait, in NEXTSENT1:
    # `DISPLAY "WORLD".` is Sentence 2.
    # `DISPLAY "AFTER-PERIOD".` is Sentence 3.
    # So executing NEXT SENTENCE in Sentence 1 skips to the start of Sentence 2!
    # Therefore, both "WORLD" and "AFTER-PERIOD" execute!
    assert output == ["HELLO", "WORLD", "AFTER-PERIOD"]

def test_next_sentence_inside_if():
    code = """
        IDENTIFICATION DIVISION.
        PROGRAM-ID. NEXTSENT2.
        DATA DIVISION.
        WORKING-STORAGE SECTION.
        01  WS-VAL  PIC 9 VALUE 1.
        PROCEDURE DIVISION.
        MAIN-PARA.
            IF WS-VAL = 1
                NEXT SENTENCE
            END-IF.
            DISPLAY "AFTER-IF".
            STOP RUN.
    """
    code_val, output = run_cobol_code("NEXTSENT2", code)
    assert code_val == 0
    # NEXT SENTENCE inside IF skips the rest of the sentence.
    # The sentence-ending period is after END-IF.
    # So "AFTER-IF" (which is the start of the next sentence) should execute!
    assert output == ["AFTER-IF"]

def test_next_sentence_multiple_statements():
    code = """
        IDENTIFICATION DIVISION.
        PROGRAM-ID. NEXTSENT3.
        DATA DIVISION.
        WORKING-STORAGE SECTION.
        01  WS-VAL  PIC 9 VALUE 1.
        PROCEDURE DIVISION.
        MAIN-PARA.
            IF WS-VAL = 1
                DISPLAY "MATCH"
                NEXT SENTENCE
                DISPLAY "SKIP-ME"
            END-IF.
            DISPLAY "AFTER-PERIOD".
            STOP RUN.
    """
    code_val, output = run_cobol_code("NEXTSENT3", code)
    assert code_val == 0
    assert "MATCH" in output
    assert "SKIP-ME" not in output
    assert "AFTER-PERIOD" in output

def test_next_sentence_period_in_literal():
    code = """
        IDENTIFICATION DIVISION.
        PROGRAM-ID. NEXTSENT4.
        DATA DIVISION.
        WORKING-STORAGE SECTION.
        01  WS-VAL  PIC 9 VALUE 1.
        PROCEDURE DIVISION.
        MAIN-PARA.
            IF WS-VAL = 1
                NEXT SENTENCE
            END-IF.
            DISPLAY "THIS IS A PERIOD. IT IS IN A LITERAL".
            STOP RUN.
    """
    code_val, output = run_cobol_code("NEXTSENT4", code)
    assert code_val == 0
    assert output == ["THIS IS A PERIOD. IT IS IN A LITERAL"]

def test_next_sentence_nested_scopes():
    code = """
        IDENTIFICATION DIVISION.
        PROGRAM-ID. NEXTSENT5.
        DATA DIVISION.
        WORKING-STORAGE SECTION.
        01  WS-VAL1  PIC 9 VALUE 1.
        01  WS-VAL2  PIC 9 VALUE 2.
        PROCEDURE DIVISION.
        MAIN-PARA.
            IF WS-VAL1 = 1
                IF WS-VAL2 = 2
                    NEXT SENTENCE
                END-IF
                DISPLAY "INNER-SKIP"
            END-IF.
            DISPLAY "OUTER-EXEC".
            STOP RUN.
    """
    code_val, output = run_cobol_code("NEXTSENT5", code)
    assert code_val == 0
    assert "INNER-SKIP" not in output
    assert "OUTER-EXEC" in output
