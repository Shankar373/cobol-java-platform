# Phase 2: Revised Implementation Scope

We define the updated plan scopes:

## 1. Phase 2 Scope:
- **Equivalence Hardening**: Implement generic checks in `stage_compare()` to capture empty output errors, mismatching files, and exit status differences.
- **Genericity Refactor**: Decouple nightly batch names from hardcoded claims files.
- **Call-graph Tracking**: Build static mapping output files tracking resolved/unresolved dependencies.

## 2. Phase 3 Scope (Deferred):
- **Native Java Translation**: Transform AST blocks into native Java structures without emulated wrappers.
- **Spring Batch Integration**: Scaffold Maven project layouts for native Java runs.
