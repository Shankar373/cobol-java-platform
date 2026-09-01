import os
import shutil
import tempfile
import json
import pytest
from modernize.native_pipeline import NativePipeline

def test_cics_flow_control_link_xctl_return():
    temp_repo = tempfile.mkdtemp()
    temp_out = tempfile.mkdtemp()

    try:
        os.makedirs(os.path.join(temp_repo, "sources"), exist_ok=True)
        os.makedirs(os.path.join(temp_repo, "data"), exist_ok=True)

        # MAIN PROG
        main_cob = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. MAINPROG.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-COM PIC X(20) VALUE "INIT-DATA           ".
       01  WS-RESP PIC 9(4) VALUE 0.
       PROCEDURE DIVISION.
           DISPLAY "MAIN: BEFORE LINK COMMAREA=" WS-COM
           EXEC CICS LINK PROGRAM('CALLEE') COMMAREA(WS-COM) LENGTH(20) RESP(WS-RESP) END-EXEC
           DISPLAY "MAIN: AFTER LINK RESP=" WS-RESP " COMMAREA=" WS-COM
           EXEC CICS RETURN TRANSID('NEXT') COMMAREA(WS-COM) END-EXEC
           DISPLAY "MAIN: UNREACHABLE AFTER RETURN".
        """
        with open(os.path.join(temp_repo, "sources", "mainprog.cob"), "w", encoding="utf-8") as fh:
            fh.write(main_cob)

        # CALLEE PROG
        callee_cob = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. CALLEE.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-CALLEE-VAR PIC X(10) VALUE "LOCAL     ".
       LINKAGE SECTION.
       01  DFHCOMMAREA PIC X(20).
       PROCEDURE DIVISION.
           DISPLAY "CALLEE: RECEIVED COMMAREA=" DFHCOMMAREA
           MOVE "MUTATED-BY-CALLEE  " TO DFHCOMMAREA
           EXEC CICS RETURN END-EXEC.
        """
        with open(os.path.join(temp_repo, "sources", "callee.cob"), "w", encoding="utf-8") as fh:
            fh.write(callee_cob)

        config = {
            "main_program": "mainprog.cob",
            "file_assignments": {}
        }
        with open(os.path.join(temp_repo, "migration_config.json"), "w", encoding="utf-8") as fh:
            json.dump(config, fh)

        p = NativePipeline(temp_repo, temp_out)
        p.stage_discover()
        p.stage_parse()
        main_src = [s for s in p.program_ir.keys() if "mainprog" in s.lower()][0]
        p.stage_generate(main_src)
        assert p.stage_dependency_gate()
        assert p.stage_build_gate()
        assert p.stage_execute_gate(main_src)
        
        stdout_path = os.path.join(temp_out, "results", "native", "stdout.txt")
        assert os.path.isfile(stdout_path)
        with open(stdout_path, "r", encoding="utf-8") as fh:
            stdout = fh.read()
        
        # Verify execution trace
        assert "MAIN: BEFORE LINK COMMAREA=INIT-DATA" in stdout
        assert "CALLEE: RECEIVED COMMAREA=INIT-DATA" in stdout
        assert "MAIN: AFTER LINK RESP=0000 COMMAREA=MUTATED-BY-CALLEE" in stdout
        assert "CICS RETURN TRANSID: NEXT" in stdout
        assert "UNREACHABLE AFTER RETURN" not in stdout

    finally:
        shutil.rmtree(temp_repo, ignore_errors=True)
        shutil.rmtree(temp_out, ignore_errors=True)

def test_cics_missing_program_pgmiderr():
    temp_repo = tempfile.mkdtemp()
    temp_out = tempfile.mkdtemp()

    try:
        os.makedirs(os.path.join(temp_repo, "sources"), exist_ok=True)
        os.makedirs(os.path.join(temp_repo, "data"), exist_ok=True)

        main_cob = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. MAINPROG.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-COM PIC X(20) VALUE "INIT-DATA           ".
       01  WS-RESP PIC 9(4) VALUE 0.
       PROCEDURE DIVISION.
           EXEC CICS LINK PROGRAM('NONEXISTENT') COMMAREA(WS-COM) LENGTH(20) RESP(WS-RESP) END-EXEC
           DISPLAY "MAIN: MISSING PROG RESP=" WS-RESP
           EXEC CICS RETURN END-EXEC.
        """
        with open(os.path.join(temp_repo, "sources", "mainprog.cob"), "w", encoding="utf-8") as fh:
            fh.write(main_cob)

        config = {
            "main_program": "mainprog.cob",
            "file_assignments": {}
        }
        with open(os.path.join(temp_repo, "migration_config.json"), "w", encoding="utf-8") as fh:
            json.dump(config, fh)

        p = NativePipeline(temp_repo, temp_out)
        p.stage_discover()
        p.stage_parse()
        main_src = [s for s in p.program_ir.keys() if "mainprog" in s.lower()][0]
        p.stage_generate(main_src)
        assert p.stage_dependency_gate()
        assert p.stage_build_gate()
        assert p.stage_execute_gate(main_src)
        
        stdout_path = os.path.join(temp_out, "results", "native", "stdout.txt")
        assert os.path.isfile(stdout_path)
        with open(stdout_path, "r", encoding="utf-8") as fh:
            stdout = fh.read()
        # DFHRESP_PGMIDERR is 27
        assert "MAIN: MISSING PROG RESP=0027" in stdout

    finally:
        shutil.rmtree(temp_repo, ignore_errors=True)
        shutil.rmtree(temp_out, ignore_errors=True)
