import pytest
from modernize.lexer import CobolLexer
from modernize.parser import CobolParser, ParserDiagnostic

def parse_cobol(src: str):
    lexer = CobolLexer("dummy.cob", format_mode="free")
    tokens = lexer.tokenize(src)
    parser = CobolParser(tokens, "dummy.cob")
    ir = parser.parse()
    return parser, ir

def test_cics_parser_valid_commands():
    src = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. TESTCICS.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-IN            PIC X(20).
       01  WS-OUT           PIC X(20).
       01  WS-COM           PIC X(10).
       01  WS-RESP          PIC 9(4).
       01  WS-RESP2         PIC 9(4).
       01  WS-TIME          PIC 9(15).
       01  WS-DATE          PIC X(8).
       01  WS-TIME-STR      PIC X(6).
       01  WS-CONT          PIC X(30).
       PROCEDURE DIVISION.
           EXEC CICS SEND MAP('MAP1') MAPSET('MSET1') FROM(WS-OUT) ERASE FREEKB ALARM RESP(WS-RESP) END-EXEC.
           EXEC CICS RECEIVE MAP('MAP1') MAPSET('MSET1') INTO(WS-IN) RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC.
           EXEC CICS LINK PROGRAM('PROG2') COMMAREA(WS-COM) LENGTH(10) RESP(WS-RESP) END-EXEC.
           EXEC CICS XCTL PROGRAM('PROG3') COMMAREA(WS-COM) RESP(WS-RESP) END-EXEC.
           EXEC CICS PUT CONTAINER('CONT1') CHANNEL('CHAN1') FROM(WS-CONT) RESP(WS-RESP) END-EXEC.
           EXEC CICS GET CONTAINER('CONT1') CHANNEL('CHAN1') INTO(WS-CONT) RESP(WS-RESP) END-EXEC.
           EXEC CICS DELETE CONTAINER('CONT1') CHANNEL('CHAN1') END-EXEC.
           EXEC CICS ASKTIME ABSTIME(WS-TIME) END-EXEC.
           EXEC CICS FORMATTIME ABSTIME(WS-TIME) YYYYMMDD(WS-DATE) TIME(WS-TIME-STR) END-EXEC.
           EXEC CICS RETURN TRANSID('TRN2') COMMAREA(WS-COM) IMMEDIATE END-EXEC.
    """
    parser, ir = parse_cobol(src)
    assert len(parser.diagnostics) == 0, f"Unexpected diagnostics: {parser.diagnostics}"
    cics_nodes = [n for n in ir.nodes.values() if n.kind == "STATEMENT" and n.properties.get("statement_type") == "EXEC_CICS"]
    assert len(cics_nodes) == 10

def test_cics_parser_unsupported_command_diagnostic():
    src = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. TESTCICS.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-REC PIC X(80).
       PROCEDURE DIVISION.
           EXEC CICS READ DATASET('FILEA') INTO(WS-REC) RIDFLD('KEY1') END-EXEC.
    """
    parser, _ = parse_cobol(src)
    assert len(parser.diagnostics) > 0
    assert any("CICS_UNSUPPORTED_COMMAND" in str(d) for d in parser.diagnostics)

def test_cics_parser_invalid_program_diagnostic():
    src = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. TESTCICS.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       PROCEDURE DIVISION.
           EXEC CICS LINK COMMAREA(WS-COM) END-EXEC.
    """
    parser, _ = parse_cobol(src)
    assert len(parser.diagnostics) > 0
    assert any("CICS_INVALID_PROGRAM" in str(d) for d in parser.diagnostics)

def test_cics_parser_missing_container_diagnostic():
    src = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. TESTCICS.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-DATA PIC X(10).
       PROCEDURE DIVISION.
           EXEC CICS GET CHANNEL('CHAN1') INTO(WS-DATA) END-EXEC.
    """
    parser, _ = parse_cobol(src)
    assert len(parser.diagnostics) > 0
    assert any("CICS_INVALID_CONTAINER" in str(d) for d in parser.diagnostics)

def test_cics_parser_undeclared_host_variable():
    src = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. TESTCICS.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       PROCEDURE DIVISION.
           EXEC CICS SEND MAP('MAP1') FROM(UNDECLARED_VAR) END-EXEC.
    """
    parser, _ = parse_cobol(src)
    assert len(parser.diagnostics) > 0
    assert any("CICS_HOST_VARIABLE_NOT_FOUND" in str(d) for d in parser.diagnostics)

def test_cics_parser_commarea_length_mismatch():
    src = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. TESTCICS.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-COM PIC X(10).
       PROCEDURE DIVISION.
           EXEC CICS LINK PROGRAM('PROG2') COMMAREA(WS-COM) LENGTH(50) END-EXEC.
    """
    parser, _ = parse_cobol(src)
    assert len(parser.diagnostics) > 0
    assert any("CICS_COMMAREA_MISMATCH" in str(d) for d in parser.diagnostics)
