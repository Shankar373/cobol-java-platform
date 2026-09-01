"""
Execution and Semantics Verification for Explicit Scope Terminators
====================================================================
Tests END-ADD, END-SUBTRACT, END-MULTIPLY, END-DIVIDE, and END-COMPUTE:
1. Verifies that the parser establishes correct sentence/statement boundaries.
2. Verifies that ON SIZE ERROR blocks inside END- verbs do not leak following statements.
3. Generates native Java classes, compiles them, and executes to verify runtime behavior.
"""
import os
import shutil
import subprocess
import tempfile
import pytest

from modernize.lexer import CobolLexer
from modernize.parser import CobolParser
from modernize.native_generator import NativeProgramGenerator


def test_end_scope_terminators_ast_and_generation():
    """Verify that all END- arithmetic verbs are parsed without leaking statements."""
    cobol_src = """000100 IDENTIFICATION DIVISION.
000200 PROGRAM-ID. SCOPETEST.
000300 DATA DIVISION.
000400 WORKING-STORAGE SECTION.
000500 01 WS-A PIC 9(2) VALUE 90.
000600 01 WS-B PIC 9(2) VALUE 20.
000700 01 WS-RES PIC 9(2) VALUE 0.
000800 01 WS-FLAG PIC X(10) VALUE "INIT".
000900 01 WS-STEP PIC 9(2) VALUE 0.
001000 PROCEDURE DIVISION.
001100     ADD WS-A TO WS-B GIVING WS-RES
001200         ON SIZE ERROR
001300             MOVE "ADD_ERR" TO WS-FLAG
001400     END-ADD
001500     MOVE 1 TO WS-STEP.
001600     
001700     SUBTRACT WS-A FROM WS-B GIVING WS-RES
001800         ON SIZE ERROR
001900             MOVE "SUB_ERR" TO WS-FLAG
002000     END-SUBTRACT
002100     MOVE 2 TO WS-STEP.
002200     
002300     MULTIPLY WS-A BY WS-B GIVING WS-RES
002400         ON SIZE ERROR
002500             MOVE "MUL_ERR" TO WS-FLAG
002600     END-MULTIPLY
002700     MOVE 3 TO WS-STEP.
002800     
002900     DIVIDE WS-A BY 0 GIVING WS-RES
003000         ON SIZE ERROR
003100             MOVE "DIV_ERR" TO WS-FLAG
003200     END-DIVIDE
003300     MOVE 4 TO WS-STEP.
003400     
003500     COMPUTE WS-RES = WS-A * 10
003600         ON SIZE ERROR
003700             MOVE "CMP_ERR" TO WS-FLAG
003800     END-COMPUTE
003900     MOVE 5 TO WS-STEP.
004000     GOBACK.
"""
    lexer = CobolLexer("SCOPETEST.cob", format_mode="fixed")
    tokens = lexer.tokenize(cobol_src)
    parser = CobolParser(tokens, "SCOPETEST.cob")
    parser.parse()

    statements = [n for n in parser.ir.nodes.values() if n.kind == "STATEMENT"]
    # We expect 5 arithmetic statements + 5 separate MOVE statements + 1 GOBACK = 11 statements
    assert len(statements) == 11, f"Expected 11 top-level statements, got {len(statements)}"

    gen = NativeProgramGenerator("SCOPETEST", list(parser.ir.nodes.values()), [])
    java_code = gen.generate_class_source({"SCOPETEST": gen})

    assert "ADD_ERR" in java_code
    assert "SUB_ERR" in java_code
    assert "MUL_ERR" in java_code
    assert "DIV_ERR" in java_code
    assert "CMP_ERR" in java_code


def test_end_scope_terminators_java_execution():
    """Verify that generated Java with END- scope terminators compiles and executes correctly."""
    cobol_src = """000100 IDENTIFICATION DIVISION.
000200 PROGRAM-ID. SCOPERUN.
000300 DATA DIVISION.
000400 WORKING-STORAGE SECTION.
000500 01 WS-A PIC 9(2) VALUE 90.
000600 01 WS-B PIC 9(2) VALUE 20.
000700 01 WS-RES PIC 9(2) VALUE 0.
000800 01 WS-LOG PIC X(30) VALUE SPACES.
000900 PROCEDURE DIVISION.
001000     ADD WS-A TO WS-B GIVING WS-RES
001100         ON SIZE ERROR
001200             DISPLAY "ADD_OVERFLOW"
001300     END-ADD.
001400     DISPLAY "AFTER_ADD".
001500     
001600     ADD 5 TO 10 GIVING WS-RES
001700         ON SIZE ERROR
001800             DISPLAY "UNEXPECTED_ERROR"
001900     END-ADD.
002000     DISPLAY "NORMAL_ADD_DONE".
002100     GOBACK.
"""
    lexer = CobolLexer("SCOPERUN.cob", format_mode="fixed")
    tokens = lexer.tokenize(cobol_src)
    parser = CobolParser(tokens, "SCOPERUN.cob")
    parser.parse()

    gen = NativeProgramGenerator("SCOPERUN", list(parser.ir.nodes.values()), [])
    java_code = gen.generate_class_source({"SCOPERUN": gen})

    temp_dir = tempfile.mkdtemp(prefix="scope_run_")
    try:
        # Copy runtime helper classes
        src_dir = os.path.join(temp_dir, "com", "systema", "modernized", "runtime")
        gen_dir = os.path.join(temp_dir, "com", "systema", "modernized", "native_gen")
        helper_dir = os.path.join(temp_dir, "com", "systema", "modernized")
        os.makedirs(src_dir, exist_ok=True)
        os.makedirs(gen_dir, exist_ok=True)
        os.makedirs(helper_dir, exist_ok=True)

        helpers_src = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "modernize", "java_helpers", "src", "main", "java", "com", "systema", "modernized")
        )
        for f in ["CobolFormatHelper.java", "JclExecutionContext.java", "CicsProgramRegistry.java"]:
            sf = os.path.join(helpers_src, f)
            if os.path.exists(sf):
                shutil.copy2(sf, os.path.join(helper_dir, f))

        runtime_src = os.path.join(helpers_src, "runtime")
        for f in os.listdir(runtime_src):
            if f.endswith(".java") and not f.startswith("Vsam"):
                shutil.copy2(os.path.join(runtime_src, f), os.path.join(src_dir, f))

        with open(os.path.join(gen_dir, "Scoperun.java"), "w", encoding="utf-8") as fh:
            fh.write(java_code)

        # Collect and compile all java files
        all_java = []
        for root, _, files in os.walk(temp_dir):
            for f in files:
                if f.endswith(".java"):
                    all_java.append(os.path.join(root, f))

        compile_res = subprocess.run(
            ["javac", "-d", temp_dir] + all_java,
            capture_output=True, text=True, timeout=30
        )
        assert compile_res.returncode == 0, f"Javac compilation failed:\n{compile_res.stderr}"

        run_res = subprocess.run(
            ["java", "-cp", temp_dir, "com.systema.modernized.native_gen.Scoperun"],
            capture_output=True, text=True, timeout=15
        )
        assert run_res.returncode == 0, f"Java execution failed:\n{run_res.stderr}"
        stdout = run_res.stdout

        assert "ADD_OVERFLOW" in stdout
        assert "AFTER_ADD" in stdout
        assert "NORMAL_ADD_DONE" in stdout
        assert "UNEXPECTED_ERROR" not in stdout

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
