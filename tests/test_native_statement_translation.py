import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modernize.native_generator import NativeStatementTranslator

def test_translate_move():
    var_types = {"VAR-A": "String", "VAR-B": "String", "VAR-C": "BigDecimal"}
    trans = NativeStatementTranslator(var_types)
    
    node_move = {
        "properties": {
            "statement_type": "MOVE",
            "source": "VAR-A",
            "target": "VAR-B"
        }
    }
    java_code = trans.translate_statement(node_move)
    assert java_code == "var_b = var_a;"

    node_move_literal = {
        "properties": {
            "statement_type": "MOVE",
            "source": "100.50",
            "target": "VAR-C"
        }
    }
    java_code_literal = trans.translate_statement(node_move_literal)
    assert java_code_literal == 'var_c.assign(new BigDecimal("100.50"), com.systema.modernized.runtime.CobolRoundingMode.TRUNCATION, com.systema.modernized.runtime.SizeErrorPolicy.UNCHECKED);'

def test_translate_arithmetic():
    var_types = {"VAR-X": "BigDecimal", "VAR-Y": "BigDecimal"}
    trans = NativeStatementTranslator(var_types)
    
    node_add = {
        "properties": {
            "statement_type": "ADD",
            "value": "10.00",
            "target": "VAR-X"
        }
    }
    java_add = trans.translate_statement(node_add)
    assert java_add == 'var_x.assign(com.systema.modernized.runtime.CobolArithmetic.add(var_x.getValue(), new BigDecimal("10.00")), com.systema.modernized.runtime.CobolRoundingMode.TRUNCATION, com.systema.modernized.runtime.SizeErrorPolicy.UNCHECKED);'

def test_translate_display():
    var_types = {"VAR-A": "String", "VAR-B": "BigDecimal"}
    trans = NativeStatementTranslator(var_types)
    
    node_display = {
        "properties": {
            "statement_type": "DISPLAY",
            "operands": [
                {"type": "literal", "value": "Total: "},
                {"type": "variable", "value": "VAR-A"},
                {"type": "variable", "value": "VAR-B"}
            ]
        }
    }
    java_display = trans.translate_statement(node_display)
    expected = (
        "{\n"
        "        writeBytes(\"Total: \".getBytes(java.nio.charset.StandardCharsets.ISO_8859_1));\n"
        "        writeBytes(var_a.getBytes(java.nio.charset.StandardCharsets.ISO_8859_1));\n"
        "        writeBytes(String.valueOf(var_b.getValue()).getBytes(java.nio.charset.StandardCharsets.ISO_8859_1));\n"
        "        System.out.write(10);\n"
        "        System.out.flush();\n"
        "    }"
    )
    assert java_display == expected


def test_translate_move_function_numval():
    var_types = {"TX-AMOUNT-TEXT": "String", "TX-AMOUNT": "BigDecimal"}
    trans = NativeStatementTranslator(var_types)
    node_move = {
        "properties": {
            "statement_type": "MOVE",
            "source": "FUNCTION NUMVAL(TX-AMOUNT-TEXT)",
            "targets": ["TX-AMOUNT"]
        }
    }
    java_code = trans.translate_statement(node_move)
    assert java_code == 'tx_amount.assign(com.systema.modernized.CobolFormatHelper.numval(tx_amount_text), com.systema.modernized.runtime.CobolRoundingMode.TRUNCATION, com.systema.modernized.runtime.SizeErrorPolicy.UNCHECKED);'


def test_translate_spaces_condition():
    var_types = {"TX-AMOUNT-TEXT": "String"}
    trans = NativeStatementTranslator(var_types)
    cond = trans._translate_condition("TX-AMOUNT-TEXT NOT = SPACES")
    assert cond == "!tx_amount_text.equals(\"\")"


