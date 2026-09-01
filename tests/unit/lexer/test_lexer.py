import pytest
from modernize import CobolLexer

def test_lexer_fixed_format_basic():
    # Indicator '*' is a comment. Columns 1-6 ignored.
    source = (
        "000100* THIS IS A COMMENT\n"
        "000200       IDENTIFICATION DIVISION.\n"
        "000300       PROGRAM-ID. HELLO.\n"
        "000400       PROCEDURE DIVISION.\n"
        "000500           DISPLAY \"HELLO WORLD\".\n"
        "000600           STOP RUN.\n"
    )
    
    lexer = CobolLexer("test_basic.cob", format_mode="fixed")
    tokens = lexer.tokenize(source)
    
    # Assert comment is preserved
    comments = [t for t in tokens if t.type == "COMMENT"]
    assert len(comments) == 1
    assert "THIS IS A COMMENT" in comments[0].value
    
    # Assert keywords
    keywords = [t for t in tokens if t.type == "KEYWORD"]
    assert any(k.value.upper() == "IDENTIFICATION" for k in keywords)
    assert any(k.value.upper() == "PROGRAM-ID" for k in keywords)
    assert any(k.value.upper() == "DISPLAY" for k in keywords)
    
    # Assert literals
    strings = [t for t in tokens if t.type == "LITERAL_STRING"]
    assert len(strings) == 1
    assert strings[0].value == "HELLO WORLD"
    # Verify line, column positions (1-based)
    assert strings[0].line == 5
    assert strings[0].column == 26

def test_lexer_continuation_lines():
    # Continued string literal in fixed format (indicator '-' in col 7)
    source = (
        "000100       DISPLAY \"HELLO \n"
        "000200-              \"WORLD\".\n"
    )
    
    lexer = CobolLexer("test_cont.cob", format_mode="fixed")
    tokens = lexer.tokenize(source)
    
    strings = [t for t in tokens if t.type == "LITERAL_STRING"]
    assert len(strings) == 1
    assert strings[0].value == "HELLO WORLD"

def test_lexer_free_format_comments_and_operators():
    source = (
        "*> This is a free comment\n"
        "DISPLAY 12.34 + 56 - 95.00.\n"
    )
    
    lexer = CobolLexer("test_free.cob", format_mode="free")
    tokens = lexer.tokenize(source)
    
    comments = [t for t in tokens if t.type == "COMMENT"]
    assert len(comments) == 1
    assert "This is a free comment" in comments[0].value
    
    numbers = [t.value for t in tokens if t.type == "LITERAL_NUMBER"]
    assert "12.34" in numbers
    assert "56" in numbers
    assert "95.00" in numbers
    
    punc = [t.value for t in tokens if t.type == "PUNCTUATION"]
    assert "+" in punc
    assert "-" in punc
    assert "." in punc

def test_lexer_malformed_unsupported_inputs():
    # Characters that are not standard in COBOL (like @ or $) should be marked as ERROR
    source = (
        "000100       MOVE @ TO $.\n"
    )
    lexer = CobolLexer("test_err.cob", format_mode="fixed")
    tokens = lexer.tokenize(source)
    
    errors = [t for t in tokens if t.type == "ERROR"]
    assert len(errors) == 2
    assert errors[0].value == "@"
    assert errors[1].value == "$"
    assert len(lexer.unsupported) == 2
