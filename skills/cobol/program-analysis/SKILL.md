---
name: cobol-program-analysis
description: Performs deterministic AST and semantic analysis of COBOL source programs, identifying symbols, paragraphs, verbs, CALL targets, and diagnostics.
stage: ANALYSIS
triggers:
  - COBOL
prerequisites:
  - repository-discovery
inputs:
  - cobol_source_file
  - copybook_directories
outputs:
  - program_analysis_report.json
deterministic_components:
  - modernize.lexer.CobolLexer
  - modernize.parser.CobolParser
  - skills.cobol.program-analysis.scripts.analyze_program.analyze_cobol_program
references:
  - references/divisions_and_verbs.md
scripts:
  - scripts/analyze_program.py
---

# COBOL Program Analysis Skill

## Overview & Responsibility
This skill performs detailed lexical and syntactic analysis of individual COBOL programs. It parses divisions, extracts variable definitions, maps out the procedure division paragraphs, detects calls, and collects any parser diagnostics without inventing or modifying code.

## Trigger Conditions & Stage Entry
- **Stage**: `ANALYSIS` (Stage 2).
- **Trigger**: Active whenever `COBOL` files are detected by `repository-discovery`.
- **Prerequisite**: Valid source file paths identified in repository profile.

## Deterministic Invocation Contract
1. Invokes `scripts/analyze_program.py` which runs `CobolLexer` and `CobolParser`.
2. Produces structured metrics:
   - Program identity (`PROGRAM-ID`).
   - Counts and inventories of variables, paragraphs, statements, and external program calls.
   - Any syntactic or unsupported command diagnostics.

## Progressive Disclosure Levels
- **Level 1 (Registry Metadata)**: Short summary in `skills/registry.json`.
- **Level 2 (Skill Spec)**: This `SKILL.md`.
- **Level 3 (Scripts & References)**: `scripts/analyze_program.py` and `references/divisions_and_verbs.md`.

## Failure Handling & Validation
- Fails closed with syntax diagnostics if the COBOL file has unrecoverable syntax errors.
