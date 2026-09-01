import os
import importlib.util
from typing import Dict, List, Any, Optional

SKILLS_ROOT = os.path.dirname(os.path.abspath(__file__))

def _load_script_module(skill_rel_path: str, script_name: str):
    script_path = os.path.join(SKILLS_ROOT, skill_rel_path, "scripts", script_name)
    if not os.path.isfile(script_path):
        raise FileNotFoundError(f"Skill script not found at {script_path}")
    module_name = f"skills.{skill_rel_path.replace(os.sep, '.').replace('-', '_')}.{script_name.replace('.py', '')}"
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

# 1. repository-discovery
def discover_repository(repo_dir: str) -> Dict[str, Any]:
    mod = _load_script_module(os.path.join("discovery", "repository-discovery"), "discover.py")
    return mod.discover_repository(repo_dir)

# 2. cobol-program-analysis
def analyze_cobol_program(source_path: str, copybook_dirs: list = None) -> Dict[str, Any]:
    mod = _load_script_module(os.path.join("cobol", "program-analysis"), "analyze_program.py")
    return mod.analyze_cobol_program(source_path, copybook_dirs)

# 3. copybook-analysis
def resolve_copybooks_for_file(source_path: str, search_dirs: List[str]) -> Dict[str, Any]:
    mod = _load_script_module(os.path.join("copybooks", "copybook-analysis"), "resolve_copybooks.py")
    return mod.resolve_copybooks_for_file(source_path, search_dirs)

# 4. ir-validation
def validate_semantic_ir(ir_or_path: Any) -> Dict[str, Any]:
    mod = _load_script_module(os.path.join("ir", "ir-validation"), "validate_ir.py")
    return mod.validate_semantic_ir(ir_or_path)

# 5. native-java-generation
def execute_native_java_generation(repo_dir: str, output_dir: str, target_source: str = None) -> Dict[str, Any]:
    mod = _load_script_module(os.path.join("java", "native-java-generation"), "generate_java.py")
    return mod.execute_native_java_generation(repo_dir, output_dir, target_source)

# 6. behavioral-equivalence
def verify_pipeline_equivalence(repo_dir: str, output_dir: str, target_source: str = None) -> Dict[str, Any]:
    mod = _load_script_module(os.path.join("validation", "behavioral-equivalence"), "verify_equivalence.py")
    return mod.verify_pipeline_equivalence(repo_dir, output_dir, target_source)
