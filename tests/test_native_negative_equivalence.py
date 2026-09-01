import sys
import os
import json
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modernize.native_pipeline import NativePipeline

def test_negative_equivalence_success(tmpdir):
    out_dir = str(tmpdir.mkdir("out"))
    p = NativePipeline("tests/repos/MULTIFILE01", out_dir)
    
    baseline_dir = os.path.join(out_dir, "baseline", "legacy")
    native_dir = os.path.join(out_dir, "results", "native")
    
    os.makedirs(baseline_dir, exist_ok=True)
    os.makedirs(native_dir, exist_ok=True)
    
    # Create matching baseline and native output files
    with open(os.path.join(baseline_dir, "report.txt"), "w") as fh:
        fh.write("RECORD1\nRECORD2\n")
    with open(os.path.join(native_dir, "report.txt"), "w") as fh:
        fh.write("RECORD1\nRECORD2\n")
        
    passed = p.stage_negative_equivalence("MULTIFILE01.cob")
    assert passed is True
    
    # Assert backup file is properly restored and cleaned up
    assert os.path.exists(os.path.join(native_dir, "report.txt"))
    assert not os.path.exists(os.path.join(native_dir, "report.txt.bak"))
    with open(os.path.join(native_dir, "report.txt"), "r") as fh:
        assert fh.read() == "RECORD1\nRECORD2\n"
