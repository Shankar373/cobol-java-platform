---
name: behavioral-equivalence
description: Orchestrates differential execution output comparison between legacy COBOL baseline and modern Java execution.
stage: VERIFICATION
triggers:
  - COBOL
  - JCL
prerequisites:
  - native-java-generation
inputs:
  - repository_directory
  - pipeline_output_directory
outputs:
  - equivalence_report.json
deterministic_components:
  - modernize.native_pipeline.NativePipeline.stage_equivalence_gate
  - skills.validation.behavioral-equivalence.scripts.verify_equivalence.verify_pipeline_equivalence
references:
  - references/differential_contract.md
scripts:
  - scripts/verify_equivalence.py
---

# Behavioral Equivalence Skill

## Overview & Responsibility
This skill performs deterministic differential verification between the legacy COBOL baseline and the modernized Java application. It executes the Java application in a standalone JVM and compares produced standard output, output datasets, transaction states, and database records against identical baseline initial conditions.

## Trigger Conditions & Stage Entry
- **Stage**: `VERIFICATION` (Stage 6).
- **Trigger**: Active when modernized Java classes have been compiled.
- **Prerequisite**: Successful completion of `native-java-generation` and Maven build gate.

## Deterministic Invocation Contract
1. Invokes `scripts/verify_equivalence.py` which delegates to `NativePipeline.stage_equivalence_gate`.
2. Verifies:
   - Standalone Java execution status.
   - Output exact match (standard output, reports, data files).
   - Negative equivalence gates (ensures differences are detected when files mismatch).
3. Produces final evidence-backed verification verdict (`PASS` / `FAIL`).

## Progressive Disclosure Levels
- **Level 1 (Registry Metadata)**: Short summary in `skills/registry.json`.
- **Level 2 (Skill Spec)**: This `SKILL.md`.
- **Level 3 (Scripts & References)**: `scripts/verify_equivalence.py` and `references/differential_contract.md`.

## Failure Handling
- If outputs differ or execution fails, emits a strict `NOT_VERIFIED` verdict and detailed diffs without silently masking mismatches.
