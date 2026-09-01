import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modernize.lexer import CobolLexer
from modernize.parser import CobolParser
from modernize.native_generator import NativeProgramGenerator

def parse_to_ir_types(content: str) -> list:
    filename = "dummy.cob"
    lexer = CobolLexer(filename)
    tokens = lexer.tokenize(content)
    parser = CobolParser(tokens, filename)
    ir = parser.parse()
    
    # Extract statement types in order of definition line
    stmts = []
    for node in sorted(ir.nodes.values(), key=lambda n: n.source_line):
        if node.kind == "STATEMENT":
            stmts.append(node.properties.get("statement_type", ""))
    return stmts

def test_single_if_period():
    code = """
        IDENTIFICATION DIVISION.
        PROGRAM-ID. TESTPROG.
        PROCEDURE DIVISION.
        PARA-1.
            IF A = B
                MOVE 1 TO C.
    """
    types = parse_to_ir_types(code)
    assert types == ["IF", "MOVE", "END-IF"]

def test_nested_if_period():
    code = """
        IDENTIFICATION DIVISION.
        PROGRAM-ID. TESTPROG.
        PROCEDURE DIVISION.
        PARA-1.
            IF A = B
                IF D = E
                    MOVE 1 TO C.
    """
    types = parse_to_ir_types(code)
    assert types == ["IF", "IF", "MOVE", "END-IF", "END-IF"]

def test_explicit_end_if_followed_by_statement():
    code = """
        IDENTIFICATION DIVISION.
        PROGRAM-ID. TESTPROG.
        PROCEDURE DIVISION.
        PARA-1.
            IF A = B
                MOVE 1 TO C
            END-IF.
            MOVE 2 TO D.
    """
    types = parse_to_ir_types(code)
    # The END-IF was explicit; the period at its end does not generate duplicate END-IF
    assert types == ["IF", "MOVE", "END-IF", "MOVE"]

def test_if_inside_perform():
    code = """
        IDENTIFICATION DIVISION.
        PROGRAM-ID. TESTPROG.
        PROCEDURE DIVISION.
        PARA-1.
            PERFORM UNTIL A = B
                IF C = D
                    MOVE 1 TO E.
    """
    types = parse_to_ir_types(code)
    assert types == ["PERFORM_UNTIL", "IF", "MOVE", "END-IF", "END-PERFORM"]

def test_evaluate_period():
    code = """
        IDENTIFICATION DIVISION.
        PROGRAM-ID. TESTPROG.
        PROCEDURE DIVISION.
        PARA-1.
            EVALUATE A
                WHEN 1
                    MOVE 2 TO B.
    """
    types = parse_to_ir_types(code)
    assert types == ["EVALUATE", "WHEN", "MOVE", "END-EVALUATE"]

def test_nested_evaluate_and_if():
    code = """
        IDENTIFICATION DIVISION.
        PROGRAM-ID. TESTPROG.
        PROCEDURE DIVISION.
        PARA-1.
            EVALUATE A
                WHEN 1
                    IF C = D
                        MOVE 2 TO B.
    """
    types = parse_to_ir_types(code)
    assert types == ["EVALUATE", "WHEN", "IF", "MOVE", "END-IF", "END-EVALUATE"]

def test_multiple_sentences_one_paragraph():
    code = """
        IDENTIFICATION DIVISION.
        PROGRAM-ID. TESTPROG.
        PROCEDURE DIVISION.
        PARA-1.
            IF A = B
                MOVE 1 TO C.
            IF D = E
                MOVE 2 TO F.
    """
    types = parse_to_ir_types(code)
    assert types == ["IF", "MOVE", "END-IF", "IF", "MOVE", "END-IF"]

def test_new_paragraph_resets_sentence():
    code = """
        IDENTIFICATION DIVISION.
        PROGRAM-ID. TESTPROG.
        PROCEDURE DIVISION.
        PARA-1.
            IF A = B
                MOVE 1 TO C
        PARA-2.
            MOVE 2 TO D.
    """
    types = parse_to_ir_types(code)
    assert types == ["IF", "MOVE", "END-IF", "MOVE"]

def test_period_inside_string_literals():
    code = """
        IDENTIFICATION DIVISION.
        PROGRAM-ID. TESTPROG.
        PROCEDURE DIVISION.
        PARA-1.
            DISPLAY "HELLO.WORLD".
    """
    types = parse_to_ir_types(code)
    assert types == ["DISPLAY"]

def test_verify_compiles_and_braces():
    code = """
        IDENTIFICATION DIVISION.
        PROGRAM-ID. TESTPROG.
        DATA DIVISION.
        WORKING-STORAGE SECTION.
        01  A PIC X.
        01  B PIC X.
        01  C PIC X.
        01  D PIC X.
        01  E PIC X.
        PROCEDURE DIVISION.
        PARA-1.
            IF A = B
                IF C = D
                    MOVE 1 TO E.
    """
    filename = "dummy.cob"
    lexer = CobolLexer(filename)
    tokens = lexer.tokenize(code)
    parser = CobolParser(tokens, filename)
    ir = parser.parse()
    gen = NativeProgramGenerator("TESTPROG", list(ir.nodes.values()))
    java_src = gen.generate_class_source()
    
    # Verify generated Java structure has correct braces
    open_count = java_src.count("{")
    close_count = java_src.count("}")
    assert open_count == close_count, "Brace count mismatch in generated Java!"
    assert "if (a.equals(b)) {" in java_src
    assert "if (c.equals(d)) {" in java_src
