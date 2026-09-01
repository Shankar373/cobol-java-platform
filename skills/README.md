# Google-Style Stage-Aware Modernization Skills Architecture

This directory implements the Google-Style Skill Architecture (`https://github.com/google/skills` reference) adapted for Mainframe COBOL to Native Java/Spring Modernization.

## Core Architectural Principle

```
Mainframe COBOL Repository
        ↓
[Skill: repository-discovery]  → Produces repository_profile.json
        ↓
[Skill Router & Registry]     → Matches required skills to detected technologies
        ↓
[Deterministic Engines]       → Lexer, Parser, Semantic IR, Dependency/CFG/DFG Analysis (modernize/)
        ↓
[Skill: ir-validation]        → Validates Semantic IR node graph integrity
        ↓
[Skill: native-java-gen]      → Drives NativeProgramGenerator for Track-B Java output
        ↓
[Runtime & Maven Build Gate]  → Real Standalone JVM compilation & execution
        ↓
[Skill: behavioral-equiv]     → Runs differential output & database state comparison
        ↓
[Evidence-Backed Matrix]      → Strict taxonomy classification
```

## Layer Separation & Governance
1. **Deterministic Transformation Engines** (`modernize/`):
   - Own lexical analysis, parsing, semantic IR, code generation, and runtime helpers.
   - Serve as the ultimate **Semantic and Transformation Authority**.
2. **Skill Layer** (`skills/`):
   - Provides domain knowledge, trigger conditions, routing, prerequisites, inputs/outputs, workflow constraints, and validation guidance.
   - Skills invoke the deterministic components without duplicating semantic logic.
3. **Execution & Evidence Layer**:
   - Standalone JVM execution, real PostgreSQL databases, and diff engines serve as the **Evidence Authority**.
4. **Agent / LLM**:
   - Acts as **Orchestration Authority Only**; never invents COBOL semantics or synthesizes false equivalence.

## Progressive Disclosure Levels
- **Level 1 (Metadata)**: Concise summaries in `skills/registry.json` for fast routing.
- **Level 2 (Skill Specification)**: Comprehensive `SKILL.md` in each skill directory defining triggers, prerequisites, inputs, deterministic invocations, outputs, and validation.
- **Level 3 (References & Scripts)**: `references/` documentation and `scripts/` deterministic CLI entry points loaded on demand.

## Six Pilot Skills
1. `discovery/repository-discovery`: Scans repository artifacts and outputs `repository_profile.json`.
2. `cobol/program-analysis`: Discovers symbols, divisions, paragraphs, and AST statements.
3. `copybooks/copybook-analysis`: Resolves copybook paths and dependencies.
4. `ir/ir-validation`: Validates Semantic IR graph completeness and node integrity.
5. `java/native-java-generation`: Drives Track B Java / Spring Boot class generation.
6. `validation/behavioral-equivalence`: Orchestrates differential output and state comparison.
