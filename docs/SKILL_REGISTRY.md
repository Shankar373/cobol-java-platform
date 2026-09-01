# Skill Registry & Dynamic Routing Specification

**Registry Path**: `skills/registry.json`  
**Registry Module**: `skills/registry.py`

---

## 1. Registry Format & Schema

The skill registry is serialized as `skills/registry.json`. Each skill contains:
- `name`: Unique skill identifier (kebab-case).
- `stage`: Modernization pipeline stage (`DISCOVERY`, `ANALYSIS`, `COPYBOOKS`, `IR_VALIDATION`, `GENERATION`, `BUILD`, `EXECUTION`, `VERIFICATION`).
- `description`: Single-sentence functional summary.
- `triggers`: List of technology triggers that activate this skill.
- `prerequisites`: Required prior skills.
- `inputs`: Expected inputs.
- `outputs`: Produced artifacts.
- `deterministic_components`: Python modules / classes in `modernize/` that own the transformation.
- `references`: Associated markdown references in `references/`.
- `scripts`: Deterministic CLI scripts in `scripts/`.

---

## 2. Active Pilot Skills Inventory

| Skill Name | Stage | Triggers | Prerequisites | Invoked Deterministic Component | Script |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `repository-discovery` | `DISCOVERY` | `ALWAYS` | None | `modernize.dependencies.DependencyAnalyzer` | `discovery/repository-discovery/scripts/discover.py` |
| `cobol-program-analysis` | `ANALYSIS` | `COBOL` | `repository-discovery` | `modernize.lexer.CobolLexer`, `CobolParser` | `cobol/program-analysis/scripts/analyze_program.py` |
| `copybook-analysis` | `COPYBOOKS` | `COPYBOOKS`, `COBOL` | `repository-discovery` | `modernize.dependencies.DependencyAnalyzer` | `copybooks/copybook-analysis/scripts/resolve_copybooks.py` |
| `ir-validation` | `IR_VALIDATION` | `COBOL` | `cobol-program-analysis` | `modernize.semantic_ir.SemanticIR` | `ir/ir-validation/scripts/validate_ir.py` |
| `native-java-generation` | `GENERATION` | `COBOL`, `JCL` | `ir-validation` | `modernize.native_generator.NativeProgramGenerator` | `java/native-java-generation/scripts/generate_java.py` |
| `behavioral-equivalence` | `VERIFICATION` | `COBOL`, `JCL` | `native-java-generation` | `modernize.native_pipeline.NativePipeline.stage_equivalence_gate` | `validation/behavioral-equivalence/scripts/verify_equivalence.py` |

---

## 3. Deterministic Matching Algorithm

Given a `repository_profile.json`, `SkillRegistry.match_skills(profile)`:
1. Universal discovery skill is always selected.
2. If `artifacts.cobol_sources` is non-empty, `cobol-program-analysis`, `ir-validation`, `native-java-generation`, and `behavioral-equivalence` are selected.
3. If `artifacts.copybooks` or COBOL sources are present, `copybook-analysis` is selected.
4. Skills are sorted by stage execution order: `DISCOVERY -> ANALYSIS -> COPYBOOKS -> IR_VALIDATION -> GENERATION -> VERIFICATION`.
5. An audit trace is recorded documenting the selection/rejection reason for every skill in the registry.
