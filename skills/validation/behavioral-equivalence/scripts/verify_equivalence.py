import os
import sys
import json
import argparse
from typing import Dict, Any

from modernize.native_pipeline import NativePipeline

def verify_pipeline_equivalence(repo_dir: str, output_dir: str, target_source: str = None) -> Dict[str, Any]:
    """
    Deterministically delegates to NativePipeline to run the compilation, execution, and differential equivalence gates.
    """
    repo_dir = os.path.abspath(repo_dir)
    output_dir = os.path.abspath(output_dir)

    pipeline = NativePipeline(repo_dir, output_dir)
    pipeline.stage_discover()
    pipeline.stage_parse()

    selected_src = target_source or pipeline.stage_select_slice()
    if not selected_src:
        raise RuntimeError("No source program selected for equivalence verification")

    pipeline.stage_generate(selected_src)
    dep_ok = pipeline.stage_dependency_gate()
    build_ok = pipeline.stage_build_gate()

    exec_ok = False
    equiv_verdict = "NOT_RUN"
    neg_ok = False

    if build_ok:
        exec_ok = pipeline.stage_execute_gate(selected_src)
        if exec_ok:
            baseline_dir = os.path.join(output_dir, "baseline", "legacy")
            if os.path.isdir(baseline_dir) and os.listdir(baseline_dir):
                pipeline.baseline_verified = True
            equiv_verdict = pipeline.stage_equivalence_gate(selected_src)
            if equiv_verdict == "PASS":
                neg_ok = pipeline.stage_negative_equivalence(selected_src)

    return {
        "repository": repo_dir,
        "selected_source": selected_src,
        "dependency_gate": "PASS" if dep_ok else "FAIL",
        "build_gate": "PASS" if build_ok else "FAIL",
        "execute_gate": "PASS" if exec_ok else "FAIL",
        "equivalence_verdict": equiv_verdict,
        "negative_equivalence": "PASS" if neg_ok else "FAIL",
        "overall_status": "VERIFIED" if (equiv_verdict == "PASS" and neg_ok) else "NOT_VERIFIED"
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deterministic Behavioral Equivalence Verification Engine")
    parser.add_argument("repo_dir", help="Path to COBOL repository")
    parser.add_argument("output_dir", help="Path to pipeline output directory")
    parser.add_argument("--source", "-s", default=None, help="Target COBOL source file")
    parser.add_argument("--out", "-o", help="Path to save JSON verdict", default=None)
    args = parser.parse_args()

    res = verify_pipeline_equivalence(args.repo_dir, args.output_dir, args.source)
    out_json = json.dumps(res, indent=2)

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(out_json)
        print(f"Equivalence verification report saved to {args.out}")
    else:
        print(out_json)

    if res["overall_status"] != "VERIFIED":
        sys.exit(1)
