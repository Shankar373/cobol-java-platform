"""
test_phase8_traceability_extended.py — Step 6: Traceability for new constructs

Extends traceability verification to:
- UNSTRING nodes: COBOL line → lexer token → parser node → IR → Java translation
- INSPECT nodes: same chain
- ON SIZE ERROR / NOT ON SIZE ERROR: source line preserved through IR
- Enterprise generated components: NativeProgramGenerator has source coordinates
"""
import os
import pytest
from modernize.lexer import CobolLexer
from modernize.parser import CobolParser
from modernize.native_generator import NativeProgramGenerator


def _parse_and_gen(name, code):
    lex = CobolLexer(f'{name}.cob')
    toks = lex.tokenize(code)
    parser = CobolParser(toks, f'{name}.cob')
    ir = parser.parse()
    gen = NativeProgramGenerator(name, list(ir.nodes.values()))
    java_src = gen.generate_class_source()
    return ir, gen, java_src, toks


# ─── UNSTRING traceability ────────────────────────────────────────────────

def test_unstring_ir_has_source_line():
    code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TRUNSTR.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-SRC PIC X(10) VALUE "A,B".
       01 WS-T1  PIC X(5).
       01 WS-T2  PIC X(5).
       PROCEDURE DIVISION.
           UNSTRING WS-SRC DELIMITED BY "," INTO WS-T1 WS-T2.
           GOBACK.
    """
    ir, gen, java_src, _ = _parse_and_gen('TRUNSTR', code)
    unstring_nodes = [n for n in ir.nodes.values()
                      if n.kind == 'STATEMENT' and n.properties.get('statement_type') == 'UNSTRING']
    assert unstring_nodes, 'No UNSTRING nodes in IR'
    for node in unstring_nodes:
        assert node.source_line > 0, f'UNSTRING node missing source_line: {node.node_id}'


def test_unstring_ir_has_source_file():
    code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TRUNSTRFILE.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-SRC PIC X(10) VALUE "X-Y".
       01 WS-T1  PIC X(5).
       PROCEDURE DIVISION.
           UNSTRING WS-SRC DELIMITED BY "-" INTO WS-T1.
           GOBACK.
    """
    ir, gen, java_src, _ = _parse_and_gen('TRUNSTRFILE', code)
    unstring_nodes = [n for n in ir.nodes.values()
                      if n.kind == 'STATEMENT' and n.properties.get('statement_type') == 'UNSTRING']
    assert unstring_nodes
    for node in unstring_nodes:
        assert node.source_file, f'UNSTRING node missing source_file: {node.node_id}'
        assert 'TRUNSTRFILE' in node.source_file.upper()


def test_unstring_java_generated():
    """UNSTRING must produce actual Java (not just a comment) in generated code."""
    code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TRUNSTRJAVA.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-SRC PIC X(10) VALUE "P,Q".
       01 WS-T1  PIC X(5).
       01 WS-T2  PIC X(5).
       PROCEDURE DIVISION.
           UNSTRING WS-SRC DELIMITED BY "," INTO WS-T1 WS-T2.
           GOBACK.
    """
    ir, gen, java_src, _ = _parse_and_gen('TRUNSTRJAVA', code)
    assert 'unstring_src' in java_src, 'UNSTRING must produce unstring_src in Java'
    assert '// UNSUPPORTED:' not in java_src, 'UNSTRING must not be marked unsupported'
    blocked = [d for d in gen.diagnostics if d['status'] == 'NATIVE_TRANSLATION_BLOCKED']
    assert not blocked, f'UNSTRING produced blocked diagnostics: {blocked}'


# ─── INSPECT traceability ─────────────────────────────────────────────────

def test_inspect_ir_has_source_line():
    code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TRINSP.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-STR PIC X(10) VALUE "ABCABC".
       01 WS-CNT PIC 9(3)  VALUE 0.
       PROCEDURE DIVISION.
           INSPECT WS-STR TALLYING WS-CNT FOR ALL "A".
           GOBACK.
    """
    ir, gen, java_src, _ = _parse_and_gen('TRINSP', code)
    inspect_nodes = [n for n in ir.nodes.values()
                     if n.kind == 'STATEMENT' and n.properties.get('statement_type') == 'INSPECT']
    assert inspect_nodes, 'No INSPECT nodes in IR'
    for node in inspect_nodes:
        assert node.source_line > 0, f'INSPECT node missing source_line: {node.node_id}'


