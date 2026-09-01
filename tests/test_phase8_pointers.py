import os
import json
import shutil
import tempfile
import pytest
from modernize.lexer import CobolLexer
from modernize.parser import CobolParser
from modernize.native_pipeline import NativePipeline

def test_pointers_parser():
    src = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. PTRTEST.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  PTR USAGE POINTER.
       01  WS PIC X(5) VALUE "HELLO".
       LINKAGE SECTION.
       01  LS PIC X(5).
       PROCEDURE DIVISION.
           SET PTR TO ADDRESS OF WS.
           SET ADDRESS OF LS TO PTR.
           GOBACK.
    """
    lexer = CobolLexer("dummy.cob", format_mode="free")
    tokens = lexer.tokenize(src)
    parser = CobolParser(tokens, "dummy.cob")
    ir = parser.parse()
    
    nodes = list(ir.nodes.values())
    set_nodes = [n for n in nodes if n.kind == "STATEMENT" and n.properties.get("statement_type") == "SET"]
    assert len(set_nodes) == 2
    assert set_nodes[0].properties["is_address_of_source"] is True
    assert set_nodes[0].properties["target_var"] == "PTR"
    assert set_nodes[0].properties["source_var"] == "WS"
    
    assert set_nodes[1].properties["is_address_of_target"] is True
    assert set_nodes[1].properties["target_var"] == "LS"
    assert set_nodes[1].properties["source_var"] == "PTR"

def test_pointers_e2e():
    repo_dir = os.path.join("tests", "repos", "POINTERS01")
    temp_out = tempfile.mkdtemp()
    
    expected_stdout = (
        "LS-VAR BEFORE: HELLO\n"
        "WS-VAR AFTER: WORLD\n"
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
