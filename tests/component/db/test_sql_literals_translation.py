import pytest
from modernize.lexer import CobolLexer
from modernize.parser import CobolParser
from modernize.native_generator import NativeProgramGenerator

def test_sql_literal_translation_to_double_quotes():
    code = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. SQLLIT.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  SQLCA-VARIABLES.
           05  SQLCODE    PIC S9(9) COMP.
       01  WS-ID          PIC S9(9) COMP VALUE 100.
       PROCEDURE DIVISION.
           EXEC SQL
               INSERT INTO CUSTOMER (CUST_ID, CUST_STATUS, CUST_TYPE)
               VALUES (:WS-ID, 'ACTIVE', 'VIP')
           END-EXEC.
           GOBACK.
    """
    lexer = CobolLexer("sqllit.cob", format_mode="free")
    tokens = lexer.tokenize(code)
    parser = CobolParser(tokens, "sqllit.cob")
    ir = parser.parse()
    
    sql_nodes = [n for n in ir.nodes.values() if n.kind == "STATEMENT" and n.properties.get("statement_type") == "EXEC_SQL"]
    assert len(sql_nodes) == 1
    
    gen = NativeProgramGenerator("SQLLIT", list(ir.nodes.values()), file_assigns=[], repo_path=".")
    java_src = gen.generate_class_source(all_generators={})
    
    # Verify that the generated jdbcTemplate.update passes "ACTIVE" and "VIP" (with double quotes)
    # instead of 'ACTIVE' or 'VIP' (single quotes)
    update_line = None
    for line in java_src.splitlines():
        if "jdbcTemplate.update" in line:
            update_line = line
            break
            
    assert update_line is not None
    assert "ACTIVE" in update_line
    assert "VIP" in update_line
    assert "BigDecimal.valueOf(ws_id)" in update_line
