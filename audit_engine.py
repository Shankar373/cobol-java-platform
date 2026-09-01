#!/usr/bin/env python3
"""Audit Engine - 22-point engineering audit for COBOL -> Java migration.

Reads a completed migration (state.json, manifest.json, generated Java)
and produces:
  target/audit-report.md
  target/audit-report.json

Also optionally runs all synthetic test repositories under tests/repos/.

Usage:
  python audit_engine.py [--repo legacy] [--out target]
                         [--run-synthetic]          # run repos A-G
                         [--skip-docker]            # skip Docker-dependent checks
"""

import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))

# Import pipeline helpers (no Docker calls needed here)
sys.path.insert(0, ROOT)
import cobol_migrate as engine

# ---------------------------------------------------------------------------
# Automatic vs Manual matrix — ground truth from code inspection
# ---------------------------------------------------------------------------
AUTO_MANUAL_MATRIX = [
    # (capability, automatic, evidence)
    ("Repository discovery (*.cob/*.cbl)",       "AUTOMATIC", "discover_sources() walks tree by extension"),
    ("COPY dependency extraction",               "AUTOMATIC", "extract_copy_deps() regex on source text"),
    ("COPYBOOK directory discovery",             "AUTOMATIC", "discover_copybook_dirs() walks for .cpy files"),
    ("Missing COPYBOOK detection",               "AUTOMATIC", "check_copybook_coverage() before transpile"),
    ("Static CALL dependency graph",             "AUTOMATIC", "extract_call_deps() static pattern"),
    ("Dynamic CALL resolution",                  "MANUAL",    "DYNAMIC_CALL_REQUIRES_REVIEW — cannot resolve statically"),
    ("FILE / SELECT..ASSIGN discovery",          "AUTOMATIC", "extract_file_assigns() regex on source text"),
    ("Free/fixed format detection",              "AUTOMATIC", "detect_format() checks line length > 72"),
    ("Source immutability (SHA-256)",            "AUTOMATIC", "compute_source_hashes() at ingest; verify_source_immutability() at report"),
    ("Source modification (normalization)",      "MANUAL",    "Original files never touched; normalized/ layer if needed"),
    ("cobj transpilation",                       "AUTOMATIC", "Docker: opensourcecobol/opensourcecobol4j:2.0.0"),
    ("Java stub detection",                      "AUTOMATIC", "is_stub_java() checks for cobj runtime imports"),
    ("Artifact provenance (per-file hash)",      "AUTOMATIC", "manifest.json records source->Java->class chain with SHA-256"),
    ("libcobj.jar vendoring",                    "AUTOMATIC", "preserve_runtime() copies from Docker image"),
    ("GnuCOBOL baseline execution",             "AUTOMATIC", "stage_baseline() via Docker"),
    ("Java execution",                           "AUTOMATIC", "stage_execute() via Docker"),
    ("Byte-level output comparison",             "AUTOMATIC", "stage_compare() exact mode"),
    ("Normalized text comparison",               "AUTOMATIC", "stage_compare() normalized mode"),
    ("Logical indexed-file comparison",          "AUTOMATIC", "logical_indexed_compare() reads SQLite"),
    ("Semantic / COMP-3 validation",             "AUTOMATIC", "run_checks() decodes packed decimal"),
    ("Partial failure detection",                "AUTOMATIC", "_compute_verdict() checks n_ok < n_total"),
    ("Checkpoint / resume",                      "AUTOMATIC", "stage_done() gate + state.json per stage"),
    ("Migration report generation",              "AUTOMATIC", "write_report() produces .md + .json"),
    ("Archive",                                  "AUTOMATIC", "stage_package() creates modernized-package.zip"),
    ("Unsupported mainframe utility (SORT etc)", "MANUAL",    "cobj may not support all JCL/utility calls"),
    ("Source refactoring (bug fixes)",           "MANUAL",    "Never automatic; must be declared in manual_source_modifications"),
]


# ---------------------------------------------------------------------------
def load(path, default=None):
    return engine.load_json(path, default)


def h(text):
    """Escape markdown special chars."""
    return str(text).replace("|", "\\|").replace("*", "\\*")


