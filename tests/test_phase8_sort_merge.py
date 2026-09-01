import os
import json
import shutil
import tempfile
import pytest
from modernize.lexer import CobolLexer
from modernize.parser import CobolParser
from modernize.native_pipeline import NativePipeline

def test_sort_merge_parser():
    src = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. SMTEST.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT SORTWORK ASSIGN TO "sortwork".
       DATA DIVISION.
       FILE SECTION.
       SD  SORTWORK.
       01  WORK-REC.
           05  WORK-KEY PIC 9(2).
       PROCEDURE DIVISION.
           SORT SORTWORK ON ASCENDING KEY WORK-KEY
               USING INFILE GIVING OUTFILE.
           GOBACK.
    """
    lexer = CobolLexer("dummy.cob", format_mode="free")
    tokens = lexer.tokenize(src)
    parser = CobolParser(tokens, "dummy.cob")
    ir = parser.parse()
    
    nodes = list(ir.nodes.values())
    sort_nodes = [n for n in nodes if n.kind == "STATEMENT" and n.properties.get("statement_type") == "SORT"]
    assert len(sort_nodes) == 1
    properties = sort_nodes[0].properties
    assert properties["work_file"] == "SORTWORK"
    assert properties["keys"] == [{"name": "WORK-KEY", "order": "ASCENDING"}]

def test_sort_merge_e2e():
    repo_dir = os.path.join("tests", "repos", "SORTMERGE01")
    temp_out = tempfile.mkdtemp()
    
    input_data = (
        "Alice     30\n"
        "Bob       25\n"
        "Charlie   35\n"
    )
    expected_output = (
        "Bob       25\n"
        "Alice     30\n"
        "Charlie   35\n"
    )
    
    try:
        # Create execution sub-directory results/native
        native_dir = os.path.join(temp_out, "results", "native")
        os.makedirs(native_dir, exist_ok=True)
        
        # Build baseline legacy folder
        baseline_dir = os.path.join(temp_out, "baseline", "legacy")
        os.makedirs(baseline_dir, exist_ok=True)
        
        # For legacy baseline, write expected output.txt and input.txt
        with open(os.path.join(baseline_dir, "output.txt"), "w", encoding="utf-8") as fh:
            fh.write(expected_output)
        with open(os.path.join(baseline_dir, "input.txt"), "w", encoding="utf-8") as fh:
            fh.write(input_data)
        with open(os.path.join(baseline_dir, "stdout.txt"), "w", encoding="utf-8") as fh:
            fh.write("")
            
        # Write input.txt to the native execution directory
        with open(os.path.join(native_dir, "input.txt"), "w", encoding="utf-8") as fh:
            fh.write(input_data)
            
        p = NativePipeline(repo_dir, temp_out)
        verdict = p.run()
        
        # Let's assert output.txt in native execution directory matches expected_output
        out_file = os.path.join(native_dir, "output.txt")
        assert os.path.exists(out_file), f"output.txt was not generated at {out_file}"
        with open(out_file, "r", encoding="utf-8") as fh:
            observed_output = fh.read()
            
        print("=== OBSERVED OUTPUT ===")
        print(repr(observed_output))
        
        assert observed_output.replace("\r\n", "\n") == expected_output.replace("\r\n", "\n")
        assert verdict == "NATIVE_JAVA_VERIFIED", f"Pipeline failed. Check temp out: {temp_out}"
        
    finally:
        shutil.rmtree(temp_out, ignore_errors=True)

def test_merge_parser():
    src = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. MGTEST.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT MERGEWORK ASSIGN TO "mergework".
       DATA DIVISION.
       FILE SECTION.
       SD  MERGEWORK.
       01  WORK-REC.
           05  WORK-KEY PIC 9(2).
       PROCEDURE DIVISION.
           MERGE MERGEWORK ON ASCENDING KEY WORK-KEY
               USING INFILE1 INFILE2 GIVING OUTFILE.
           GOBACK.
    """
    lexer = CobolLexer("dummy.cob", format_mode="free")
    tokens = lexer.tokenize(src)
    parser = CobolParser(tokens, "dummy.cob")
    ir = parser.parse()
    
    nodes = list(ir.nodes.values())
    merge_nodes = [n for n in nodes if n.kind == "STATEMENT" and n.properties.get("statement_type") == "MERGE"]
    assert len(merge_nodes) == 1
    properties = merge_nodes[0].properties
    assert properties["work_file"] == "MERGEWORK"
    assert properties["keys"] == [{"name": "WORK-KEY", "order": "ASCENDING"}]
    assert properties["using_files"] == ["INFILE1", "INFILE2"]
    assert properties["giving_files"] == ["OUTFILE"]

