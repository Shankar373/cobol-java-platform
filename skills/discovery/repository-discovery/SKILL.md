---
name: repository-discovery
description: Inspects arbitrary enterprise repository directories, detects mainframe artifacts (COBOL, JCL, BMS, SQL, copybooks), and produces repository_profile.json.
stage: DISCOVERY
triggers:
  - ALWAYS
prerequisites: []
inputs:
  - repository_directory
outputs:
  - repository_profile.json
deterministic_components:
  - modernize.dependencies.DependencyAnalyzer
  - skills.discovery.repository-discovery.scripts.discover.discover_repository
references:
  - references/detection_rules.md
scripts:
  - scripts/discover.py
---

# Repository Discovery Skill

## Overview & Responsibility
This skill performs evidence-driven discovery of an enterprise mainframe repository. It scans the filesystem, identifies source files, copybooks, JCL scripts, BMS screens, and SQL files, and generates a structured `repository_profile.json`.

## Trigger Conditions & Stage Entry
- **Stage**: `DISCOVERY` (First stage of the modernization workflow).
- **Trigger**: Always active on any input workspace or repository directory.

## Deterministic Invocation Contract
1. Invokes `scripts/discover.py` to scan directories and content signatures.
2. Identifies:
   - Target programming languages (COBOL, JCL, SQL).
   - Middleware and transaction layers (CICS, BMS, DB2).
   - Data storage paradigms (Sequential, VSAM KSDS, Relational).
   - Program entry points and dependency graphs.
3. Emits `repository_profile.json`.

## Progressive Disclosure Levels
- **Level 1 (Registry Metadata)**: Short summary for initial skill matching in `skills/registry.json`.
- **Level 2 (Skill Spec)**: This `SKILL.md` specification.
- **Level 3 (Scripts & References)**: `scripts/discover.py` and `references/detection_rules.md`.

## Failure Handling
If the directory does not exist or has inaccessible permissions, discovery fails immediately with explicit file error diagnostics.