# ---------------------------------------------------------------------------
def audit_source_inventory(repo_dir, state, cfg):
    """Section A/B: source inventory + hashes."""
    disc = state.get("data", {}).get("discover", {})
    ingest_hashes = state.get("data", {}).get("ingest_hashes", {})
    sources = disc.get("sources", [])
    copybooks = disc.get("all_copybooks", [])

    rows = []
    for s in sources:
        pid = disc.get("program_ids", {}).get(s, "?")
        h_val = ingest_hashes.get(s, "unknown")
        rows.append({"file": s, "type": "SOURCE", "program_id": pid, "hash": h_val})
    for cp in copybooks:
        h_val = ingest_hashes.get(cp, "unknown")
        rows.append({"file": cp, "type": "COPYBOOK", "program_id": "", "hash": h_val})
    return rows


def audit_immutability(repo_dir, state):
    """Section C: source immutability verification."""
    stored = state.get("data", {}).get("ingest_hashes", {})
    if not stored:
        return [], "NO_BASELINE"
    results = engine.verify_source_immutability(repo_dir, stored)
    status = "IMMUTABLE" if all(r["status"] == "IMMUTABLE" for r in results) else "MODIFIED"
    return results, status


def audit_format_detection(state):
    """Section D: COBOL format detection."""
    disc = state.get("data", {}).get("discover", {})
    return {
        "detected": disc.get("format", "unknown"),
        "method": "line-length > 72 heuristic",
        "sources": disc.get("sources", []),
    }


def audit_copy_graph(state):
    """Section E: COPYBOOK dependency graph."""
    disc = state.get("data", {}).get("discover", {})
    return {
        "copy_deps": disc.get("copy_deps", {}),
        "coverage": disc.get("copybook_coverage", {}),
        "missing": disc.get("missing_copybooks", []),
        "dirs": disc.get("copybook_dirs", []),
    }


def audit_call_graph(state):
    """Section F: CALL dependency graph."""
    disc = state.get("data", {}).get("discover", {})
    return disc.get("call_graph", {"graph": {}, "roots": [], "dynamic_callers": []})


def audit_file_assigns(state):
    """Section G: FILE / SELECT..ASSIGN dataset map."""
    disc = state.get("data", {}).get("discover", {})
    return disc.get("file_assigns", {})


def audit_entry_point(state):
    """Section H: entry point analysis."""
    disc = state.get("data", {}).get("discover", {})
    cg = disc.get("call_graph", {})
    entry = disc.get("entry", "unknown")
    roots = cg.get("roots", [])
    status = "AUTO_DETECTED"
    if len(roots) > 1:
        status = "MULTIPLE_CANDIDATES"
    elif not roots:
        status = "NO_ROOT_DETECTED"
    return {"entry": entry, "roots": roots, "status": status}


def audit_cobj_invocation(state):
    """Section I: exact cobj Docker invocation."""
    tr = state.get("data", {}).get("transpile", {})
    return {
        "image": tr.get("image", engine.DEFAULT_COBJ_IMAGE),
        "digest": tr.get("image_digest", "unknown"),
        "flags": tr.get("cobj_flags", []),
        "command": tr.get("docker_command", "not recorded"),
        "rc": tr.get("all_at_once_rc", "?"),
        "n_ok": tr.get("n_ok", 0),
        "n_total": tr.get("n_total", 0),
        "status": tr.get("status", {}),
    }


def audit_java_inventory(out_dir, state):
    """Section J/K: generated Java + class inventory."""
    co = state.get("data", {}).get("collect", {})
    manifest = load(os.path.join(out_dir, "manifest.json"), {})
    provenance = manifest.get("programs", [])
    stub_flags = co.get("stub_flags", {})

    items = []
    for p in provenance:
        java_path = os.path.join(out_dir, "generated", p.get("java_file") or "")
        class_path = os.path.join(out_dir, "generated", p.get("class_file") or "")
        items.append({
            "source": p["source"],
            "program_id": p["program_id"],
            "java_file": p.get("java_file"),
            "java_exists": os.path.isfile(java_path) if p.get("java_file") else False,
            "java_hash": p.get("java_hash"),
            "class_exists": os.path.isfile(class_path) if p.get("class_file") else False,
            "stub_detected": p["program_id"] + ".java" in stub_flags,
            "transpiled": p.get("transpiled", False),
        })
    return items


