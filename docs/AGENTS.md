# AGENTS.md

## Project Overview

This repository is a **general-purpose COBOL/JCL to Native Java
modernization platform**.

The primary objective is to transform legacy mainframe applications into
maintainable, executable **native Java / Spring Boot / Spring Batch**
applications while preserving business behavior and providing
evidence-based validation.

The platform must remain **repository-agnostic**. Do not optimize the
implementation around a single benchmark repository such as ClaimsCore,
Banking, INVMGR, or any other fixture.

------------------------------------------------------------------------

## 1. Core Modernization Architecture

The expected modernization flow is:

``` text
Legacy COBOL / JCL / COPYBOOK / SQL / CICS / VSAM
                    |
                    v
          Ingest / Discovery
                    |
                    v
        Lexer + COBOL/JCL Parsers
                    |
                    v
       Flow & Dependency Analysis
                    |
                    v
              Semantic IR
                    |
                    v
       Native Java / Spring Generator
                    |
                    v
       Compile + Execute Target
                    |
                    v
 Legacy Baseline vs Java Differential
             Equivalence Engine
                    |
                    v
        Validation / Hardening Gates
                    |
                    v
       Report + Package + UI Results
```

The exact pipeline implementation may contain additional stages, but the
architectural principle must remain the same.

------------------------------------------------------------------------

## 2. Primary Engineering Principles

### Repository Agnosticism

-   Never hardcode business entities, table names, program names,
    copybook names, output values, or fixture-specific assumptions into
    production modernization logic.
-   Derive models, variables, dependencies, schemas, and generated
    structures from the input repository.
-   Tests may use benchmark-specific fixtures, but production code must
    not depend on them.

### Native Java / Track-B

The primary target is native Java.

Generated applications should:

-   use standard Java types and APIs;
-   use Spring Boot/Spring Batch where appropriate;
-   use JPA/JDBC/database abstractions where appropriate;
-   avoid proprietary legacy runtime dependencies;
-   avoid generating wrappers that merely execute the original COBOL
    runtime;
-   remain independently compilable and executable.

Do not introduce `libcobj.jar`, `jp.osscons`, or OpenSourceCOBOL4J
runtime dependencies into generated Track-B applications.

### Business Equivalence First

Successful parsing or compilation is **not** equivalent to successful
modernization.

A modernization result should only be considered verified when
appropriate evidence exists for:

-   legacy baseline execution;
-   target Java execution;
-   exit codes;
-   stdout/stderr where applicable;
-   generated/output files;
-   database state where applicable;
-   relevant records/data;
-   important side effects;
-   business-level comparison.

Never convert an unavailable, skipped, partial, or environment-blocked
verification into `PASS`.

------------------------------------------------------------------------

## 3. Parser and Semantic IR Rules

When extending the parser:

1.  Preserve existing supported COBOL behavior.
2.  Prefer structured AST/Semantic IR representations over string hacks.
3.  Preserve source semantics and ordering where required.
4.  Record unsupported constructs explicitly through diagnostics.
5.  Never silently discard unsupported COBOL statements.
6.  Add regression tests for every new grammar rule.
7.  Test both fixed-format and free-format COBOL.
8.  Test COPYBOOK and nested-program scenarios when relevant.
9.  Consider continuation lines, comments, literals, qualified names,
    reference modification, and nested expressions.
10. Avoid regex-only solutions when the construct requires nesting or
    grammar awareness.

Important areas include:

-   DATA DIVISION
-   PROCEDURE DIVISION
-   PIC clauses
-   REDEFINES
-   OCCURS
-   level-88 conditions
-   COMP/COMP-3
-   pointers/reference modification
-   PERFORM
-   IF/EVALUATE
-   CALL USING/RETURNING/GIVING
-   SORT/MERGE
-   VSAM
-   embedded SQL
-   EXEC CICS
-   Report Writer

------------------------------------------------------------------------

