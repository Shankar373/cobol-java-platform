import os
import sys
import json
import argparse
from typing import Dict, List, Tuple, Any

from modernize.semantic_ir import SemanticIR

VALID_NODE_KINDS = ["PROGRAM", "VARIABLE", "DATA_ITEM", "SECTION", "PARAGRAPH", "STATEMENT", "COMMENT"]

def validate_semantic_ir(ir_or_path: Any) -> Dict[str, Any]:
    """
    Deterministically validates a SemanticIR object or JSON file against structural and semantic rules.
    """
    if isinstance(ir_or_path, str):
        if not os.path.isfile(ir_or_path):
            raise FileNotFoundError(f"IR file not found: {ir_or_path}")
        ir = SemanticIR.load(ir_or_path)
    elif isinstance(ir_or_path, SemanticIR):
        ir = ir_or_path
    else:
        raise TypeError(f"Expected SemanticIR instance or file path, got {type(ir_or_path)}")

    errors: List[str] = []
    warnings: List[str] = []

    program_nodes = []
    variable_nodes = []
    statement_nodes = []
    paragraph_nodes = []

    for nid, node in ir.nodes.items():
        if node.kind not in VALID_NODE_KINDS:
            errors.append(f"Node {nid} has invalid kind: '{node.kind}'")

        if node.kind == "PROGRAM":
            program_nodes.append(node)
            if not node.properties.get("program_id"):
                warnings.append(f"PROGRAM node {nid} missing 'program_id' property")

        elif node.kind in ("VARIABLE", "DATA_ITEM"):
            variable_nodes.append(node)
            name = node.properties.get("name")
            if not name:
                errors.append(f"Variable node {nid} is missing required 'name' property")
            level = node.properties.get("level")
            if level is None:
                errors.append(f"Variable node {nid} ({name}) is missing 'level' property")

        elif node.kind == "STATEMENT":
            statement_nodes.append(node)
            stype = node.properties.get("statement_type")
            if not stype:
                errors.append(f"Statement node {nid} is missing required 'statement_type' property")

        elif node.kind == "PARAGRAPH":
            paragraph_nodes.append(node)

        # Check source location
        if not node.source_file and node.kind != "COMMENT":
            warnings.append(f"Node {nid} has empty source_file")

    if not program_nodes:
        warnings.append("SemanticIR contains no PROGRAM root node")

    is_valid = len(errors) == 0

    return {
        "valid": is_valid,
        "errors_count": len(errors),
        "warnings_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "metrics": {
            "total_nodes": len(ir.nodes),
            "program_nodes": len(program_nodes),
            "variable_nodes": len(variable_nodes),
            "paragraph_nodes": len(paragraph_nodes),
            "statement_nodes": len(statement_nodes)
        }
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deterministic Semantic IR Validation Engine")
    parser.add_argument("ir_file", help="Path to semantic_ir.json")
    parser.add_argument("--out", "-o", help="Path to save validation output", default=None)
    args = parser.parse_args()

    res = validate_semantic_ir(args.ir_file)
    out_json = json.dumps(res, indent=2)

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(out_json)
        print(f"IR validation report saved to {args.out}")
    else:
        print(out_json)
    
    if not res["valid"]:
        sys.exit(1)
