import os
import json
import shutil
import tempfile
import subprocess
import pytest
from modernize.lexer import CobolLexer
from modernize.parser import CobolParser
from modernize.native_pipeline import NativePipeline

def test_pic_parser_is_edited():
    src = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. EDTEST.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  VAR-A PIC $$,$$9.99.
       01  VAR-B PIC ZZ,ZZ9.99.
       01  VAR-C PIC S9(5).
    """
    lexer = CobolLexer("dummy.cob", format_mode="free")
    tokens = lexer.tokenize(src)
    parser = CobolParser(tokens, "dummy.cob")
    ir = parser.parse()
    
    nodes = list(ir.nodes.values())
    var_a = [n for n in nodes if n.properties.get("name") == "VAR-A"][0]
    var_b = [n for n in nodes if n.properties.get("name") == "VAR-B"][0]
    var_c = [n for n in nodes if n.properties.get("name") == "VAR-C"][0]
    
    assert var_a.properties["is_edited"] is True
    assert var_b.properties["is_edited"] is True
    assert var_c.properties.get("is_edited", False) is False

def test_pic_formatting_e2e():
    repo_dir = os.path.join("tests", "repos", "PICTUREEDIT01")
    temp_out = tempfile.mkdtemp()
    
    expected_stdout = (
        "POS CURR: $12,345.67\n"
        "NEG CURR: $12,345.67\n"
        "ZERO CURR:      $0.00\n"
        "POS PLUS:  +12,345.67\n"
        "NEG PLUS:  -12,345.67\n"
        "POS MINUS:   12,345.67\n"
        "NEG MINUS:  -12,345.67\n"
        "POS ZSUPP: 12,345.67\n"
        "ZERO ZSUPP:      0.00\n"
        "POS AST: 12,345.67\n"
        "ZERO AST: *****0.12\n"
        "POS CR: 12,345.67  \n"
        "NEG CR: 12,345.67CR\n"
        "POS DB: 12,345.67  \n"
        "NEG DB: 12,345.67DB\n"
        "OVERFLOW: 567.89\n"
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