## 4. JCL Rules

JCL modernization must preserve workflow semantics.

Pay particular attention to:

-   JOB / EXEC / DD
-   symbolic parameters
-   `SET`
-   `PROC` / `PEND`
-   nested procedure expansion
-   SYSIN
-   DD overrides
-   dataset dependencies
-   COND
-   IF / THEN / ELSE
-   return-code propagation
-   common utilities such as SORT, IEBGENER, and IDCAMS

Unresolved symbols or procedures must generate explicit diagnostics.

Do not silently substitute arbitrary values for unresolved JCL
parameters.

------------------------------------------------------------------------

## 5. DB2 / SQL Rules

Embedded DB2 SQL must be clearly classified.

Distinguish between:

-   SQL syntax successfully parsed;
-   SQL translated;
-   SQL verified using local/emulated database execution;
-   SQL verified against a real DB2 environment.

H2 or another local database emulator must never be reported as proof of
real DB2 compatibility.

Use parameterized SQL.

Do not introduce SQL injection through string concatenation.

Preserve:

-   host variables;
-   SQLCODE/SQLSTATE behavior where implemented;
-   transactions;
-   predicates;
-   joins;
-   aliases;
-   subqueries;
-   GROUP BY/HAVING/ORDER BY;
-   NULL behavior.

------------------------------------------------------------------------

## 6. CICS / BMS Rules

Clearly distinguish semantic emulation from real CICS/3270 execution.

Supported/emulated functionality must be reported honestly.

Do not claim real mainframe terminal equivalence unless it has actually
been tested against the relevant environment.

For BMS:

-   preserve field names;
-   positions;
-   lengths;
-   attributes;
-   input/output semantics;
-   SEND/RECEIVE MAP behavior where supported.

Unsupported terminal behavior must generate diagnostics rather than
false success.

------------------------------------------------------------------------

## 7. VSAM / File I/O Rules

Preserve the semantic behavior of:

-   OPEN
-   CLOSE
-   READ
-   WRITE
-   REWRITE
-   DELETE
-   START
-   sequential access
-   indexed access

If SQLite, maps, or other local structures are used as an emulation
layer, report the result as logical/emulated equivalence unless physical
format equivalence is explicitly verified.

------------------------------------------------------------------------

## 8. Code Generation Rules

Generated Java must be:

-   compilable;
-   readable;
-   deterministic;
-   repository-specific based on discovered metadata;
-   free from benchmark-specific hardcoding;
-   free from unnecessary legacy runtime dependencies.

Prefer clear domain models, services, repositories, tasklets, jobs, and
configuration.

Avoid generating:

-   dead code;
-   duplicate classes;
-   duplicate helper methods;
-   placeholder implementations presented as complete functionality;
-   hardcoded sample data in generic production paths.

Generated code should preserve business logic rather than merely
producing code that compiles.

------------------------------------------------------------------------

## 9. Validation Gate Rules

Validation must be fail-closed.

Use explicit states such as:

``` text
PASS
FAILED
UNVERIFIED
PARTIAL
ENVIRONMENT_BLOCKED
SKIPPED
```

Rules:

-   Compilation success does not imply equivalence.
-   Execution success does not imply equivalence.
-   Matching stdout alone does not prove full business equivalence when
    files/database state are part of the application behavior.
-   Missing baseline evidence must not become PASS.
-   Skipped tests must remain skipped.
-   Environment failures must remain environment failures.
-   A test must never be weakened merely to obtain a green result.

When a verification dependency is unavailable, report the exact
dependency and environment reason.

------------------------------------------------------------------------

## 10. Maven and Dependency Verification

Dependency verification must be deterministic.

Never rely on:

``` text
mvn dependency:get
```

without project context and without a pinned plugin version.

Prefer the repository's seed POM or another controlled Maven project.

Requirements:

