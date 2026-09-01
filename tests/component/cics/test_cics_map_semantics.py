import os
import json
import shutil
import tempfile
import pytest
from modernize.native_pipeline import NativePipeline

def test_cics_map_semantics_options_e2e():
    temp_out = tempfile.mkdtemp()
    repo_dir = os.path.join(temp_out, "CICSMAP01")
    os.makedirs(os.path.join(repo_dir, "src"), exist_ok=True)
    
    # Write a simple COBOL CICS program that sends and receives map with options
    cobol_src = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. COBPROG1.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  MAP-DATA PIC X(10).
       PROCEDURE DIVISION.
           EXEC CICS SEND MAP('MAP1') MAPSET('MSET1')
                     FROM(MAP-DATA) DATAONLY ERASE ALARM FREEKB
           END-EXEC.
           EXEC CICS RECEIVE MAP('MAP1') MAPSET('MSET1')
                     INTO(MAP-DATA)
           END-EXEC.
           GOBACK.
    """
    with open(os.path.join(repo_dir, "src", "COBPROG1.cob"), "w", encoding="utf-8") as fh:
        fh.write(cobol_src)
        
    config = {
        "main_program": "COBPROG1.cob",
        "file_assignments": {}
    }
    with open(os.path.join(repo_dir, "migration_config.json"), "w", encoding="utf-8") as fh:
        json.dump(config, fh)
        
    try:
        p = NativePipeline(repo_dir, temp_out)
        p.stage_discover()
        p.stage_parse()
        main_src = [s for s in p.program_ir if "cobprog1" in s.lower()][0]
        p.stage_generate(main_src)
        assert p.stage_dependency_gate()
        assert p.stage_build_gate()
        assert p.stage_execute_gate(main_src)

        stdout_path = os.path.join(temp_out, "results", "native", "stdout.txt")
        assert os.path.isfile(stdout_path)
        with open(stdout_path, "r", encoding="utf-8") as fh:
            stdout = fh.read()

        assert "CICS SEND MAP: MAP1 MAPSET: MSET1" in stdout
        assert "erase" in stdout.lower()
        assert "freekb" in stdout.lower()
        assert "alarm" in stdout.lower()
        assert "dataonly" in stdout.lower()
        assert "CICS RECEIVE MAP: MAP1 MAPSET: MSET1" in stdout
        
    finally:
        shutil.rmtree(temp_out, ignore_errors=True)
