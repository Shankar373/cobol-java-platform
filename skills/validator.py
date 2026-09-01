import os
import re
import yaml
from typing import Dict, List, Tuple, Any

REQUIRED_FRONTMATTER_KEYS = [
    "name",
    "description",
    "stage",
    "triggers",
    "prerequisites",
    "inputs",
    "outputs",
    "deterministic_components",
    "references",
    "scripts"
]

VALID_STAGES = [
    "DISCOVERY",
    "ANALYSIS",
    "COPYBOOKS",
    "IR_VALIDATION",
    "GENERATION",
    "BUILD",
    "EXECUTION",
    "VERIFICATION"
]

class SkillValidationError(Exception):
    pass

def parse_skill_file(skill_md_path: str) -> Tuple[Dict[str, Any], str]:
    """
    Parses a SKILL.md file and returns (frontmatter_dict, markdown_body).
    """
    if not os.path.isfile(skill_md_path):
        raise SkillValidationError(f"SKILL.md file not found: {skill_md_path}")

    with open(skill_md_path, "r", encoding="utf-8") as fh:
        content = fh.read()

    # Frontmatter pattern: --- \n yaml \n ---
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
    if not match:
        raise SkillValidationError(f"Invalid SKILL.md format: missing YAML frontmatter delimiters (---) in {skill_md_path}")

    raw_yaml = match.group(1)
    body = match.group(2)

    try:
        frontmatter = yaml.safe_load(raw_yaml)
    except Exception as e:
        raise SkillValidationError(f"Error parsing YAML frontmatter in {skill_md_path}: {e}")

    if not isinstance(frontmatter, dict):
        raise SkillValidationError(f"YAML frontmatter must be a dictionary in {skill_md_path}")

    return frontmatter, body

def validate_skill_directory(skill_dir: str) -> Tuple[bool, List[str], List[str]]:
    """
    Validates a skill directory containing SKILL.md, references/, and scripts/.
    Returns (is_valid, errors, warnings).
    """
    errors: List[str] = []
    warnings: List[str] = []

    skill_md_path = os.path.join(skill_dir, "SKILL.md")
    if not os.path.isfile(skill_md_path):
        errors.append(f"Missing SKILL.md in {skill_dir}")
        return False, errors, warnings

    try:
        fm, body = parse_skill_file(skill_md_path)
    except SkillValidationError as e:
        errors.append(str(e))
        return False, errors, warnings

    # 1. Validate required frontmatter keys
    for req_key in REQUIRED_FRONTMATTER_KEYS:
        if req_key not in fm or fm[req_key] is None:
            errors.append(f"Missing required frontmatter key '{req_key}' in {skill_md_path}")

    # 2. Validate stage
    stage = fm.get("stage", "").upper()
    if stage not in VALID_STAGES:
        errors.append(f"Invalid stage '{stage}' in {skill_md_path}. Must be one of: {VALID_STAGES}")

    # 3. Validate lists
    for list_key in ("triggers", "prerequisites", "inputs", "outputs", "deterministic_components", "references", "scripts"):
        val = fm.get(list_key)
        if val is not None and not isinstance(val, list):
            errors.append(f"Frontmatter key '{list_key}' must be a list in {skill_md_path}")

    # 4. Check referenced scripts and docs exist
    scripts = fm.get("scripts", [])
    if isinstance(scripts, list):
        for script_rel in scripts:
            script_full = os.path.normpath(os.path.join(skill_dir, script_rel))
            if not os.path.isfile(script_full):
                errors.append(f"Referenced script does not exist: {script_rel} (checked {script_full})")

    references = fm.get("references", [])
    if isinstance(references, list):
        for ref_rel in references:
            ref_full = os.path.normpath(os.path.join(skill_dir, ref_rel))
            if not os.path.isfile(ref_full):
                errors.append(f"Referenced doc does not exist: {ref_rel} (checked {ref_full})")

    # 5. Check markdown body contains key sections
    body_upper = body.upper()
    for required_section in ("OVERVIEW", "WORKFLOW", "VALIDATION"):
        if required_section not in body_upper:
            warnings.append(f"SKILL.md body in {skill_dir} is missing recommended section heading '{required_section}'")

    is_valid = len(errors) == 0
    return is_valid, errors, warnings