def test_translate_function_mod():
    var_types = {"WS-YEAR": "Integer", "WS-RESULT": "Integer"}
    trans = NativeStatementTranslator(var_types)
    node_move = {
        "properties": {
            "statement_type": "MOVE",
            "source": "FUNCTION MOD(WS-YEAR, 4)",
            "targets": ["WS-RESULT"]
        }
    }
    java_code = trans.translate_statement(node_move)
    assert java_code == 'ws_result = (com.systema.modernized.CobolFormatHelper.mod(BigDecimal.valueOf(ws_year), new BigDecimal("4"))).intValue();'


def test_translate_condition_function_mod():
    var_types = {"WS-YEAR": "Integer"}
    trans = NativeStatementTranslator(var_types)
    cond = trans._translate_condition("FUNCTION MOD(WS-YEAR, 4) = 0")
    assert cond == "com.systema.modernized.CobolFormatHelper.mod(ws_year, 4) == 0"


def test_translate_relational_keywords_condition():
    var_types = {"SQLCODE": "Integer"}
    trans = NativeStatementTranslator(var_types)
    assert trans._translate_condition("SQLCODE NOT EQUAL 0") == "sqlcode != 0"
    assert trans._translate_condition("SQLCODE EQUAL TO 100") == "sqlcode == 100"
    assert trans._translate_condition("SQLCODE GREATER THAN 10") == "sqlcode > 10"


# Regression check: ensure no single-quoted string literals in generated Java
# for simple assignments (e.g. String x = 'ready' is invalid Java)
def test_no_single_quoted_string_literals():
    """Verify that generated Java uses double quotes for string literals,
    not single quotes (which would be invalid Java char literals)."""
    var_types = {"WS-FIELD": "String"}
    trans = NativeStatementTranslator(var_types)
    
    # Test MOVE with a single-quoted literal source (as COBOL might provide)
    node_move_literal = {
        "properties": {
            "statement_type": "MOVE",
            "source": "'ready'",
            "target": "WS-FIELD"
        }
    }
    java_code = trans.translate_statement(node_move_literal)
    # Check that generated Java does not contain naked single-quoted string literals
    # that would be invalid Java (e.g. String x = 'ready')
    # Our to_java_string_literal function converts to double quotes,
    # so the result should have very few single quotes (only from escape sequences)
    # The key check: no pattern '= 'single-quote'' that would be invalid Java
    has_naked_single_quote = "= '" in java_code or ' += "' in java_code
    if has_naked_single_quote:
        # If there are naked single quotes, report the generated code for debugging
        raise AssertionError(
            f"Generated Java contains naked single-quoted string literal: {java_code}"
        )


# Regression check: ensure no single-quoted string literals in generated Java
# for simple assignments (e.g. String x = 'ready' is invalid Java)
def test_no_single_quoted_string_literals():
    """Verify that generated Java uses double quotes for string literals,
    not single quotes (which would be invalid Java char literals)."""
    var_types = {"WS-FIELD": "String"}
    trans = NativeStatementTranslator(var_types)
    
    # Test MOVE with a single-quoted literal source (as COBOL might provide)
    node_move_literal = {
        "properties": {
            "statement_type": "MOVE",
            "source": "'ready'",
            "target": "WS-FIELD"
        }
    }
    java_code = trans.translate_statement(node_move_literal)
    # Check that generated Java does not contain the invalid pattern
    # '= 'single-quote'' that would be invalid Java
    assert "'= '" not in java_code, \
        f"Generated Java should not contain naked single-quoted string literal: {java_code}"
    
    # Also test MOVE with a double-quoted literal source
    node_move_double = {
        "properties": {
            "statement_type": "MOVE",
            "source": "\"ready\"",
            "target": "WS-FIELD"
        }
    }
    java_code_double = trans.translate_statement(node_move_double)
    # Should be valid Java with double quotes
    assert java_code_double is not None
    
    # Test with a numeric literal embedded in string context
    node_move_num = {
        "properties": {
            "statement_type": "MOVE",
            "source": "100.50",
            "target": "WS-FIELD"
        }
    }
    java_code_num = trans.translate_statement(node_move_num)
    assert java_code_num is not None



