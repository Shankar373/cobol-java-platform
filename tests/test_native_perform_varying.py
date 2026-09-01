import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modernize.native_generator import NativeStatementTranslator

def test_perform_varying_translation():
    var_types = {"WS-I": "Integer", "WS-LIMIT": "Integer", "WS-VAL": "BigDecimal"}
    trans = NativeStatementTranslator(var_types)
    
    node_perf = {
        "properties": {
            "statement_type": "PERFORM_VARYING",
            "index": "WS-I",
            "from_value": "1",
            "by_value": "1",
            "condition": "WS-I > WS-LIMIT"
        }
    }
    
    java_stmt = trans.translate_statement(node_perf)
    expected = "for (ws_i = 1; !(ws_i > ws_limit) && !programExited; ws_i += 1) {"
    assert java_stmt == expected

def test_perform_varying_bigdecimal_index_translation():
    var_types = {"WS-IDX": "BigDecimal", "WS-LIMIT": "BigDecimal"}
    trans = NativeStatementTranslator(var_types)
    
    node_perf = {
        "properties": {
            "statement_type": "PERFORM_VARYING",
            "index": "WS-IDX",
            "from_value": "1.5",
            "by_value": "0.5",
            "condition": "WS-IDX > WS-LIMIT"
        }
    }
    
    java_stmt = trans.translate_statement(node_perf)
    assert "for (ws_idx = new BigDecimal(\"1.5\");" in java_stmt
    assert "ws_idx = ws_idx.add(new BigDecimal(\"0.5\"))" in java_stmt