def audit_business_logic(out_dir, state):
    """Section N: check generated Java for real business logic (not stubs)."""
    co = state.get("data", {}).get("collect", {})
    java_files = co.get("java_files", [])
    results = []
    for jf in java_files:
        path = os.path.join(out_dir, "generated", jf)
        if not os.path.isfile(path):
            results.append({"file": jf, "status": "MISSING"})
            continue
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        is_stub = engine.is_stub_java(text)
        # Count real cobj patterns
        real_count = sum(1 for sig in [
            "CobolDataStorage", "CobolRunnable", "jp.osscons", "libcobj"
        ] if sig in text)
        results.append({
            "file": jf,
            "status": "STUB" if is_stub else "REAL",
            "cobj_signals": real_count,
            "loc": text.count("\n"),
            "has_generated_comment": "Generated by opensource COBOL 4J" in text[:200],
        })
    return results


def audit_behavioral_comparison(state):
    """Section K/L/M: behavioral validation results."""
    cmp = state.get("data", {}).get("compare", {})
    checks = cmp.get("checks", [])
    rows = cmp.get("rows", [])

    exact = sum(1 for r in rows if r["verdict"] == "exact")
    baseline_only = sum(1 for r in rows if r["verdict"] == "baseline-only")
    java_only = sum(1 for r in rows if r["verdict"] == "java-only")
    differ = sum(1 for r in rows if r["verdict"] == "differ")
    logical_match = sum(1 for r in rows
                       if r.get("logical", {}) and
                          r.get("logical", {}).get("verdict") == "LOGICAL_MATCH")

    checks_pass = sum(1 for c in checks if c["ok"])
    checks_total = len(checks)

    return {
        "exact_matches": exact,
        "baseline_only": baseline_only,
        "java_only": java_only,
        "differs": differ,
        "logical_matches": logical_match,
        "semantic_checks_pass": checks_pass,
        "semantic_checks_total": checks_total,
        "all_semantic_pass": checks_pass == checks_total,
        "rows": rows,
        "checks": checks,
    }


def compute_final_verdict(state, imm_status, java_inventory, beh):
    """Section R: final verdict."""
    tr = state.get("data", {}).get("transpile", {})
    n_ok = tr.get("n_ok", 0)
    n_total = tr.get("n_total", 0)

    issues = []

    # Stubs
    stubs = [j for j in java_inventory if j["status"] == "STUB"]
    if stubs:
        issues.append(f"Java stub detected in {len(stubs)} file(s)")

    # Source modified
    if imm_status == "MODIFIED":
        issues.append("Source files MODIFIED since ingest (undocumented)")

    # Partial transpilation
    if n_ok < n_total and n_total > 0:
        issues.append(f"Partial transpilation: {n_ok}/{n_total} programs compiled")

    # Semantic check failures
    if not beh["all_semantic_pass"]:
        issues.append(f"Semantic checks: {beh['semantic_checks_pass']}/{beh['semantic_checks_total']} passed")

    # Output differences (non-logical)
    hard_differs = [r for r in beh["rows"]
                   if r["verdict"] == "differ" and
                      not (r.get("logical") and r.get("logical", {}).get("verdict") == "LOGICAL_MATCH")]
    if hard_differs:
        issues.append(f"{len(hard_differs)} output file(s) differ with no logical equivalence")

    # File-set mismatches: an output file present on only one side means the
    # migration dropped or invented an artifact — never GREEN.
    if beh.get("baseline_only"):
        issues.append(f"{beh['baseline_only']} baseline output file(s) missing from Java results")
    if beh.get("java_only"):
        issues.append(f"{beh['java_only']} Java-only output file(s) not produced by baseline")

    if not issues:
        verdict = "AUTOMATED AND VERIFIED"
        color = "GREEN"
    elif all("MODIFIED" not in i and "stub" not in i.lower() for i in issues):
        verdict = "AUTOMATED WITH LIMITATIONS"
        color = "YELLOW"
    else:
        verdict = "MANUAL INTERVENTION REQUIRED"
        color = "RED"

    return {"verdict": verdict, "color": color, "issues": issues}


