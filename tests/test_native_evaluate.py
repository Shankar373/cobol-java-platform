import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modernize.native_generator import NativeStatementTranslator

def test_evaluate_string_subject():
    var_types = {"WS-STATUS": "String"}
    trans = NativeStatementTranslator(var_types)
    
    # Simulate:
    # EVALUATE WS-STATUS
    #     WHEN "A"
    #         MOVE "OK" TO WS-RESULT
    #     WHEN OTHER
    #         MOVE "ERR" TO WS-RESULT
    # END-EVALUATE
    
    node_eval = {
        "properties": {
            "statement_type": "EVALUATE",
            "subject": "WS-STATUS"
        }
    }
    
    node_when_a = {
        "properties": {
            "statement_type": "WHEN",
            "condition": '"A"'
        }
    }
    
    node_when_other = {
        "properties": {
            "statement_type": "WHEN",
            "condition": "OTHER"
        }
    }
    
    node_end = {
        "properties": {
            "statement_type": "END-EVALUATE"
        }
    }
    
    assert trans.translate_statement(node_eval) is None
    assert trans.translate_statement(node_when_a) == 'if (Objects.equals(ws_status, "A")) {'
    assert trans.translate_statement(node_when_other) == '} else {'
    assert trans.translate_statement(node_end) == '}'

def test_evaluate_numeric_subject():
    var_types = {"WS-CODE": "Integer", "WS-VAL": "BigDecimal"}
    trans = NativeStatementTranslator(var_types)
    
    node_eval = {
        "properties": {
            "statement_type": "EVALUATE",
            "subject": "WS-CODE"
        }
    }
    node_when_1 = {
        "properties": {
            "statement_type": "WHEN",
            "condition": "1"
        }
    }
    node_when_2 = {
        "properties": {
            "statement_type": "WHEN",
            "condition": "2"
        }
    }
    
    assert trans.translate_statement(node_eval) is None
    assert trans.translate_statement(node_when_1) == 'if (ws_code == 1) {'
    assert trans.translate_statement(node_when_2) == '} else if (ws_code == 2) {'

def test_evaluate_bigdecimal_subject():
    var_types = {"WS-VAL": "BigDecimal"}
    trans = NativeStatementTranslator(var_types)
    
    node_eval = {
        "properties": {
            "statement_type": "EVALUATE",
            "subject": "WS-VAL"
        }
    }
    node_when_val = {
        "properties": {
            "statement_type": "WHEN",
            "condition": "100.50"
        }
    }
    
    assert trans.translate_statement(node_eval) is None
    assert trans.translate_statement(node_when_val) == 'if (ws_val.getValue().compareTo(new BigDecimal("100.50")) == 0) {'
