import json
import os
from .semantic_ir import SemanticIR
from .control_flow import ControlFlowModel
from .data_flow import DataFlowModel

class CallDependencyRecord:
    def __init__(
        self,
        caller: str,
        target: str,
        resolution: str = "UNRESOLVED_DYNAMIC",
        reachable: str = "NO",
        executed: str = "NO",
        java_target: str = "NOT_GENERATED",
        migration_status: str = "UNMIGRATED",
        evidence: str = "",
        dependency_type: str = "CALL",
        source_location: dict = None,
        arguments: list = None,
        argument_count: int = 0
    ):
        self.caller = caller
        self.target = target
        self.resolution = resolution
        self.reachable = reachable
        self.executed = executed
        self.java_target = java_target
        self.migration_status = migration_status
        self.evidence = evidence
        self.dependency_type = dependency_type
        self.source_location = source_location or {}
        self.arguments = arguments or []
        self.argument_count = argument_count

    def to_dict(self) -> dict:
        return {
            "caller": self.caller,
            "target": self.target,
            "resolution": self.resolution,
            "reachable": self.reachable,
            "executed": self.executed,
            "java_target": self.java_target,
            "migration_status": self.migration_status,
            "evidence": self.evidence,
            "dependency_type": self.dependency_type,
            "source_location": self.source_location,
            "arguments": self.arguments,
            "argument_count": self.argument_count
        }


class DependencyMigrationStatus:
    def __init__(self, schema_version: str = "1.0"):
        self.schema_version = schema_version
        self.calls = []

    def add_call(self, record: CallDependencyRecord):
        self.calls.append(record)

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "calls": [call.to_dict() for call in self.calls]
        }

    def save(self, path: str):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2)


