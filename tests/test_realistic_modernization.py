import os
import shutil
import tempfile
import pytest
import json
from cobol_migrate import Pipeline

def test_realistic_pipeline_lifecycle():
    # 1. Create temporary directories for repository and output
    repo_dir = tempfile.mkdtemp()
    out_dir = tempfile.mkdtemp()
    
    try:
        # Create folder structure
        os.makedirs(os.path.join(repo_dir, "src"), exist_ok=True)
        os.makedirs(os.path.join(repo_dir, "copybooks"), exist_ok=True)
        os.makedirs(os.path.join(repo_dir, "data", "in"), exist_ok=True)
        os.makedirs(os.path.join(repo_dir, "data", "work"), exist_ok=True)
        os.makedirs(os.path.join(repo_dir, "data", "out"), exist_ok=True)
        
        # 2. Write migration_config.json
        config = {
            "main_program": "REALPROG.cob",
            "entry": "REALPROG",
            "legacy_exclude_sources": ["REALSQL.cob"],
            "file_assignments": {
                "SEQ-IN": "data/in/seqinput.dat",
                "SEQ-OUT": "data/out/seqoutput.dat",
                "IDX-FILE": "data/work/indexedfile.dat"
            }
        }
        with open(os.path.join(repo_dir, "migration_config.json"), "w", encoding="utf-8") as fh:
            json.dump(config, fh, indent=2)
            
        # 3. Write COPYBOOK copybooks/REALREC.cpy (fixed format, starts at Area A)
        copybook_code = """      * Copybook record fields
           05  REC-KEY          PIC 9(4).
           05  REC-NAME         PIC X(20).
           05  REC-NUM-STR      PIC X(5).
           05  REC-AMOUNT       PIC 9(5)V99.
           05  REC-STATUS       PIC X(2).
"""
        with open(os.path.join(repo_dir, "copybooks", "REALREC.cpy"), "w", encoding="utf-8") as fh:
            fh.write(copybook_code)
            
        # 4. Write JCL src/REALJOB.jcl (fixed format layout)
        jcl_code = """//REALJOB  JOB (ACCT),'REALISTIC',CLASS=A
//STEP1    EXEC PGM=REALPROG
//SEQIN    DD DSN='data/in/seqinput.dat',DISP=SHR
//SEQOUT   DD DSN='data/out/seqoutput.dat',DISP=(NEW,CATLG)
//IDXFILE  DD DSN='data/work/indexedfile.dat',DISP=SHR
"""
        with open(os.path.join(repo_dir, "src", "REALJOB.jcl"), "w", encoding="utf-8") as fh:
            fh.write(jcl_code)
            
        # 5. Write Main COBOL src/REALPROG.cob (traditional fixed format, 7 spaces indent)
        cobol_code = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. REALPROG.
       
      * REALISTIC01 TEST PROGRAM
      * EXERCISES ALL COBOL CONSTRUCTS
      * END-TO-END PIPELINE CERTIFICATION
      * FIXED FORMAT VERIFICATION
      * COBOL TO JAVA MODERNIZATION
      
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT SEQ-IN ASSIGN TO "data/in/seqinput.dat"
               ORGANIZATION IS LINE SEQUENTIAL.
           SELECT SEQ-OUT ASSIGN TO "data/out/seqoutput.dat"
               ORGANIZATION IS LINE SEQUENTIAL.
           SELECT IDX-FILE ASSIGN TO "data/work/indexedfile.dat"
               ORGANIZATION IS INDEXED
               ACCESS MODE IS DYNAMIC
               RECORD KEY IS REC-KEY.
               
       DATA DIVISION.
       FILE SECTION.
       FD  SEQ-IN.
       01  SEQ-REC-IN          PIC X(38).
       
       FD  SEQ-OUT.
       01  SEQ-REC-OUT.
           05  OUT-KEY          PIC 9(4).
           05  OUT-NAME         PIC X(20).
           05  OUT-NUM-STR      PIC X(5).
           05  OUT-AMOUNT       PIC 9(5)V99.
           05  OUT-STATUS       PIC X(2).
       
       FD  IDX-FILE.
       01  IDX-REC.
           COPY "REALREC.cpy".
           
       WORKING-STORAGE SECTION.
       01  WS-EOF               PIC X VALUE 'N'.
       01  WS-NUM-VAL           PIC 9(5).
       01  WS-MOD-VAL           PIC 9(4).
       01  WS-AMT               PIC 9(5)V99.
       01  WS-STAT1             PIC X.
       01  WS-STAT2             PIC X.
       
       01  WS-ARRAY-DATA.
           05  WS-ELEMENTS OCCURS 5 TIMES PIC 9(3).
       01  WS-REDEFINED-DATA REDEFINES WS-ARRAY-DATA.
           05  WS-RAW-CHARS    PIC X(15).
           
       01  WS-IN-REC.
           05  IN-KEY           PIC 9(4).
           05  IN-NAME          PIC X(20).
           05  IN-NUM-STR       PIC X(5).
           05  IN-AMOUNT        PIC 9(5)V99.
           05  IN-STATUS        PIC X(2).
           
       PROCEDURE DIVISION.
       MAIN-PARA.
           OPEN INPUT SEQ-IN.
           OPEN OUTPUT SEQ-OUT.
           OPEN OUTPUT IDX-FILE.
           
      * Redefines and occurs simulation
           MOVE 100 TO WS-ELEMENTS(1)
           MOVE 200 TO WS-ELEMENTS(2)
           
           PERFORM UNTIL WS-EOF = 'Y'
               READ SEQ-IN INTO WS-IN-REC
                   AT END MOVE 'Y' TO WS-EOF
                   NOT AT END PERFORM PROCESS-REC
               END-READ
           END-PERFORM.
           
           CLOSE SEQ-IN.
           CLOSE SEQ-OUT.
           CLOSE IDX-FILE.
           GOBACK.

       PROCESS-REC.
      * COMPUTE / ADD / SUBTRACT
           COMPUTE WS-AMT = IN-AMOUNT + 100.50
           ADD 10.00 TO WS-AMT
           SUBTRACT 5.00 FROM WS-AMT
           
      * MOVE, STRING, UNSTRING
           MOVE IN-KEY TO REC-KEY
           MOVE IN-NAME TO REC-NAME
           STRING "PREFIX-" IN-NAME DELIMITED BY SIZE 
                  INTO REC-NAME
           UNSTRING IN-STATUS DELIMITED BY SPACES
                    INTO WS-STAT1 WS-STAT2
                    
      * NUMVAL / MOD
           MOVE FUNCTION NUMVAL ( IN-NUM-STR ) TO WS-NUM-VAL
           MOVE FUNCTION MOD ( IN-KEY , 2 ) TO WS-MOD-VAL
           
      * IF / ELSE, EVALUATE
           IF WS-MOD-VAL = 0
               MOVE "EV" TO REC-STATUS
           ELSE
               MOVE "OD" TO REC-STATUS
           END-IF
           
           EVALUATE REC-STATUS
               WHEN "EV"
                   PERFORM EVEN-PARA
               WHEN "OD"
                   PERFORM ODD-PARA
           END-EVALUATE
           
           MOVE IN-NUM-STR TO REC-NUM-STR
           MOVE WS-AMT TO REC-AMOUNT
           WRITE IDX-REC
           
           MOVE REC-KEY TO OUT-KEY
           MOVE REC-NAME TO OUT-NAME
           MOVE REC-NUM-STR TO OUT-NUM-STR
           MOVE REC-AMOUNT TO OUT-AMOUNT
           MOVE REC-STATUS TO OUT-STATUS
           WRITE SEQ-REC-OUT.
           
       EVEN-PARA.
           DISPLAY "EVEN KEY: " REC-KEY.
           
       ODD-PARA.
           DISPLAY "ODD KEY: " REC-KEY.
