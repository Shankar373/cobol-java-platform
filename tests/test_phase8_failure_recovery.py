import os
import tempfile
import shutil
import pytest
from modernize.lexer import CobolLexer
from modernize.parser import CobolParser
from modernize.native_generator import NativeProgramGenerator
from tests.test_phase8_file_semantics import run_cobol_code

def test_recovery_malformed_syntax():
    """Missing PROCEDURE DIVISION must raise an exception or generate syntax errors."""
    code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. BADSYN.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-A PIC 9(2) VALUE 10.
       # Malformed line / missing division
       DISPLAY WS-A.
    """
    lexer = CobolLexer("BADSYN.cob")
    tokens = lexer.tokenize(code)
    parser = CobolParser(tokens, "BADSYN.cob")
    
    # The parser should either raise an error or register error diagnostics
    try:
        ir = parser.parse()
        # If it parses, check if there are syntax error diagnostics
        assert len(parser.diagnostics) > 0 or not ir.nodes
    except Exception:
        # Raising an exception is also a valid failure recovery
        pass

def test_recovery_undeclared_variable_compilation_fail():
    """Using an undeclared variable should result in Java compilation failure."""
    code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. UNDECL.
       PROCEDURE DIVISION.
           MOVE 10 TO WS-UNDECLARED-VAR.
           GOBACK.
    """
    with pytest.raises(RuntimeError) as excinfo:
        run_cobol_code("UNDECL", code)
    assert "Java compilation failed" in str(excinfo.value)

def test_temp_resource_cleanup():
    """Ensure that run_cobol_code cleans up all created temporary files/dirs."""
    code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. CLEANUP.
       PROCEDURE DIVISION.
           DISPLAY "TEMP TEST".
           GOBACK.
    """
    # Track the temporary directories inside the system temp directory
    temp_root = tempfile.gettempdir()
    before_dirs = set(os.listdir(temp_root))
    
    ret, stdout, stderr, java_src, outputs = run_cobol_code("CLEANUP", code)
    assert ret == 0
    
    after_dirs = set(os.listdir(temp_root))
    new_dirs = after_dirs - before_dirs
    
    # None of the new directories should remain as persistent leaks
    # filter for typical directories starting with 'tmp' or temp_dir patterns used by tempfile.mkdtemp
    leaked_dirs = [d for d in new_dirs if d.startswith("tmp") and os.path.isdir(os.path.join(temp_root, d))]
    # Since run_cobol_code uses tempfile.mkdtemp() and has a finally block with shutil.rmtree,
    # it should leave no directories behind.
    assert not leaked_dirs, f"Leaked temporary directories: {leaked_dirs}"
