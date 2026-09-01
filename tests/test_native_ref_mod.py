import pytest
from modernize.native_generator import to_java_var, NativeExpressionTranslator, NativeStatementTranslator

def test_to_java_var_ref_mod_constants():
    # Test reference modification with literals/constants
    assert to_java_var("FIELD(1:1)") == "field.substring(0, 1)"
    assert to_java_var("FIELD(1:5)") == "field.substring(0, 5)"
    assert to_java_var("FIELD(5:1)") == "field.substring(4, 5)"
    assert to_java_var("FIELD(25:13)") == "field.substring(24, 37)"
    assert to_java_var("FIELD(25:)") == "field.substring(24)"

def test_to_java_var_ref_mod_expressions():
    # Test reference modification with variable expressions
    assert to_java_var("FIELD(START:5)") == "field.substring((start) - 1, (start) - 1 + 5)"
    assert to_java_var("FIELD(5:LENGTH)") == "field.substring(4, 4 + (length))"
    assert to_java_var("FIELD(START:LENGTH)") == "field.substring((start) - 1, (start) - 1 + (length))"

def test_to_java_var_ordinary_subscripts():
    # Ensure ordinary subscripts still translate to array access
    assert to_java_var("TABLE-FIELD(INDEX)") == "table_field[index - 1]"
    assert to_java_var("TABLE-FIELD(5)") == "table_field[4]"

def test_expression_translator_ref_mod():
    # Test NativeExpressionTranslator handles ref mod subscripts
    variables = {
        "FIELD": "String",
        "START": "int",
        "LENGTH": "int"
    }
    translator = NativeExpressionTranslator(variables)
    
    # Context: Subscript/Ref Mod extraction in expressions
    assert translator._translate_subscripts("FIELD(25:13)") == "field.substring(24, 37)"
    assert translator._translate_subscripts("FIELD(START:LENGTH)") == "field.substring((start) - 1, (start) - 1 + (length))"

def test_condition_translator_ref_mod():
    # Test condition translation maps to .equals() in Java
    translator = NativeStatementTranslator(
        var_types={"AUDIT-LINE": "String", "FIELD": "String"}
    )
    
    # Verify string comparison mapping to equals for substring/slice calls
    cond1 = translator._translate_condition("AUDIT-LINE (25:13) = 'MANUAL_REVIEW'")
    assert cond1 == "audit_line.substring(24, 37).equals(\"MANUAL_REVIEW\")"
    
    cond2 = translator._translate_condition("AUDIT-LINE (25:13) <> 'MANUAL_REVIEW'")
    assert cond2 == "!audit_line.substring(24, 37).equals(\"MANUAL_REVIEW\")"

def test_level78_constants():
    translator = NativeStatementTranslator(
        var_types={"WS-RESULT": "String"},
        constants_map={"CC-VALID": "V", "CC-REVIEW": "M"}
    )
    # Test condition constant mapping
    assert translator._translate_condition("WS-RESULT = CC-VALID") == "ws_result.equals(\"V\")"
    assert translator._translate_condition("WS-RESULT = CC-REVIEW") == "ws_result.equals(\"M\")"
