import concurrent.futures
import subprocess
import tempfile
import os
import shutil
import pytest

def test_jcl_execution_context_thread_isolation():
    """Verify ThreadLocal isolation in JclExecutionContext across concurrent threads."""
    test_java_src = """
package com.systema.modernized;

import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;

public class ConcurrencyTest {
    public static void main(String[] args) throws Exception {
        int numThreads = 8;
        ExecutorService executor = Executors.newFixedThreadPool(numThreads);
        CountDownLatch startLatch = new CountDownLatch(1);
        CountDownLatch doneLatch = new CountDownLatch(numThreads);
        AtomicInteger failures = new AtomicInteger(0);

        for (int i = 0; i < numThreads; i++) {
            final int threadId = i;
            executor.submit(() -> {
                try {
                    startLatch.await();
                    // Set thread-local DDs and return codes
                    String ddValue = "DSN.THREAD." + threadId;
                    String sysinValue = "SYSIN_THREAD_" + threadId;
                    JclExecutionContext.setDdAssignment("INPUTDD", ddValue);
                    JclExecutionContext.setSysinData("SYSIN", sysinValue);
                    JclExecutionContext.recordStepReturnCode("STEP1", threadId * 4);

                    // Sleep slightly to interleave execution
                    Thread.sleep(20 + (threadId % 3) * 10);

                    // Validate thread-local values remain isolated
                    String actualDd = JclExecutionContext.getDdAssignment("INPUTDD");
                    String actualSysin = JclExecutionContext.getSysinData("SYSIN");
                    int actualRc = JclExecutionContext.getStepReturnCode("STEP1");

                    if (!ddValue.equals(actualDd)) {
                        System.err.printf("Thread %d DD mismatch: expected %s, got %s%n", threadId, ddValue, actualDd);
                        failures.incrementAndGet();
                    }
                    if (!sysinValue.equals(actualSysin)) {
                        System.err.printf("Thread %d SYSIN mismatch: expected %s, got %s%n", threadId, sysinValue, actualSysin);
                        failures.incrementAndGet();
                    }
                    if (actualRc != threadId * 4) {
                        System.err.printf("Thread %d RC mismatch: expected %d, got %d%n", threadId, threadId * 4, actualRc);
                        failures.incrementAndGet();
                    }
                } catch (Exception e) {
                    e.printStackTrace();
                    failures.incrementAndGet();
                } finally {
                    JclExecutionContext.clear();
                    doneLatch.countDown();
                }
            });
        }

        startLatch.countDown();
        doneLatch.await(10, TimeUnit.SECONDS);
        executor.shutdown();

        if (failures.get() > 0) {
            System.err.println("Concurrency test failed with " + failures.get() + " errors.");
            System.exit(1);
        } else {
            System.out.println("Concurrency test PASSED: 0 cross-thread contamination errors.");
            System.exit(0);
        }
    }
}
"""
    temp_dir = tempfile.mkdtemp(prefix="jcl_concurr_")
    try:
        src_dir = os.path.join(temp_dir, "com", "systema", "modernized")
        os.makedirs(src_dir, exist_ok=True)
        
        # Copy canonical JclExecutionContext.java
        canonical_ctx = os.path.abspath("modernize/java_helpers/src/main/java/com/systema/modernized/JclExecutionContext.java")
        shutil.copy2(canonical_ctx, os.path.join(src_dir, "JclExecutionContext.java"))
        
        # Write test harness
        with open(os.path.join(src_dir, "ConcurrencyTest.java"), "w", encoding="utf-8") as fh:
            fh.write(test_java_src)
            
        # Compile
        javac_res = subprocess.run(
            ["javac", "-d", temp_dir, os.path.join(src_dir, "JclExecutionContext.java"), os.path.join(src_dir, "ConcurrencyTest.java")],
            capture_output=True, text=True, cwd=temp_dir
        )
        assert javac_res.returncode == 0, f"Compilation failed: {javac_res.stderr}"
        
        # Execute
        java_res = subprocess.run(
            ["java", "-cp", temp_dir, "com.systema.modernized.ConcurrencyTest"],
            capture_output=True, text=True, cwd=temp_dir, timeout=15
        )
        assert java_res.returncode == 0, f"Concurrent execution failed: {java_res.stderr}\n{java_res.stdout}"
        assert "Concurrency test PASSED" in java_res.stdout
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
