"""Unit tests for the COBOL lexer."""
import os
import sys
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

from engine.lexer.lexer import CobolLexer

PAYMAIN_COB = os.path.join(ROOT, "tests", "fixtures", "A-PAYONLY", "src", "PAYMAIN.cob")


def _lex(path, fmt="fixed"):
    """Helper: create lexer, read file, tokenize, return lexer."""
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        text = fh.read()
    lexer = CobolLexer(path, format_mode=fmt)
    lexer.tokenize(text)
    return lexer


class TestCobolLexer:
    def test_tokenizes_paymain(self):
        assert os.path.isfile(PAYMAIN_COB), f"Fixture not found: {PAYMAIN_COB}"
        lexer = _lex(PAYMAIN_COB)
        assert len(lexer.tokens) > 0, "Expected tokens but got none"

    def test_detects_keywords(self):
        lexer = _lex(PAYMAIN_COB)
        kw_values = {t.value.upper() for t in lexer.tokens if t.type == "KEYWORD"}
        assert "IDENTIFICATION" in kw_values, "IDENTIFICATION not found as keyword"
        assert "PROCEDURE" in kw_values, "PROCEDURE not found as keyword"
        assert "DATA" in kw_values, "DATA not found as keyword"

    def test_source_locations(self):
        lexer = _lex(PAYMAIN_COB)
        for tok in lexer.tokens:
            assert tok.line > 0, f"Token {tok!r} has invalid line number"

    def test_no_unsupported_tokens(self):
        lexer = _lex(PAYMAIN_COB)
        assert lexer.unsupported == [], f"Unexpected unsupported tokens: {lexer.unsupported}"

    def test_display_keyword_found(self):
        lexer = _lex(PAYMAIN_COB)
        kw_values = {t.value.upper() for t in lexer.tokens if t.type == "KEYWORD"}
        assert "DISPLAY" in kw_values, "DISPLAY keyword not found"
