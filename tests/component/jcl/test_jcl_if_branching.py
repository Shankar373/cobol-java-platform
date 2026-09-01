import os
import tempfile
import pytest
from modernize.native_pipeline import NativePipeline

def test_jcl_if_then_else_e2e():
    """Verify JCL IF/THEN/ELSE conditional branching differential equivalence."""
    repo_dir = os.path.abspath("tests/repos/JCLIF01")
    temp_out = tempfile.mkdtemp(prefix="jcl_if_")
    
    # Clean any leftover binaries
    for f in os.listdir(repo_dir):
        if f.endswith((".so", ".exe", ".tmp")):
            try: os.remove(os.path.join(repo_dir, f))
            except Exception: pass
            
    try:
        pipeline = NativePipeline(repo_dir, temp_out)
        verdict = pipeline.run()
        
        assert verdict == "NATIVE_JAVA_VERIFIED", f"JCL IF/THEN/ELSE pipeline failed with verdict: {verdict}"
        
        # Verify stdout lines match expected sequence
        native_stdout = os.path.join(temp_out, "results", "native", "stdout.txt")
        with open(native_stdout, "r", encoding="utf-8") as fh:
            lines = fh.read().splitlines()
            
        print("=== EXECUTION TRACE ===")
        for l in lines:
            print(l)
            
        # STEP1 ran (RC=0)
        assert any("EXECUTE STEP: STEP1" in l for l in lines)
        # STEP2 ran (RC=4)
        assert any("EXECUTE STEP: STEP2" in l for l in lines)
        # STEP3 ran (THEN branch of IF1: STEP2.RC = 4 is true)
        assert any("EXECUTE STEP: STEP3" in l for l in lines)
        # STEP4 NOT executed (ELSE branch of IF1 skipped)
        assert not any("EXECUTE STEP: STEP4" in l for l in lines)
        # STEP5 NOT executed (THEN branch of IF2: STEP1.RC > 0 is false)
        assert not any("EXECUTE STEP: STEP5" in l for l in lines)
        # STEP6 ran (ELSE branch of IF2)
        assert any("EXECUTE STEP: STEP6" in l for l in lines)
        
    finally:
        pass
