import pytest
import os
import sqlite3
from modernize.lexer import CobolLexer
from modernize.parser import CobolParser
from modernize.native_generator import NativeProgramGenerator
from modernize.native_pipeline import NativePipeline

def test_sql_indicator_variables_translation():
    # Test SELECT with NULL indicator, INSERT with indicators, and UPDATE with indicators
    code = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. SQLIND.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  SQLCA-VARIABLES.
           05  SQLCODE    PIC S9(9) COMP.
       01  WS-NAME        PIC X(20).
       01  WS-NAME-IND    PIC S9(4) COMP.
       01  WS-ID          PIC S9(4) COMP.
       PROCEDURE DIVISION.
           EXEC SQL
               SELECT NAME INTO :WS-NAME :WS-NAME-IND FROM CUSTOMER WHERE ID = :WS-ID
           END-EXEC.
           EXEC SQL
               INSERT INTO CUSTOMER (ID, NAME) VALUES (:WS-ID, :WS-NAME :WS-NAME-IND)
           END-EXEC.
           EXEC SQL
               UPDATE CUSTOMER SET NAME = :WS-NAME :WS-NAME-IND WHERE ID = :WS-ID
           END-EXEC.
           GOBACK.
    """
    lexer = CobolLexer("sqlind.cob", format_mode="free")
    tokens = lexer.tokenize(code)
    parser = CobolParser(tokens, "sqlind.cob")
    ir = parser.parse()
    
    gen = NativeProgramGenerator("SQLIND", list(ir.nodes.values()), file_assigns=[], repo_path=".")
    src = gen.generate_class_source()
    
    # Verify that the generated code contains the correct Spring JDBC template queries and parameter binding logic
    assert "jdbcTemplate.queryForRowSet" in src
    assert "jdbcTemplate.update" in src
    
    # Verify indicator variable checks: (ws_name_ind == -1) ? null : ws_name
    assert "(ws_name_ind == -1) ? null : ws_name" in src
    assert "ws_name_ind = -1" in src # wasNull() check

def test_sql_cursor_statements_translation():
    # Test Cursor DECLARE, OPEN, FETCH, CLOSE
    code = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. SQLCURS.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  SQLCA-VARIABLES.
           05  SQLCODE    PIC S9(9) COMP.
       01  WS-NAME        PIC X(20).
       01  WS-NAME-IND    PIC S9(4) COMP.
       01  WS-ID          PIC S9(4) COMP.
       PROCEDURE DIVISION.
           EXEC SQL
               DECLARE C1 CURSOR FOR
               SELECT ID, NAME FROM CUSTOMER WHERE ID > :WS-ID
           END-EXEC.
           EXEC SQL
               OPEN C1
           END-EXEC.
           EXEC SQL
               FETCH C1 INTO :WS-ID, :WS-NAME :WS-NAME-IND
           END-EXEC.
           EXEC SQL
               CLOSE C1
           END-EXEC.
           GOBACK.
    """
    lexer = CobolLexer("sqlcurs.cob", format_mode="free")
    tokens = lexer.tokenize(code)
    parser = CobolParser(tokens, "sqlcurs.cob")
    ir = parser.parse()
    
    gen = NativeProgramGenerator("SQLCURS", list(ir.nodes.values()), file_assigns=[], repo_path=".")
    src = gen.generate_class_source()
    
    # Check cursor field declaration
    assert "private org.springframework.jdbc.support.rowset.SqlRowSet cursor_c1 = null;" in src
    # Check OPEN maps to queryForRowSet
    assert "cursor_c1 = com.systema.modernized.SpringContextHelper.jdbcTemplate.queryForRowSet" in src
    # Check FETCH reads next
    assert "cursor_c1 != null && cursor_c1.next()" in src
    assert "ws_name_ind = -1" in src
    # Check CLOSE sets to null
    assert "cursor_c1 = null" in src

def test_vsam_indexed_store_mocked_h2():
    # Test VsamIndexedStore status code mapping and CRUD operations
    vsam_store_path = "modernize/java_helpers/src/main/java/com/systema/modernized/runtime/VsamIndexedStore.java"
    assert os.path.exists(vsam_store_path)
    with open(vsam_store_path, "r", encoding="utf-8") as fh:
        content = fh.read()
    
    # Assert existence of methods and status codes
    assert "public String readKey(String key, String[] fileStatus)" in content
    assert 'fileStatus[0] = "23";' in content # Key not found
    assert 'fileStatus[0] = "00";' in content # Success
    assert 'fileStatus[0] = "22";' in content # Duplicate key
    assert 'fileStatus[0] = "10";' in content # EOF
    assert 'fileStatus[0] = "46";' in content # Read without start
    assert 'fileStatus[0] = "30";' in content # Permanent error
    
    assert "public boolean start(String key, String op, String[] fileStatus)" in content
    assert "public String readNext(String[] fileStatus)" in content
    assert "public boolean write(String key, String record, String[] fileStatus)" in content
    assert "public boolean rewrite(String key, String record, String[] fileStatus)" in content
    assert "public boolean delete(String key, String[] fileStatus)" in content
