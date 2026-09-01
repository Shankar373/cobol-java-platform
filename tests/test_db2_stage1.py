import os
import sys
import json
import shutil
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modernize.lexer import CobolLexer
from modernize.parser import CobolParser
from modernize.native_pipeline import NativePipeline
from modernize.native_generator import NativeProgramGenerator

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
        
        # Set PG connection parameters in environment for the host Java run.
        os.environ["PGHOST"] = "localhost"
        os.environ["PGPORT"] = "5432"
        os.environ["PGUSER"] = "modernize"
        os.environ["PGPASSWORD"] = "modernize"
        os.environ["PGDATABASE"] = "modernization_db"

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

# ─── E2E Tests ──────────────────────────────────────────────────────────────

def test_db2_inner_join_e2e():
    expected = "SQLCODE: +0000000000\nCUST: TEST CUSTOMER       \nORDER: 2024-01-15\n"
    run_db2_pipeline_e2e("DB2JOIN01", expected)

def test_db2_left_outer_join_e2e():
    expected = "SQLCODE: +0000000000\nCUST: TEST CUSTOMER       \nDEPT: NULL\n"
    run_db2_pipeline_e2e("DB2LEFTJOIN01", expected)

def test_db2_count_aggregate_e2e():
    expected = "SQLCODE: +0000000000\nCOUNT: +000000002\n"
    run_db2_pipeline_e2e("DB2AGGREGATE01", expected)

def test_db2_group_by_having_e2e():
    expected = "OPEN SQLCODE: +0000000000\nDEPT: +000000010 COUNT: +000000002\n"
    run_db2_pipeline_e2e("DB2GROUPBY01", expected)

def test_db2_subquery_e2e():
    expected = "SQLCODE: +0000000000\nFOUND: TEST CUSTOMER       \n"
    run_db2_pipeline_e2e("DB2SUBQUERY01", expected)

def test_db2_tx_commit_visible_e2e():
    expected = "COMMITTED: YES\nROLLED BACK: YES\n"
    run_db2_pipeline_e2e("DB2TXVISIBILITY01", expected)

def test_db2_error_constraint_violation_e2e():
    expected = "SQLCODE: -0000000803\n"
    run_db2_pipeline_e2e("DB2ERRCONSTRAINT", expected)

def test_db2_error_not_found_e2e():
    expected = "SQLCODE: +0000000100\n"
    run_db2_pipeline_e2e("DB2ERRNOTFOUND", expected)

# ─── Unit Tests ─────────────────────────────────────────────────────────────

def test_db2_sqlcode_mapping_unit():
    from modernize.native_pipeline import NativePipeline
    temp_dir = tempfile.mkdtemp()
    try:
        p = NativePipeline("tests/repos/DB2JOIN01", temp_dir)
        p.stage_discover()
        p.stage_parse()
        p.stage_generate(p.sources[0])
        mapper_file = os.path.join(p.generated_dir, "src", "main", "java", "com", "systema", "modernized", "Db2ErrorMapper.java")
        assert os.path.exists(mapper_file)
        with open(mapper_file, "r") as fh:
            content = fh.read()
            assert "-803" in content
            assert "-204" in content
            assert "-206" in content
            assert "-911" in content
            assert "-900" in content
            assert "08000" in content
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def test_db2_group_by_parser_unit():
    code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. GRPPARS.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  SQLCA-VARIABLES.
           05  SQLCODE    PIC S9(9) COMP.
           05  SQLSTATE   PIC X(5).
       01  WS-DEPT-COUNT.
           05  WS-DEPT-ID     PIC S9(9) COMP.
           05  WS-COUNT       PIC S9(9) COMP.
       PROCEDURE DIVISION.
           EXEC SQL
               SELECT DEPT_ID, COUNT(*)
               INTO :WS-DEPT-ID, :WS-COUNT
               FROM CUSTOMER
               GROUP BY DEPT_ID
               HAVING COUNT(*) > 1
               ORDER BY DEPT_ID
           END-EXEC.
           GOBACK.
    """
    lexer = CobolLexer("grppars.cob")
    tokens = lexer.tokenize(code)
    parser = CobolParser(tokens, "grppars.cob")
    ir = parser.parse()
    sql_nodes = [n for n in ir.nodes.values() if n.kind == "STATEMENT" and n.properties.get("statement_type") == "EXEC_SQL"]
    assert len(sql_nodes) == 1
    sp = sql_nodes[0].properties.get("sql_props", {})
    assert "original_sql" in sp or "SELECT" in str(sp)

def test_db2_subquery_parser_unit():
    code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. SUBPARS.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  SQLCA-VARIABLES.
           05  SQLCODE    PIC S9(9) COMP.
           05  SQLSTATE   PIC X(5).
       01  WS-NAME        PIC X(20).
       PROCEDURE DIVISION.
           EXEC SQL
               SELECT CUST_NAME
               INTO :WS-NAME
               FROM CUSTOMER
               WHERE CUST_ID IN (SELECT CUSTOMER_ID FROM ORDERS)
           END-EXEC.
           GOBACK.
    """
    lexer = CobolLexer("subpars.cob")
    tokens = lexer.tokenize(code)
    parser = CobolParser(tokens, "subpars.cob")
    ir = parser.parse()
    sql_nodes = [n for n in ir.nodes.values() if n.kind == "STATEMENT" and n.properties.get("statement_type") == "EXEC_SQL"]
    assert len(sql_nodes) == 1
    sp = sql_nodes[0].properties.get("sql_props", {})
    assert "original_sql" in sp or "SELECT" in str(sp)
