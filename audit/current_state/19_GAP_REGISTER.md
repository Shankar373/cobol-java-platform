# 19. Gap Register

This document registers missing functional requirements in the repository.

---

## Gap ID: GAP-001
- **Severity**: `P0` (Core correctness blocker)
- **Component**: Native Java Scaffolder
- **File**: [`cobol_migrate.py`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/cobol_migrate.py)
- **Description**: The Spring Boot refactoring pipeline (`stage_refactor`) is hardcoded to match the specific shapes of the BankCore and Claims PAS benchmarks. It cannot dynamically build repository-agnostic native Spring Boot structures for previously unseen repositories.
- **Ceiling**: Generates hardcoded code segments.
- **Upgrade Path**: Derive JPA entities and Spring Batch readers directly from parsed Semantic IR variable nodes.

---

## Gap ID: GAP-002
- **Severity**: `P1` (Major capability gap)
- **Component**: Transpilation
- **File**: [`cobol_migrate.py`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/cobol_migrate.py)
- **Description**: The generated Java bytecode from the `cobj` transpiler is emulated Java which has a hard classpath dependency on `libcobj.jar`.
- **Upgrade Path**: Implement a native Java AST translator in future phases.

---

## Gap ID: GAP-003
- **Severity**: `P2` (Significant issue)
- **Component**: Dependency Analysis
- **File**: [`modernize/dependencies.py`](file:///c:/Users/bandi/Desktop/SystemaOps/Cobol-to-java-test/modernize/dependencies.py)
- **Description**: The CALL dependency analyzer cannot trace dynamic variable values set inside conditional branch loops.
- **Upgrade Path**: Integrate the Data Flow Model value tracer into the Call Engine.
