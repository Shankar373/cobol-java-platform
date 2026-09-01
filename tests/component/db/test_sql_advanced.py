import pytest
from modernize.lexer import CobolLexer
from modernize.parser import CobolParser, ParserDiagnostic
from modernize.native_generator import NativeProgramGenerator

def test_complex_sql_where_parsing():
    code = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. SQLCOMP.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  SQLCA-VARIABLES.
           05  SQLCODE    PIC S9(9) COMP.
       01  WS-AGE         PIC S9(4) COMP.
       01  WS-STATUS      PIC X(10).
       01  WS-NAME        PIC X(20).
       PROCEDURE DIVISION.
           EXEC SQL
               SELECT NAME INTO :WS-NAME FROM CUSTOMER
               WHERE (STATUS = :WS-STATUS AND AGE >= :WS-AGE)
                  OR CUSTOMER_TYPE = 'VIP'
                  OR OTHER_FIELD IS NULL
                  OR RATING BETWEEN 1 AND 5
                  OR CLASS IN ('A', 'B', 'C')
                  OR DESCRIPTION LIKE '%GOLD%'
           END-EXEC.
           GOBACK.
    """
    lexer = CobolLexer("sqlcomp.cob", format_mode="free")
    tokens = lexer.tokenize(code)
    parser = CobolParser(tokens, "sqlcomp.cob")
    ir = parser.parse()
    
    sql_nodes = [n for n in ir.nodes.values() if n.kind == "STATEMENT" and n.properties.get("statement_type") == "EXEC_SQL"]
    assert len(sql_nodes) == 1
    sp = sql_nodes[0].properties["sql_props"]
    
    assert sp["sql_type"] == "SELECT"
    assert sp["table"] == "CUSTOMER"
    
    # Verify predicates
    preds = sp["predicates"]
    # We expect complex predicates including AND, OR, parentheses, IS NULL, BETWEEN, IN, LIKE
    logicals = [p["logical"] for p in preds if "logical" in p]
    assert "(" in logicals
    assert ")" in logicals
    assert "AND" in logicals
    assert "OR" in logicals
    
    operators = [p["op"] for p in preds if "op" in p]
    assert "IS NULL" in operators
    assert "BETWEEN" in operators
    assert "IN" in operators
    assert "LIKE" in operators

def test_sql_joins_and_aliases():
    code = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. SQLJOIN.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  SQLCA-VARIABLES.
           05  SQLCODE    PIC S9(9) COMP.
       01  WS-NAME        PIC X(20).
       01  WS-DATE        PIC X(10).
       PROCEDURE DIVISION.
           EXEC SQL
               SELECT C.CUST_NAME, O.ORDER_DATE INTO :WS-NAME, :WS-DATE
               FROM CUSTOMER C INNER JOIN ORDERS O ON C.ID = O.CUSTOMER_ID
               WHERE C.STATUS = 'ACTIVE'
           END-EXEC.
           GOBACK.
    """
    lexer = CobolLexer("sqljoin.cob", format_mode="free")
    tokens = lexer.tokenize(code)
    parser = CobolParser(tokens, "sqljoin.cob")
    ir = parser.parse()
    
    sql_nodes = [n for n in ir.nodes.values() if n.kind == "STATEMENT" and n.properties.get("statement_type") == "EXEC_SQL"]
    assert len(sql_nodes) == 1
    sp = sql_nodes[0].properties["sql_props"]
    
    assert sp["tables"] == ["CUSTOMER", "ORDERS"]
    assert sp["alias_map"] == {"C": "CUSTOMER", "O": "ORDERS"}

def test_sql_unresolved_host_var_error():
    code = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. SQLERR.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  SQLCA-VARIABLES.
           05  SQLCODE    PIC S9(9) COMP.
       PROCEDURE DIVISION.
           EXEC SQL
               SELECT NAME FROM CUSTOMER WHERE AGE = :WS-UNDECLARED
           END-EXEC.
           GOBACK.
    """
    lexer = CobolLexer("sqlerr.cob", format_mode="free")
    tokens = lexer.tokenize(code)
    parser = CobolParser(tokens, "sqlerr.cob")
    parser.parse()
    assert len(parser.diagnostics) > 0
    assert "SQL_HOST_VARIABLE_NOT_FOUND" in str(parser.diagnostics[0])
