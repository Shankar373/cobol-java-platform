# Stage-to-Skill Mapping Matrix

This document maps every modernization pipeline stage to its responsible deterministic engine component, corresponding skill, operational contracts, and verification gates.

---

## 1. End-to-End Pipeline Mapping

| Stage Index & Name | Deterministic Pipeline Stage | Invoked Engine Component (`modernize/`) | Mapped Skill (`skills/`) | Skill Trigger | Input Artifacts | Output Artifacts | Verification Gate |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Stage 1: Discovery** | `NativePipeline.stage_discover` | `dependencies.py` | `repository-discovery` | Repository directory provided | Workspace filesystem | `repository_profile.json` | Discovery Gate: All sources indexed |
| **Stage 2: Program Analysis** | `NativePipeline.stage_parse` | `lexer.py`, `parser.py`, `control_flow.py` | `cobol-program-analysis` | `COBOL` in repo profile | `.cob` / `.cbl` files | AST Symbol Table, Call Graph | Syntax Gate: Zero fatal parse errors |
| **Stage 3: Copybooks** | `NativePipeline.stage_parse` | `dependencies.py`, parser COPY expander | `copybook-analysis` | `COPY` statements detected | COBOL files, Copybook dirs | Resolved copybook paths | Copybook Gate: Zero missing copybooks |
| **Stage 4: IR Validation** | `NativePipeline.stage_parse` | `semantic_ir.py` | `ir-validation` | `SemanticIR` graph produced | `SemanticIR` | `ir_validation_report.json` | IR Gate: Valid node hierarchy & typing |
| **Stage 5: Java Generation** | `NativePipeline.stage_generate` | `native_generator.py` (`NativeProgramGenerator`) | `native-java-generation` | Validated `SemanticIR` | `SemanticIR`, DTO templates | Modern Java classes, `pom.xml` | Dependency Gate: Zero forbidden jars |
| **Stage 6: Maven Build** | `NativePipeline.stage_build_gate` | Maven Compiler Plugin (JDK 17) | Runtime Orchestration | Java sources emitted | `pom.xml`, Java sources | Compiled `.class` files | Build Gate: `mvn compile` exit code 0 |
| **Stage 7: Execution** | `NativePipeline.stage_execute_gate` | Standalone JVM / Spring Boot Runner | Runtime Orchestration | Compiled `.class` files | Compiled `.class`, test DB/files | `stdout.txt`, output datasets | Execution Gate: JVM exit code 0 |
| **Stage 8: Equivalence** | `NativePipeline.stage_equivalence_gate` | Differential comparison engine | `behavioral-equivalence` | Java execution completed | Baseline outputs, Java outputs | `equivalence_report.json` | Equivalence Gate: Exact byte/file match |
