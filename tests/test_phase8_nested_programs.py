import os
import json
import shutil
import tempfile
import pytest
from modernize.lexer import CobolLexer
from modernize.parser import CobolParser
from modernize.native_pipeline import NativePipeline

def test_nested_program_parser():
    src = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. PARENT.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  VAR-GLOBAL PIC X(10) GLOBAL VALUE "GLOB".
       
       PROCEDURE DIVISION.
           CALL "CHILD".
           GOBACK.
           
       IDENTIFICATION DIVISION.
       PROGRAM-ID. CHILD.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  VAR-LOCAL PIC X(10) VALUE "LOC".
       
       PROCEDURE DIVISION.
           DISPLAY "IN CHILD" VAR-GLOBAL.
           GOBACK.
       END PROGRAM CHILD.
       END PROGRAM PARENT.
    """
    lexer = CobolLexer("dummy.cob", format_mode="free")
    tokens = lexer.tokenize(src)
    parser = CobolParser(tokens, "dummy.cob")
    ir = parser.parse()
    
    nodes = list(ir.nodes.values())
    var_global = [n for n in nodes if n.properties.get("name") == "VAR-GLOBAL"][0]
    var_local = [n for n in nodes if n.properties.get("name") == "VAR-LOCAL"][0]
    
    assert var_global.properties.get("is_global") is True
    assert var_local.properties.get("is_global", False) is False
    
    # Check program scoping properties
    assert var_global.properties.get("program") == "PARENT"
    assert var_local.properties.get("program") == "CHILD"

def test_nested_program_e2e():
    repo_dir = os.path.join("tests", "repos", "NESTEDPROG01")
    temp_out = tempfile.mkdtemp()
    
    expected_stdout = (
        "PARENT START\n"
        "GLOBAL BEFORE: GLOBAL_VAL_01  \n"
        "CHILD START\n"
        "GLOBAL IN CHILD: UPDATED_GLOBAL \n"
        "LINKAGE IN CHILD: LOCAL_PARENT   \n"
        "CHILD END\n"
        "GLOBAL AFTER: CHILD_TOUCH    \n"
        "LOCAL AFTER: CHILD_LINK     \n"
        "PARENT END\n"
    )
    
    try:
        baseline_dir = os.path.join(temp_out, "baseline", "legacy")
        os.makedirs(baseline_dir, exist_ok=True)
        with open(os.path.join(baseline_dir, "stdout.txt"), "w", encoding="utf-8") as fh:
            fh.write(expected_stdout)
            
        p = NativePipeline(repo_dir, temp_out)
        verdict = p.run()
        
        obs_file = os.path.join(temp_out, "generated", "native_execution_observation.json")
        if os.path.exists(obs_file):
            with open(obs_file, "r") as fh:
                obs = json.load(fh)
                print("=== NATIVE RUN OBS ===")
                print(json.dumps(obs, indent=2))
        
        assert verdict == "NATIVE_JAVA_VERIFIED", f"Pipeline failed. Check temp out: {temp_out}"
        
    finally:
        shutil.rmtree(temp_out, ignore_errors=True)
