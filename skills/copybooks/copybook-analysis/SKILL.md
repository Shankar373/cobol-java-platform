---
name: copybook-analysis
description: Analyzes and resolves COBOL COPY statements, locating library copybooks across search directories with case-sensitivity fallback.
stage: COPYBOOKS
triggers:
  - COPYBOOKS
  - COBOL
prerequisites:
  - repository-discovery
inputs:
  - cobol_source_file
  - search_directories
outputs:
  - copybook_resolution_report.json
deterministic_components:
  - modernize.dependencies.DependencyAnalyzer
  - skills.copybooks.copybook-analysis.scripts.resolve_copybooks.resolve_copybooks_for_file
references:
  - references/copy_semantics.md
scripts:
  - scripts/resolve_copybooks.py
---

# Copybook Analysis Skill

## Overview & Responsibility
This skill identifies all `COPY` statements inside COBOL programs and resolves their target files against library directories, applying case-insensitive matching and standard copybook extension fallbacks (`.cpy`, `.cpb`, `.cbl`).

## Trigger Conditions & Stage Entry
- **Stage**: `COPYBOOKS` (Stage 3).
- **Trigger**: Active when `COPYBOOKS` or `COBOL` sources containing `COPY` statements are present.
- **Prerequisite**: Source file paths identified in discovery.

## Deterministic Invocation Contract
1. Invokes `scripts/resolve_copybooks.py`.
2. Scans for `COPY <name>` tokens and traverses search paths.
3. Produces a complete map of resolved file paths and reports any missing copybooks as potential blockers.

## Progressive Disclosure Levels
- **Level 1 (Registry Metadata)**: Short summary in `skills/registry.json`.
- **Level 2 (Skill Spec)**: This `SKILL.md`.
- **Level 3 (Scripts & References)**: `scripts/resolve_copybooks.py` and `references/copy_semantics.md`.

## Failure Handling
- Emits explicit missing copybook warnings and marks `all_resolved: false` if any copybook cannot be found on disk.
