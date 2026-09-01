import os
import shutil
import tempfile
import json
import subprocess
import pytest
from modernize.native_pipeline import NativePipeline

def test_cics_multithreaded_transaction_isolation():
    temp_repo = tempfile.mkdtemp()
    temp_out = tempfile.mkdtemp()

    try:
        os.makedirs(os.path.join(temp_repo, "sources"), exist_ok=True)
        os.makedirs(os.path.join(temp_repo, "data"), exist_ok=True)

        # Worker program that processes a thread-specific transaction
        worker_cob = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. WORKERPG.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-IN-CONT   PIC X(30) VALUE "                             ".
       01  WS-OUT-CONT  PIC X(30) VALUE "                             ".
       01  WS-RESP      PIC 9(4)  VALUE 0.
       PROCEDURE DIVISION.
           EXEC CICS GET CONTAINER('REQ') CHANNEL('WORKCHAN') INTO(WS-IN-CONT) RESP(WS-RESP) END-EXEC
           MOVE WS-IN-CONT TO WS-OUT-CONT
           EXEC CICS PUT CONTAINER('RESP') CHANNEL('WORKCHAN') FROM(WS-OUT-CONT) RESP(WS-RESP) END-EXEC
           EXEC CICS RETURN END-EXEC.
        """
        with open(os.path.join(temp_repo, "sources", "workerpg.cob"), "w", encoding="utf-8") as fh:
            fh.write(worker_cob)

        config = {
            "main_program": "workerpg.cob",
            "file_assignments": {}
        }
        with open(os.path.join(temp_repo, "migration_config.json"), "w", encoding="utf-8") as fh:
            json.dump(config, fh)

        p = NativePipeline(temp_repo, temp_out)
        p.stage_discover()
        p.stage_parse()
        main_src = [s for s in p.program_ir.keys() if "workerpg" in s.lower()][0]
        p.stage_generate(main_src)
        assert p.stage_dependency_gate()
        assert p.stage_build_gate()

        # Now write and compile a concurrent Java harness with 8 concurrent threads
        harness_src = """package com.systema.modernized.native_gen;

import com.systema.modernized.CicsTransactionContext;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.ArrayList;
import java.util.List;

public class ConcurrencyHarness {
    public static void main(String[] args) throws Exception {
        int numThreads = 8;
        ExecutorService executor = Executors.newFixedThreadPool(numThreads);
        List<Future<Boolean>> futures = new ArrayList<>();

        for (int i = 0; i < numThreads; i++) {
            final int threadId = i;
            futures.add(executor.submit(() -> {
                try {
                    CicsTransactionContext.clear();
                    String reqData = String.format("THREAD-%02d-PAYLOAD              ", threadId);
                    CicsTransactionContext.putStringContainer("WORKCHAN", "REQ", reqData);
                    CicsTransactionContext.setEibtrnid("TRN" + threadId);

                    Workerpg worker = new Workerpg();
                    worker.execute();

                    String respData = CicsTransactionContext.getStringContainer("WORKCHAN", "RESP");
                    String currentTrn = CicsTransactionContext.getEibtrnid();

                    if (!reqData.trim().equals(respData != null ? respData.trim() : "")) {
                        System.err.println("Mismatch in thread " + threadId + ": expected " + reqData + " but got " + respData);
                        return false;
                    }
                    if (!("TRN" + threadId).equals(currentTrn)) {
                        System.err.println("TrnId mismatch in thread " + threadId + ": expected TRN" + threadId + " but got " + currentTrn);
                        return false;
                    }

                    CicsTransactionContext.clear();
                    return true;
                } catch (Exception e) {
                    e.printStackTrace();
                    return false;
                }
            }));
        }

        executor.shutdown();
        boolean allPassed = true;
        for (int i = 0; i < numThreads; i++) {
            Boolean res = futures.get(i).get();
            if (res == null || !res) {
                allPassed = false;
            }
        }

        if (allPassed) {
            System.out.println("CONCURRENCY_TEST: ALL 8 THREADS ISOLATED SUCCESSFULLY");
        } else {
            System.exit(1);
        }
    }
}
"""
        harness_path = os.path.join(p.src_dir, "ConcurrencyHarness.java")
        with open(harness_path, "w", encoding="utf-8") as fh:
            fh.write(harness_src)

        # Rebuild with harness
        assert p.stage_build_gate()

        # Run ConcurrencyHarness
        cp_file = os.path.join(p.generated_dir, "cp.txt")
        classpath = "target/classes" + os.pathsep + "."
        if os.path.exists(cp_file):
            with open(cp_file, "r", encoding="utf-8") as fh:
                deps = fh.read().strip()
                if deps:
                    classpath += os.pathsep + deps

        res = subprocess.run([
            "java", "-cp", classpath, "com.systema.modernized.native_gen.ConcurrencyHarness"
        ], cwd=p.generated_dir, capture_output=True, text=True, timeout=30)

        assert res.returncode == 0, f"Concurrency test failed: {res.stderr}\n{res.stdout}"
        assert "CONCURRENCY_TEST: ALL 8 THREADS ISOLATED SUCCESSFULLY" in res.stdout

    finally:
        shutil.rmtree(temp_repo, ignore_errors=True)
        shutil.rmtree(temp_out, ignore_errors=True)