def test_inspect_java_generated():
    """INSPECT TALLYING must produce Java counting logic, not a comment."""
    code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TRINSPJAVA.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-STR PIC X(10) VALUE "XAXAX".
       01 WS-CNT PIC 9(3)  VALUE 0.
       PROCEDURE DIVISION.
           INSPECT WS-STR TALLYING WS-CNT FOR ALL "A".
           GOBACK.
    """
    ir, gen, java_src, _ = _parse_and_gen('TRINSPJAVA', code)
    assert 's_search' in java_src or 'indexOf' in java_src, \
        'INSPECT TALLYING must produce search logic in Java'
    assert '// UNSUPPORTED:' not in java_src
    blocked = [d for d in gen.diagnostics if d['status'] == 'NATIVE_TRANSLATION_BLOCKED']
    assert not blocked, f'INSPECT produced blocked diagnostics: {blocked}'


def test_inspect_replacing_java_generated():
    code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TRINSPREPL.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-STR PIC X(10) VALUE "HELLO".
       PROCEDURE DIVISION.
           INSPECT WS-STR REPLACING ALL "L" BY "X".
           GOBACK.
    """
    ir, gen, java_src, _ = _parse_and_gen('TRINSPREPL', code)
    assert 'replace' in java_src.lower(), 'INSPECT REPLACING must produce replace logic in Java'
    blocked = [d for d in gen.diagnostics if d['status'] == 'NATIVE_TRANSLATION_BLOCKED']
    assert not blocked


# ─── ON SIZE ERROR traceability ───────────────────────────────────────────

def test_size_error_ir_has_source_line():
    code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TRSIZE.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-A PIC 9(2) VALUE 90.
       01 WS-B PIC 9(2) VALUE 15.
       PROCEDURE DIVISION.
           ADD WS-B TO WS-A
               ON SIZE ERROR DISPLAY "ERR".
           GOBACK.
    """
    ir, gen, java_src, _ = _parse_and_gen('TRSIZE', code)
    stmt_nodes = [n for n in ir.nodes.values() if n.kind == 'STATEMENT']
    add_nodes = [n for n in stmt_nodes if n.properties.get('statement_type') == 'ADD']
    assert add_nodes, 'No ADD nodes in IR'
    for node in add_nodes:
        assert node.source_line > 0, f'ADD node missing source_line: {node.node_id}'


def test_size_error_java_contains_check():
    code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TRSIZEJAVA.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-A PIC 9(2) VALUE 90.
       01 WS-B PIC 9(2) VALUE 15.
       PROCEDURE DIVISION.
           ADD WS-B TO WS-A
               ON SIZE ERROR DISPLAY "ERR"
               NOT ON SIZE ERROR DISPLAY "OK".
           GOBACK.
    """
    ir, gen, java_src, _ = _parse_and_gen('TRSIZEJAVA', code)
    assert 'checkSizeError' in java_src, 'ON SIZE ERROR must produce checkSizeError in Java'
    blocked = [d for d in gen.diagnostics if d['status'] == 'NATIVE_TRANSLATION_BLOCKED']
    assert not blocked, f'SIZE ERROR produced blocked diagnostics: {blocked}'


# ─── Statement chain completeness ────────────────────────────────────────

def test_all_procedure_stmts_have_source_line():
    """Every STATEMENT node in a multi-construct program must have source_line > 0."""
    code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TRCHAIN.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-SRC PIC X(10) VALUE "A,B".
       01 WS-T1  PIC X(5).
       01 WS-T2  PIC X(5).
       01 WS-CNT PIC 9(3) VALUE 0.
       01 WS-X   PIC 9(3) VALUE 0.
       01 WS-Y   PIC 9(3) VALUE 100.
       PROCEDURE DIVISION.
           UNSTRING WS-SRC DELIMITED BY "," INTO WS-T1 WS-T2.
           INSPECT WS-SRC TALLYING WS-CNT FOR ALL "A".
           ADD 10 TO WS-X ON SIZE ERROR DISPLAY "ERR".
           GOBACK.
    """
    ir, gen, java_src, _ = _parse_and_gen('TRCHAIN', code)
    stmt_nodes = [n for n in ir.nodes.values() if n.kind == 'STATEMENT']
    no_line = [n for n in stmt_nodes if n.source_line == 0]
    assert not no_line, f'Statements with no source_line: {[n.node_id for n in no_line]}'
