import os
import json
from typing import Dict, List, Optional, Any, Tuple
from skills.validator import parse_skill_file, validate_skill_directory

class SkillRecord:
    def __init__(
        self,
        name: str,
        skill_dir: str,
        stage: str,
        description: str,
        triggers: List[str],
        prerequisites: List[str],
        inputs: List[str],
        outputs: List[str],
        deterministic_components: List[str],
        references: List[str],
        scripts: List[str],
        frontmatter: Dict[str, Any],
        body: str
    ):
        self.name = name
        self.skill_dir = skill_dir
        self.stage = stage
        self.description = description
        self.triggers = triggers
        self.prerequisites = prerequisites
        self.inputs = inputs
        self.outputs = outputs
        self.deterministic_components = deterministic_components
        self.references = references
        self.scripts = scripts
        self.frontmatter = frontmatter
        self.body = body

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "stage": self.stage,
            "description": self.description,
            "skill_dir": os.path.relpath(self.skill_dir, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "triggers": self.triggers,
            "prerequisites": self.prerequisites,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "deterministic_components": self.deterministic_components,
            "references": self.references,
            "scripts": self.scripts
        }

class SkillRegistry:
    def __init__(self, skills_root: Optional[str] = None):
        if skills_root is None:
            skills_root = os.path.dirname(os.path.abspath(__file__))
        self.skills_root = os.path.abspath(skills_root)
        self.skills: Dict[str, SkillRecord] = {}
        self.load_all()

    def load_all(self):
        """Scans skills_root for SKILL.md files and registers valid skills."""
        self.skills.clear()
        for root, dirs, files in os.walk(self.skills_root):
            if "SKILL.md" in files:
                skill_dir = root
                is_valid, errors, warnings = validate_skill_directory(skill_dir)
                if not is_valid:
                    print(f"[SKILL REGISTRY WARNING] Skill in {skill_dir} is invalid: {errors}")
                    continue

                fm, body = parse_skill_file(os.path.join(skill_dir, "SKILL.md"))
                record = SkillRecord(
                    name=fm["name"],
                    skill_dir=skill_dir,
                    stage=fm.get("stage", "ANALYSIS"),
                    description=fm.get("description", ""),
                    triggers=fm.get("triggers", []),
                    prerequisites=fm.get("prerequisites", []),
                    inputs=fm.get("inputs", []),
                    outputs=fm.get("outputs", []),
                    deterministic_components=fm.get("deterministic_components", []),
                    references=fm.get("references", []),
                    scripts=fm.get("scripts", []),
                    frontmatter=fm,
                    body=body
                )
                self.skills[record.name] = record

    def save_registry_json(self, out_path: Optional[str] = None) -> str:
        if out_path is None:
            out_path = os.path.join(self.skills_root, "registry.json")
        data = {
            "version": "1.0.0",
            "skills": {k: v.to_dict() for k, v in sorted(self.skills.items())}
        }
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        return out_path

    def get_skill(self, name: str) -> Optional[SkillRecord]:
        return self.skills.get(name)

    def match_skills(self, repo_profile: Dict[str, Any]) -> Tuple[List[SkillRecord], List[Dict[str, str]]]:
        """
        Deterministically evaluates repository profile against registered skills.
        Returns (matched_skills_in_stage_order, decision_trace).
        """
        matched: List[SkillRecord] = []
        trace: List[Dict[str, str]] = []

        technologies = [t.upper() for t in repo_profile.get("technologies", [])]
        artifacts = repo_profile.get("artifacts", {})
        has_cobol = len(artifacts.get("cobol_sources", [])) > 0 or "COBOL" in technologies
        has_copybooks = len(artifacts.get("copybooks", [])) > 0 or "COPYBOOKS" in technologies
        has_jcl = len(artifacts.get("jcl_files", [])) > 0 or "JCL" in technologies
        has_sql = "SQL" in technologies or "DB2" in technologies or "EXEC SQL" in technologies
        has_cics = "CICS" in technologies or "EXEC CICS" in technologies or "BMS" in technologies

        # Define deterministic stage execution priority
        stage_order = [
            "DISCOVERY",
            "ANALYSIS",
            "COPYBOOKS",
            "IR_VALIDATION",
            "GENERATION",
            "BUILD",
            "EXECUTION",
            "VERIFICATION"
        ]

        for skill_name, skill in self.skills.items():
            selected = False
            reason = ""

            # Universal / foundation skills
            if skill.name == "repository-discovery":
                selected = True
                reason = "Always selected for repository inspection and capability detection"
            elif skill.name == "ir-validation":
                if has_cobol:
                    selected = True
                    reason = "Selected because COBOL sources are present to produce Semantic IR"
                else:
                    reason = "Skipped: No COBOL sources to produce Semantic IR"
            elif skill.name == "native-java-generation":
                if has_cobol or has_jcl:
                    selected = True
                    reason = "Selected because modernizable sources (COBOL/JCL) are present"
                else:
                    reason = "Skipped: No COBOL or JCL sources present"
            elif skill.name == "behavioral-equivalence":
                if has_cobol or has_jcl:
                    selected = True
                    reason = "Selected for differential output verification"
                else:
                    reason = "Skipped: No modernizable sources present"

            # Domain specific skills
            elif skill.name == "cobol-program-analysis":
                if has_cobol:
                    selected = True
                    reason = "Selected because COBOL program files (.cob/.cbl) were detected"
                else:
                    reason = "Skipped: No COBOL files detected in repository profile"
            elif skill.name == "copybook-analysis":
                if has_copybooks or has_cobol:
                    selected = True
                    reason = "Selected to resolve COPY statements and layout definitions"
                else:
                    reason = "Skipped: No copybooks or COBOL sources present"
            else:
                # Custom trigger condition evaluation
                matched_trigger = False
                for trig in skill.triggers:
                    trig_upper = trig.upper()
                    if trig_upper in technologies:
                        matched_trigger = True
                        reason = f"Selected because technology '{trig}' was detected in repository"
                        break
                    if trig_upper == "ALWAYS":
                        matched_trigger = True
                        reason = "Selected due to ALWAYS trigger condition"
                        break
                selected = matched_trigger
                if not selected and not reason:
                    reason = f"Skipped: Required triggers ({skill.triggers}) not satisfied by profile"

            trace.append({
                "skill": skill.name,
                "stage": skill.stage,
                "selected": selected,
                "reason": reason
            })

            if selected:
                matched.append(skill)

        # Sort matched skills by deterministic stage order
        matched.sort(key=lambda s: stage_order.index(s.stage) if s.stage in stage_order else 99)
        return matched, trace
