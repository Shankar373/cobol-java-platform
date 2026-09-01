import os
import re
import json
import tempfile
import subprocess
from modernize.semantic_ir import SemanticIR
from modernize.proleap_adapter.ir_mapper import ProLeapIRMapper
from modernize.proleap_adapter.diagnostics import ProLeapDiagnostic

def resolve_copybooks_recursively(file_path, search_dirs, visited=None):
    if visited is None:
        visited = set()
    real_path = os.path.abspath(file_path)
    if real_path in visited:
        return []
    visited.add(real_path)
    
    if not os.path.exists(real_path):
        return [os.path.basename(file_path)]
        
    try:
        with open(real_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception:
        return [os.path.basename(file_path)]
        
    copy_pattern = re.compile(r'\bCOPY\s+["\']?([A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)?)["\']?', re.IGNORECASE)
    copybooks = copy_pattern.findall(content)

    # Extension set must be a SUPERSET of cobol_migrate.COPYBOOK_EXTENSIONS
    # (".cpy", ".CPY", ".copy", ".COPY"): the two resolvers previously drifted,
    # so a copybook named X.copy resolved for the cobj pipeline but was
    # reported missing by the ProLeap adapter. tests/test_hardening_parity_and_ui.py
    # enforces agreement.
    copybook_exts = ["", ".cpy", ".CPY", ".copy", ".COPY", ".cob", ".COB", ".cbl", ".CBL"]

    missing = []
    for cb in copybooks:
        found_path = None
        for sdir in search_dirs:
            # 1. Exact case check
            for ext in copybook_exts:
                p = os.path.join(sdir, cb + ext)
                if os.path.exists(p) and os.path.isfile(p):
                    found_path = p
                    break
            if found_path:
                break

            # 2. Case-insensitive lookup check
            if os.path.exists(sdir) and os.path.isdir(sdir):
                try:
                    files_in_dir = os.listdir(sdir)
                except OSError:
                    continue
                for ext in copybook_exts:
                    target_lower = (cb + ext).lower()
                    for filename in files_in_dir:
                        if filename.lower() == target_lower:
                            full_p = os.path.join(sdir, filename)
                            if os.path.isfile(full_p):
                                found_path = full_p
                                break
                    if found_path:
                        break
            if found_path:
                break

        if not found_path:
            missing.append(cb)
        else:
            missing.extend(resolve_copybooks_recursively(found_path, search_dirs, visited))
            
    return list(set(missing))

class ProLeapParserAdapter:
    def __init__(self, file_path: str):
        self.file_path = os.path.abspath(file_path)
        self.diagnostics = []
        self.status = "SUCCESS"

    @staticmethod
    def required_proleap_jars() -> list:
        """Absolute paths of every JAR the adapter needs on the classpath.

        Single source of truth: availability guards (tests, doctor tooling)
        MUST call this instead of maintaining a parallel list — a partial
        guard previously let a half-seeded environment reach parse() and
        fail with the wrong diagnostic.
        """
        m2_repo = os.path.join(os.path.expanduser("~"), ".m2", "repository")
        project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        proleap_jar = os.path.join(
            project_root, "third_party", "proleap", "artifact",
            "proleap-cobol-parser-4.0.0.jar")
        poc_jar = os.path.join(
            project_root, "third_party", "proleap", "artifact",
            "proleap-poc-1.0.0.jar")
        jackson_databind = os.path.join(
            m2_repo, "com", "fasterxml", "jackson", "core", "jackson-databind",
            "2.15.2", "jackson-databind-2.15.2.jar")
        jackson_annotations = os.path.join(
            m2_repo, "com", "fasterxml", "jackson", "core", "jackson-annotations",
            "2.15.2", "jackson-annotations-2.15.2.jar")
        jackson_core = os.path.join(
            m2_repo, "com", "fasterxml", "jackson", "core", "jackson-core",
            "2.15.2", "jackson-core-2.15.2.jar")
        antlr_runtime = os.path.join(
            m2_repo, "org", "antlr", "antlr4-runtime",
            "4.7.2", "antlr4-runtime-4.7.2.jar")
        slf4j_api = os.path.join(
            m2_repo, "org", "slf4j", "slf4j-api",
            "2.0.9", "slf4j-api-2.0.9.jar")
        return [proleap_jar, poc_jar, jackson_databind,
                jackson_annotations, jackson_core, antlr_runtime, slf4j_api]

    def parse(self) -> SemanticIR:
        batch_results = self.parse_batch([self.file_path])
        res = batch_results.get(self.file_path)
        if res:
            self.status = res["status"]
            self.diagnostics = res["diagnostics"]
            return res["ir"]
        else:
            ir = SemanticIR()
            ir.status = "FAILURE"
            self.status = "FAILURE"
            return ir

    @classmethod
    def parse_batch(cls, file_paths: list) -> dict:
        results = {}
        required_jars = cls.required_proleap_jars()
        missing_jars = [r for r in required_jars if not os.path.exists(r)]
        # Legacy-copybook fallback root for search_dirs below.
        project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        to_parse = []
        
        for fp in file_paths:
            fp_abs = os.path.abspath(fp)
            results[fp_abs] = {
                "ir": None,
                "diagnostics": [],
                "status": "SUCCESS"
            }
            
            # Check classpath dependencies
            if missing_jars:
                results[fp_abs]["status"] = "FAILURE"
                results[fp_abs]["diagnostics"].append(
                    ProLeapDiagnostic(
                        severity="ERROR",
                        detail=f"PROLEAP_UNAVAILABLE: Dependency jars missing: {[os.path.basename(m) for m in missing_jars]}",
                        line=1,
                        col=1
                    )
                )
                ir = SemanticIR()
                ir.status = "FAILURE"
                results[fp_abs]["ir"] = ir
                continue
                
            # Perform COPYBOOK checks
            search_dirs = [
                os.path.dirname(fp_abs),
                os.path.join(os.path.dirname(fp_abs), "copybooks"),
                os.path.join(os.path.dirname(os.path.dirname(fp_abs)), "copybooks"),
                os.path.join(project_root, "legacy", "copybooks"),
                os.path.join(project_root, "legacy")
            ]
            
            missing_copybooks = resolve_copybooks_recursively(fp_abs, search_dirs)
            if missing_copybooks:
                results[fp_abs]["status"] = "FAILURE"
                for cb in missing_copybooks:
                    results[fp_abs]["diagnostics"].append(
                        ProLeapDiagnostic(
                            severity="ERROR",
                            detail=f"PROLEAP_MISSING_COPYBOOK: Copybook '{cb}' could not be resolved",
                            line=1,
                            col=1
                        )
                    )
                ir = SemanticIR()
                ir.status = "FAILURE"
                results[fp_abs]["ir"] = ir
            else:
                to_parse.append(fp_abs)
                
        if not to_parse:
            return results
            
        # 2. Run Java Parser in a single batch process invocation.
        # os.pathsep: ';' on Windows, ':' on Linux/containers — the previous
        # hardcoded ';' made the adapter silently unusable under Docker.
        classpath = os.pathsep.join(required_jars)
        cmd = ["java", "-cp", classpath, "com.systema.proleappoc.ProLeapPoc"]
        
        temp_files = {} # fp_abs -> temp_json_path
        
        for fp_abs in to_parse:
            fd, temp_json_path = tempfile.mkstemp(suffix=".json")
            os.close(fd)
            temp_files[fp_abs] = temp_json_path
            cmd.extend([fp_abs, temp_json_path])
            
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            # Read output JSON files and map
            for fp_abs in to_parse:
                temp_json_path = temp_files[fp_abs]
                
                if res.returncode != 0 or not os.path.exists(temp_json_path) or os.path.getsize(temp_json_path) == 0:
                    results[fp_abs]["status"] = "FAILURE"
                    results[fp_abs]["diagnostics"].append(
                        ProLeapDiagnostic(
                            severity="ERROR",
                            detail=f"PROLEAP_PARSER_FAILURE: Batch parsing failed for file",
                            line=1,
                            col=1
                        )
                    )
                    ir = SemanticIR()
                    ir.status = "FAILURE"
                    results[fp_abs]["ir"] = ir
                else:
                    try:
                        with open(temp_json_path, "r", encoding="utf-8") as f:
                            ast_json = json.load(f)
                            
                        mapper = ProLeapIRMapper(fp_abs)
                        ir = mapper.map_to_ir(ast_json)
                        results[fp_abs]["diagnostics"].extend(mapper.diagnostics)
                        results[fp_abs]["ir"] = ir
                        results[fp_abs]["status"] = "SUCCESS"
                        ir.status = "SUCCESS"
                    except Exception as ex:
                        results[fp_abs]["status"] = "FAILURE"
                        results[fp_abs]["diagnostics"].append(
                            ProLeapDiagnostic(
                                severity="ERROR",
                                detail=f"PROLEAP_ADAPTER_ERROR: {str(ex)}",
                                line=1,
                                col=1
                            )
                        )
                        ir = SemanticIR()
                        ir.status = "FAILURE"
                        results[fp_abs]["ir"] = ir
        finally:
            for temp_json_path in temp_files.values():
                if os.path.exists(temp_json_path):
                    try:
                        os.remove(temp_json_path)
                    except Exception:
                        pass
                        
        return results