# ---------------------------------------------------------------------------
def run_synthetic_test(repo_path, repo_name, skip_docker=False):
    """Run discover (and optionally transpile) for a synthetic repo.
    Returns a summary dict."""
    out_path = os.path.join(ROOT, "tests", "out", repo_name)
    os.makedirs(out_path, exist_ok=True)

    cfg = {}
    cfg_path = os.path.join(repo_path, "migration_config.json")
    if os.path.isfile(cfg_path):
        cfg = engine.load_json(cfg_path, {}) or {}

    p = engine.Pipeline(repo_path, out_path, cfg=cfg, pull=False)
    result = {"repo": repo_name, "path": repo_path, "stages": {}}

    try:
        # Always run ingest + discover (no Docker)
        _idx_ingest   = engine.STAGES.index("ingest")
        _idx_discover = engine.STAGES.index("discover")
        _idx_transpile = engine.STAGES.index("transpile")
        _idx_execute  = engine.STAGES.index("execute")

        ok, detail, _ = p.stage_ingest()
        p.mark(_idx_ingest, "done" if ok else "error", detail)
        result["stages"]["ingest"] = {"ok": ok, "detail": detail}

        if ok:
            ok2, detail2, _ = p.stage_discover()
            p.mark(_idx_discover, "done" if ok2 else "error", detail2)
            result["stages"]["discover"] = {"ok": ok2, "detail": detail2}
            disc = p.data("discover", {})
            result["programs"] = len(disc.get("sources", []))
            result["missing_copybooks"] = disc.get("missing_copybooks", [])
            result["call_graph"] = disc.get("call_graph", {})
            result["format"] = disc.get("format", "?")
            result["entry"] = disc.get("entry", "?")

        if skip_docker:
            result["transpile"] = {"ok": None, "detail": "SKIPPED — DOCKER UNAVAILABLE"}
        elif ok and ok2:
            if not engine.docker_available():
                result["transpile"] = {"ok": None, "detail": "SKIPPED — DOCKER UNAVAILABLE"}
            else:
                ok3, detail3, _ = p.stage_transpile()
                p.mark(_idx_transpile, "done" if ok3 else "error", detail3)
                tr = p.data("transpile", {})
                result["transpile"] = {
                    "ok": ok3,
                    "detail": detail3,
                    "n_ok": tr.get("n_ok", 0),
                    "n_total": tr.get("n_total", 0),
                    "status": tr.get("status", {}),
                }
                runtime_scaffold = (os.path.isdir(os.path.join(out_path, "generated"))
                                    and os.path.isfile(os.path.join(out_path, "libcobj.jar")))
                if ok3 and tr.get("n_ok", 0) > 0 and runtime_scaffold:
                    try:
                        ok5, detail5, _ = p.stage_execute()
                        p.mark(_idx_execute, "done" if ok5 else "error", detail5)
                        result["execute"] = {"ok": ok5, "detail": detail5}
                    except Exception as exc:
                        result["execute"] = {"ok": False, "detail": str(exc)}
                elif ok3 and tr.get("n_ok", 0) > 0:
                    result["execute"] = {"ok": None,
                                         "detail": "skipped — runtime vendoring (libcobj.jar) not built for synthetic repo"}
    except Exception as exc:
        result["error"] = str(exc)

    return result


