import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modernize.native_generator import NativeStatementTranslator, NativeProgramGenerator
from modernize.parser import SemanticIRNode

def test_occurs_array_declarations():
    ir_nodes = [
        SemanticIRNode(
            node_id=1, kind="VARIABLE",
            properties={"name": "ITEM-AMOUNT", "picture": "99V99", "level": 5, "occurs": 10},
            source_file="test.cbl", source_line=1, source_column=1, start_offset=0, end_offset=0, status="PARSED"
        ),
        SemanticIRNode(
            node_id=2, kind="VARIABLE",
            properties={"name": "ITEM-NAME", "picture": "X(10)", "level": 5, "occurs": 5},
            source_file="test.cbl", source_line=2, source_column=1, start_offset=0, end_offset=0, status="PARSED"
        )
    ]
    gen = NativeProgramGenerator(program_name="TESTPROG", ir_nodes=ir_nodes)
    
    assert "ITEM-AMOUNT" in gen.occurs_map
    assert gen.occurs_map["ITEM-AMOUNT"] == (10, "BigDecimal")
    
    class_src = gen.generate_class_source()
    assert "public com.systema.modernized.runtime.CobolNumeric[] item_amount = new com.systema.modernized.runtime.CobolNumeric[10];" in class_src
    assert "item_amount[i] = new com.systema.modernized.runtime.CobolNumeric(new com.systema.modernized.runtime.CobolNumericSpec(false, 4, 2, com.systema.modernized.runtime.CobolUsage.DISPLAY, com.systema.modernized.runtime.CobolSignPosition.TRAILING, false));" in class_src
    assert "public String[] item_name = new String[5];" in class_src
    assert "java.util.Arrays.fill(item_name, \"\");" in class_src

def test_occurs_subscript_translation_in_statements():
    var_types = {"ITEM-AMOUNT": "BigDecimal", "ITEM-NAME": "String", "WS-I": "Integer"}
    trans = NativeStatementTranslator(var_types)
    
    # MOVE 10.50 TO ITEM-AMOUNT(3)
    node_move = {
        "properties": {
            "statement_type": "MOVE",
            "source": "10.50",
            "targets": ["ITEM-AMOUNT(3)"]
        }
    }
    java_stmt = trans.translate_statement(node_move)
    assert java_stmt == 'item_amount[2].assign(new BigDecimal("10.50"), com.systema.modernized.runtime.CobolRoundingMode.TRUNCATION, com.systema.modernized.runtime.SizeErrorPolicy.UNCHECKED);'
    
    # MOVE ITEM-NAME(WS-I) TO ITEM-NAME(WS-I + 1) -> wait, simple index variable or expression
    node_move_var = {
        "properties": {
            "statement_type": "MOVE",
            "source": "ITEM-NAME(WS-I)",
            "targets": ["ITEM-NAME(4)"]
        }
    }
    java_stmt_var = trans.translate_statement(node_move_var)
    assert java_stmt_var == 'item_name[3] = item_name[ws_i - 1];'

def test_occurs_subscript_translation_in_conditions():
    var_types = {"ITEM-AMOUNT": "BigDecimal", "WS-I": "Integer"}
    trans = NativeStatementTranslator(var_types)
    
    cond_str = "ITEM-AMOUNT(WS-I) > 100.00"
    java_cond = trans._translate_condition(cond_str)
    assert java_cond == "item_amount[ws_i - 1].getValue().compareTo(new BigDecimal(\"100.00\")) > 0"
