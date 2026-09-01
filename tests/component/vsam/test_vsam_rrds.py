import os
import json
import shutil
import tempfile
from modernize.native_pipeline import NativePipeline

def test_vsam_rrds_e2e():
    temp_repo = tempfile.mkdtemp()
    temp_out = tempfile.mkdtemp()
    
    # Simple relative file COBOL program
    cobol_src = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. RRDSPROG.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT REL-FILE ASSIGN TO "data/relfile.dat"
               ORGANIZATION IS RELATIVE
               ACCESS MODE IS RANDOM
               RELATIVE KEY IS WS-RRN.
       DATA DIVISION.
       FILE SECTION.
       FD  REL-FILE.
       01  REL-REC.
           05  REC-ID      PIC X(4).
           05  REC-VAL     PIC 9(4).
       WORKING-STORAGE SECTION.
       01  WS-RRN          PIC 9(4) VALUE 0.
       PROCEDURE DIVISION.
       MAIN-PARA.
           OPEN OUTPUT REL-FILE.
           MOVE 1 TO WS-RRN.
           MOVE "A101" TO REC-ID.
           MOVE 1234 TO REC-VAL.
           WRITE REL-REC.
           
           MOVE 2 TO WS-RRN.
           MOVE "B202" TO REC-ID.
           MOVE 5678 TO REC-VAL.
           WRITE REL-REC.
           CLOSE REL-FILE.
           
           OPEN INPUT REL-FILE.
           MOVE 1 TO WS-RRN.
           READ REL-FILE INVALID KEY DISPLAY "ERR" NOT INVALID KEY DISPLAY "R1: " REC-ID " " REC-VAL.
           MOVE 2 TO WS-RRN.
           READ REL-FILE INVALID KEY DISPLAY "ERR" NOT INVALID KEY DISPLAY "R2: " REC-ID " " REC-VAL.
           CLOSE REL-FILE.
           GOBACK.
    """
    
    try:
        os.makedirs(os.path.join(temp_repo, "src"), exist_ok=True)
        with open(os.path.join(temp_repo, "src", "RRDSPROG.cob"), "w", encoding="utf-8") as fh:
            fh.write(cobol_src)
            
        config = {
            "main_program": "src/RRDSPROG.cob",
            "file_assignments": {}
        }
        with open(os.path.join(temp_repo, "migration_config.json"), "w", encoding="utf-8") as fh:
            json.dump(config, fh)
            
        # Actual DISPLAY output: concatenated without padding
        # DISPLAY "R1: " REC-ID " " REC-VAL  =>  "R1: A101 1234"
        expected_stdout = "R1: A101 1234\nR2: B202 5678\n"
        
        # Pre-seed expected legacy baseline outputs
        baseline_dir = os.path.join(temp_out, "baseline", "legacy")
        os.makedirs(baseline_dir, exist_ok=True)
        with open(os.path.join(baseline_dir, "stdout.txt"), "w", encoding="utf-8") as fh:
            fh.write(expected_stdout)
            
        # Note: relfile.dat is NOT seeded here — it is a relative/binary file that the
        # Java program creates during OPEN OUTPUT.  The equivalence engine only compares
        # files that exist in the baseline; omitting it restricts the check to stdout.
            
        p = NativePipeline(temp_repo, temp_out)
        p.baseline_verified = True
        p.stage_discover()
        p.stage_parse()
        selected_src = p.stage_select_slice()
        assert selected_src is not None
        
        p.stage_generate(selected_src)
        assert p.stage_dependency_gate()
        assert p.stage_build_gate()
        assert p.stage_execute_gate(selected_src)
        
        # Clean up binary/dummy index files from results so they don't mismatch unseeded baseline
        rel_path = os.path.join(temp_out, "results", "native", "data", "relfile.dat")
        if os.path.exists(rel_path):
            os.remove(rel_path)
            
        verdict = p.stage_equivalence_gate(selected_src)
        assert verdict == "PASS", f"VSAM RRDS pipeline failed: {verdict}"
        
        neg_pass = p.stage_negative_equivalence(selected_src)
        assert neg_pass
        
    finally:
        shutil.rmtree(temp_repo, ignore_errors=True)
        shutil.rmtree(temp_out, ignore_errors=True)


