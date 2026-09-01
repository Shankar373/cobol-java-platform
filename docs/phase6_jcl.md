# Phase 6 — JCL / Batch Orchestration Modernization

## Overview

Phase 6 implements and differentially verifies automated modernization of mainframe JCL batch workflows into native Java orchestration.

The pipeline architecture translates multi-step JCL jobs into clean, native Java workflow classes (`JclJob_<jobname>.java`) and canonical ThreadLocal runtime execution contexts (`JclExecutionContext.java`), maintaining byte-exact equivalence with baseline GnuCOBOL multi-step execution.

```
REAL JCL Job
    ↓
JclParser (Lex, AST, Symbol Substitution, PROC Expansion, COND/IF extraction)
    ↓
JclGenerator (Native Java Workflow Generation)
    ↓
JclExecutionContext (ThreadLocal DD, SYSIN, Step RC, Abend State Isolation)
    ↓
Maven Build & Standalone JVM Execution
    ↓
Differential Comparison Engine vs GnuCOBOL Baseline (Byte-exact Dataset & Execution Trace Matching)
    ↓
NATIVE_JAVA_VERIFIED
```

## Supported Capabilities

| Capability | Scope | Evidence Level | Verification Path |
|---|---|---|---|
| `JOB` / `EXEC` / `DD` | Step routing, parameter binding, dataset resolution | `DIFFERENTIALLY_VERIFIED` | `tests/component/jcl/test_jcl_modernization.py` |
| `SET` / Symbols / PROCs | Symbol resolution, default overrides, fail-closed diagnostics | `DIFFERENTIALLY_VERIFIED` | `tests/component/jcl/test_jcl_symbols_complete.py` |
| `COND` Bypass Semantics | `(code, op, step)`, global `(code, op)`, `EVEN`, `ONLY`, abend bypass | `DIFFERENTIALLY_VERIFIED` | `tests/component/jcl/test_jcl_conditional.py`, `tests/test_parity_fixtures.py::test_parity_jcl_conditional` |
| `IF` / `THEN` / `ELSE` / `ENDIF` | Nested branching, comparison operators (`=`, `!=`, `<`, `>`, `<=`, `>=`), `RC` & `<step>.RC` | `DIFFERENTIALLY_VERIFIED` | `tests/component/jcl/test_jcl_if_branching.py`, `tests/test_jcl_generator_fail_closed.py` |
| Standard Utilities | `IEBGENER`, `IDCAMS`, `SORT` emulation with byte-level parity | `DIFFERENTIALLY_VERIFIED` | `tests/component/jcl/test_jcl_utilities.py` |
| Thread Isolation | Concurrent jobs, `ThreadLocal` storage, no cross-thread state leakage | `DIFFERENTIALLY_VERIFIED` | `tests/component/jcl/test_jcl_concurrency.py` |

## Fail-Closed Diagnostics

- `JCL_UNRESOLVED_SYMBOL`: Raised when a variable symbol (`&VAR`) has no defined value or PROC override.
- `JCL_UNRESOLVED_PROC`: Raised when an `EXEC PROC=...` statement references a procedure that cannot be resolved in the catalog or stream.
- `JCL_UNSUPPORTED_CONDITION`: Raised when an unparseable conditional expression is encountered.
