import sys
import os
import subprocess
import tempfile
import shutil
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.utils.cobol_runner import run_cobol_code
from modernize.lexer import CobolLexer
from modernize.parser import CobolParser
from modernize.native_generator import NativeProgramGenerator

def test_goto_same_paragraph():
    code = """
        IDENTIFICATION DIVISION.
        PROGRAM-ID. GOTOSAME.
        PROCEDURE DIVISION.
        MAIN-PARA.
            DISPLAY "HELLO".
            GO TO MAIN-PARA.
            DISPLAY "WORLD".
    """
    # This would loop infinitely, so we won't execute it, but we can verify it parses and generates correctly.
    lexer = CobolLexer("gotosame.cob")
    tokens = lexer.tokenize(code)
    parser = CobolParser(tokens, "gotosame.cob")
    ir = parser.parse()
    gen = NativeProgramGenerator("GOTOSAME", list(ir.nodes.values()))
    src = gen.generate_class_source()
    assert "nextParagraphIndex = getParagraphIndex(\"main_para\");" in src

def test_goto_another_paragraph():
    code = """
        IDENTIFICATION DIVISION.
        PROGRAM-ID. GOTOOTHER.
        PROCEDURE DIVISION.
        FIRST-PARA.
            DISPLAY "FIRST".
            GO TO THIRD-PARA.
            DISPLAY "SECOND".
        SECOND-PARA.
            DISPLAY "SECOND-PARA-RUN".
        THIRD-PARA.
            DISPLAY "THIRD".
            STOP RUN.
    """
    code_val, output = run_cobol_code("GOTOOTHER", code)
    assert code_val == 0
    assert output == ["FIRST", "THIRD"]

def test_conditional_goto():
    code = """
        IDENTIFICATION DIVISION.
        PROGRAM-ID. CONDGOTO.
        DATA DIVISION.
        WORKING-STORAGE SECTION.
        01  WS-VAL  PIC 9 VALUE 1.
        PROCEDURE DIVISION.
        FIRST-PARA.
            IF WS-VAL = 1
                GO TO THIRD-PARA
            END-IF.
            DISPLAY "SECOND".
        THIRD-PARA.
            DISPLAY "THIRD".
            STOP RUN.
    """
    code_val, output = run_cobol_code("CONDGOTO", code)
    assert code_val == 0
    assert output == ["THIRD"]

def test_goto_after_perform():
    code = """
        IDENTIFICATION DIVISION.
        PROGRAM-ID. GOTOPERF.
        PROCEDURE DIVISION.
        MAIN-PARA.
            PERFORM SUB-PARA.
            DISPLAY "AFTER-PERFORM".
            STOP RUN.
        SUB-PARA.
            DISPLAY "SUB".
            GO TO TARGET-PARA.
            DISPLAY "SUB-END".
        TARGET-PARA.
            DISPLAY "TARGET".
    """
    code_val, output = run_cobol_code("GOTOPERF", code)
    assert code_val == 0
    # PERFORM to SUB-PARA executes SUB. SUB-PARA jumps outside range to TARGET-PARA.
    # Therefore, SUB-END is skipped, and control returns to main_loop dispatcher executing TARGET-PARA.
    assert "SUB" in output
    assert "TARGET" in output
    assert "SUB-END" not in output

def test_goto_unresolved():
    code = """
        IDENTIFICATION DIVISION.
        PROGRAM-ID. GOTOUNRES.
        PROCEDURE DIVISION.
        MAIN-PARA.
            GO TO MISSING-PARA.
    """
    lexer = CobolLexer("gotounres.cob")
    tokens = lexer.tokenize(code)
    parser = CobolParser(tokens, "gotounres.cob")
    ir = parser.parse()
    gen = NativeProgramGenerator("GOTOUNRES", list(ir.nodes.values()))
    src = gen.generate_class_source()
    assert len(gen.diagnostics) > 0
    assert gen.diagnostics[0]["construct"] == "GO TO"
    assert "Unresolved GO TO target" in gen.diagnostics[0]["detail"]

def test_continue_standalone():
    code = """
        IDENTIFICATION DIVISION.
        PROGRAM-ID. CONTST.
        PROCEDURE DIVISION.
        MAIN-PARA.
            DISPLAY "BEFORE".
            CONTINUE.
            DISPLAY "AFTER".
            STOP RUN.
    """
    code_val, output = run_cobol_code("CONTST", code)
    assert code_val == 0
    assert output == ["BEFORE", "AFTER"]

