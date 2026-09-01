import os
import sys
import json
import shutil
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modernize.lexer import CobolLexer
from modernize.parser import CobolParser, ParserDiagnostic
from modernize.native_generator import NativeProgramGenerator
from modernize.native_pipeline import NativePipeline

# ─── 1. Lexer & Parser Unit Tests ──────────────────────────────────────────

def test_db2_lexer_sql_token():
    code = """
       PROCEDURE DIVISION.
           EXEC SQL
               SELECT CUST_NAME INTO :WS-CUST-NAME FROM CUSTOMER WHERE CUST_ID = :WS-CUST-ID
           END-EXEC.
    """
    lexer = CobolLexer("smoke_db2.cob")
    tokens = lexer.tokenize(code)
    
    sql_toks = [t for t in tokens if t.type == "EXEC_SQL"]
    assert len(sql_toks) == 1
    assert "SELECT CUST_NAME" in sql_toks[0].value
    assert sql_toks[0].line == 3
    assert sql_toks[0].column == 12

def test_db2_parser_semantic_ir():
    code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. DB2PARS.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  SQLCA-VARIABLES.
           05  SQLCODE    PIC S9(9) COMP.
           05  SQLSTATE   PIC X(5).
       01  WS-CUST-ID     PIC S9(9) COMP.
       01  WS-CUST-NAME   PIC X(20).
       PROCEDURE DIVISION.
           EXEC SQL
               SELECT CUST_NAME INTO :WS-CUST-NAME FROM CUSTOMER WHERE CUST_ID = :WS-CUST-ID
           END-EXEC.
           GOBACK.
    """
    lexer = CobolLexer("db2pars.cob")
    tokens = lexer.tokenize(code)
    parser = CobolParser(tokens, "db2pars.cob")
    ir = parser.parse()
    
    sql_nodes = [n for n in ir.nodes.values() if n.kind == "STATEMENT" and n.properties.get("statement_type") == "EXEC_SQL"]
    assert len(sql_nodes) == 1
    props = sql_nodes[0].properties
    assert props["sql_props"]["sql_type"] == "SELECT"
    assert props["sql_props"]["table"] == "CUSTOMER"
    assert "WS-CUST-NAME" in props["sql_props"]["into_variables"]
    assert "WS-CUST-ID" in props["host_variables"]

def test_db2_parser_invalid_host_variable():
    code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. DB2ERR.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  SQLCA-VARIABLES.
           05  SQLCODE    PIC S9(9) COMP.
       PROCEDURE DIVISION.
           EXEC SQL
               SELECT CUST_NAME INTO :WS-UNDECLARED-VAR FROM CUSTOMER
           END-EXEC.
           GOBACK.
    """
    lexer = CobolLexer("db2err.cob")
    tokens = lexer.tokenize(code)
    parser = CobolParser(tokens, "db2err.cob")
    parser.parse()
    assert len(parser.diagnostics) > 0
    assert "SQL_HOST_VARIABLE_NOT_FOUND" in str(parser.diagnostics[0])

# ─── 2. End-to-End Pipeline Execution Tests ────────────────────────────────

def run_db2_pipeline_e2e(repo_name, expected_stdout):
    repo_dir = os.path.join("tests", "repos", repo_name)
    temp_out = tempfile.mkdtemp()
    
    try:
        # Pre-seed expected baseline stdout.txt
        baseline_dir = os.path.join(temp_out, "baseline", "legacy")
        os.makedirs(baseline_dir, exist_ok=True)
        with open(os.path.join(baseline_dir, "stdout.txt"), "w", encoding="utf-8") as fh:
            fh.write(expected_stdout)
        with open(os.path.join(baseline_dir, "baseline_evidence.json"), "w", encoding="utf-8") as fh:
            json.dump({"status": "PASS", "evidence": "DB2 standard baseline"}, fh)
            
        p = NativePipeline(repo_dir, temp_out)
        p.baseline_verified = True
        verdict = p.run()
        
        # Verify NativePipeline returned success
        if verdict != "NATIVE_JAVA_VERIFIED":
            print(f"FAILED VERDICT: {verdict}")
            b_path = os.path.join(temp_out, "baseline", "legacy", "stdout.txt")
            n_path = os.path.join(temp_out, "results", "native", "stdout.txt")
            print(f"Baseline path exists: {os.path.exists(b_path)}")
            print(f"Native path exists: {os.path.exists(n_path)}")
            if os.path.exists(b_path):
                print(f"--- BASELINE --- \n{open(b_path).read()}")
            if os.path.exists(n_path):
                print(f"--- NATIVE --- \n{open(n_path).read()}")
        assert verdict == "NATIVE_JAVA_VERIFIED", f"Pipeline failed. Check temp out: {temp_out}"
        
        # Double check that the execution observation exists and was captured
        obs_file = os.path.join(temp_out, "generated", "native_execution_observation.json")
        assert os.path.exists(obs_file)
        with open(obs_file, "r", encoding="utf-8") as fh:
            obs = json.load(fh)
            assert obs["exit_code"] == 0
            
    finally:
        shutil.rmtree(temp_out, ignore_errors=True)

def test_db2_select_e2e():
    expected = "SQLCODE: +0000000000\nSQLSTATE: 00000\nCUST-NAME: TEST CUSTOMER       \n"
    run_db2_pipeline_e2e("DB2SELECT01", expected)

def test_db2_insert_e2e():
    expected = "SQLCODE: +0000000000\nSQLSTATE: 00000\n"
    run_db2_pipeline_e2e("DB2INSERT01", expected)

def test_db2_update_e2e():
    expected = "SQLCODE: +0000000000\nSQLSTATE: 00000\n"
    run_db2_pipeline_e2e("DB2UPDATE01", expected)

def test_db2_delete_e2e():
    expected = "SQLCODE: +0000000000\nSQLSTATE: 00000\n"
    run_db2_pipeline_e2e("DB2DELETE01", expected)

def test_db2_cursor_e2e():
    expected = "OPEN SQLCODE: +0000000000\nFETCHED: +000000101 TEST CUSTOMER       \nFETCHED: +000000102 ANOTHER CUST        \nCLOSE SQLCODE: +0000000000\n"
    run_db2_pipeline_e2e("DB2CURSOR01", expected)

def test_db2_transaction_e2e():
    expected = "COMMIT SQLCODE: +0000000000\nROLLBACK SQLCODE: +0000000000\n"
    run_db2_pipeline_e2e("DB2TRANSACTION01", expected)

def test_db2_nested_e2e():
    expected = "NESTED SELECT SQLCODE: +0000000000\n"
    run_db2_pipeline_e2e("DB2NESTED01", expected)
