import os
import shutil
import tempfile
import json
import pytest
from modernize.native_pipeline import NativePipeline

def test_cics_channel_and_containers_link():
    temp_repo = tempfile.mkdtemp()
    temp_out = tempfile.mkdtemp()

    try:
        os.makedirs(os.path.join(temp_repo, "sources"), exist_ok=True)
        os.makedirs(os.path.join(temp_repo, "data"), exist_ok=True)

        # CLIENT PROG: Put container, LINK with channel, Get response container
        client_cob = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. CLIENT.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-REQ   PIC X(30) VALUE "CUSTOMER-ID:1001             ".
       01  WS-RESP  PIC X(30) VALUE "                             ".
       01  WS-RC    PIC 9(4)  VALUE 0.
       PROCEDURE DIVISION.
           DISPLAY "CLIENT: PUTTING REQUEST CONTAINER"
           EXEC CICS PUT CONTAINER('REQ') CHANNEL('CUSTCHAN') FROM(WS-REQ) RESP(WS-RC) END-EXEC
           DISPLAY "CLIENT: LINKING SERVICE CHANNEL=CUSTCHAN"
           EXEC CICS LINK PROGRAM('SERVICE') CHANNEL('CUSTCHAN') RESP(WS-RC) END-EXEC
           DISPLAY "CLIENT: GETTING RESPONSE CONTAINER"
           EXEC CICS GET CONTAINER('RESP') CHANNEL('CUSTCHAN') INTO(WS-RESP) RESP(WS-RC) END-EXEC
           DISPLAY "CLIENT: RECEIVED RESULT=" WS-RESP
           EXEC CICS DELETE CONTAINER('REQ') CHANNEL('CUSTCHAN') END-EXEC
           EXEC CICS RETURN END-EXEC.
        """
        with open(os.path.join(temp_repo, "sources", "client.cob"), "w", encoding="utf-8") as fh:
            fh.write(client_cob)

        # SERVICE PROG: Get container, compute response, Put container
        service_cob = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. SERVICE.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-IN-REQ  PIC X(30) VALUE "                             ".
       01  WS-OUT-RSP PIC X(30) VALUE "                             ".
       01  WS-RC      PIC 9(4)  VALUE 0.
       PROCEDURE DIVISION.
           DISPLAY "SERVICE: RETRIEVING REQ FROM CHANNEL"
           EXEC CICS GET CONTAINER('REQ') CHANNEL('CUSTCHAN') INTO(WS-IN-REQ) RESP(WS-RC) END-EXEC
           DISPLAY "SERVICE: READ REQ=" WS-IN-REQ
           MOVE "STATUS:APPROVED:BALANCE:50000 " TO WS-OUT-RSP
           EXEC CICS PUT CONTAINER('RESP') CHANNEL('CUSTCHAN') FROM(WS-OUT-RSP) RESP(WS-RC) END-EXEC
           EXEC CICS RETURN END-EXEC.
        """
        with open(os.path.join(temp_repo, "sources", "service.cob"), "w", encoding="utf-8") as fh:
            fh.write(service_cob)

        config = {
            "main_program": "client.cob",
            "file_assignments": {}
        }
        with open(os.path.join(temp_repo, "migration_config.json"), "w", encoding="utf-8") as fh:
            json.dump(config, fh)

        p = NativePipeline(temp_repo, temp_out)
        p.stage_discover()
        p.stage_parse()
        main_src = [s for s in p.program_ir.keys() if "client" in s.lower()][0]
        p.stage_generate(main_src)
        assert p.stage_dependency_gate()
        assert p.stage_build_gate()
        assert p.stage_execute_gate(main_src)

        stdout_path = os.path.join(temp_out, "results", "native", "stdout.txt")
        assert os.path.isfile(stdout_path)
        with open(stdout_path, "r", encoding="utf-8") as fh:
            stdout = fh.read()

        assert "CLIENT: PUTTING REQUEST CONTAINER" in stdout
        assert "SERVICE: RETRIEVING REQ FROM CHANNEL" in stdout
        assert "SERVICE: READ REQ=CUSTOMER-ID:1001" in stdout
        assert "CLIENT: RECEIVED RESULT=STATUS:APPROVED:BALANCE:50000" in stdout

    finally:
        shutil.rmtree(temp_repo, ignore_errors=True)
        shutil.rmtree(temp_out, ignore_errors=True)
