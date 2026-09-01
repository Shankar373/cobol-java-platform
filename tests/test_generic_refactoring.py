import sys
import os
import shutil
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cobol_migrate import Pipeline

def test_generic_refactoring_unseen_repo():
    from cobol_migrate import docker_available
    if not docker_available():
        pytest.skip("Docker is not available, skipping unseen repo refactoring test")
        
    temp_repo = tempfile.mkdtemp()
    temp_out = tempfile.mkdtemp()
    
    try:
        # 1. Scaffold completely unseen repo structure
        os.makedirs(os.path.join(temp_repo, "sources"), exist_ok=True)
        os.makedirs(os.path.join(temp_repo, "data", "in"), exist_ok=True)
        
        # Write input data
        # FLIGHT-ID: FL101 (5 bytes)
        # PASSENGERS: 120 (3 bytes)
        # PRICE: 0150 (4 bytes)
        input_data = "FL1011200150\nFL2020800300\n"
        with open(os.path.join(temp_repo, "data", "in", "flights.dat"), "w", encoding="utf-8") as f:
            f.write(input_data)
            
        # Write COBOL program
        cobol_code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. FLIGHTPROC.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT FLIGHT-FILE ASSIGN TO "data/in/flights.dat"
               ORGANIZATION IS LINE SEQUENTIAL.
           SELECT REPORT-FILE ASSIGN TO "data/out/report.dat"
               ORGANIZATION IS LINE SEQUENTIAL.
       DATA DIVISION.
       FILE SECTION.
       FD  FLIGHT-FILE.
       01  FLIGHT-REC.
           05  FLIGHT-ID       PIC X(5).
           05  PASSENGERS      PIC 9(3).
           05  PRICE           PIC 9(4).
       FD  REPORT-FILE.
       01  REPORT-REC.
           05  REP-ID          PIC X(5).
           05  REP-COUNT       PIC 9(3).
           05  REP-REVENUE     PIC 9(7).
       WORKING-STORAGE SECTION.
       01  WS-EOF             PIC X VALUE 'N'.
       01  WS-CALC-REV        PIC 9(7) VALUE 0.
       01  WS-TEMP-PASS       PIC 9(3) VALUE 0.
       PROCEDURE DIVISION.
       MAIN-PARA.
           OPEN INPUT FLIGHT-FILE
                OUTPUT REPORT-FILE.
           PERFORM READ-AND-PROCESS-PARA THRU END-PROCESS-PARA
               UNTIL WS-EOF = 'Y'.
           CLOSE FLIGHT-FILE REPORT-FILE.
           STOP RUN.
       READ-AND-PROCESS-PARA.
           READ FLIGHT-FILE
               AT END
                   MOVE 'Y' TO WS-EOF
               NOT AT END
                   PERFORM PROCESS-REC-PARA
           .
       PROCESS-REC-PARA.
           MOVE FLIGHT-ID TO REP-ID
           MOVE PASSENGERS TO WS-TEMP-PASS
           MULTIPLY PASSENGERS BY PRICE GIVING WS-CALC-REV
           MOVE WS-TEMP-PASS TO REP-COUNT
           MOVE WS-CALC-REV TO REP-REVENUE
           WRITE REPORT-REC.
       END-PROCESS-PARA.
           EXIT.
        """
        with open(os.path.join(temp_repo, "sources", "flight_proc.cob"), "w", encoding="utf-8") as f:
            f.write(cobol_code)
            
        # 2. Run Pipeline
        pipeline = Pipeline(temp_repo, temp_out, skip_legacy=True)
        pipeline.run()
        
        # 3. Verify target Spring project was generated
        mod_dir = os.path.join(temp_out, "modernized")
        assert os.path.isdir(mod_dir)
        
        # 4. Verify pom.xml has exactly zero references to forbidden libraries
        pom_path = os.path.join(mod_dir, "pom.xml")
        assert os.path.isfile(pom_path)
        with open(pom_path, "r", encoding="utf-8") as f:
            pom_content = f.read()
        for forbidden in ["jp.osscons", "libcobj", "opensourcecobol", "CobolResolve"]:
            assert forbidden not in pom_content, f"Forbidden library {forbidden} found in pom.xml!"
            
        # 5. Verify Java source files have exactly zero references to forbidden libraries
        java_base = os.path.join(mod_dir, "src", "main", "java", "com", "systema", "modernized")
        for root, dirs, files in os.walk(java_base):
            for file in files:
                if file.endswith(".java"):
                    with open(os.path.join(root, file), "r", encoding="utf-8") as f:
                        java_content = f.read()
                    for forbidden in ["jp.osscons", "libcobj", "CobolResolve", "opensourcecobol4j", "CobolField"]:
                        assert forbidden not in java_content, f"Forbidden library {forbidden} found in {file}!"

        # 6. Verify Spring Batch configuration tasklet executes the native gen entrypoint
        batch_config = os.path.join(java_base, "batch", "SpringBatchConfig.java")
        assert os.path.isfile(batch_config)
        with open(batch_config, "r") as f:
            batch_content = f.read()
        assert "new com.systema.modernized.native_gen.Flightproc().execute();" in batch_content

        # 7. Check Maven compile status in pipeline refactor state
        refactor_state = pipeline.state["data"].get("refactor", {})
        assert "compiled successfully" in refactor_state.get("compile_status", "").lower()

    except Exception as e:
        log_path = os.path.join(temp_out, "validation-run.log")
        if os.path.isfile(log_path):
            with open(log_path, "r", encoding="utf-8", errors="replace") as lf:
                print("\n=== validation-run.log tail ===")
                print(lf.read()[-3000:])
        raise
    finally:
        shutil.rmtree(temp_repo, ignore_errors=True)
        shutil.rmtree(temp_out, ignore_errors=True)
