import sys
import os
import shutil
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cobol_migrate import Pipeline

def test_validation_gate2_no_bypass_on_mismatch():
    from cobol_migrate import docker_available
    if not docker_available():
        pytest.skip("Docker is not available, skipping Gate 2 validation bypass test")
        
    temp_repo = tempfile.mkdtemp()
    temp_out = tempfile.mkdtemp()
    
    try:
        # 1. Scaffold a simple COBOL application (not Claims/BankCore)
        os.makedirs(os.path.join(temp_repo, "sources"), exist_ok=True)
        os.makedirs(os.path.join(temp_repo, "data", "in"), exist_ok=True)
        
        # Write input data
        input_data = "LINE1\nLINE2\n"
        with open(os.path.join(temp_repo, "data", "in", "input.dat"), "w", encoding="utf-8") as f:
            f.write(input_data)
            
        # Write COBOL program (entry point is NOBYPASS)
        cobol_code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. NOBYPASS.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT IN-FILE ASSIGN TO "data/in/input.dat"
               ORGANIZATION IS LINE SEQUENTIAL.
           SELECT OUT-FILE ASSIGN TO "data/out/output.dat"
               ORGANIZATION IS LINE SEQUENTIAL.
       DATA DIVISION.
       FILE SECTION.
       FD  IN-FILE.
       01  IN-REC.
           05  IN-TEXT        PIC X(5).
       FD  OUT-FILE.
       01  OUT-REC.
           05  OUT-TEXT       PIC X(5).
       WORKING-STORAGE SECTION.
       01  WS-EOF             PIC X VALUE 'N'.
       PROCEDURE DIVISION.
       MAIN-PARA.
           OPEN INPUT IN-FILE
                OUTPUT OUT-FILE.
           PERFORM UNTIL WS-EOF = 'Y'
               READ IN-FILE
                   AT END
                       MOVE 'Y' TO WS-EOF
                   NOT AT END
                       MOVE IN-TEXT TO OUT-TEXT
                       WRITE OUT-REC
               END-READ
           END-PERFORM.
           CLOSE IN-FILE OUT-FILE.
           STOP RUN.
        """
        with open(os.path.join(temp_repo, "sources", "nobypass.cob"), "w", encoding="utf-8") as f:
            f.write(cobol_code)
            
        # 2. Run Pipeline up to execute to generate baseline
        pipeline = Pipeline(temp_repo, temp_out)
        from cobol_migrate import STAGES
        
        def run_stage(idx):
            name = STAGES[idx]
            fn = getattr(pipeline, "stage_" + name)
            ok, detail, artifacts = fn()
            if ok:
                pipeline.mark(idx, "done", detail, artifacts)
            else:
                pipeline.mark(idx, "error", detail)
            return ok

        # Let's run up to compare stage (stage 8)
        for stage_idx in range(9): # 0 to 8
            assert run_stage(stage_idx), f"Stage {stage_idx} failed"
            
        # Corrupt the baseline file
        baseline_file = os.path.join(temp_out, "baseline", "legacy", "data", "out", "output.dat")
        assert os.path.isfile(baseline_file), "Baseline output file was not produced!"
        with open(baseline_file, "w", encoding="utf-8") as f:
            f.write("CORRUPTED_DIFFERENT_DATA\n")
            
        # Run refactor stage (stage 9)
        assert run_stage(9), "Refactor stage failed"
        
        # Run validate stage (stage 10)
        # Since baseline file is corrupted, validation must run, detect the mismatch, and return False (fail).
        # It must NOT return True (success/bypass).
        success = run_stage(10)
        
        assert not success, "Gate 2 validation bypassed check and returned success instead of failing on mismatch!"
        
        # Verify state is failed
        val_data = pipeline.state["data"].get("validate", {})
        assert val_data.get("status") == "failed"
        assert val_data.get("gate2_passed") is False
        assert "mismatch" in val_data.get("detail", "").lower()
        print("Validation gate correctly caught mismatch and rejected the run (no bypass).")

    finally:
        shutil.rmtree(temp_repo, ignore_errors=True)
        shutil.rmtree(temp_out, ignore_errors=True)
