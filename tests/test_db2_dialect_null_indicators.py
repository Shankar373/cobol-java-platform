import pytest
from modernize.lexer import CobolLexer
from modernize.parser import CobolParser
from modernize.native_generator import NativeProgramGenerator

def test_db2_dialect_dummy_table_translation():
    code = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. DUMMYT.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  SQLCA-VARIABLES.
           05  SQLCODE    PIC S9(9) COMP.
       01  WS-TIME        PIC X(26).
       PROCEDURE DIVISION.
           EXEC SQL
               SELECT CURRENT TIMESTAMP INTO :WS-TIME FROM SYSIBM.SYSDUMMY1
           END-EXEC.
           GOBACK.
    """
    lexer = CobolLexer("dummyt.cob", format_mode="free")
    tokens = lexer.tokenize(code)
    parser = CobolParser(tokens, "dummyt.cob")
    ir = parser.parse()
    
    gen = NativeProgramGenerator("DUMMYT", list(ir.nodes.values()))
    java_src = gen.generate_class_source(all_generators={"DUMMYT": gen})
    
    # Assert that FROM SYSIBM.SYSDUMMY1 was stripped and CURRENT TIMESTAMP was converted to CURRENT_TIMESTAMP
    assert "FROM SYSIBM.SYSDUMMY1" not in java_src
    assert "CURRENT_TIMESTAMP" in java_src
    assert "CURRENT TIMESTAMP" not in java_src

def test_db2_null_indicator_variables():
    code = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. NULLIND.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  SQLCA-VARIABLES.
           05  SQLCODE    PIC S9(9) COMP.
       01  WS-CUST.
           05  WS-CUST-NAME  PIC X(20).
           05  WS-CUST-IND   PIC S9(4) COMP.
       PROCEDURE DIVISION.
           EXEC SQL
               SELECT CUST_NAME INTO :WS-CUST-NAME :WS-CUST-IND FROM CUSTOMER
           END-EXEC.
           GOBACK.
    """
    lexer = CobolLexer("nullind.cob", format_mode="free")
    tokens = lexer.tokenize(code)
    parser = CobolParser(tokens, "nullind.cob")
    ir = parser.parse()
    
    sql_nodes = [n for n in ir.nodes.values() if n.kind == "STATEMENT" and n.properties.get("statement_type") == "EXEC_SQL"]
    assert len(sql_nodes) == 1
    
    gen = NativeProgramGenerator("NULLIND", list(ir.nodes.values()))
    java_src = gen.generate_class_source(all_generators={"NULLIND": gen})
    
    # Assert that both ws_cust_name and ws_cust_ind are declared
    assert "String ws_cust_name" in java_src
    assert "int ws_cust_ind" in java_src
    
    # Assert wasNull() checks and indicator assignment are generated
    assert "rs.wasNull()" in java_src
    assert "ws_cust_ind = -1;" in java_src
    assert "ws_cust_ind = 0;" in java_src


def test_db2_insert_null_indicator_variables():
    code = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. INSIND.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  SQLCA-VARIABLES.
           05  SQLCODE    PIC S9(9) COMP.
       01  WS-CUST.
           05  WS-CUST-NAME  PIC X(20).
           05  WS-CUST-IND   PIC S9(4) COMP.
       PROCEDURE DIVISION.
           EXEC SQL
               INSERT INTO CUSTOMER (CUST_NAME) VALUES (:WS-CUST-NAME :WS-CUST-IND)
           END-EXEC.
           GOBACK.
    """
    lexer = CobolLexer("insind.cob", format_mode="free")
    tokens = lexer.tokenize(code)
    parser = CobolParser(tokens, "insind.cob")
    ir = parser.parse()
    
    gen = NativeProgramGenerator("INSIND", list(ir.nodes.values()))
    java_src = gen.generate_class_source(all_generators={"INSIND": gen})
    
    assert "ws_cust_ind == -1" in java_src
    assert "null : ws_cust_name" in java_src
    assert 'VALUES ( ? )' in java_src
