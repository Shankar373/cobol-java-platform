import sys
import os
import json
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modernize.native_pipeline import NativePipeline

def test_equivalence_pass(tmpdir):
    out_dir = str(tmpdir.mkdir("out"))
    p = NativePipeline("tests/repos/MULTIFILE01", out_dir)
    p.baseline_verified = True
    
    baseline_dir = os.path.join(out_dir, "baseline", "legacy")
    native_dir = os.path.join(out_dir, "results", "native")
    
    os.makedirs(baseline_dir, exist_ok=True)
    os.makedirs(native_dir, exist_ok=True)
    
    with open(os.path.join(baseline_dir, "report.txt"), "w") as fh:
        fh.write("HELLO WORLD")
    with open(os.path.join(native_dir, "report.txt"), "w") as fh:
        fh.write("HELLO WORLD")
        
    try:
        verdict = p.stage_equivalence_gate("MULTIFILE01.cob")
        assert verdict == "PASS"
        
        equiv_file = os.path.join(out_dir, "generated", "native_equivalence_result.json")
        assert os.path.exists(equiv_file)
        with open(equiv_file, "r") as fh:
            res = json.load(fh)
            assert res["verdict"] == "PASS"
            assert "report.txt" in res["matched_files"]
            assert len(res["mismatches"]) == 0
    finally:
        pass

def test_equivalence_fail(tmpdir):
    out_dir = str(tmpdir.mkdir("out"))
    p = NativePipeline("tests/repos/MULTIFILE01", out_dir)
    p.baseline_verified = True
    
    baseline_dir = os.path.join(out_dir, "baseline", "legacy")
    native_dir = os.path.join(out_dir, "results", "native")
    
    os.makedirs(baseline_dir, exist_ok=True)
    os.makedirs(native_dir, exist_ok=True)
    
    with open(os.path.join(baseline_dir, "report.txt"), "w") as fh:
        fh.write("HELLO WORLD")
    with open(os.path.join(native_dir, "report.txt"), "w") as fh:
        fh.write("HELLO DIFFERENCE")
        
    try:
        verdict = p.stage_equivalence_gate("MULTIFILE01.cob")
        assert verdict == "FAIL"
        
        equiv_file = os.path.join(out_dir, "generated", "native_equivalence_result.json")
        assert os.path.exists(equiv_file)
        with open(equiv_file, "r") as fh:
            res = json.load(fh)
            assert res["verdict"] == "FAIL"
            assert len(res["mismatches"]) > 0
    finally:
        pass

def test_equivalence_unverified(tmpdir):
    out_dir = str(tmpdir.mkdir("out"))
    p = NativePipeline("tests/repos/MULTIFILE01", out_dir)
    
    # Do not create baseline dir
    verdict = p.stage_equivalence_gate("MULTIFILE01.cob")
    assert verdict == "UNVERIFIED"