-   pin Maven plugin versions;
-   declare required dependencies explicitly;
-   resolve dependencies through the seed POM;
-   verify expected artifacts individually in the local Maven
    repository;
-   distinguish missing dependencies from network failures;
-   support offline operation after dependencies have been seeded;
-   verify vendored ProLeap artifacts independently;
-   do not treat successful Maven execution alone as proof that an
    artifact exists.

No hidden network dependency should exist in offline verification.

------------------------------------------------------------------------

## 11. ProLeap Integration Rules

ProLeap is an auxiliary parsing/validation capability, not the
production runtime of generated applications.

If ProLeap is used:

-   keep the adapter boundary isolated;
-   keep version and commit information documented;
-   preserve license information;
-   keep vendored artifacts reproducible;
-   ensure generated applications do not depend on ProLeap;
-   ensure generated applications do not import `io.proleap.*`;
-   preserve offline usability where required.

The custom/native parser remains the primary production path unless a
deliberate architectural decision changes this.

------------------------------------------------------------------------

## 12. Security Rules

Treat all uploaded repositories and source files as untrusted input.

Validate:

-   ZIP extraction paths;
-   artifact paths;
-   COPYBOOK paths;
-   Git URLs/branches;
-   subprocess arguments;
-   uploaded file sizes;
-   user-controlled parameters.

Never use `shell=True` for user-controlled command construction.

Use:

-   argument arrays;
-   path boundary checks;
-   explicit timeouts;
-   upload limits;
-   authentication/authorization where applicable;
-   safe temporary directories.

Do not expose arbitrary filesystem files through UI/API endpoints.

------------------------------------------------------------------------

## 13. Concurrency and Workspace Isolation

Each modernization run should have isolated state.

Avoid shared mutable global state for:

-   logs;
-   event sinks;
-   execution context;
-   generated artifacts;
-   database mappings;
-   return codes.

Use run-specific workspaces and thread-safe/thread-local state where
appropriate.

Concurrent runs must not leak:

-   logs;
-   files;
-   configuration;
-   database state;
-   status;
-   results.

------------------------------------------------------------------------

## 14. UI / Frontend Rules

The UI is part of the product, not merely a test interface.

The dashboard must:

-   clearly show current pipeline stage;
-   distinguish RUNNING from PASS;
-   distinguish FAILED from UNVERIFIED;
-   show environment-blocked conditions;
-   show warnings and diagnostics;
-   avoid stale PASS/VERIFIED values after a failed run;
-   provide useful logs;
-   display meaningful validation evidence;
-   prevent overlapping runs;
-   safely handle artifact access.

Never optimize UI presentation to make a failed migration look
successful.

------------------------------------------------------------------------

## 15. Testing Requirements

Every meaningful change must include appropriate tests.

Use multiple levels:

### Unit Tests

Test parser, lexer, IR, generator, utility, security, and validation
logic independently.

### Integration Tests

Test parser → IR → generator → compilation.

### End-to-End Tests

Test:

``` text
COBOL/JCL repository
        ↓
pipeline
        ↓
baseline
        ↓
native Java
        ↓
compile
        ↓
execute
        ↓
compare
        ↓
final verdict
```

### Unseen Repository Tests

Always include repositories that were not used while implementing the
feature.

Do not use only benchmark fixtures as proof of universality.

### Negative Tests

Intentionally test:

-   invalid COBOL;
-   unsupported statements;
-   compilation failures;
-   runtime failures;
-   output mismatches;
-   missing dependencies;
-   missing Docker;
-   missing Maven artifacts;
-   malformed ZIPs;
-   path traversal;
-   unresolved JCL symbols.

The platform must fail correctly.

------------------------------------------------------------------------

## 16. Test Integrity

Do not modify tests solely to make them pass.

Allowed:

-   correcting an objectively incorrect test;
-   making environment detection explicit;
-   improving diagnostics;
-   adding missing assertions;
-   pinning deterministic dependencies.

Not allowed:

