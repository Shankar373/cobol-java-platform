import os
import shutil
import tempfile
import subprocess
import pytest
from modernize.native_pipeline import NativePipeline

def test_vsam_persistence_across_jvm_restart():
    """Phase 4H: Verify data persistence across multiple independent JVM process lifecycles.
    
    Lifecycle:
    1. Process 1 (JVM 1): OPEN OUTPUT -> WRITE 3 records -> CLOSE -> JVM terminates.
    2. Process 2 (JVM 2): New JVM process -> OPEN I-O -> READ, REWRITE record 2, DELETE record 1 -> CLOSE -> JVM terminates.
    3. Process 3 (JVM 3): New JVM process -> OPEN INPUT -> START -> READ NEXT all records -> verifies persisted state -> CLOSE.
    """
    temp_dir = tempfile.mkdtemp(prefix="vsam_persistence_")
    
    try:
        data_dir = os.path.join(temp_dir, "data")
        os.makedirs(data_dir, exist_ok=True)
        storage_file = os.path.join(data_dir, "customer_store.dat").replace("\\", "/")
        
        # --- Program 1: Seed Initial Data ---
        cobol_src_1 = f"""       IDENTIFICATION DIVISION.
       PROGRAM-ID. PROG1.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT CUST-FILE ASSIGN TO "{storage_file}"
               ORGANIZATION IS INDEXED
               ACCESS MODE IS DYNAMIC
               RECORD KEY IS CUST-ID
               FILE STATUS IS WS-FS.
       DATA DIVISION.
       FILE SECTION.
       FD  CUST-FILE.
       01  CUST-REC.
           05 CUST-ID   PIC X(4).
           05 CUST-NAME PIC X(10).
           05 CUST-BAL  PIC 9(4).
       WORKING-STORAGE SECTION.
       01  WS-FS        PIC XX.
       PROCEDURE DIVISION.
           OPEN OUTPUT CUST-FILE.
           MOVE "1001" TO CUST-ID.
           MOVE "ALICE     " TO CUST-NAME.
           MOVE 1000 TO CUST-BAL.
           WRITE CUST-REC.
           
           MOVE "1002" TO CUST-ID.
           MOVE "BOB       " TO CUST-NAME.
           MOVE 2000 TO CUST-BAL.
           WRITE CUST-REC.
           
           MOVE "1003" TO CUST-ID.
           MOVE "CHARLIE   " TO CUST-NAME.
           MOVE 3000 TO CUST-BAL.
           WRITE CUST-REC.
           
           CLOSE CUST-FILE.
           DISPLAY "PROG1_DONE: " WS-FS.
           GOBACK.
"""

        # --- Program 2: Modify & Delete in New Process ---
        cobol_src_2 = f"""       IDENTIFICATION DIVISION.
       PROGRAM-ID. PROG2.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT CUST-FILE ASSIGN TO "{storage_file}"
               ORGANIZATION IS INDEXED
               ACCESS MODE IS DYNAMIC
               RECORD KEY IS CUST-ID
               FILE STATUS IS WS-FS.
       DATA DIVISION.
       FILE SECTION.
       FD  CUST-FILE.
       01  CUST-REC.
           05 CUST-ID   PIC X(4).
           05 CUST-NAME PIC X(10).
           05 CUST-BAL  PIC 9(4).
       WORKING-STORAGE SECTION.
       01  WS-FS        PIC XX.
       PROCEDURE DIVISION.
           OPEN I-O CUST-FILE.
           MOVE "1002" TO CUST-ID.
           READ CUST-FILE.
           MOVE "ROBERT    " TO CUST-NAME.
           MOVE 2500 TO CUST-BAL.
           REWRITE CUST-REC.
           
           MOVE "1001" TO CUST-ID.
           DELETE CUST-FILE.
           
           CLOSE CUST-FILE.
           DISPLAY "PROG2_DONE: " WS-FS.
           GOBACK.
"""

        # --- Program 3: Read Final State in New Process ---
        cobol_src_3 = f"""       IDENTIFICATION DIVISION.
       PROGRAM-ID. PROG3.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT CUST-FILE ASSIGN TO "{storage_file}"
               ORGANIZATION IS INDEXED
               ACCESS MODE IS DYNAMIC
               RECORD KEY IS CUST-ID
               FILE STATUS IS WS-FS.
       DATA DIVISION.
       FILE SECTION.
       FD  CUST-FILE.
       01  CUST-REC.
           05 CUST-ID   PIC X(4).
           05 CUST-NAME PIC X(10).
           05 CUST-BAL  PIC 9(4).
       WORKING-STORAGE SECTION.
       01  WS-FS        PIC XX.
       PROCEDURE DIVISION.
           OPEN INPUT CUST-FILE.
           MOVE "1000" TO CUST-ID.
           START CUST-FILE KEY IS >= CUST-ID.
           
           PERFORM UNTIL WS-FS NOT = "00"
               READ CUST-FILE NEXT
               IF WS-FS = "00"
                   DISPLAY "REC: " CUST-ID " | " CUST-NAME " | " CUST-BAL
               END-IF
           END-PERFORM.
           
           CLOSE CUST-FILE.
           DISPLAY "PROG3_DONE".
           GOBACK.
"""

        # Helper to generate and run in separate Java JVM process
        def run_java_proc(prog_name, cobol_src):
            proc_dir = os.path.join(temp_dir, prog_name)
            os.makedirs(os.path.join(proc_dir, "src"), exist_ok=True)
            with open(os.path.join(proc_dir, "src", f"{prog_name}.cob"), "w", encoding="utf-8") as fh:
                fh.write(cobol_src)
                
            out_dir = os.path.join(temp_dir, f"out_{prog_name}")
            pipe = NativePipeline(proc_dir, out_dir)
            pipe.stage_discover()
            pipe.stage_parse()
            src = pipe.stage_select_slice()
            pipe.stage_generate(src)
            assert pipe.stage_dependency_gate()
            assert pipe.stage_build_gate(), f"Build failed for {prog_name}"
            assert pipe.stage_execute_gate(src), f"Execution failed for {prog_name}"
            
            stdout_path = os.path.join(out_dir, "results", "native", "stdout.txt")
            with open(stdout_path, "r", encoding="utf-8") as fh:
                return fh.read()

        # Step 1: Run Process 1 -> Writes 1001 (ALICE), 1002 (BOB), 1003 (CHARLIE)
        out1 = run_java_proc("PROG1", cobol_src_1)
        assert "PROG1_DONE: 00" in out1

        # Step 2: Run Process 2 in fresh JVM -> Deletes 1001, Updates 1002 to ROBERT / 2500
        out2 = run_java_proc("PROG2", cobol_src_2)
        assert "PROG2_DONE: 00" in out2

        # Step 3: Run Process 3 in fresh JVM -> Reads all records
        out3 = run_java_proc("PROG3", cobol_src_3)
        assert "REC: 1002 | ROBERT     | 2500" in out3
        assert "REC: 1003 | CHARLIE    | 3000" in out3
        assert "1001" not in out3
        assert "PROG3_DONE" in out3

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
