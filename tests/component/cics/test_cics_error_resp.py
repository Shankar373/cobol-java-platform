import os
import shutil
import tempfile
import json
import pytest
from modernize.native_pipeline import NativePipeline

def test_cics_resp_codes_and_abend():
    temp_repo = tempfile.mkdtemp()
    temp_out = tempfile.mkdtemp()

    try:
        os.makedirs(os.path.join(temp_repo, "sources"), exist_ok=True)
        os.makedirs(os.path.join(temp_repo, "data"), exist_ok=True)

        resp_cob = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. RESPPG.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-COM       PIC X(10) VALUE "DATA      ".
       01  WS-RESP      PIC 9(4)  VALUE 9999.
       01  WS-RESP2     PIC 9(4)  VALUE 9999.
       PROCEDURE DIVISION.
           DISPLAY "TESTING SUCCESSFUL SEND RESP"
           EXEC CICS SEND MAP('MAP1') FROM(WS-COM) RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
           DISPLAY "AFTER SEND RESP=" WS-RESP " RESP2=" WS-RESP2

           DISPLAY "TESTING MISSING LINK PROGRAM RESP"
           EXEC CICS LINK PROGRAM('UNKNOWN') COMMAREA(WS-COM) LENGTH(10) RESP(WS-RESP) END-EXEC
           DISPLAY "AFTER FAILED LINK RESP=" WS-RESP

           EXEC CICS RETURN END-EXEC.
        """
        with open(os.path.join(temp_repo, "sources", "resppg.cob"), "w", encoding="utf-8") as fh:
            fh.write(resp_cob)

        config = {
            "main_program": "resppg.cob",
            "file_assignments": {}
        }
        with open(os.path.join(temp_repo, "migration_config.json"), "w", encoding="utf-8") as fh:
            json.dump(config, fh)

        p = NativePipeline(temp_repo, temp_out)
        p.stage_discover()
        p.stage_parse()
        main_src = [s for s in p.program_ir.keys() if "resppg" in s.lower()][0]
        p.stage_generate(main_src)
        assert p.stage_dependency_gate()
        assert p.stage_build_gate()
        assert p.stage_execute_gate(main_src)

        stdout_path = os.path.join(temp_out, "results", "native", "stdout.txt")
        assert os.path.isfile(stdout_path)
        with open(stdout_path, "r", encoding="utf-8") as fh:
            stdout = fh.read()

        assert "AFTER SEND RESP=0000 RESP2=0000" in stdout
        assert "AFTER FAILED LINK RESP=0027" in stdout

    finally:
        shutil.rmtree(temp_repo, ignore_errors=True)
        shutil.rmtree(temp_out, ignore_errors=True)
