import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modernize.native_generator import NativeStatementTranslator, NativeProgramGenerator
from modernize.parser import SemanticIRNode

def test_level88_conditions_translation():
    # Setup level-88 map
    level88_map = {
        "STATUS-OPEN": ("WS-STATUS", ["O", "OP"]),
        "STATUS-CLOSED": ("WS-STATUS", ["C"])
    }
    var_types = {"WS-STATUS": "String"}
    
    trans = NativeStatementTranslator(var_types, level88_map=level88_map)
    
    cond_open = trans._translate_condition("STATUS-OPEN")
    cond_closed = trans._translate_condition("STATUS-CLOSED")
    
    assert cond_open == "isStatusOpen()"
    assert cond_closed == "isStatusClosed()"

def test_level88_boolean_methods_generation():
    # Construct nodes simulating COBOL variables and level-88 items
    ir_nodes = [
        SemanticIRNode(
            node_id=1, kind="VARIABLE",
            properties={"name": "WS-STATUS", "picture": "X", "level": 1},
            source_file="test.cbl", source_line=1, source_column=1, start_offset=0, end_offset=0, status="PARSED"
        ),
        SemanticIRNode(
            node_id=2, kind="VARIABLE",
            properties={"name": "STATUS-OPEN", "level": 88, "condition_values": ["O", "OP"]},
            source_file="test.cbl", source_line=2, source_column=1, start_offset=0, end_offset=0, status="PARSED"
        )
    ]
    gen = NativeProgramGenerator(program_name="TESTPROG", ir_nodes=ir_nodes)
    
    assert "STATUS-OPEN" in gen.level88_map
    assert gen.level88_map["STATUS-OPEN"] == ("WS-STATUS", ["O", "OP"])
    
    class_src = gen.generate_class_source()
    assert "public boolean isStatusOpen() { return Objects.equals(ws_status, \"O\") || Objects.equals(ws_status, \"OP\"); }" in class_src
