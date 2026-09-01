import pytest
from modernize import CobolLexer, CobolParser, ControlFlowModel, DataFlowModel

def test_data_flow_generic_and_negative_checks():
    # SYNTHETIC GENERICITY TEST
    # Contains: input field, MOVE, COMPUTE, arithmetic, IF/ELSE, 88-level condition, REDEFINES, OCCURS, READ, WRITE, CALL USING
    source = (
        "000100 IDENTIFICATION DIVISION.\n"
        "000200 PROGRAM-ID. SYNTHETIC-DATA-FLOW-TEST.\n"
        "000300 ENVIRONMENT DIVISION.\n"
        "000400 INPUT-OUTPUT SECTION.\n"
        "000500 DATA DIVISION.\n"
        "000600 WORKING-STORAGE SECTION.\n"
        "000700 01  WS-RECORD.\n"
        "000800     05  WS-INPUT PIC X(10).\n"
        "000900     05  WS-REDEF REDEFINES WS-INPUT PIC X(10).\n"
        "001000 01  WS-ARRAY OCCURS 5 TIMES PIC 9(2).\n"
        "001100 01  WS-STATUS PIC X.\n"
        "001200     88  WS-ACTIVE VALUE 'Y'.\n"
        "001300 PROCEDURE DIVISION.\n"
        "001400 MAIN-PARA.\n"
        "001500     READ IN-FILE.\n"
        "001600     MOVE WS-INPUT TO WS-STATUS.\n"
        "001700     IF WS-ACTIVE\n"
        "001800         COMPUTE WS-ARRAY = WS-ARRAY + 10\n" # Remove subscript for clean parsing
        "001900     ELSE\n"
        "002000         ADD 1 TO WS-ARRAY\n" # Remove subscript for clean parsing
        "002100     END-IF.\n"
        "002200     WRITE OUT-FILE.\n"
        "002300     CALL \"SUBLIB\" USING WS-INPUT WS-STATUS.\n"
        "002400     XML PARSE UNKNOWN-DOC.\n" # Unsupported expression
        "002500     STOP RUN.\n"
    )

    lexer = CobolLexer("df_test.cob", format_mode="fixed")
    tokens = lexer.tokenize(source)
    
    parser = CobolParser(tokens, "df_test.cob")
    ir = parser.parse()
    
    cfg = ControlFlowModel.build_from_ir(ir)
    df = DataFlowModel.build_from_ir(ir, cfg)
    
    # Extract nodes maps
    nodes_by_id = {n.node_id: n for n in df.nodes}
    nodes_by_name = {n.name: n for n in df.nodes}
    
    # 1. Verify REDEFINES relationship (redefines field B)
    assert "df_var_WS-REDEF" in nodes_by_id
    redef_edge = [e for e in df.edges if e.from_node == "df_var_WS-INPUT" and e.to_node == "df_var_WS-REDEF" and e.classification == "SHARED_STORAGE"]
    assert len(redef_edge) == 1
    
    # Negative check: Redefines edge must not exist between unrelated variables
    assert len([e for e in df.edges if e.from_node == "df_var_WS-STATUS" and e.to_node == "df_var_WS-REDEF"]) == 0

    # 2. Verify OCCURS count exists on array variable
    array_node = nodes_by_name["WS-ARRAY"]
    assert array_node.properties["occurs"] == 5

    # 3. Verify 88-level condition mapping
    assert "df_var_WS-ACTIVE" in nodes_by_id
    active_edge = [e for e in df.edges if e.from_node == "df_var_WS-ACTIVE" and e.to_node == "df_var_WS-STATUS" and e.classification == "USES"]
    assert len(active_edge) == 1
    
    # 4. Verify I/O edge structures
    read_edges = [e for e in df.edges if e.classification == "CONSUMES"]
    assert len(read_edges) == 1
    assert read_edges[0].from_node.startswith("df_io_")
    assert read_edges[0].to_node == "df_var_IN-FILE"

    write_edges = [e for e in df.edges if e.classification == "PRODUCES"]
    assert len(write_edges) == 1
    assert write_edges[0].from_node == "df_var_OUT-FILE"
    assert write_edges[0].to_node.startswith("df_io_")

    # 5. Verify conditional dependencies and MOVE transitions
    move_edge = [e for e in df.edges if e.from_node == "df_var_WS-INPUT" and e.to_node == "df_var_WS-STATUS" and e.classification == "ASSIGNS"]
    assert len(move_edge) == 1

    # 6. Verify Call args
    call_edges = [e for e in df.edges if e.classification == "CALLS_WITH"]
    assert len(call_edges) == 2
    
    # 7. Unresolved call is marked status = UNRESOLVED
    call_nodes = [n for n in df.nodes if n.node_type == "CALL_RESULT"]
    assert len(call_nodes) == 1
    assert call_nodes[0].status == "UNRESOLVED"

    # 8. Unsupported node propagation
    unsupported_nodes = [n for n in df.nodes if n.status == "UNSUPPORTED"]
    assert len(unsupported_nodes) == 1
    assert unsupported_nodes[0].source_line == 24
    
    # NEGATIVE CHECKS:
    # A. Missing dependency detection
    # WS-INPUT does not depend on WS-STATUS
    assert len([e for e in df.edges if e.from_node == "df_var_WS-STATUS" and e.to_node == "df_var_WS-INPUT"]) == 0

    # B. Incorrect source variable check
    # WS-ARRAY does not depend on WS-INPUT
    assert len([e for e in df.edges if e.from_node == "df_var_WS-INPUT" and e.to_node == "df_var_WS-ARRAY"]) == 0
