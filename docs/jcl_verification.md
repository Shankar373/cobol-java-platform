# Phase 6 Differential Verification & Evidence

## Verification Strategy

Phase 6 verification is 100% evidence-driven with zero mock reliance:
1. **Multi-Step GnuCOBOL Baseline**:
   - Discovered COBOL programs are compiled in Docker (`cobc -x -free`).
   - JCL steps, DD bindings, and inline SYSIN streams are executed sequentially in an isolated temporary clone.
   - Exact return codes, step execution order, bypassed steps, and output datasets are captured.
2. **Native Java Modernization**:
   - Modernized Java source code (`JclJob_<name>.java` and program classes) is generated.
   - Built and type-checked via standalone Maven compile.
   - Executed inside the JVM with isolated ThreadLocal DD and return-code contexts.
3. **Differential Equivalence Gate**:
   - Byte-exact output dataset comparisons.
   - Normalized execution trace comparisons (`stdout.txt`).
   - Negative mutation gates verifying failure sensitivity.

## Verified Test Matrix

| Test Module | Verified Capabilities | Verdict |
|---|---|---|
| `tests/component/jcl/test_jcl_modernization.py` | Multi-step JCL workflow, step return codes, DD routing, E2E differential | `PASS` |
| `tests/component/jcl/test_jcl_symbols_complete.py` | SET symbols, PROC resolution, overrides, fail-closed diagnostics | `PASS` |
| `tests/component/jcl/test_jcl_conditional.py` | COND bypass logic (EQ, GT, EVEN, ONLY), abend tracking | `PASS` |
| `tests/component/jcl/test_jcl_if_branching.py` | IF/THEN/ELSE conditional branching, relational operators | `PASS` |
| `tests/component/jcl/test_jcl_utilities.py` | IEBGENER, IDCAMS, SORT utility emulation | `PASS` |
| `tests/component/jcl/test_jcl_concurrency.py` | Multi-threaded ThreadLocal execution context isolation (8 concurrent threads) | `PASS` |
| `tests/test_parity_fixtures.py::test_parity_jcl_conditional` | Real differential parity gate for JCL COND routing | `PASS` |
