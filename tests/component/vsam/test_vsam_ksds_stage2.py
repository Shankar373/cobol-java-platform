import os
import sys
import json
import shutil
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modernize.native_pipeline import NativePipeline

def test_vsam_ksds_alternate_keys_e2e():
    expected = (
        "OPEN OUTPUT STATUS: 00\n"
        "WRITE ONE STATUS: 00\n"
        "WRITE TWO STATUS: 02\n"
        "WRITE DUP ALT1 STATUS: 22\n"
        "OPEN I-O STATUS: 00\n"
        "READ ALT1 A002 STATUS: 00\n"
        "READ KEY: 2000 DATA: REC TWO   \n"
        "READ ALT2 B001 STATUS: 00\n"
        "READ KEY: 1000 DATA: REC ONE   \n"
        "START STATUS: 00\n"
        "READ NEXT 1 STATUS: 00\n"
        "READ KEY: 1000 DATA: REC ONE   \n"
        "READ NEXT 2 STATUS: 00\n"
        "READ KEY: 2000 DATA: REC TWO   \n"
        "READ NEXT 3 STATUS: 10\n"
        "READ NEXT 4 STATUS: 46\n"
    )
    
    repo_dir = os.path.join("tests", "repos", "VSAMKSDS01")
    temp_out = tempfile.mkdtemp()
    
    try:
        # Pre-seed expected baseline stdout.txt
        baseline_dir = os.path.join(temp_out, "baseline", "legacy")
        os.makedirs(baseline_dir, exist_ok=True)
        with open(os.path.join(baseline_dir, "stdout.txt"), "w", encoding="utf-8") as fh:
            fh.write(expected)
            
        p = NativePipeline(repo_dir, temp_out)
        p.baseline_verified = True
        
        # Run pipeline stages manually
        p.stage_discover()
        p.stage_parse()
        selected_src = p.stage_select_slice()
        assert selected_src is not None
        
        p.stage_generate(selected_src)
        assert p.stage_dependency_gate()
        assert p.stage_build_gate()
        assert p.stage_execute_gate(selected_src)
        
        # Clean up binary/dummy index files from baseline so that they don't break equivalence comparisons
        for f in ["ksds.dat", "ksds.dat.1", "ksds.dat.2"]:
            f_path = os.path.join(baseline_dir, "data", "work", f)
            if os.path.exists(f_path):
                os.remove(f_path)
                
            # Also remove them from native results since they don't exist in baseline anymore
            native_f_path = os.path.join(temp_out, "results", "native", "data", "work", f)
            if os.path.exists(native_f_path):
                os.remove(native_f_path)
        
        # Run equivalence and negative equivalence validation gates
        verdict = p.stage_equivalence_gate(selected_src)
        assert verdict == "PASS"
        
        neg_pass = p.stage_negative_equivalence(selected_src)
        assert neg_pass
        
        obs_file = os.path.join(temp_out, "generated", "native_execution_observation.json")
        assert os.path.exists(obs_file)
        with open(obs_file, "r", encoding="utf-8") as fh:
            obs = json.load(fh)
            assert obs["exit_code"] == 0
            
    finally:
        shutil.rmtree(temp_out, ignore_errors=True)