def test_continue_conditional():
    code = """
        IDENTIFICATION DIVISION.
        PROGRAM-ID. CONTCOND.
        DATA DIVISION.
        WORKING-STORAGE SECTION.
        01  WS-VAL  PIC 9 VALUE 1.
        PROCEDURE DIVISION.
        MAIN-PARA.
            IF WS-VAL = 1
                CONTINUE
            ELSE
                DISPLAY "ELSE"
            END-IF.
            DISPLAY "DONE".
            STOP RUN.
    """
    code_val, output = run_cobol_code("CONTCOND", code)
    assert code_val == 0
    assert output == ["DONE"]

def test_exit_perform_single_loop():
    code = """
        IDENTIFICATION DIVISION.
        PROGRAM-ID. EXITPERF1.
        DATA DIVISION.
        WORKING-STORAGE SECTION.
        01  WS-IDX   PIC 9 VALUE 0.
        PROCEDURE DIVISION.
        MAIN-PARA.
            PERFORM UNTIL WS-IDX = 5
                ADD 1 TO WS-IDX
                IF WS-IDX = 3
                    EXIT PERFORM
                END-IF
                DISPLAY WS-IDX
            END-PERFORM.
            DISPLAY "EXITED".
            STOP RUN.
    """
    code_val, output = run_cobol_code("EXITPERF1", code)
    assert code_val == 0
    assert output == ["1", "2", "EXITED"]

def test_exit_perform_nested_loop():
    code = """
        IDENTIFICATION DIVISION.
        PROGRAM-ID. EXITPERFN.
        DATA DIVISION.
        WORKING-STORAGE SECTION.
        01  I  PIC 9 VALUE 0.
        01  J  PIC 9 VALUE 0.
        PROCEDURE DIVISION.
        MAIN-PARA.
            PERFORM UNTIL I = 3
                ADD 1 TO I
                MOVE 0 TO J
                PERFORM UNTIL J = 3
                    ADD 1 TO J
                    IF J = 2
                        EXIT PERFORM
                    END-IF
                    DISPLAY J
                END-PERFORM
            END-PERFORM.
            STOP RUN.
    """
    code_val, output = run_cobol_code("EXITPERFN", code)
    assert code_val == 0
    assert output == ["1", "1", "1"]

def test_exit_paragraph_fallthrough():
    code = """
        IDENTIFICATION DIVISION.
        PROGRAM-ID. EXITPARAFALL.
        PROCEDURE DIVISION.
        FIRST-PARA.
            DISPLAY "FIRST-START".
            EXIT PARAGRAPH.
            DISPLAY "FIRST-END".
        SECOND-PARA.
            DISPLAY "SECOND".
            STOP RUN.
    """
    code_val, output = run_cobol_code("EXITPARAFALL", code)
    assert code_val == 0
    assert output == ["FIRST-START", "SECOND"]

def test_exit_paragraph_performed():
    code = """
        IDENTIFICATION DIVISION.
        PROGRAM-ID. EXITPARAPERF.
        PROCEDURE DIVISION.
        MAIN-PARA.
            PERFORM SUB-PARA.
            DISPLAY "BACK".
            STOP RUN.
        SUB-PARA.
            DISPLAY "SUB-START".
            EXIT PARAGRAPH.
            DISPLAY "SUB-END".
    """
    code_val, output = run_cobol_code("EXITPARAPERF", code)
    assert code_val == 0
    assert output == ["SUB-START", "BACK"]

def test_exit_paragraph_conditional():
    code = """
        IDENTIFICATION DIVISION.
        PROGRAM-ID. EXITPARACOND.
        DATA DIVISION.
        WORKING-STORAGE SECTION.
        01  WS-VAL  PIC 9 VALUE 1.
        PROCEDURE DIVISION.
        MAIN-PARA.
            DISPLAY "START".
            IF WS-VAL = 1
                EXIT PARAGRAPH
            END-IF.
            DISPLAY "END".
    """
    code_val, output = run_cobol_code("EXITPARACOND", code)
    assert code_val == 0
    assert output == ["START"]

def test_exit_section():
    code = """
        IDENTIFICATION DIVISION.
        PROGRAM-ID. EXITSEC.
        PROCEDURE DIVISION.
        SEC-A SECTION.
        PARA-1.
            DISPLAY "PARA-1".
            EXIT SECTION.
            DISPLAY "PARA-1-END".
        PARA-2.
            DISPLAY "PARA-2".
        SEC-B SECTION.
        PARA-3.
            DISPLAY "PARA-3".
            STOP RUN.
    """
    code_val, output = run_cobol_code("EXITSEC", code)
    assert code_val == 0
    assert output == ["PARA-1", "PARA-3"]