def test_merge_e2e():
    temp_out = tempfile.mkdtemp()
    repo_dir = os.path.join(temp_out, "repo")
    os.makedirs(os.path.join(repo_dir, "src"), exist_ok=True)
    
    cob_code = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. MERGE01.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT INFILE1 ASSIGN TO "input1.txt"
               ORGANIZATION IS LINE SEQUENTIAL.
           SELECT INFILE2 ASSIGN TO "input2.txt"
               ORGANIZATION IS LINE SEQUENTIAL.
           SELECT OUTFILE ASSIGN TO "output.txt"
               ORGANIZATION IS LINE SEQUENTIAL.
           SELECT MERGEWORK ASSIGN TO "mergework.tmp".
       DATA DIVISION.
       FILE SECTION.
       FD  INFILE1.
       01  IN-REC1.
           05  IN-NAME1 PIC X(10).
           05  IN-AGE1  PIC 9(2).
       FD  INFILE2.
       01  IN-REC2.
           05  IN-NAME2 PIC X(10).
           05  IN-AGE2  PIC 9(2).
       FD  OUTFILE.
       01  OUT-REC.
           05  OUT-NAME PIC X(10).
           05  OUT-AGE  PIC 9(2).
       SD  MERGEWORK.
       01  WORK-REC.
           05  WORK-NAME PIC X(10).
           05  WORK-AGE  PIC 9(2).
       PROCEDURE DIVISION.
       MAIN-PARA.
           MERGE MERGEWORK ON ASCENDING KEY WORK-AGE
               USING INFILE1 INFILE2 GIVING OUTFILE.
           GOBACK.
    """
    
    with open(os.path.join(repo_dir, "src", "MERGE01.cob"), "w", encoding="utf-8") as fh:
        fh.write(cob_code)
        
    input1_data = "Alice     30\nCharlie   35\n"
    input2_data = "Bob       25\n"
    expected_output = "Bob       25\nAlice     30\nCharlie   35\n"
    
    try:
        native_dir = os.path.join(temp_out, "results", "native")
        os.makedirs(native_dir, exist_ok=True)
        
        baseline_dir = os.path.join(temp_out, "baseline", "legacy")
        os.makedirs(baseline_dir, exist_ok=True)
        # For legacy baseline, write expected output.txt and inputs
        with open(os.path.join(baseline_dir, "output.txt"), "w", encoding="utf-8") as fh:
            fh.write(expected_output)
        with open(os.path.join(baseline_dir, "input1.txt"), "w", encoding="utf-8") as fh:
            fh.write(input1_data)
        with open(os.path.join(baseline_dir, "input2.txt"), "w", encoding="utf-8") as fh:
            fh.write(input2_data)
        with open(os.path.join(baseline_dir, "stdout.txt"), "w", encoding="utf-8") as fh:
            fh.write("")
            
        with open(os.path.join(native_dir, "input1.txt"), "w", encoding="utf-8") as fh:
            fh.write(input1_data)
        with open(os.path.join(native_dir, "input2.txt"), "w", encoding="utf-8") as fh:
            fh.write(input2_data)
            
        p = NativePipeline(repo_dir, temp_out)
        verdict = p.run()
        
        out_file = os.path.join(native_dir, "output.txt")
        assert os.path.exists(out_file)
        with open(out_file, "r", encoding="utf-8") as fh:
            observed = fh.read()
            
        assert observed.replace("\r\n", "\n") == expected_output.replace("\r\n", "\n")
        assert verdict == "NATIVE_JAVA_VERIFIED"
        
    finally:
        shutil.rmtree(temp_out, ignore_errors=True)
