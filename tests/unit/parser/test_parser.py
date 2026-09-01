import pytest
from modernize import CobolLexer, CobolParser

def test_parser_complete_flow():
    source = (
        "000100 IDENTIFICATION DIVISION.\n"
        "000200 PROGRAM-ID. TESTPROG.\n"
        "000300 ENVIRONMENT DIVISION.\n"
        "000400 CONFIGURATION SECTION.\n"
        "000500 DATA DIVISION.\n"
        "000600 WORKING-STORAGE SECTION.\n"
        "000700 01  WS-GROUP-VAR.\n"
        "000800     05  WS-SUB-VAR PIC X(10) VALUE \"HELLO\".\n"
        "000900     05  WS-REDEF-VAR REDEFINES WS-SUB-VAR PIC X(10).\n"
        "001000 01  WS-NUMERIC-VAR PIC S9(7)V99 COMP-3.\n"
        "001100 01  WS-OCCURS-VAR OCCURS 5 TIMES PIC 9(4) COMP.\n"
        "001200 01  WS-COND-VAR PIC X.\n"
        "001300     88  WS-IS-TRUE VALUE \"Y\".\n"
        "001400 PROCEDURE DIVISION.\n"
        "001500 MAIN-PARA.\n"
        "001600     MOVE \"WORLD\" TO WS-SUB-VAR.\n"
        "001700     COMPUTE WS-NUMERIC-VAR = 12.34 + 5.0.\n"
        "001800     IF WS-IS-TRUE\n"
        "001900         PERFORM OTHER-PARA THRU EXIT-PARA\n"
        "002000     ELSE\n"
        "002100         CALL \"SUBLIB\" USING WS-SUB-VAR\n"
        "002200     END-IF.\n"
        "002300     READ IN-FILE.\n"
        "002400     WRITE OUT-FILE.\n"
        "002500     STOP RUN.\n"
    )

    lexer = CobolLexer("test_prog.cob", format_mode="fixed")
    tokens = lexer.tokenize(source)
    
    parser = CobolParser(tokens, "test_prog.cob")
    ir = parser.parse()
    
    # Assert divisions
    divisions = [n for n in ir.nodes.values() if n.kind == "DIVISION"]
    div_names = [d.properties.get("name") for d in divisions]
    assert "IDENTIFICATION" in div_names
    assert "ENVIRONMENT" in div_names
    assert "DATA" in div_names
    assert "PROCEDURE" in div_names

    # Assert Program ID
    programs = [n for n in ir.nodes.values() if n.kind == "PROGRAM"]
    assert len(programs) == 1
    assert programs[0].properties["name"] == "TESTPROG"

    # Assert configuration section
    sections = [n for n in ir.nodes.values() if n.kind == "SECTION"]
    sec_names = [s.properties.get("name") for s in sections]
    assert "CONFIGURATION" in sec_names
    assert "WORKING-STORAGE" in sec_names

    # Assert group and elementary variables
    vars_nodes = [n for n in ir.nodes.values() if n.kind == "DATA_ITEM"]
    vars_map = {v.properties["name"]: v.properties for v in vars_nodes}
    
    assert "WS-GROUP-VAR" in vars_map
    assert vars_map["WS-GROUP-VAR"]["is_group"] is True
    assert vars_map["WS-GROUP-VAR"]["level"] == 1
    
    assert "WS-SUB-VAR" in vars_map
    assert vars_map["WS-SUB-VAR"]["picture"] == "X(10)"
    assert vars_map["WS-SUB-VAR"]["value"] == "HELLO"
    
    # Redefines check
    assert "WS-REDEF-VAR" in vars_map
    assert vars_map["WS-REDEF-VAR"]["redefines"] == "WS-SUB-VAR"

    # Numeric precision check: S9(7)V99 COMP-3 -> signed=True, digits=9, scale=2, COMP-3 usage
    assert "WS-NUMERIC-VAR" in vars_map
    assert vars_map["WS-NUMERIC-VAR"]["signed"] is True
    assert vars_map["WS-NUMERIC-VAR"]["digits"] == 9
    assert vars_map["WS-NUMERIC-VAR"]["scale"] == 2
    assert vars_map["WS-NUMERIC-VAR"]["usage"] == "COMP-3"

    # Occurs check
    assert "WS-OCCURS-VAR" in vars_map
    assert vars_map["WS-OCCURS-VAR"]["occurs"] == 5
    assert vars_map["WS-OCCURS-VAR"]["usage"] == "COMP"

    # 88-level condition check
    assert "WS-IS-TRUE" in vars_map
    assert vars_map["WS-IS-TRUE"]["level"] == 88
    assert "Y" in vars_map["WS-IS-TRUE"]["condition_values"]

    # Assert statements
    statements = [n for n in ir.nodes.values() if n.kind == "STATEMENT"]
    stmt_types = [s.properties["statement_type"] for s in statements]
    
    assert "MOVE" in stmt_types
    assert "COMPUTE" in stmt_types
    assert "IF" in stmt_types
    assert "ELSE" in stmt_types
    assert "PERFORM" in stmt_types
    assert "CALL" in stmt_types
    assert "READ" in stmt_types
    assert "WRITE" in stmt_types
    assert "STOP RUN" in stmt_types

    # Test properties extraction
    move_stmt = [s for s in statements if s.properties["statement_type"] == "MOVE"][0]
    assert move_stmt.properties["source"] == "WORLD"
    assert "WS-SUB-VAR" in move_stmt.properties["targets"]

    compute_stmt = [s for s in statements if s.properties["statement_type"] == "COMPUTE"][0]
    assert compute_stmt.properties["target"] == "WS-NUMERIC-VAR"
    assert "12.34" in compute_stmt.properties["expression"]

    perform_stmt = [s for s in statements if s.properties["statement_type"] == "PERFORM"][0]
    assert perform_stmt.properties["target"] == "OTHER-PARA"
    assert perform_stmt.properties["thru"] == "EXIT-PARA"

    call_stmt = [s for s in statements if s.properties["statement_type"] == "CALL"][0]
    assert call_stmt.properties["target"] == "SUBLIB"
    assert "WS-SUB-VAR" in call_stmt.properties["arguments"]

    # Source location tracking check
    assert move_stmt.source_line == 16
    assert move_stmt.source_column == 12
    assert move_stmt.start_offset > 0
    assert move_stmt.end_offset > move_stmt.start_offset

