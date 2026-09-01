import os
import shutil
import tempfile
import pytest
import subprocess
import re
from modernize.jcl_parser import JclParser
from modernize.native_pipeline import NativePipeline

def test_jcl_parser_unit():
    jcl_path = os.path.join("tests", "repos", "JCLBATCH01", "src", "JCLBATCH01.jcl")
    content = open(jcl_path, "r", encoding="utf-8").read()
    parser = JclParser(content, repo_dir=os.path.join("tests", "repos", "JCLBATCH01"))
    job = parser.parse()
    
    assert job.name == "JCLBATCH01"
    # Flat steps collected count should be 4 (STEP1, STEP2.PROCSTEP, STEPBYPS, STEP3)
    flat_steps = parser.collect_all_steps(job.steps)
    assert len(flat_steps) == 4
    
    # Check STEP1
    step1 = flat_steps[0]
    assert step1["name"] == "STEP1"
    assert step1["pgm"] == "COBPROG1"
    assert "INPUTDD" in step1["dds"]
    assert step1["dds"]["INPUTDD"]["dsn"] == "MY.INPUT.DATA"
    assert step1["dds"]["SYSIN"]["sysin_data"] == "SYSIN DATA LINE 1"
    
    # Check PROC expansion on STEP2
    step2 = flat_steps[1]
    assert step2["name"] == "STEP2.PROCSTEP"
    assert step2["pgm"] == "COBPROG2"
    assert "REPORTDD" in step2["dds"]
    assert step2["dds"]["REPORTDD"]["dsn"] == "MY.REPORT.DATA" # Symbol outputfile replaced
    assert len(step2["conds"]) == 1
    assert step2["conds"][0] == (0, "NE", "STEP1")

def test_jcl_parser_invalid():
    jcl_path = os.path.join("tests", "repos", "JCLINVALID01", "src", "JCLINVALID01.jcl")
    content = open(jcl_path, "r", encoding="utf-8").read()
    parser = JclParser(content)
    job = parser.parse()
    
    diags = parser.diagnostics
    assert len(diags) > 0
    
    reasons = [d["reason"] for d in diags]
    # Check that we logged expected syntax/logical errors
    assert any("JCL_INVALID_STEP" in r for r in reasons)
    assert any("JCL_UNRESOLVED_PROC" in r for r in reasons)
    assert any("JCL_UNRESOLVED_SYMBOL" in r for r in reasons)
    assert any("JCL_UNSUPPORTED_CONDITION" in r for r in reasons)
    assert any("UNRESOLVED_DATASET" in r for r in reasons)

def test_jcl_pipeline_e2e():
    repo = os.path.join("tests", "repos", "JCLBATCH01")
    out_dir = tempfile.mkdtemp(prefix="jcl_batch_")
    
    # Create input dataset
    input_file = os.path.join(repo, "MY.INPUT.DATA")
    with open(input_file, "w", encoding="utf-8") as f:
        f.write("HELLO WORLD".ljust(80))
        
    try:
        pipeline = NativePipeline(repo, out_dir)
        res = pipeline.run()
        
        # Check verdict
        if res != "NATIVE_JAVA_VERIFIED":
            obs_path = os.path.join(out_dir, "generated", "native_execution_observation.json")
            if os.path.exists(obs_path):
                with open(obs_path, "r", encoding="utf-8") as fh:
                    print("=== NATIVE RUN OBSERVATION ===")
                    print(fh.read())
            legacy_stdout = os.path.join(out_dir, "baseline", "legacy", "stdout.txt")
            if os.path.exists(legacy_stdout):
                with open(legacy_stdout, "r", encoding="utf-8") as fh:
                    print("=== LEGACY STDOUT ===")
                    print(fh.read())
            native_stdout = os.path.join(out_dir, "results", "native", "stdout.txt")
            if os.path.exists(native_stdout):
                with open(native_stdout, "r", encoding="utf-8") as fh:
                    print("=== NATIVE STDOUT ===")
                    print(fh.read())
                    
        assert res == "NATIVE_JAVA_VERIFIED"
        
        # Verify output files created during execution
        results_dir = os.path.join(out_dir, "results", "native")
        output_data = os.path.join(results_dir, "MY.OUTPUT.DATA")
        report_data = os.path.join(results_dir, "MY.REPORT.DATA")
        final_data = os.path.join(results_dir, "MY.FINAL.DATA")
        
        assert os.path.exists(output_data), "MY.OUTPUT.DATA was not created"
        assert os.path.exists(report_data), "MY.REPORT.DATA was not created"
        assert os.path.exists(final_data), "MY.FINAL.DATA was not created"
        
        # Read files and verify output strings
        with open(output_data, "r", encoding="utf-8") as fh:
            out_content = fh.read().strip()
        with open(report_data, "r", encoding="utf-8") as fh:
            rep_content = fh.read().strip()
        with open(final_data, "r", encoding="utf-8") as fh:
            fin_content = fh.read().strip()
            
        assert "PROG1:HELLO WORLD" in out_content
        assert "SYSIN DATA LINE 1" in out_content
        assert "PROG2:" in rep_content
        assert "PROG3:" in fin_content
        
    finally:
        if os.path.exists(input_file):
            try: os.remove(input_file)
            except Exception: pass
        # Cleanup files generated during execution in repo
        for f in ["MY.INPUT.DATA", "MY.OUTPUT.DATA", "MY.REPORT.DATA", "MY.FINAL.DATA", "cobprog1.exe", "cobprog2.exe", "cobprog3.exe"]:
            p = os.path.join(repo, f)
            if os.path.exists(p):
                try: os.remove(p)
                except Exception: pass
        shutil.rmtree(out_dir, ignore_errors=True)