# ---------------------------------------------------------------------------
def write_audit_report(out_dir, audit_data):
    """Write audit-report.md and audit-report.json."""
    md = []
    j = audit_data  # convenience alias

    md.append("# COBOL → Java Pipeline — Engineering Audit Report\n")
    md.append(f"- **run at**: {engine.now_iso()} (UTC)")
    md.append(f"- **repo**: `{j['repo']}`")
    md.append(f"- **target**: `{j['target']}`")

    verdict = j.get("final_verdict", {})
    color_emoji = {"GREEN": "🟢", "YELLOW": "🟡", "RED": "🔴"}.get(verdict.get("color"), "⚪")
    md.append("\n## Final Verdict\n")
    md.append(f"### {color_emoji} {verdict.get('verdict', 'UNKNOWN')}\n")
    if verdict.get("issues"):
        for issue in verdict["issues"]:
            md.append(f"- ⚠️ {issue}")
    else:
        md.append("- ✅ No issues detected.")
    md.append("")

    # A. Source inventory
    md.append("## A. Source Inventory\n")
    md.append("| file | type | PROGRAM-ID | SHA-256 (first 16) |")
    md.append("|---|---|---|---|")
    for r in j.get("source_inventory", []):
        h16 = (r["hash"] or "unknown")[:16]
        md.append(f"| {r['file']} | {r['type']} | {r.get('program_id','')} | `{h16}...` |")
    md.append("")

    # B. Source immutability
    md.append("## B. Source Immutability\n")
    imm_rows = j.get("immutability", [])
    imm_status = j.get("immutability_status", "NO_BASELINE")
    md.append(f"**Overall status: {imm_status}**\n")
    if imm_rows:
        md.append("| file | ingest hash | current hash | status |")
        md.append("|---|---|---|---|")
        for r in imm_rows:
            ih = (r.get("ingest_hash") or "")[:16]
            ch = (r.get("current_hash") or "N/A")[:16]
            s = r["status"]
            icon = "✅" if s == "IMMUTABLE" else ("❌" if s == "MODIFIED" else "⚠️")
            md.append(f"| {r['file']} | `{ih}...` | `{ch}...` | {icon} **{s}** |")
    md.append("")

    # C. Format detection
    fmt = j.get("format_detection", {})
    md.append("## C. COBOL Format Detection\n")
    md.append(f"- Detected format: **{fmt.get('detected','?')}**")
    md.append(f"- Method: {fmt.get('method','?')}\n")

    # D. COPYBOOK dependency graph
    cp = j.get("copy_graph", {})
    md.append("## D. COPYBOOK Dependency Graph\n")
    for src, copies in cp.get("copy_deps", {}).items():
        if copies:
            md.append(f"**{src}**")
            cov = cp.get("coverage", {}).get(src, {})
            found_map = {f["ref"]: f["path"] for f in cov.get("found", [])}
            for c in copies:
                p_path = found_map.get(c) or found_map.get(c.upper())
                icon = "✅" if p_path else "❌"
                md.append(f"  - COPY `{c}` {icon} {'→ `' + p_path + '`' if p_path else '→ MISSING'}")
    if cp.get("missing"):
        md.append(f"\n> ❌ **{len(cp['missing'])} missing copybook reference(s)**")
    md.append("")

    # E. CALL dependency graph
    cg = j.get("call_graph", {})
    md.append("## E. CALL Dependency Graph\n")
    graph = cg.get("graph", {})
    roots = cg.get("roots", [])
    dyn = cg.get("dynamic_callers", [])
    if graph:
        for prog, deps in graph.items():
            if deps.get("static") or deps.get("dynamic"):
                md.append(f"**{prog}**")
                for s in deps.get("static", []):
                    md.append(f"  - CALL `{s}` (static)")
                for d in deps.get("dynamic", []):
                    md.append(f"  - CALL `{d}` (**DYNAMIC** — manual review required)")
    md.append(f"\n- Entry roots (no callers): `{roots}`")
    if dyn:
        md.append(f"- Dynamic callers (require review): `{dyn}`")
    md.append("")

    # F. FILE/dataset map
    md.append("## F. File / Dataset Dependency Map\n")
    fas = j.get("file_assigns", {})
    any_assigns = any(fas.values())
    if any_assigns:
        md.append("| source | logical name | assign path | organization |")
        md.append("|---|---|---|---|")
        for src, assigns in fas.items():
            for a in assigns:
                md.append(f"| {src} | {a['logical_name']} | `{a['assign_path']}` "
                          f"| {a.get('organization','?')} |")
    else:
        md.append("_No SELECT…ASSIGN statements found._")
    md.append("")

    # G. Entry point
    ep = j.get("entry_point", {})
    md.append("## G. Entry Point Analysis\n")
    md.append(f"- Configured entry: **`{ep.get('entry','?')}`**")
    md.append(f"- Call-graph roots: `{ep.get('roots', [])}`")
    md.append(f"- Status: **{ep.get('status','?')}**\n")

    # H. cobj invocation
    ci = j.get("cobj_invocation", {})
    md.append("## H. Exact cobj Docker Invocation\n")
    md.append(f"- Image: `{ci.get('image','?')}`")
    md.append(f"- Digest: `{ci.get('digest','?')}`")
    md.append(f"- Flags: `{ci.get('flags', [])}`")
    md.append(f"- RC: `{ci.get('rc','?')}`")
    md.append(f"- Programs: {ci.get('n_ok','?')}/{ci.get('n_total','?')} compiled")
    if ci.get("command"):
        md.append(f"\n```\n{ci['command']}\n```\n")

    # I. Generated Java inventory
    md.append("## I. Generated Java Inventory\n")
    md.append("| source | PROGRAM-ID | Java file | Java hash | .class | transpiled | logic |")
    md.append("|---|---|---|---|---|---|---|")
    for item in j.get("java_inventory", []):
        jh = (item.get("java_hash") or "")[:16]
        stub = "⚠️ STUB" if item.get("stub_detected") else "✅ REAL"
        trans = "✅" if item.get("transpiled") else "❌"
        cls = "✅" if item.get("class_exists") else "❌"
        md.append(f"| {item['source']} | {item['program_id']} | "
                  f"{item.get('java_file','—')} | `{jh}...` | {cls} | {trans} | {stub} |")
    md.append("")

    # J. Business logic verification
    md.append("## J. Business Logic Verification\n")
    md.append("| Java file | status | cobj signals | LOC | generated header |")
    md.append("|---|---|---|---|---|")
    for bl in j.get("business_logic", []):
        icon = "✅ REAL" if bl["status"] == "REAL" else "❌ STUB"
        hdr = "✅" if bl.get("has_generated_comment") else "❌"
        md.append(f"| {bl['file']} | {icon} | {bl.get('cobj_signals',0)} | "
                  f"{bl.get('loc',0)} | {hdr} |")
    md.append("")

    # K. Behavioral comparison
    beh = j.get("behavioral_comparison", {})
    md.append("## K. Behavioral Validation\n")
    md.append(f"- Exact byte matches: **{beh.get('exact_matches',0)}**")
    md.append(f"- Normalized matches: **{beh.get('normalized_matches',0)}**")
    md.append(f"- Logical matches: **{beh.get('logical_matches',0)}** (indexed file SQLite vs GnuCOBOL)")
    md.append(f"- Hard differs: **{beh.get('differs',0)}**")
    md.append(f"- Semantic checks: **{beh.get('semantic_checks_pass',0)}/{beh.get('semantic_checks_total',0)}** pass\n")
    if beh.get("checks"):
        for c in beh["checks"]:
            icon = "✅" if c["ok"] else "❌"
            md.append(f"- {icon} `{c['name']}` ({c['kind']}): "
                      f"expected `{c['expected']}` → actual `{c.get('actual')}`")
    md.append("")

    # L. Automatic vs Manual matrix
    md.append("## L. Automatic vs Manual Operation Matrix\n")
    md.append("| Capability | Automatic? | Evidence |")
    md.append("|---|---|---|")
    for cap, auto, ev in AUTO_MANUAL_MATRIX:
        icon = "✅ AUTO" if auto == "AUTOMATIC" else "⚠️ MANUAL"
        md.append(f"| {cap} | {icon} | {ev} |")
    md.append("")

    # M. Synthetic repository results
    md.append("## M. Synthetic Repository Results\n")
    synth = j.get("synthetic_results", [])
    if synth:
        md.append("| repo | programs | entry | format | missing copybooks | transpile | execute | result |")
        md.append("|---|---|---|---|---|---|---|---|")
        for r in synth:
            tr = r.get("transpile", {})
            n_ok = tr.get("n_ok", "—")
            n_tot = tr.get("n_total", "—")
            tr_str = f"{n_ok}/{n_tot}" if tr.get("ok") is not None else tr.get("detail","?")
            missing = len(r.get("missing_copybooks", []))
            disc_ok = r.get("stages", {}).get("discover", {}).get("ok", False)
            ex = r.get("execute", {})
            exec_ok = ex.get("ok")
            # PASS reflects discovery AND (when attempted) transpile + execute.
            ok_flags = [disc_ok]
            if tr.get("ok") is not None:
                # Transpile counts as OK only when it ran AND produced Java.
                ok_flags.append(bool(tr.get("ok")) and (tr.get("n_ok", 0) > 0))
            if exec_ok is not None:
                ok_flags.append(bool(exec_ok))
            result_icon = "✅" if all(ok_flags) else "❌"
            ex_label = "✅" if exec_ok is True else ("—" if exec_ok is None else "❌")
            md.append(f"| {r['repo']} | {r.get('programs','?')} | "
                      f"`{r.get('entry','?')}` | {r.get('format','?')} | "
                      f"{missing} | {tr_str} | {ex_label} | {result_icon} |")
    else:
        md.append("_Synthetic tests not run. Use `--run-synthetic` flag._")
    md.append("")

    # N. Remaining limitations (evidence-driven; repo-specific facts are
    # reported from the immutability audit rather than hardcoded narratives)
    md.append("## N. Remaining Limitations\n")
    md.append("- Dynamic CALL targets cannot be statically resolved (require runtime analysis)")
    md.append("- Physical byte comparison of indexed files is excluded (different backends)")
    if imm_rows and any(r.get("status") == "MODIFIED" for r in imm_rows):
        for r in imm_rows:
            if r.get("status") == "MODIFIED":
                md.append(f"- `{r.get('file', '?')}` contains a **MANUAL SOURCE MODIFICATION** "
                          f"(detected by ingest hash comparison)")
        md.append("  - Recommendation: maintain `original/` and `patched/` layers for future repos")
    md.append("- libcobj.jar runtime tied to COBOL 4J 2.0.0 Docker image")
    md.append("- No JCL/utility (SORT, IDCAMS) support in cobj transpiler")
    md.append("")

    with open(os.path.join(out_dir, "audit-report.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(md))

    with open(os.path.join(out_dir, "audit-report.json"), "w", encoding="utf-8") as fh:
        json.dump(audit_data, fh, indent=2, default=str)

    print(f"audit-report.md  -> {os.path.join(out_dir, 'audit-report.md')}")
    print(f"audit-report.json -> {os.path.join(out_dir, 'audit-report.json')}")


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--config", default="migration_config.json")
    ap.add_argument("--run-synthetic", action="store_true")
    ap.add_argument("--skip-docker", action="store_true")
    args = ap.parse_args()

    cfg = engine.load_json(args.config, {}) or {}
    repo = os.path.abspath(args.repo or cfg.get("repo") or os.path.join(ROOT, "legacy"))
    out  = os.path.abspath(args.out  or cfg.get("out")  or os.path.join(ROOT, "target"))

    state_path = os.path.join(out, "state.json")
    state = load(state_path, {}) or {}
    if not state.get("stages"):
        print(f"ERROR: no state.json found at {state_path}")
        print("Run cobol_migrate.py first to complete the pipeline.")
        sys.exit(1)

    print(f"Auditing: repo={repo}  target={out}")

    # Run all audit sections
    inventory       = audit_source_inventory(repo, state, cfg)
    imm_rows, imm_s = audit_immutability(repo, state)
    fmt_det         = audit_format_detection(state)
    copy_graph      = audit_copy_graph(state)
    call_graph      = audit_call_graph(state)
    file_assigns    = audit_file_assigns(state)
    entry_pt        = audit_entry_point(state)
    cobj_inv        = audit_cobj_invocation(state)
    java_inv        = audit_java_inventory(out, state)
    biz_logic       = audit_business_logic(out, state)
    beh             = audit_behavioral_comparison(state)
    final_verdict   = compute_final_verdict(state, imm_s, biz_logic, beh)

    # Synthetic tests
    synth_results = []
    if args.run_synthetic:
        synth_base = os.path.join(ROOT, "tests", "repos")
        if os.path.isdir(synth_base):
            for repo_name in sorted(os.listdir(synth_base)):
                repo_path = os.path.join(synth_base, repo_name)
                if os.path.isdir(repo_path):
                    print(f"  synthetic: {repo_name} ...")
                    r = run_synthetic_test(repo_path, repo_name, args.skip_docker)
                    synth_results.append(r)
                    ok_flags = [r.get("stages", {}).get("discover", {}).get("ok")]
                    tr_ok = r.get("transpile", {}).get("ok")
                    if tr_ok is not None:
                        ok_flags.append(bool(tr_ok))
                    ex_ok = r.get("execute", {}).get("ok")
                    if ex_ok is not None:
                        ok_flags.append(bool(ex_ok))
                    verdict_icon = "PASS" if all(ok_flags) else "FAIL"
                    print(f"    -> {verdict_icon}: {r.get('stages',{}).get('discover',{}).get('detail','?')}")

    audit_data = {
        "repo": repo,
        "target": out,
        "audit_at": engine.now_iso(),
        "source_inventory": inventory,
        "immutability": imm_rows,
        "immutability_status": imm_s,
        "format_detection": fmt_det,
        "copy_graph": copy_graph,
        "call_graph": call_graph,
        "file_assigns": file_assigns,
        "entry_point": entry_pt,
        "cobj_invocation": cobj_inv,
        "java_inventory": java_inv,
        "business_logic": biz_logic,
        "behavioral_comparison": beh,
        "auto_manual_matrix": AUTO_MANUAL_MATRIX,
        "synthetic_results": synth_results,
        "final_verdict": final_verdict,
    }

    write_audit_report(out, audit_data)

    print(f"\nFinal Verdict: {final_verdict['color']} - {final_verdict['verdict']}")
    if final_verdict["issues"]:
        for issue in final_verdict["issues"]:
            print(f"  [WARN] {issue}")


if __name__ == "__main__":
    main()
