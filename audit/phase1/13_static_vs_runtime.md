# Phase 1: Static Audit vs Real Execution

We compared the static code design against actual runtime execution findings:

## 1. Findings Table
- **Static Assumption**: GnuCOBOL baseline will always run if compilation passes.
- **Execution Reality**: Stale docker container locks and WSL backend socket failures block execution and cause silent hangs.
- **Static Assumption**: Transpiled Java code runs cleanly.
- **Execution Reality**: Subprogram caller parameter size mismatches cause immediate `ArrayIndexOutOfBoundsException` crashes at runtime.
