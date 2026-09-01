import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modernize.native_generator import NativeStatementTranslator, NativeProgramGenerator
from modernize.semantic_ir import SemanticIRNode

def test_static_call_translation():
    var_types = {"VAR-A": "String"}
    class MockGenerator:
        program_name = "SUBPROG1"
        using_args = ["PARAM-A", "PARAM-B"]
        group_fields = {}
        var_types = {"PARAM-A": "String", "PARAM-B": "String"}
        var_pics = {"PARAM-A": "X(10)", "PARAM-B": "X(10)"}
        
    other_gen = MockGenerator()
    class MockCurrentGenerator:
        program_name = "MAINPROG"
        group_fields = {}
        diagnostics = []
        
    curr_gen = MockCurrentGenerator()
    all_generators = {"SUBPROG1": other_gen}
    trans = NativeStatementTranslator(var_types, all_generators=all_generators, current_generator=curr_gen)
    
    node_call = SemanticIRNode(
        node_id="node_1",
        kind="STATEMENT",
        source_line=10,
        properties={
            "statement_type": "CALL",
            "target": "SUBPROG1",
            "arguments": ["VAR-A"]
        }
    )
    
    res = trans.translate_statement(node_call)
    assert "Subprog1 subprog1_" in res
    assert ".param_a = var_a;" in res
    assert ".execute();" in res
    assert "return_code = subprog1_" in res
    assert "var_a = subprog1_" in res

def test_dynamic_call_translation():
    var_types = {"PROG-NAME": "String", "VAR-A": "String"}
    class MockGenerator:
        program_name = "SUBPROG2"
        using_args = ["PARAM-X"]
        group_fields = {}
        
    other_gen = MockGenerator()
    class MockCurrentGenerator:
        program_name = "MAINPROG"
        group_fields = {}
        diagnostics = []
        
    curr_gen = MockCurrentGenerator()
    all_generators = {"SUBPROG2": other_gen}
    trans = NativeStatementTranslator(var_types, all_generators=all_generators, current_generator=curr_gen)
    
    node_call = SemanticIRNode(
        node_id="node_2",
        kind="STATEMENT",
        source_line=12,
        properties={
            "statement_type": "CALL",
            "target": "PROG-NAME",
            "arguments": ["VAR-A"]
        }
    )
    
    res = trans.translate_statement(node_call)
    assert "targetProg_prog_name = prog_name.trim().toUpperCase();" in res
    assert 'targetProg_prog_name.equals("SUBPROG2")' in res
    assert "Subprog2 subprog2_" in res
    assert ".param_x = var_a;" in res
    assert ".execute();" in res
