---
name: native-java-generation
description: Drives deterministic Track B Java and Spring Boot code generation from validated Semantic IR, adhering to zero-proprietary-runtime-dependency standards.
stage: GENERATION
triggers:
  - COBOL
  - JCL
prerequisites:
  - ir-validation
inputs:
  - repository_directory
  - semantic_ir
outputs:
  - java_source_files
  - pom.xml
deterministic_components:
  - modernize.native_generator.NativeProgramGenerator
  - modernize.native_pipeline.NativePipeline
  - skills.java.native-java-generation.scripts.generate_java.execute_native_java_generation
references:
  - references/track_b_standards.md
scripts:
  - scripts/generate_java.py
---

# Native Java Generation Skill

## Overview & Responsibility
This skill orchestrates the transformation of validated `SemanticIR` into native Java / Spring Boot source files. It enforces Track B compliance: zero proprietary runtime jars (`libcobj.jar`, `COBOL4J`), clean Spring Boot REST/Batch services, and typed Java models.

## Trigger Conditions & Stage Entry
- **Stage**: `GENERATION` (Stage 5).
- **Trigger**: Active when `SemanticIR` is validated for COBOL or JCL applications.
- **Prerequisite**: Successful completion of `ir-validation`.

## Deterministic Invocation Contract
1. Invokes `scripts/generate_java.py` which delegates directly to `modernize.native_generator.NativeProgramGenerator` and `modernize.native_pipeline.NativePipeline`.
2. Generates:
   - Modernized Java classes in package `com.systema.modernized.native_gen`.
   - Typed BMS Screen DTOs in package `com.systema.modernized.bms`.
   - Standalone Maven `pom.xml` configured for Java 17 and Spring Boot 3.2.5.
3. Passes through the standalone dependency gate (`stage_dependency_gate`).

## Progressive Disclosure Levels
- **Level 1 (Registry Metadata)**: Short summary in `skills/registry.json`.
- **Level 2 (Skill Spec)**: This `SKILL.md`.
- **Level 3 (Scripts & References)**: `scripts/generate_java.py` and `references/track_b_standards.md`.

## Failure Handling
- If unmapped statements or invalid types occur, generation fails closed with explicit source coordinates.