class DependencyAnalysisEngine:
    @staticmethod
    def analyze(
        repo_path: str,
        entrypoint: str,
        ir_models: dict,
        data_flows: dict = None
    ) -> DependencyMigrationStatus:
        status = DependencyMigrationStatus()
        data_flows = data_flows or {}

        # 1. Discover all source files inside repository
        discovered_programs = {}
        for root, dirs, files in os.walk(repo_path):
            for file in files:
                if file.lower().endswith((".cob", ".cbl", ".cobol")):
                    prog_name = os.path.splitext(file)[0].upper()
                    discovered_programs[prog_name] = os.path.join(root, file)

        # 2. Graph reachability calculations
        reachable_programs = set()
        queue = [entrypoint.upper()]
        
        while queue:
            curr = queue.pop(0)
            if curr in reachable_programs:
                continue
            reachable_programs.add(curr)

            # Analyze calls in current program's IR model
            ir = ir_models.get(curr)
            if not ir:
                continue

            prog_vars_map = {n.properties.get("name", "").upper(): n for n in ir.nodes.values() if n.kind == "DATA_ITEM"}

            for node in ir.nodes.values():
                if node.kind == "STATEMENT" and node.properties.get("statement_type") == "CALL":
                    target = node.properties.get("target", "").upper()
                    
                    # Clean quotes
                    if (target.startswith("'") and target.endswith("'")) or (target.startswith('"') and target.endswith('"')):
                        target = target[1:-1].upper()
                    
                    # Resolve dynamic variables with constant values
                    if target in prog_vars_map:
                        var_node = prog_vars_map[target]
                        if var_node.properties.get("value"):
                            resolved_val = var_node.properties.get("value")
                            if (resolved_val.startswith("'") and resolved_val.endswith("'")) or (resolved_val.startswith('"') and resolved_val.endswith('"')):
                                resolved_val = resolved_val[1:-1]
                            target = resolved_val.upper()
                    
                    # If target is reachable, push it to resolution queue
                    if target in discovered_programs and target not in reachable_programs:
                        queue.append(target)

        # 3. Create dependency records for CALL statements
        for prog_name, ir in ir_models.items():
            is_reachable = "REACHABLE" if prog_name in reachable_programs else "UNREACHABLE"
            df = data_flows.get(prog_name)
            prog_vars = {n.properties.get("name", "").upper() for n in ir.nodes.values() if n.kind == "DATA_ITEM"}

            for node in ir.nodes.values():
                if node.kind == "STATEMENT" and node.properties.get("statement_type") == "CALL":
                    target = node.properties.get("target", "")
                    clean_target = target
                    if (clean_target.startswith("'") and clean_target.endswith("'")) or (clean_target.startswith('"') and clean_target.endswith('"')):
                        clean_target = clean_target[1:-1]
                    clean_target_upper = clean_target.upper()
                    
                    # Determine classification
                    resolution = "RESOLVED_STATIC"
                    dep_type = "CALL"
                    args = node.properties.get("arguments", [])
                    
                    # External system targets
                    if clean_target_upper.startswith(("DFH", "DSN", "CICS", "VSAM", "DB2")):
                        resolution = "EXTERNAL_SYSTEM"
                        dep_type = clean_target_upper[:4] if clean_target_upper.startswith(("CICS", "VSAM", "JCL")) else "EXTERNAL"
                    
                    # Dynamic CALL classification
                    elif clean_target_upper in prog_vars:
                        # Dynamic target variable
                        resolution = "UNRESOLVED_DYNAMIC"
                        # Check constant initialization
                        var_node = None
                        for n in ir.nodes.values():
                            if n.kind == "DATA_ITEM" and n.properties.get("name", "").upper() == clean_target_upper:
                                var_node = n
                                break
                        if var_node and var_node.properties.get("value"):
                            resolved_val = var_node.properties.get("value")
                            if (resolved_val.startswith("'") and resolved_val.endswith("'")) or (resolved_val.startswith('"') and resolved_val.endswith('"')):
                                resolved_val = resolved_val[1:-1]
                            
                            if resolved_val.upper() in discovered_programs:
                                resolution = "RESOLVED_DYNAMIC"
                            else:
                                resolution = "MISSING_SOURCE"
                    
                    # Missing targets
                    elif clean_target_upper not in discovered_programs:
                        resolution = "MISSING_SOURCE"

                    record = CallDependencyRecord(
                        caller=prog_name,
                        target=clean_target,
                        resolution=resolution,
                        reachable="YES" if prog_name in reachable_programs else "NO",
                        executed="NO",
                        java_target="NOT_GENERATED",
                        migration_status="UNMIGRATED",
                        evidence=f"CALL statement in {prog_name}",
                        dependency_type=dep_type,
                        source_location={
                            "file": node.source_file,
                            "line": node.source_line,
                            "column": node.source_column
                        },
                        arguments=args,
                        argument_count=len(args)
                    )
                    status.add_call(record)

            # 4. Scan source files or tokens directly for COPY book references
            src_path = discovered_programs.get(prog_name)
            if src_path and os.path.exists(src_path):
                with open(src_path, "r", encoding="utf-8") as fh:
                    for line_idx, line in enumerate(fh, 1):
                        cleaned = line.split("*>")[0].strip() # Strip line comments
                        words = cleaned.upper().split()
                        if "COPY" in words:
                            copy_idx = words.index("COPY")
                            if copy_idx + 1 < len(words):
                                copy_part = words[copy_idx + 1]
                                # Clean periods
                                if copy_part.endswith("."):
                                    copy_part = copy_part[:-1].strip()
                                
                                copybook_name = copy_part
                                if copybook_name:
                                    # Clean quotes if any
                                    if (copybook_name.startswith("'") and copybook_name.endswith("'")) or (copybook_name.startswith('"') and copybook_name.endswith('"')):
                                        copybook_name = copybook_name[1:-1]
                                    
                                    # Check copybook presence in same folder or subfolders
                                    copy_found = False
                                    resolved_path = ""
                                    for root, dirs, files in os.walk(repo_path):
                                        for file in files:
                                            # Match copybook file name
                                            base_name = os.path.splitext(file)[0].upper()
                                            if base_name == copybook_name.upper():
                                                copy_found = True
                                                resolved_path = os.path.join(root, file)
                                                break
                                    
                                    resolution = "COPY_FOUND" if copy_found else "COPY_MISSING"
                                    
                                    record = CallDependencyRecord(
                                        caller=prog_name,
                                        target=copybook_name,
                                        resolution=resolution,
                                        reachable="YES" if prog_name in reachable_programs else "NO",
                                        executed="NO",
                                        java_target="NOT_GENERATED",
                                        migration_status="UNMIGRATED",
                                        evidence=f"COPY statement in {prog_name}",
                                        dependency_type="COPY",
                                        source_location={
                                            "file": os.path.basename(src_path),
                                            "line": line_idx,
                                            "column": line.upper().find("COPY") + 1
                                        }
                                    )
                                    status.add_call(record)

        return status
