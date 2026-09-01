---
name: ir-validation
description: Validates Semantic IR graph completeness, verifying node schema, variable declarations, statement types, and traceability properties.
stage: IR_VALIDATION
triggers:
  - COBOL
prerequisites:
  - cobol-program-analysis
inputs:
  - semantic_ir
outputs:
  - ir_validation_report.json
deterministic_components:
  - modernize.semantic_ir.SemanticIR
  - skills.ir.ir-validation.scripts.validate_ir.validate_semantic_ir
references:
  - references/ir_specification.md
scripts:
  - scripts/validate_ir.py
---

# Semantic IR Validation Skill

## Overview & Responsibility
This skill inspects the in-memory or serialized `SemanticIR` graph produced by the deterministic parser. It verifies node typing, variable hierarchies, statement semantics, and source traceability coordinates before code generation.

## Trigger Conditions & Stage Entry
- **Stage**: `IR_VALIDATION` (Stage 4).
- **Trigger**: Active whenever `SemanticIR` has been constructed.
- **Prerequisite**: Successful completion of program parsing.

## Deterministic Invocation Contract
1. Invokes `scripts/validate_ir.py`.
2. Inspects every `SemanticIRNode` against strict structural invariants:
   - Valid node kinds (`PROGRAM`, `VARIABLE`, `DATA_ITEM`, `PARAGRAPH`, `STATEMENT`).
   - Non-empty variable names and level numbers.
   - Non-empty statement verbs.
3. Produces a validation report and blocks invalid IR from reaching generation.

## Progressive Disclosure Levels
- **Level 1 (Registry Metadata)**: Short summary in `skills/registry.json`.
- **Level 2 (Skill Spec)**: This `SKILL.md`.
- **Level 3 (Scripts & References)**: `scripts/validate_ir.py` and `references/ir_specification.md`.

## Failure Handling
- If structural integrity checks fail, generation is blocked with explicit node-level diagnostics.
