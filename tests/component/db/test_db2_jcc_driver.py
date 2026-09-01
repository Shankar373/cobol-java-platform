import os
import shutil
import tempfile
import subprocess
import pytest
from modernize.native_pipeline import NativePipeline

def test_db2_jcc_driver_in_pom_and_classpath(monkeypatch):
    monkeypatch.setenv("REAL_DB2_MODE", "1")
    
    # Create simple DB2 SELECT project
    repo_dir = os.path.join("tests", "repos", "DB2SELECT01")
    tmp_out = tempfile.mkdtemp()
    
    try:
        # Pre-seed expected baseline
        baseline_dir = os.path.join(tmp_out, "baseline", "legacy")
        os.makedirs(baseline_dir, exist_ok=True)
        with open(os.path.join(baseline_dir, "stdout.txt"), "w") as fh:
            fh.write("")
            
        p = NativePipeline(repo_dir, tmp_out)
        p.stage_discover()
        p.stage_parse()
        src_key = list(p.program_ir.keys())[0]
        p.stage_generate(src_key)
        
        # Check generated pom.xml does NOT contain DB2 JCC dependency, but contains postgresql
        pom_path = os.path.join(p.generated_dir, "pom.xml")
        assert os.path.exists(pom_path)
        with open(pom_path, "r") as fh:
            pom_content = fh.read()
        assert "com.ibm.db2" not in pom_content
        assert "postgresql" in pom_content
        
        # Verify driver is resolved in Maven classpath
        mvn_exe = "mvn.cmd" if os.name == "nt" else "mvn"
        res = subprocess.run([
            mvn_exe, "dependency:build-classpath", "-Dmdep.outputFile=cp.txt"
        ], cwd=p.generated_dir, capture_output=True, text=True)
        
        assert res.returncode == 0, f"Maven dependency resolve failed: {res.stderr}\n{res.stdout}"
        
        cp_file = os.path.join(p.generated_dir, "cp.txt")
        assert os.path.exists(cp_file)
        with open(cp_file, "r") as fh:
            classpath = fh.read()
            
        # Verify postgresql jar is in the classpath, not DB2
        assert "postgresql" in classpath.lower()
        assert "db2" not in classpath.lower()
        
    finally:
        shutil.rmtree(tmp_out, ignore_errors=True)
