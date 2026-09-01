import os
import json
import shutil
import tempfile
import pytest
from modernize.lexer import CobolLexer
from modernize.parser import CobolParser
from modernize.jcl_parser import JclParser
from modernize.native_pipeline import NativePipeline

def test_jcl_symbol_substitution():
    jcl_content = """//TESTJOB  JOB (ACCT)
//SET1     SET VAR1='MY.VAL1'
//SET2     SET VAR2=&VAR1
//STEP1    EXEC PGM=PROG1
//DD1      DD DSN=&VAR2..DATA,DISP=SHR
//DD2      DD DSN=&&TEMP,DISP=NEW
"""
    parser = JclParser(jcl_content, "/dummy/repo")
    job = parser.parse()
    
    assert job.symbols["VAR1"] == "MY.VAL1"
    assert job.symbols["VAR2"] == "MY.VAL1"
    
    step1 = job.steps[0]
    dd1 = step1.dds["DD1"]
    dd2 = step1.dds["DD2"]
    
    assert dd1.dsn == "MY.VAL1.DATA"
    # Should preserve temporary dataset semantics (&&)
    assert dd2.dsn == "&&TEMP"

def test_jcl_symbol_unresolved_diag():
    jcl_content = """//TESTJOB  JOB (ACCT)
//STEP1    EXEC PGM=PROG1
//DD1      DD DSN=&UNRESOLVED.DATA,DISP=SHR
"""
    parser = JclParser(jcl_content, "/dummy/repo")
    parser.parse()
    diags = parser.diagnostics
    assert len(diags) > 0
    assert "JCL_UNRESOLVED_SYMBOL" in diags[0]["reason"]

def test_jcl_symbols_e2e():
    repo_dir = os.path.join("tests", "repos", "JCLSYMBOL01")
    temp_out = tempfile.mkdtemp(prefix="jcl_symbol_")
    
    # Create input datasets in repo
    input_file = os.path.join(repo_dir, "MY.INPUT.DATA")
    temp_file = os.path.join(repo_dir, "MYTEMP")
    
    with open(input_file, "w", encoding="utf-8") as fh:
        fh.write("INPUT DATA LINE 1\nINPUT DATA LINE 2\n")
    with open(temp_file, "w", encoding="utf-8") as fh:
        fh.write("TEMP DATA LINE 1\n")
        
    try:
        p = NativePipeline(repo_dir, temp_out)
        verdict = p.run()
        
        # Verify success
        if verdict != "NATIVE_JAVA_VERIFIED":
            obs_path = os.path.join(temp_out, "generated", "native_execution_observation.json")
            if os.path.exists(obs_path):
                with open(obs_path, "r", encoding="utf-8") as fh:
                    print("=== NATIVE RUN OBSERVATION ===")
                    print(fh.read())
            legacy_stdout = os.path.join(temp_out, "baseline", "legacy", "stdout.txt")
            if os.path.exists(legacy_stdout):
                with open(legacy_stdout, "r", encoding="utf-8") as fh:
                    print("=== LEGACY STDOUT ===")
                    print(fh.read())
            native_stdout = os.path.join(temp_out, "results", "native", "stdout.txt")
            if os.path.exists(native_stdout):
                with open(native_stdout, "r", encoding="utf-8") as fh:
                    print("=== NATIVE STDOUT ===")
                    print(fh.read())
                    
        assert verdict == "NATIVE_JAVA_VERIFIED", f"JCL Symbol E2E pipeline failed with verdict: {verdict}"
        
    finally:
        if os.path.exists(input_file):
            try: os.remove(input_file)
            except Exception: pass
        if os.path.exists(temp_file):
            try: os.remove(temp_file)
            except Exception: pass
        for f in ["cobprog1.exe", "MY.OUTPUT.DATA", "MY.OVERRIDDEN.DATA"]:
            p_f = os.path.join(repo_dir, f)
            if os.path.exists(p_f):
                try: os.remove(p_f)
                except Exception: pass
        shutil.rmtree(temp_out, ignore_errors=True)

