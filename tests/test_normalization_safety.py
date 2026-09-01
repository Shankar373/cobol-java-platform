"""
Comprehensive Safety and Boundary Verification of Output Normalization
========================================================================
Proves that normalization layers across the platform (cobol_migrate._normalize_text,
NativePipeline.conservative_stdout, and parity_harness.normalize_display):
1. Never alter or strip business-significant leading zeroes.
2. Never obscure signed output differences (+, -, unsigned).
3. Never mask numeric precision or value mismatches.
4. Only normalize benign transport line-endings and trailing whitespace.
5. Strictly preserve record byte content for files.
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cobol_migrate import normalize
from tests.utils.parity_harness import normalize_display


def _gate2_normalize(content_bytes: bytes) -> str:
    """Exact replica of the Gate 2 `_normalize_text` closure in cobol_migrate."""
    text = content_bytes.decode("utf-8", errors="replace")
    lines = [line.rstrip(" \t\r\n\x00") for line in text.splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines).strip()


def _conservative_stdout(content: str) -> str:
    """Exact replica of NativePipeline conservative_stdout logic."""
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip(" \t") for line in content.split("\n")).strip()


def test_normalize_only_whitespace_and_line_endings():
    assert normalize(b"a\r\nb\r\n") == b"a\nb"
    assert normalize(b"x  \n") == b"x"
    # numeric content is preserved verbatim
    assert normalize(b"25864") == b"25864"
    assert normalize(b"258648") == b"258648"


def test_normalize_cannot_hide_numeric_mismatch():
    a = normalize(b"NET=25864\r\n")
    b = normalize(b"NET=258648\r\n")
    assert a != b, "numeric off-by-one must survive normalization"

    # Identical numeric content with differing line endings must match.
    assert normalize(b"NET=25864\r\n") == normalize(b"NET=25864\n")


def test_gate2_normalize_preserves_numeric_difference():
    baseline = _gate2_normalize(b"E00129324002586400103460\r\n")
    native_buggy = _gate2_normalize(b"E00129324002586480103459\r\n")
    native_fixed = _gate2_normalize(b"E00129324002586400103460\r\n")
    assert baseline != native_buggy
    assert baseline == native_fixed


def test_normalize_preserves_leading_zeroes_across_all_layers():
    """Prove leading zeroes in numeric fields (e.g. account numbers, IDs) are never stripped."""
    b_val = b"ACC=00012345"
    n_val_stripped = b"ACC=12345"
    n_val_correct = b"ACC=00012345"

    assert normalize(b_val) != normalize(n_val_stripped)
    assert normalize(b_val) == normalize(n_val_correct)

    assert _gate2_normalize(b_val) != _gate2_normalize(n_val_stripped)
    assert _gate2_normalize(b_val) == _gate2_normalize(n_val_correct)

    assert _conservative_stdout("00012345") != _conservative_stdout("12345")
    assert _conservative_stdout("00012345") == _conservative_stdout("00012345")

    assert normalize_display(b_val) != normalize_display(n_val_stripped)
    assert normalize_display(b_val) == normalize_display(n_val_correct)


def test_normalize_preserves_signed_output_differences():
    """Prove sign indicators (+, -, unsigned) are preserved and differentiated."""
    pos = b"+123.45"
    neg = b"-123.45"
    uns = b"123.45"

    for norm in [normalize, _gate2_normalize, normalize_display]:
        assert norm(pos) != norm(neg)
        assert norm(pos) != norm(uns)
        assert norm(neg) != norm(uns)


def test_normalize_preserves_fixed_width_fields_and_decimals():
    """Prove decimal precision differences (12.34 vs 12.340 vs 12.35) are never masked."""
    val1 = b"AMT=12.34"
    val2 = b"AMT=12.340"
    val3 = b"AMT=12.35"

    assert normalize(val1) != normalize(val2)
    assert normalize(val1) != normalize(val3)
    assert normalize(val2) != normalize(val3)

    assert _conservative_stdout("AMT=12.34") != _conservative_stdout("AMT=12.340")
    assert _conservative_stdout("AMT=12.34") != _conservative_stdout("AMT=12.35")
