import os
import sys
import json
import argparse
from typing import Dict, Any

from modernize.native_pipeline import NativePipeline
from modernize.native_generator import NativeProgramGenerator
from modernize.semantic_ir import SemanticIR

def execute_native_java_generation(repo_dir: str, output_dir: str, target_source: str = None) -> Dict[str, Any]:
    """
    Deterministically drives NativePipeline and NativeProgramGenerator to produce Track-B Java output.
    """
    repo_dir = os.path.abspath(repo_dir)
    output_dir = os.path.abspath(output_dir)

    pipeline = NativePipeline(repo_dir, output_dir)
    pipeline.stage_discover()
    pipeline.stage_parse()

    if target_source:
        selected_src = target_source
    else:
        selected_src = pipeline.stage_select_slice()

    if not selected_src:
        raise RuntimeError("No suitable COBOL source file could be selected for Java generation")

    pipeline.stage_generate(selected_src)
    dep_ok = pipeline.stage_dependency_gate()

    generated_files = []
    for root, dirs, files in os.walk(pipeline.src_dir):
        for f in files:
            if f.endswith(".java"):
                generated_files.append(os.path.relpath(os.path.join(root, f), pipeline.src_dir))

    return {
        "repository": repo_dir,
        "output_dir": output_dir,
        "selected_source": selected_src,
        "dependency_gate_passed": dep_ok,
        "generated_classes_count": len(generated_files),
        "generated_files": sorted(generated_files)
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deterministic Native Java Generator Driver")
    parser.add_argument("repo_dir", help="Path to COBOL repository")
    parser.add_argument("output_dir", help="Path to output directory")
    parser.add_argument("--source", "-s", default=None, help="Specific source file to translate")
    parser.add_argument("--out", "-o", help="Path to save JSON generation metadata", default=None)
    args = parser.parse_args()

    res = execute_native_java_generation(args.repo_dir, args.output_dir, args.source)
    out_json = json.dumps(res, indent=2)

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(out_json)
        print(f"Generation report saved to {args.out}")
    else:
        print(out_json)
