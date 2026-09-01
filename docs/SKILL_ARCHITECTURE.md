# Google-Style Skill Architecture for COBOL Modernization

**Standard Reference**: `https://github.com/google/skills`  
**System**: Deterministic Modernization Engine + Stage-Aware Skill Layer  
**Date**: September 2026

---

## 1. Architectural Philosophy & Responsibility Boundaries

The platform establishes strict separation of responsibilities across five distinct layers:

```
Mainframe COBOL Repository
        ↓
[Skill: repository-discovery]  → Produces repository_profile.json
        ↓
[Skill Router & Registry]     → Evaluates triggers & selects applicable skills
        ↓
[Deterministic Engines]       → Lexer, Parser, Semantic IR, Dependency/CFG/DFG Analysis (modernize/)
        ↓
[Skill: ir-validation]        → Validates Semantic IR graph invariants
        ↓
[Skill: native-java-gen]      → Drives NativeProgramGenerator for Track-B Java output
        ↓
[Runtime & Maven Build Gate]  → Real Standalone JVM compilation & execution
        ↓
[Skill: behavioral-equiv]     → Runs differential output & database state comparison
        ↓
[Evidence-Backed Matrix]      → Strict taxonomy classification
```

### Layer Separation
1. **Deterministic Transformation Engines** (`modernize/`):
   - Own lexical analysis, parsing, semantic IR, code generation, and runtime helpers.
   - Serve as the ultimate **Semantic and Transformation Authority**.
2. **Skill Layer** (`skills/`):
   - Provides domain knowledge, trigger conditions, routing, prerequisites, inputs/outputs, workflow constraints, and validation guidance.
   - Invokes deterministic components through clean scripts without duplicating semantic logic.
3. **Execution & Runtime**:
   - Standalone JVM, PostgreSQL, and file engines serve as the **Execution Authority**.
4. **Differential Verification**:
   - Compares initial and final states across COBOL baseline and modernized Java to serve as the **Evidence Authority**.
5. **Agent / LLM**:
   - Acts as **Orchestration Authority Only**; never invents COBOL semantics or synthesizes false equivalence.

---

## 2. Google-Style Conventions Adopted vs Rejected

### Adopted Concepts
- **`SKILL.md` Specification**: Formal operational contract per skill with YAML frontmatter.
- **Concise Metadata & Progressive Disclosure**:
  - **Level 1 (Metadata)**: Machine-readable JSON summary in `skills/registry.json`.
  - **Level 2 (Specification)**: Operational guidelines in `SKILL.md`.
  - **Level 3 (References & Scripts)**: Specialized documentation in `references/` and deterministic CLI entry points in `scripts/`.
- **Modular Directory Structure**: Scoped subdirectories by domain (`discovery/`, `cobol/`, `copybooks/`, `ir/`, `java/`, `validation/`).
- **Validation Engine**: Built-in `skills/validator.py` verifying all frontmatter, schema, script paths, and doc references.

### Explicitly Rejected Concepts
- **Google Cloud / GCP / Gemini Dependencies**: No proprietary cloud SDKs or cloud credentials required; runs completely local and standalone.
- **LLM-Based Code Generation**: The transformation engine is strictly deterministic; LLM is not used to synthesize Java code.

---

## 3. The Six Pilot Skills

1. **`discovery/repository-discovery`**:
   - Inspects target repository directories, detects mainframe artifacts, and produces `repository_profile.json`.
2. **`cobol/program-analysis`**:
   - Discovers program divisions, symbols, paragraphs, verbs, CALL targets, and diagnostics.
3. **`copybooks/copybook-analysis`**:
   - Analyzes and resolves `COPY` statements across library directories with case-sensitivity fallback.
4. **`ir/ir-validation`**:
   - Inspects `SemanticIR` node graphs for structural integrity and typing invariants before code generation.
5. **`java/native-java-generation`**:
   - Drives Track-B Java / Spring Boot class generation with zero proprietary runtime dependencies.
6. **`validation/behavioral-equivalence`**:
   - Orchestrates differential output and database state comparison between COBOL baseline and modern Java.
