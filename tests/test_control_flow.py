import pytest
from modernize import CobolLexer, CobolParser, ControlFlowModel

def test_control_flow_nested_if_and_statements():
    # SYNTHETIC GENERICITY TEST
    # Unique program name, unique paragraph names, nested IF, PERFORM, CALL, data declarations
    source = (
        "000100 IDENTIFICATION DIVISION.\n"
        "000200 PROGRAM-ID. SYNTHETIC-GENERIC-TEST.\n"
        "000250 DATA DIVISION.\n"
        "000260 WORKING-STORAGE SECTION.\n"
        "000270 01  A PIC 9 VALUE 1.\n"
        "000280 01  B PIC 9 VALUE 2.\n"
        "000290 01  X PIC 9 VALUE 3.\n"
        "000295 01  Y PIC 9 VALUE 4.\n"
        "000296 01  Z PIC 9 VALUE 5.\n"
        "000297 01  Q PIC 9 VALUE 6.\n"
        "000300 PROCEDURE DIVISION.\n"
        "000400 FIRST-PARA.\n"
        "000500     MOVE A TO B.\n"
        "000600     IF A = 1\n"
        "000700         IF B = 2\n"
        "000800             MOVE X TO Y\n"
        "000900         ELSE\n"
        "001000             MOVE Z TO Y\n"
        "001100         END-IF\n"
        "001200     ELSE\n"
        "001300         MOVE Q TO Y\n"
        "001400     END-IF.\n"
        "001500 SECOND-PARA.\n"
        "001600     PERFORM FIRST-PARA.\n"
        "001700     CALL \"MOCKLIB\".\n"
        "001800     XML PARSE UNKNOWN-DOC.\n" # Unsupported statement to test status propagation
        "001900     STOP RUN.\n"
    )

    lexer = CobolLexer("synth_test.cob", format_mode="fixed")
    tokens = lexer.tokenize(source)
    
    parser = CobolParser(tokens, "synth_test.cob")
    ir = parser.parse()
    
    cfg = ControlFlowModel.build_from_ir(ir)
    
    # Assert nodes count and types
    nodes_map = {n.node_id: n for n in cfg.nodes}
    assert len(nodes_map) > 5
    
    # Assert paragraph exit and fallthrough edges
    exit_node = nodes_map["cfg_exit"]
    assert exit_node.node_type == "EXIT"
    
    # Find statements nodes
    if_stmt_nodes = [n for n in cfg.nodes if n.node_type == "CONDITION"]
    assert len(if_stmt_nodes) == 2 # Outer IF and Inner IF
    
    # Verify edges
    edges = cfg.edges
    edge_types = [e.classification for e in edges]
    
    assert "TRUE_BRANCH" in edge_types
    assert "FALSE_BRANCH" in edge_types
    assert "FALLTHROUGH" in edge_types
    assert "PERFORM" in edge_types
    assert "RETURN" in edge_types
    assert "EXIT" in edge_types
    
    # Verify that the nested branching edges exist
    outer_if_cfg = [n for n in if_stmt_nodes if n.source_line == 14][0]
    inner_if_cfg = [n for n in if_stmt_nodes if n.source_line == 15][0]
    
    # Check that outer_if TRUE_BRANCH goes to inner_if
    outer_true_edge = [e for e in edges if e.from_node == outer_if_cfg.node_id and e.classification == "TRUE_BRANCH"][0]
    assert outer_true_edge.to_node == inner_if_cfg.node_id
    
    # Verify unsupported node propagation
    unsupported_ir = [n for n in ir.nodes.values() if n.status == "UNSUPPORTED"]
    assert len(unsupported_ir) > 0
    
    unsupported_cfg = [n for n in cfg.nodes if n.ir_node_id == unsupported_ir[0].node_id]
    assert len(unsupported_cfg) > 0
    assert unsupported_cfg[0].status == "UNSUPPORTED"
    assert unsupported_cfg[0].source_line == 26

def test_control_flow_perform_thru():
    source = (
        "000100 PROCEDURE DIVISION.\n"
        "000200 PARA-A.\n"
        "000300     PERFORM PARA-B THRU PARA-C.\n"
        "000400     STOP RUN.\n"
        "000500 PARA-B.\n"
        "000600     MOVE A TO B.\n"
        "000700 PARA-C.\n"
        "000800     MOVE B TO C.\n"
    )
    lexer = CobolLexer("test_thru.cob", format_mode="fixed")
    tokens = lexer.tokenize(source)
    parser = CobolParser(tokens, "test_thru.cob")
    ir = parser.parse()
    
    cfg = ControlFlowModel.build_from_ir(ir)
    
    # Verify PERFORM_THRU edge
    thru_edges = [e for e in cfg.edges if e.classification == "PERFORM_THRU"]
    assert len(thru_edges) == 1
    
    # Verify RETURN edge from the end of PARA-C back to the instruction after PERFORM (which is STOP RUN)
    return_edges = [e for e in cfg.edges if e.classification == "RETURN"]
    assert len(return_edges) == 1
