import os
import shutil
import tempfile
import json
import pytest
from modernize.native_pipeline import NativePipeline

def test_cics_screen_send_receive_map():
    temp_repo = tempfile.mkdtemp()
    temp_out = tempfile.mkdtemp()

    try:
        os.makedirs(os.path.join(temp_repo, "sources"), exist_ok=True)
        os.makedirs(os.path.join(temp_repo, "data"), exist_ok=True)

        screen_cob = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. SCREENPG.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-IN-SCREEN  PIC X(30) VALUE "                              ".
       01  WS-OUT-SCREEN PIC X(30) VALUE "DISPLAY SCREEN READY          ".
       01  WS-RESP       PIC 9(4)  VALUE 0.
       01  WS-RESP2      PIC 9(4)  VALUE 0.
       PROCEDURE DIVISION.
           DISPLAY "SCREENPG: SENDING MAP"
           EXEC CICS SEND MAP('MAP1') MAPSET('MSET1') FROM(WS-OUT-SCREEN) ERASE FREEKB ALARM RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
           DISPLAY "SCREENPG: AFTER SEND RESP=" WS-RESP
           DISPLAY "SCREENPG: RECEIVING MAP"
           EXEC CICS RECEIVE MAP('MAP1') MAPSET('MSET1') INTO(WS-IN-SCREEN) RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
           DISPLAY "SCREENPG: AFTER RECEIVE RESP=" WS-RESP " INPUT=" WS-IN-SCREEN
           EXEC CICS RETURN END-EXEC.
        """
        with open(os.path.join(temp_repo, "sources", "screenpg.cob"), "w", encoding="utf-8") as fh:
            fh.write(screen_cob)

        config = {
            "main_program": "screenpg.cob",
            "file_assignments": {}
        }
        with open(os.path.join(temp_repo, "migration_config.json"), "w", encoding="utf-8") as fh:
            json.dump(config, fh)

        p = NativePipeline(temp_repo, temp_out)
        p.stage_discover()
        p.stage_parse()
        main_src = [s for s in p.program_ir.keys() if "screenpg" in s.lower()][0]
        p.stage_generate(main_src)
        assert p.stage_dependency_gate()
        assert p.stage_build_gate()
        assert p.stage_execute_gate(main_src)

        stdout_path = os.path.join(temp_out, "results", "native", "stdout.txt")
        assert os.path.isfile(stdout_path)
        with open(stdout_path, "r", encoding="utf-8") as fh:
            stdout = fh.read()

        assert "SCREENPG: SENDING MAP" in stdout
        assert "CICS SEND MAP: MAP1 MAPSET: MSET1 DATA: DISPLAY SCREEN READY" in stdout
        assert "SCREENPG: AFTER SEND RESP=0000" in stdout
        assert "SCREENPG: RECEIVING MAP" in stdout
        assert "CICS RECEIVE MAP: MAP1 MAPSET: MSET1" in stdout
        assert "SCREENPG: AFTER RECEIVE RESP=0000" in stdout

    finally:
        shutil.rmtree(temp_repo, ignore_errors=True)
        shutil.rmtree(temp_out, ignore_errors=True)