-   deleting failing assertions;
-   broadening expected output to hide differences;
-   converting failures to skips without a genuine environmental reason;
-   treating unavailable verification as PASS;
-   bypassing validation gates.

------------------------------------------------------------------------

## 17. Documentation Requirements

Keep documentation synchronized with implementation.

Important documents should cover:

-   architecture;
-   pipeline;
-   supported features;
-   known limitations;
-   security;
-   testing;
-   production readiness;
-   SBOM/dependencies;
-   final engineering status.

Every major limitation should be classified honestly as:

``` text
VERIFIED
EMULATED
PARTIAL
UNSUPPORTED
NOT_VERIFIED
ENVIRONMENT_BLOCKED
```

Do not describe emulation as real mainframe compatibility.

------------------------------------------------------------------------

## 18. Production Readiness Standard

The platform should not be called **Production Ready** merely because
the test suite is green.

Before production readiness, verify:

1.  Repository-agnostic behavior.
2.  Business-equivalence evidence.
3.  Native Java independence.
4.  Security controls.
5.  Dependency reproducibility.
6.  Clean-checkout reproducibility.
7.  Offline behavior where required.
8.  Concurrent execution isolation.
9.  Failure/negative-path behavior.
10. Multiple unseen repository validations.
11. Operational logging and diagnostics.
12. Clear documented limitations.
13. CI/CD reproducibility.
14. Artifact/package integrity.
15. No critical known bugs.

If any critical area remains unverified, use **Production Candidate**,
**MVP**, or another evidence-backed status instead of claiming
Production Ready.

------------------------------------------------------------------------

## 19. Standard Engineering Workflow for Agents

Before changing code:

1.  Inspect the existing implementation.
2.  Identify callers and dependencies.
3.  Search for duplicate implementations.
4.  Understand existing tests.
5.  Determine whether the behavior is benchmark-specific or generic.
6.  Make the smallest architecture-consistent change.
7.  Add/update tests.
8.  Run targeted tests.
9.  Run the complete regression suite.
10. Run at least one unseen-repository test where applicable.
11. Review generated Java.
12. Review validation evidence.
13. Update documentation.
14. Report exact remaining limitations.

Do not make broad rewrites without evidence that the existing
architecture requires them.

------------------------------------------------------------------------

## 20. Required Final Report After Significant Changes

After completing a substantial task, report:

``` text
CHANGES
- What changed
- Why it changed
- Files/components affected

VERIFICATION
- Targeted tests
- Full regression results
- E2E results
- Unseen repository results

SECURITY
- Security checks performed
- Any remaining risks

EQUIVALENCE
- What was actually compared
- What remains unverified

DEPENDENCIES
- Added/removed dependencies
- License/provenance impact
- Offline status

REMAINING LIMITATIONS
- Known gaps
- Environment limitations

FINAL STATUS
- PASS / FAILED / PARTIAL / UNVERIFIED / ENVIRONMENT_BLOCKED
- Evidence supporting the status
```

Never claim a result that was not actually executed and verified.

------------------------------------------------------------------------

## 21. Priority Order

When making engineering decisions, prioritize:

1.  Business correctness and equivalence
2.  Parser/semantic correctness
3.  Generated Java correctness
4.  Validation integrity / false-pass prevention
5.  Security
6.  Repository generality
7.  Reliability and concurrency
8.  Dependency reproducibility
9.  Performance
10. UI polish

UI improvements are valuable, but must never hide or override technical
validation results.

------------------------------------------------------------------------

## 22. Definition of Done

A feature is considered complete only when:

-   implementation is complete;
-   supported behavior is covered by tests;
-   negative cases are considered;
-   generated output is inspected where relevant;
-   no benchmark-specific hardcoding is introduced;
-   security implications are reviewed;
-   regression tests pass;
-   documentation is updated;
-   verification status is evidence-based;
-   remaining limitations are explicitly documented.