"""
        # Replace tabs with spaces
        cobol_code = cobol_code.replace("\t", "    ")
        
        with open(os.path.join(repo_dir, "src", "REALPROG.cob"), "w", encoding="utf-8") as fh:
            fh.write(cobol_code)

        # 6. Write SQL COBOL src/REALSQL.cob (traditional fixed format, 7 spaces indent)
        sql_code = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. REALSQL.
       
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  SQLCA-VARIABLES.
           05  SQLCODE          PIC S9(9) COMP.
           05  SQLSTATE         PIC X(5).
       01  WS-CUST-ID           PIC S9(9) COMP VALUE 101.
       01  WS-CUST-NAME         PIC X(20) VALUE SPACES.
       
       PROCEDURE DIVISION.
      * SQL database select step
           EXEC SQL
               SELECT CUST_NAME INTO :WS-CUST-NAME
               FROM CUSTOMER WHERE CUST_ID = :WS-CUST-ID
           END-EXEC.
           GOBACK.
"""
        # Replace tabs with spaces
        sql_code = sql_code.replace("\t", "    ")
        
        with open(os.path.join(repo_dir, "src", "REALSQL.cob"), "w", encoding="utf-8") as fh:
            fh.write(sql_code)
            
        # 7. Write input data file and database seed
        input_data = "1001FIRST CUSTOMER      001200100000AB\n1002SECOND CUSTOMER     003400200000CD\n"
        with open(os.path.join(repo_dir, "data", "in", "seqinput.dat"), "w", encoding="utf-8") as fh:
            fh.write(input_data)
            
        with open(os.path.join(repo_dir, "data", "customer.sql"), "w", encoding="utf-8") as fh:
            fh.write("INSERT INTO customer (cust_id, cust_name) VALUES (101, 'TEST CUSTOMER');\n")
            
        # 8. Instantiate and execute the Pipeline orchestrator.
        # HONEST MODE: no --skip-legacy and NO hand-seeded baseline. Earlier
        # versions of this test seeded fabricated "golden" outputs which did
        # NOT match the real program behavior — the hardened equivalence engine
        # correctly rejects them. A realistic lifecycle must produce its own
        # GnuCOBOL baseline and compare against it for real.
        from cobol_migrate import docker_available
        if not docker_available():
            pytest.skip("ENVIRONMENT_BLOCKED: Docker required to build the "
                        "GnuCOBOL baseline and transpile via cobj")
        p = Pipeline(repo_dir, out_dir, cfg=config)
        p.pull = False

        p.run()

        # Verify the final certification verdict
        verdict = p._compute_verdict()
        assert verdict in ("VERIFIED", "VERIFIED_WITH_LIMITATIONS",
                           "NATIVE_JAVA_VERIFIED", "NATIVE_SPRING_UNIFIED"), (
            f"unexpected verdict {verdict}")

        # Verify stages are all executed successfully
        for stage in p.state["stages"].values():
            assert stage["status"] in ("done", "skipped")
            
    finally:
        shutil.rmtree(repo_dir, ignore_errors=True)
        shutil.rmtree(out_dir, ignore_errors=True)
