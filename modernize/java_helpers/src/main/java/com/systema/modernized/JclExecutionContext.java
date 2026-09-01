package com.systema.modernized;

import java.util.HashMap;
import java.util.Map;

/**
 * JCL Execution Context providing isolated ThreadLocal state for:
 * - DD assignments (logical ddname -> physical file path)
 * - SYSIN data (logical ddname -> inline data string or temp path)
 * - Step return codes (stepname / procstepname -> integer return code)
 * - Job abend flag (for COND=EVEN / COND=ONLY)
 */
public class JclExecutionContext {
    private static final ThreadLocal<Map<String, String>> ddAssignments = ThreadLocal.withInitial(HashMap::new);
    private static final ThreadLocal<Map<String, String>> sysinData = ThreadLocal.withInitial(HashMap::new);
    private static final ThreadLocal<Map<String, Integer>> stepReturnCodes = ThreadLocal.withInitial(HashMap::new);
    private static final ThreadLocal<Boolean> jobAbended = ThreadLocal.withInitial(() -> false);

    public static void setDdAssignment(String ddName, String physicalPath) {
        if (ddName != null && physicalPath != null) {
            ddAssignments.get().put(ddName.toUpperCase(), physicalPath);
        }
    }

    public static String getDdAssignment(String ddName) {
        if (ddName == null) return null;
        String val = ddAssignments.get().get(ddName.toUpperCase());
        if (val != null) {
            String cleanName = val.startsWith("&&") ? val.substring(2) : val;
            java.io.File f = new java.io.File(cleanName);
            if (!f.isAbsolute()) {
                java.io.File resultsDir = new java.io.File("../results/native");
                if (resultsDir.exists() && resultsDir.isDirectory()) {
                    try { return new java.io.File(resultsDir, cleanName).getCanonicalPath(); } catch (Exception e) { return new java.io.File(resultsDir, cleanName).getAbsolutePath(); }
                }
                java.io.File resultsDir2 = new java.io.File("../../results/native");
                if (resultsDir2.exists() && resultsDir2.isDirectory()) {
                    try { return new java.io.File(resultsDir2, cleanName).getCanonicalPath(); } catch (Exception e) { return new java.io.File(resultsDir2, cleanName).getAbsolutePath(); }
                }
            }
            if (val.startsWith("&&")) {
                return java.nio.file.Paths.get(cleanName).toAbsolutePath().toString();
            }
        }
        return val;
    }

    public static void setSysinData(String ddName, String data) {
        if (ddName != null) {
            sysinData.get().put(ddName.toUpperCase(), data != null ? data : "");
        }
    }

    public static String getSysinData(String ddName) {
        if (ddName == null) return null;
        return sysinData.get().get(ddName.toUpperCase());
    }

    public static void setStepReturnCode(String stepName, int rc) {
        if (stepName != null) {
            stepReturnCodes.get().put(stepName.toUpperCase(), rc);
        }
    }

    public static void recordStepReturnCode(String stepName, int rc) {
        setStepReturnCode(stepName, rc);
    }

    public static Integer getStepReturnCode(String stepName) {
        if (stepName == null) return 0;
        return stepReturnCodes.get().getOrDefault(stepName.toUpperCase(), 0);
    }

    public static int getLatestReturnCode() {
        Map<String, Integer> map = stepReturnCodes.get();
        if (map.isEmpty()) return 0;
        int last = 0;
        for (int v : map.values()) last = v;
        return last;
    }

    public static void setJobAbended(boolean abended) {
        jobAbended.set(abended);
    }

    public static boolean hasJobAbended() {
        return jobAbended.get();
    }

    /**
     * Evaluates global COND=(code, operator) against all preceding steps.
     * In JCL, if ANY preceding step satisfies 'code op step.RC', the step is bypassed.
     */
    public static boolean checkAnyStepCond(int code, String op) {
        for (int rc : stepReturnCodes.get().values()) {
            if (compareRc(code, op, rc)) {
                return true;
            }
        }
        return false;
    }

    /**
     * Standard JCL COND evaluation:
     * COND=(code, operator, stepname) tests: 'code operator actual_rc'.
     * If the condition evaluates to true, the step is bypassed.
     */
    public static boolean compareRc(int code, String op, int rc) {
        if (op == null) return false;
        switch (op.toUpperCase().trim()) {
            case "EQ":
            case "=":
            case "==":
                return code == rc;
            case "NE":
            case "!=":
            case "<>":
                return code != rc;
            case "GT":
            case ">":
                return code > rc;
            case "LT":
            case "<":
                return code < rc;
            case "GE":
            case ">=":
                return code >= rc;
            case "LE":
            case "<=":
                return code <= rc;
            default:
                return false;
        }
    }

    /**
     * Reset all ThreadLocal execution context state for the current thread.
     */
    public static void clear() {
        ddAssignments.get().clear();
        sysinData.get().clear();
        stepReturnCodes.get().clear();
        jobAbended.set(false);
    }
}
