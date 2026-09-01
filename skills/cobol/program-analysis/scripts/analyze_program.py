import os
import sys
import json
import argparse
from typing import Dict, Any

from modernize.lexer import CobolLexer
from modernize.parser import CobolParser

def analyze_cobol_program(source_path: str, copybook_dirs: list = None) -> Dict[str, Any]:
    """
    Deterministically parses and analyzes a single COBOL program source file using CobolLexer & CobolParser.
    """
    source_path = os.path.abspath(source_path)
    if not os.path.isfile(source_path):
        raise FileNotFoundError(f"COBOL source file not found: {source_path}")

    with open(source_path, "r", encoding="utf-8", errors="replace") as fh:
        content = fh.read()

    lexer = CobolLexer(source_path, format_mode="auto")
    tokens = lexer.tokenize(content)

    parser = CobolParser(tokens, source_path)
    ir = parser.parse()

    # Summarize IR
    program_nodes = [n for n in ir.nodes.values() if n.kind == "PROGRAM"]
    variable_nodes = [n for n in ir.nodes.values() if n.kind in ("VARIABLE", "DATA_ITEM")]
    paragraph_nodes = [n for n in ir.nodes.values() if n.kind == "PARAGRAPH"]
    statement_nodes = [n for n in ir.nodes.values() if n.kind == "STATEMENT"]

    program_id = "UNKNOWN"
    if program_nodes:
        program_id = program_nodes[0].properties.get("name") or program_nodes[0].properties.get("program_id") or "UNKNOWN"
    calls = []
    exec_sqls = []
    exec_cics = []
    files_used = []

    for stmt in statement_nodes:
        stype = stmt.properties.get("statement_type", "")
        if stype == "CALL":
            target = stmt.properties.get("target", "")
            if target:
                calls.append(target)
        elif stype == "EXEC_SQL":
            exec_sqls.append(stmt.properties.get("sql_props", {}).get("verb", "SQL"))
        elif stype == "EXEC_CICS":
            exec_cics.append(stmt.properties.get("cics_props", {}).get("cics_type", "CICS"))

    summary = {
        "file": source_path,
        "program_id": program_id,
        "diagnostics_count": len(parser.diagnostics),
        "diagnostics": [str(d) for d in parser.diagnostics],
        "metrics": {
            "tokens_count": len(tokens),
            "total_nodes": len(ir.nodes),
            "variables_count": len(variable_nodes),
            "paragraphs_count": len(paragraph_nodes),
            "statements_count": len(statement_nodes)
        },
        "calls": sorted(list(set(calls))),
        "features": {
            "has_sql": len(exec_sqls) > 0,
            "sql_verbs": sorted(list(set(exec_sqls))),
            "has_cics": len(exec_cics) > 0,
            "cics_verbs": sorted(list(set(exec_cics)))
        }
    }
    return summary

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deterministic COBOL Program Analysis Engine")
    parser.add_argument("source_file", help="Path to .cob/.cbl source file")
    parser.add_argument("--copy-dir", action="append", default=[], help="Copybook directory (can specify multiple)")
    parser.add_argument("--out", "-o", help="Path to save analysis JSON", default=None)
    args = parser.parse_args()

    res = analyze_cobol_program(args.source_file, copybook_dirs=args.copy_dir)
    out_json = json.dumps(res, indent=2)

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(out_json)
        print(f"Analysis saved to {args.out}")
    else:
        print(out_json)
