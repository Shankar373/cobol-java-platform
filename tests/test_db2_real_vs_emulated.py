import os
import pytest
from modernize.lexer import CobolLexer
from modernize.parser import CobolParser

def test_db2_dialect_warnings():
    code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. DB2WARN.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  SQLCA-VARIABLES.
           05  SQLCODE    PIC S9(9) COMP.
       PROCEDURE DIVISION.
           EXEC SQL
               SELECT CUST_NAME FROM CUSTOMER WHERE CUST_ID = 1 WITH UR
           END-EXEC.
           EXEC SQL
               SELECT CUST_NAME FROM CUSTOMER FOR UPDATE
           END-EXEC.
           GOBACK.
    """
    lexer = CobolLexer("db2warn.cob")
    tokens = lexer.tokenize(code)
    parser = CobolParser(tokens, "db2warn.cob")
    parser.parse()
    
    warnings = [d for d in parser.diagnostics if "DB2_UNSUPPORTED_CONSTRUCT" in d.message]
    assert len(warnings) == 2
    assert "WITH UR" in warnings[0].message
    assert "FOR UPDATE" in warnings[1].message


def test_db2_real_vs_emulated_status(monkeypatch):
    """Exercise the REAL classification logic (cobol_migrate.classify_db2_status)."""
    import cobol_migrate as cm

    # No embedded SQL in the repository -> nothing to verify.
    assert cm.classify_db2_status(has_sql=False) == "NOT_VERIFIED"

    # SQL present, no DB2_URL configured: must NOT claim any real-DB2 state.
    monkeypatch.delenv("DB2_URL", raising=False)
    assert cm.classify_db2_status(has_sql=True) == "REAL_DB2_NOT_CONFIGURED"

    # With REAL_DB2_MODE=1 and missing DB2_URL/USERNAME/PASSWORD: ENVIRONMENT_BLOCKED
    monkeypatch.setenv("REAL_DB2_MODE", "1")
    monkeypatch.delenv("DB2_URL", raising=False)
    monkeypatch.delenv("DB2_USERNAME", raising=False)
    monkeypatch.delenv("DB2_PASSWORD", raising=False)
    assert cm.classify_db2_status(has_sql=True, real_db2_mode=True) == "ENVIRONMENT_BLOCKED"

    # Missing username or password
    monkeypatch.setenv("DB2_URL", "jdbc:db2://127.0.0.1:50000/SAMPLE")
    assert cm.classify_db2_status(has_sql=True, real_db2_mode=True) == "ENVIRONMENT_BLOCKED"
    
    monkeypatch.setenv("DB2_USERNAME", "db2user")
    monkeypatch.setenv("DB2_PASSWORD", "secret")

    # Malformed URL must be rejected explicitly as INVALID_CONFIGURATION under REAL_DB2_MODE
    monkeypatch.setenv("DB2_URL", "some-garbage-not-a-jdbc-url")
    assert cm.classify_db2_status(has_sql=True, real_db2_mode=True) == "INVALID_CONFIGURATION"

    # Reachable port: REAL_DB2_NOT_VERIFIED
    import socket
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(5)
    port = srv.getsockname()[1]
    try:
        monkeypatch.setenv("DB2_URL", f"jdbc:db2://127.0.0.1:{port}")
        # Without REAL_DB2_MODE: reachability only
        assert cm.classify_db2_status(has_sql=True) == "REAL_DB2_NOT_VERIFIED_REACHABLE"
        # With REAL_DB2_MODE: REAL_DB2_NOT_VERIFIED (reachable but not verified yet)
        assert cm.classify_db2_status(has_sql=True, real_db2_mode=True) == "REAL_DB2_NOT_VERIFIED"
    finally:
        srv.close()

    # Unreachable endpoint: REAL_DB2_UNREACHABLE (without mode) and ENVIRONMENT_BLOCKED (with mode)
    monkeypatch.setenv("DB2_URL", "jdbc:db2://127.0.0.1:1")
    assert cm.classify_db2_status(has_sql=True) == "REAL_DB2_UNREACHABLE"
    assert cm.classify_db2_status(has_sql=True, real_db2_mode=True) == "ENVIRONMENT_BLOCKED"