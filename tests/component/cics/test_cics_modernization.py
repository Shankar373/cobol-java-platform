import os
import shutil
import tempfile
import pytest
import subprocess
from modernize.lexer import CobolLexer
from modernize.parser import CobolParser
from modernize.native_pipeline import NativePipeline

def test_cics_lexer():
    src = "       EXEC CICS SEND MAP('OUTMAP') END-EXEC."
    lexer = CobolLexer("dummy.cob", format_mode="free")
    tokens = lexer.tokenize(src)
    cics_toks = [t for t in tokens if t.type == "EXEC_CICS"]
    assert len(cics_toks) == 1
    assert "SEND MAP('OUTMAP')" in cics_toks[0].value

def test_cics_parser_valid():
    src = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. TESTCICS.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-VAR PIC X(10).
       PROCEDURE DIVISION.
           EXEC CICS SEND MAP('MAP1') FROM(WS-VAR) END-EXEC.
    """
    lexer = CobolLexer("dummy.cob", format_mode="free")
    tokens = lexer.tokenize(src)
    parser = CobolParser(tokens, "dummy.cob")
    ir = parser.parse()
    cics_nodes = [n for n in ir.nodes.values() if n.kind == "STATEMENT" and n.properties.get("statement_type") == "EXEC_CICS"]
    assert len(cics_nodes) == 1
    assert cics_nodes[0].properties["cics_props"]["cics_type"] == "SEND"

def test_cics_pipeline_e2e():
    repo = os.path.join("tests", "repos", "CICSREST01")
    out_dir = tempfile.mkdtemp()
    try:
        pipeline = NativePipeline(repo, out_dir)
        pipeline.stage_discover()
        pipeline.stage_parse()
        main_src = [s for s in pipeline.program_ir if "cicsrest01" in s.lower()][0]
        pipeline.stage_generate(main_src)
        assert pipeline.stage_dependency_gate()
        assert pipeline.stage_build_gate()

        # Build classpath
        classpath = "target/classes"
        cp_file = os.path.join(pipeline.generated_dir, "cp.txt")
        if os.path.exists(cp_file):
            with open(cp_file, "r", encoding="utf-8") as fh:
                cp_deps = fh.read().strip()
                if cp_deps:
                    classpath += os.pathsep + cp_deps

        # Execute Cicsrest01 with "LINK" session input
        link_harness = """package com.systema.modernized.native_gen;
import com.systema.modernized.CicsTransactionContext;

public class TestRunner {
    public static void main(String[] args) {
        String mode = args.length > 0 ? args[0] : "LINK";
        CicsTransactionContext.clear();
        CicsTransactionContext.setSessionInput("INPUTMAP", "MSET", mode);
        
        Cicsrest01 prog = new Cicsrest01();
        prog.execute();
        
        Object sent = CicsTransactionContext.getSessionSent("OUTMAP", "MSET");
        System.out.println("TEST_RUNNER_SENT: " + sent);
    }
}
"""
        with open(os.path.join(pipeline.src_dir, "TestRunner.java"), "w", encoding="utf-8") as fh:
            fh.write(link_harness)

        assert pipeline.stage_build_gate()

        # Test LINK flow
        res = subprocess.run([
            "java", "-cp", classpath, "com.systema.modernized.native_gen.TestRunner", "LINK"
        ], cwd=pipeline.generated_dir, capture_output=True, text=True)
        assert res.returncode == 0, f"LINK execution failed: {res.stderr}\n{res.stdout}"
        assert "RECEIVED INPUT: LINK" in res.stdout
        assert "LINKPROG CALLED" in res.stdout
        assert "LINK COMMAREA: UPDATEDVAL" in res.stdout
        assert "TEST_RUNNER_SENT: UPDATEDVAL" in res.stdout

        # Test XCTL flow
        res2 = subprocess.run([
            "java", "-cp", classpath, "com.systema.modernized.native_gen.TestRunner", "XCTL"
        ], cwd=pipeline.generated_dir, capture_output=True, text=True)
        assert res2.returncode == 0, f"XCTL execution failed: {res2.stderr}\n{res2.stdout}"
        assert "RECEIVED INPUT: XCTL" in res2.stdout
        assert "LINKPROG CALLED" in res2.stdout

    finally:
        shutil.rmtree(out_dir, ignore_errors=True)

def test_cics_parser_invalid_variable():
    src = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. TESTCICS.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       PROCEDURE DIVISION.
           EXEC CICS SEND MAP('MAP1') FROM(UNDECLARED-VAR) END-EXEC.
    """
    lexer = CobolLexer("dummy.cob", format_mode="free")
    tokens = lexer.tokenize(src)
    parser = CobolParser(tokens, "dummy.cob")
    parser.parse()
    assert len(parser.diagnostics) > 0
    assert "CICS_HOST_VARIABLE_NOT_FOUND" in str(parser.diagnostics[0])
