# Phase 1: Bug & Issue Classification

We classified the following issues discovered during validation:

## Classified Issues List:
- **Issue 1**: WSL engine 500 API errors block command line executions. **Severity: P0** (Blocks entire project). **Type: ENVIRONMENT BUG**.
- **Issue 2**: Subprogram call parameter size mismatches cause target crashes. **Severity: P1** (Blocks first goal). **Type: REPOSITORY BUG**.
- **Issue 3**: cobj transpiler does not support Level 78 constants. **Severity: P1** (Blocks first goal). **Type: ARCHITECTURAL GAP**.
- **Issue 4**: Command injections in subprocess shell wrapper calls. **Severity: P2** (Works but has security risk). **Type: SECURITY ISSUE**.
