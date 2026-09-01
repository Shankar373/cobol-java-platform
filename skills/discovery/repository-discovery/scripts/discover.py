import os
import sys
import json
import argparse
from typing import Dict, List, Any

def discover_repository(repo_dir: str) -> Dict[str, Any]:
    """
    Deterministically inspects target repository directory and extracts technology signatures,
    artifacts, entry points, and required skills.
    """
    repo_dir = os.path.abspath(repo_dir)
    if not os.path.isdir(repo_dir):
        raise FileNotFoundError(f"Target repository directory does not exist: {repo_dir}")

    cobol_sources = []
    copybooks = []
    jcl_files = []
    bms_maps = []
    sql_files = []
    technologies = set()
    blockers = []

    # Walk filesystem
    for root, dirs, files in os.walk(repo_dir):
        for f in files:
            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, repo_dir).replace("\\", "/")
            f_lower = f.lower()

            if f_lower.endswith((".cob", ".cbl", ".pco")):
                cobol_sources.append(rel_path)
            elif f_lower.endswith((".cpy", ".cpb", ".copy", ".cblcopy")) or "copybook" in rel_path.lower():
                copybooks.append(rel_path)
            elif f_lower.endswith((".jcl", ".job", ".cntl")):
                jcl_files.append(rel_path)
            elif f_lower.endswith((".map", ".bms")):
                bms_maps.append(rel_path)
            elif f_lower.endswith((".sql", ".ddl", ".dml")):
                sql_files.append(rel_path)

    if cobol_sources:
        technologies.add("COBOL")
    if copybooks:
        technologies.add("COPYBOOKS")
    if jcl_files:
        technologies.add("JCL")
    if bms_maps:
        technologies.add("BMS")
    if sql_files:
        technologies.add("SQL")

    # Content-based scanning
    for src in cobol_sources:
        full_src = os.path.join(repo_dir, src)
        try:
            with open(full_src, "r", encoding="utf-8", errors="ignore") as fh:
                content = fh.read().upper()
                if "EXEC SQL" in content:
                    technologies.add("SQL")
                    technologies.add("DB2")
                if "EXEC CICS" in content:
                    technologies.add("CICS")
                if "ORGANIZATION IS INDEXED" in content or "ACCESS MODE IS RANDOM" in content or "ACCESS MODE IS DYNAMIC" in content:
                    technologies.add("VSAM")
                if "REPORT SECTION" in content or " RD " in content:
                    technologies.add("REPORT_WRITER")
                if "DFHMSD" in content:
                    technologies.add("BMS")
                    if src not in bms_maps:
                        bms_maps.append(src)
                if any(x in content for x in ("CBLTDLI", "ASMTDLI", "PLITDLI", "EXEC DLI")):
                    technologies.add("IMS")
                    blockers.append(f"IMS/DLI hierarchical database usage detected in {src} (Unsupported natively)")
                if any(x in content for x in ("MQCONN", "MQOPEN", "MQPUT", "MQGET", "MQCLOSE", "MQDISC")):
                    technologies.add("MQ")
                    blockers.append(f"IBM MQ messaging API usage detected in {src} (Unsupported natively)")
                if "PROGRAM COLLATING SEQUENCE" in content and "EBCDIC" in content:
                    technologies.add("EBCDIC")
                    blockers.append(f"Mainframe EBCDIC collating sequence detected in {src} (Unsupported natively)")
        except Exception as e:
            blockers.append(f"Unreadable source file {src}: {e}")

    # Discover entry points
    entry_points = []
    config_path = os.path.join(repo_dir, "migration_config.json")
    if os.path.isfile(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as fh:
                cfg = json.load(fh)
                main_prog = cfg.get("main_program")
                if main_prog:
                    entry_points.append(main_prog)
        except Exception:
            pass

    if not entry_points and cobol_sources:
        # Default entry point heuristic: program not called by any other program, or first file
        entry_points.append(cobol_sources[0])

    unsupported_features = []
    if "IMS" in technologies:
        unsupported_features.append("IMS_DLI_DATABASE")
    if "MQ" in technologies:
        unsupported_features.append("IBM_MQ_MESSAGING")
    if "EBCDIC" in technologies:
        unsupported_features.append("EBCDIC_COLLATING_SEQUENCE")

    profile = {
        "repository_path": repo_dir,
        "technologies": sorted(list(technologies)),
        "artifacts": {
            "cobol_sources": sorted(cobol_sources),
            "copybooks": sorted(copybooks),
            "jcl_files": sorted(jcl_files),
            "bms_maps": sorted(bms_maps),
            "sql_files": sorted(sql_files)
        },
        "entry_points": entry_points,
        "unsupported_features": unsupported_features,
        "potential_blockers": blockers,
        "verification_requirements": [
            "MAVEN_BUILD_GATE",
            "STANDALONE_EXECUTION_GATE",
            "BEHAVIORAL_EQUIVALENCE_GATE"
        ]
    }
    return profile

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Universal Repository Discovery Engine")
    parser.add_argument("repo_dir", help="Path to repository root")
    parser.add_argument("--out", "-o", help="Path to save repository_profile.json", default=None)
    args = parser.parse_args()

    prof = discover_repository(args.repo_dir)
    out_json = json.dumps(prof, indent=2)

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(out_json)
        print(f"Repository profile saved to {args.out}")
    else:
        print(out_json)
