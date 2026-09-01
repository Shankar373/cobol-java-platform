import os
import json
import shutil
import tempfile
import pytest
from modernize.lexer import CobolLexer
from modernize.parser import CobolParser
from modernize.native_pipeline import NativePipeline

def test_report_writer_parser():
    src = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. RWTEST.
       DATA DIVISION.
       REPORT SECTION.
       RD  SAL-REPORT.
       01  TYPE IS PAGE HEADING.
           05  LINE NUMBER IS 1.
               10  COLUMN NUMBER IS 1 PIC X(30) VALUE "DEPARTMENT SALARY REPORT".
       01  EMP-LINE TYPE IS DETAIL.
           05  LINE NUMBER IS PLUS 1.
               10  COLUMN NUMBER IS 5 PIC X(10) VALUE "SALARY:".
               10  COLUMN NUMBER IS 16 PIC ZZZZ9 SOURCE SALARY.
       PROCEDURE DIVISION.
           INITIATE SAL-REPORT.
           GENERATE EMP-LINE.
           TERMINATE SAL-REPORT.
           GOBACK.
    """
    lexer = CobolLexer("dummy.cob", format_mode="free")
    tokens = lexer.tokenize(src)
    parser = CobolParser(tokens, "dummy.cob")
    ir = parser.parse()
    
    nodes = list(ir.nodes.values())
    
    # Check RD node
    rd_nodes = [n for n in nodes if n.kind == "RD"]
    assert len(rd_nodes) == 1
    assert rd_nodes[0].properties["name"] == "SAL-REPORT"
    
    # Check INITIATE / GENERATE / TERMINATE statement nodes
    initiate_nodes = [n for n in nodes if n.kind == "STATEMENT" and n.properties.get("statement_type") == "INITIATE"]
    assert len(initiate_nodes) == 1
    assert initiate_nodes[0].properties["report_name"] == "SAL-REPORT"
    
    generate_nodes = [n for n in nodes if n.kind == "STATEMENT" and n.properties.get("statement_type") == "GENERATE"]
    assert len(generate_nodes) == 1
    assert generate_nodes[0].properties["target"] == "EMP-LINE"

def test_report_writer_e2e():
    repo_dir = os.path.join("tests", "repos", "REPORTWRITER01")
    temp_out = tempfile.mkdtemp()
    
    # Construct exact expected output
    expected_output = (
        "DEPARTMENT SALARY REPORT      \n"
        "    SALARY:    15000\n"
        "    SALARY:    25000\n"
        "\n"
        "PAGE:       1\n"
    )
    
    try:
        native_dir = os.path.join(temp_out, "results", "native")
        os.makedirs(native_dir, exist_ok=True)
        
        # Build baseline legacy folder
        baseline_dir = os.path.join(temp_out, "baseline", "legacy")
        os.makedirs(baseline_dir, exist_ok=True)
        
        # For legacy baseline, write expected output.txt, stdout.txt, and baseline_evidence.json
        with open(os.path.join(baseline_dir, "output.txt"), "w", encoding="utf-8") as fh:
            fh.write(expected_output)
        with open(os.path.join(baseline_dir, "stdout.txt"), "w", encoding="utf-8") as fh:
            fh.write("")
        with open(os.path.join(baseline_dir, "baseline_evidence.json"), "w", encoding="utf-8") as fh:
            json.dump({"status": "PASS", "evidence": "ReportWriter baseline"}, fh)
            
        p = NativePipeline(repo_dir, temp_out)
        verdict = p.run()
        
        # Check output.txt in native execution directory
        out_file = os.path.join(native_dir, "output.txt")
        assert os.path.exists(out_file), f"output.txt was not generated at {out_file}"
        with open(out_file, "r", encoding="utf-8") as fh:
            observed_output = fh.read()
            
        print("=== OBSERVED OUTPUT ===")
        print(repr(observed_output))
        
        # Let's compare stripped lines to be robust against trailing whitespace differences
        observed_lines = [l.rstrip() for l in observed_output.splitlines()]
        expected_lines = [l.rstrip() for l in expected_output.splitlines()]
        
        # We can still assert they are equivalent
        assert observed_lines == expected_lines, f"Mismatch!\nExpected:\n{expected_lines}\nObserved:\n{observed_lines}"
        assert verdict == "NATIVE_JAVA_VERIFIED", f"Pipeline failed. Check temp out: {temp_out}"
        
    finally:
        shutil.rmtree(temp_out, ignore_errors=True)
