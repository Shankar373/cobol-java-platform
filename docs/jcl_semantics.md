# JCL Semantics and Translation Architecture

## 1. COND Bypass Semantics

A common pitfall in JCL migration is treating `COND=(code, op, step)` as an "execute if" condition. In z/OS JCL:
- **`COND` is a bypass condition**: If the comparison `code op step.RC` evaluates to **true**, the step is **bypassed (skipped)**. If it evaluates to false, the step executes.
- **Global `COND=(code, op)`**: If `code op preceding_step.RC` evaluates to true for *any* preceding step in the job, the step is bypassed.
- **`COND=EVEN`**: The step executes even if a preceding step abended or returned a severe error code ($\ge 8$).
- **`COND=ONLY`**: The step executes *only* if a preceding step abended.

### Java Implementation
`JclExecutionContext` maintains the execution history:
```java
public static boolean compareRc(int code, String op, int rc) {
    switch (op.toUpperCase()) {
        case "EQ": case "==": case "=": return code == rc;
        case "NE": case "!=": case "<>": return code != rc;
        case "GT": case ">": return code > rc;
        case "LT": case "<": return code < rc;
        case "GE": case ">=": return code >= rc;
        case "LE": case "<=": return code <= rc;
        default: return false;
    }
}
```

Step methods evaluate bypass conditions prior to invocation:
```java
private static boolean shouldBypassStep_STEP2() {
    boolean abended = JclExecutionContext.hasJobAbended();
    if (!abended && false) return true;
    if (JclExecutionContext.compareRc(4, "EQ", JclExecutionContext.getStepReturnCode("STEP1"))) return true;
    return false;
}
```

## 2. IF / THEN / ELSE / ENDIF Flow Control

JCL `IF/THEN/ELSE` blocks evaluate conditional expressions directly:
- `(STEP1.RC EQ 0)` $\to$ `JclExecutionContext.getStepReturnCode("STEP1") == 0`
- `(RC > 4)` $\to$ `JclExecutionContext.getLatestReturnCode() > 4`
- `(STEP1.RUN)` $\to$ `JclExecutionContext.getStepReturnCode("STEP1") != 0`

Unrecognized or malformed IF condition expressions fail fast with `JCL_UNSUPPORTED_CONDITION` rather than defaulting to execution.

## 3. Dataset (DD) and SYSIN Isolation

`JclExecutionContext` uses `ThreadLocal` mappings for DD file bindings and inline `SYSIN` streams, ensuring concurrent jobs running on multiple worker threads never experience cross-job data pollution or file descriptor collisions.

```java
private static final ThreadLocal<Map<String, String>> ddAssignments = ThreadLocal.withInitial(HashMap::new);
private static final ThreadLocal<Map<String, String>> sysinData = ThreadLocal.withInitial(HashMap::new);
private static final ThreadLocal<Map<String, Integer>> stepReturnCodes = ThreadLocal.withInitial(HashMap::new);
private static final ThreadLocal<Boolean> jobAbended = ThreadLocal.withInitial(() -> false);
```
