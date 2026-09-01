import os
import tempfile
import pytest
from modernize.native_pipeline import NativePipeline

def test_jcl_conditional_e2e():
    """Verify comprehensive JCL COND evaluation (EQ, GT, EVEN, ONLY, abend tracking)."""
    repo_dir = os.path.abspath("tests/repos/JCLCOND01")
    temp_out = tempfile.mkdtemp(prefix="jcl_cond_")
    
    # Clean any leftover binaries
    for f in os.listdir(repo_dir):
        if f.endswith((".so", ".exe", ".tmp")):
            try: os.remove(os.path.join(repo_dir, f))
            except Exception: pass
            
    try:
        pipeline = NativePipeline(repo_dir, temp_out)
        verdict = pipeline.run()
        
        assert verdict == "NATIVE_JAVA_VERIFIED", f"JCL COND pipeline failed with verdict: {verdict}"
        
        # Verify stdout lines match expected sequence
        native_stdout = os.path.join(temp_out, "results", "native", "stdout.txt")
        with open(native_stdout, "r", encoding="utf-8") as fh:
            lines = fh.read().splitlines()
            
        print("=== EXECUTION TRACE ===")
        for l in lines:
            print(l)
            
        # STEP1 ran (RC=4)
        assert any("EXECUTE STEP: STEP1" in l for l in lines)
        # STEP2 bypassed (4 EQ 4 is true)
        assert any("STEP BYPASS: STEP2" in l for l in lines)
        # STEP3 bypassed (0 NE 4 is true)
        assert any("STEP BYPASS: STEP3" in l for l in lines)
        # STEP4 ran (4 GT 4 is false -> executes and abends with RC=8)
        assert any("EXECUTE STEP: STEP4" in l for l in lines)
        # STEP5 bypassed (abended)
        assert any("STEP BYPASS: STEP5" in l for l in lines)
        # STEP6 ran (EVEN)
        assert any("EXECUTE STEP: STEP6" in l for l in lines)
        # STEP7 ran (ONLY)
        assert any("EXECUTE STEP: STEP7" in l for l in lines)
        
    finally:
        pass
