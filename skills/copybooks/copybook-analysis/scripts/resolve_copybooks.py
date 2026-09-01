import os
import sys
import re
import json
import argparse
from typing import Dict, List, Any

def resolve_copybooks_for_file(source_path: str, search_dirs: List[str]) -> Dict[str, Any]:
    """
    Deterministically identifies all COPY statements in a source file and resolves them to disk paths.
    """
    source_path = os.path.abspath(source_path)
    if not os.path.isfile(source_path):
        raise FileNotFoundError(f"Source file not found: {source_path}")

    # Build search directories
    all_search_dirs = [os.path.dirname(source_path)]
    for d in search_dirs:
        d_abs = os.path.abspath(d)
        if os.path.isdir(d_abs) and d_abs not in all_search_dirs:
            all_search_dirs.append(d_abs)

    # Scan for COPY statements
    with open(source_path, "r", encoding="utf-8", errors="replace") as fh:
        content = fh.read()

    copy_pattern = re.compile(r'\bCOPY\s+["\'\s]?([A-Za-z0-9\-\._/]+)["\'\s]?(?:\s*\.?)\s*', re.IGNORECASE)
    copy_names = []
    for m in copy_pattern.finditer(content):
        raw = m.group(1).strip("'\"").rstrip(".")
        if raw:
            copy_names.append(raw)

    copy_names = sorted(list(set(copy_names)))

    resolved = {}
    missing = []

    possible_exts = ["", ".cpy", ".CPY", ".cpb", ".CPB", ".cbl", ".CBL", ".cob", ".COB", ".copy", ".COPY"]

    for cname in copy_names:
        cname_base = os.path.basename(cname)
        found_path = None
        for sdir in all_search_dirs:
            # Check sdir directly, sdir parent, and sdir/copybooks
            search_roots = [sdir, os.path.dirname(sdir), os.path.join(sdir, "copybooks"), os.path.join(os.path.dirname(sdir), "copybooks")]
            for sroot in search_roots:
                if not os.path.isdir(sroot):
                    continue
                for name_variant in (cname, cname_base, cname_base.lower(), cname_base.upper()):
                    for ext in possible_exts:
                        target = os.path.join(sroot, name_variant + ext)
                        if os.path.isfile(target):
                            found_path = os.path.abspath(target)
                            break
                    if found_path:
                        break
                if found_path:
                    break
            if found_path:
                break

        if found_path:
            resolved[cname] = found_path
        else:
            missing.append(cname)

    return {
        "source_file": source_path,
        "copy_references_count": len(copy_names),
        "resolved_copybooks": resolved,
        "missing_copybooks": missing,
        "all_resolved": len(missing) == 0
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deterministic Copybook Resolution Engine")
    parser.add_argument("source_file", help="Path to COBOL source file")
    parser.add_argument("--search-dir", "-d", action="append", default=[], help="Copybook search directory")
    parser.add_argument("--out", "-o", help="Path to save JSON output", default=None)
    args = parser.parse_args()

    res = resolve_copybooks_for_file(args.source_file, args.search_dir)
    out_json = json.dumps(res, indent=2)

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(out_json)
        print(f"Copybook resolution saved to {args.out}")
    else:
        print(out_json)