def test_parser_unsupported_and_diagnostics():
    # Parsing unsupported statement and syntax check
    source = (
        "000100 PROCEDURE DIVISION.\n"
        "000200     XML PARSE MY-DOC.\n"  # Unsupported XML statement
        "000300     MOVE @ TO B.\n"        # Malformed Syntax
    )
    lexer = CobolLexer("test_unsupported.cob", format_mode="fixed")
    tokens = lexer.tokenize(source)
    
    parser = CobolParser(tokens, "test_unsupported.cob")
    ir = parser.parse()
    
    # Assert XML statement is captured as UNSUPPORTED
    unsupported = [n for n in ir.nodes.values() if n.status == "UNSUPPORTED"]
    assert len(unsupported) > 0
    assert unsupported[0].properties["statement_type"] == "UNKNOWN"
    
    # Assert malformed syntax registers diagnostics
    assert len(parser.diagnostics) > 0
    assert parser.diagnostics[0].line == 3
    assert parser.diagnostics[0].token_value == "@"

def test_parser_arithmetic_regression_parsing():
    template = (
        "000100 IDENTIFICATION DIVISION.\n"
        "000200 PROGRAM-ID. TESTPROG.\n"
        "000300 PROCEDURE DIVISION.\n"
        "000400 MAIN-PARA.\n"
        "000500     {}\n"
    )
    cases = [
        (template.format("COMPUTE X = A - 1."), "A - 1"),
        (template.format("COMPUTE X = A -1."), "A - 1"),
        (template.format("COMPUTE X = A - -1."), "A - -1"),
    ]
    for source, expected_expr in cases:
        lexer = CobolLexer("test.cob", format_mode="fixed")
        tokens = lexer.tokenize(source)
        parser = CobolParser(tokens, "test.cob")
        ir = parser.parse()
        stmt = [n for n in ir.nodes.values() if n.kind == "STATEMENT" and n.properties["statement_type"] == "COMPUTE"][0]
        assert stmt.properties["expression"] == expected_expr

    # Test SUBTRACT 1 FROM A GIVING X
    lexer = CobolLexer("test.cob", format_mode="fixed")
    tokens = lexer.tokenize(template.format("SUBTRACT 1 FROM A GIVING X."))
    parser = CobolParser(tokens, "test.cob")
    ir = parser.parse()
    stmt = [n for n in ir.nodes.values() if n.kind == "STATEMENT" and n.properties["statement_type"] == "SUBTRACT"][0]
    assert stmt.properties["value"] == "1"
    assert stmt.properties["targets"][0]["name"] == "X"

    # Test SUBTRACT 1 FROM A (in-place)
    lexer = CobolLexer("test.cob", format_mode="fixed")
    tokens = lexer.tokenize(template.format("SUBTRACT 1 FROM A."))
    parser = CobolParser(tokens, "test.cob")
    ir = parser.parse()
    stmt = [n for n in ir.nodes.values() if n.kind == "STATEMENT" and n.properties["statement_type"] == "SUBTRACT"][0]
    assert stmt.properties["value"] == "1"
    assert stmt.properties["targets"][0]["name"] == "A"
def test_parser_call_modifiers_parsing():
    template = (
        "000100 IDENTIFICATION DIVISION.\n"
        "000200 PROGRAM-ID. TESTPROG.\n"
        "000300 PROCEDURE DIVISION.\n"
        "000400 MAIN-PARA.\n"
        "000500     CALL \"SUBLIB\" USING BY REFERENCE A BY CONTENT B BY VALUE C.\n"
    )
    lexer = CobolLexer("test.cob", format_mode="fixed")
    tokens = lexer.tokenize(template)
    parser = CobolParser(tokens, "test.cob")
    ir = parser.parse()
    stmt = [n for n in ir.nodes.values() if n.kind == "STATEMENT" and n.properties["statement_type"] == "CALL"][0]
    assert stmt.properties["target"] == "SUBLIB"
    assert stmt.properties["arguments"] == ["A", "B", "C"]
    assert stmt.properties["arguments_info"] == [
        {"value": "A", "mode": "REFERENCE"},
        {"value": "B", "mode": "CONTENT"},
        {"value": "C", "mode": "VALUE"}
    ]
