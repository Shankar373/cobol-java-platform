"""Detect whether a COBOL entry point's reachable code contains interactive ACCEPT statements.

Classification:
    NON_INTERACTIVE  — no stdin-consuming ACCEPT found in reachable call graph
    INTERACTIVE      — at least one stdin-consuming ACCEPT found
    UNKNOWN          — analysis inconclusive (e.g. dynamic CALLs prevent full traversal)

Rules for ACCEPT classification (per approved spec):
    ACCEPT <var>                          → potentially INTERACTIVE
    ACCEPT <var> FROM DATE                → NON_INTERACTIVE (system clock)
    ACCEPT <var> FROM TIME                → NON_INTERACTIVE (system clock)
    ACCEPT <var> FROM DAY                 → NON_INTERACTIVE (system clock)
    ACCEPT <var> FROM DAY-OF-WEEK        → NON_INTERACTIVE (system clock)
    ACCEPT <var> FROM ENVIRONMENT-VALUE  → NON_INTERACTIVE (environment)
    ACCEPT <var> FROM COMMAND-LINE       → NON_INTERACTIVE (argument)

Any ACCEPT without a recognized non-interactive FROM clause is classified as
potentially requiring stdin input.
"""

import os
import re

# Matches:  ACCEPT <identifier> [FROM <source>]
# Group 1 = identifier, Group 2 = FROM source (optional)
_RE_ACCEPT = re.compile(
    r'\bACCEPT\s+(\S+)'          # ACCEPT <identifier>
    r'(?:\s+FROM\s+(\S+))?',     # optional FROM <source>
    re.IGNORECASE,
)

# These FROM sources do NOT consume stdin — they read system clock/environment
_NON_INTERACTIVE_FROM = frozenset({
    "DATE",
    "TIME",
    "DAY",
    "DAY-OF-WEEK",
    "ENVIRONMENT",
    "ENVIRONMENT-VALUE",
    "COMMAND-LINE",
    "ARGUMENT-NUMBER",
    "ARGUMENT-VALUE",
    "STDIN",            # explicitly named STDIN is still interactive but rare
})
# STDIN is intentionally not in the non-interactive set; it IS interactive.

_STDIN_SOURCES = frozenset({"STDIN"})

# Identifier names that are clearly data definitions, not ACCEPT targets
# (avoids false positives from COBOL keywords appearing after ACCEPT)
_COBOL_KEYWORDS = frozenset({
    "DIVISION", "SECTION", "PROGRAM-ID", "ENVIRONMENT", "CONFIGURATION",
    "INPUT-OUTPUT", "FILE", "WORKING-STORAGE", "LINKAGE", "PROCEDURE",
    "IDENTIFICATION",
})


def _is_interactive_accept(identifier: str, from_source: str | None) -> bool:
    """Return True if this ACCEPT statement consumes user stdin."""
    id_upper = identifier.upper().rstrip(".")
    if id_upper in _COBOL_KEYWORDS:
        return False  # parser false positive

    if from_source is None:
        return True   # bare ACCEPT → stdin

    src_upper = from_source.upper().rstrip(".")
    if src_upper in _STDIN_SOURCES:
        return True
    if src_upper in _NON_INTERACTIVE_FROM:
        return False
    # Unknown FROM source — conservatively classify as interactive
    return True


def _sources_reachable_from(entry: str, call_graph: dict, program_ids: dict) -> set:
    """BFS over call_graph to collect all source files reachable from entry.

    call_graph is the dict stored in state["data"]["discover"]["call_graph"].
    program_ids is the dict {source_relpath: program_id}.

    ponytail: linear BFS is fine; call graphs in COBOL repos are small.
    """
    # Build reverse map: program_id → source_relpath
    id_to_src = {v.upper(): k for k, v in program_ids.items()}
    # Adjacency: program_id → [called program_id, ...]
    edges = call_graph.get("edges", {})

    entry_upper = entry.upper()
    visited_ids = set()
    queue = [entry_upper]
    while queue:
        pid = queue.pop()
        if pid in visited_ids:
            continue
        visited_ids.add(pid)
        for callee in edges.get(pid, []):
            callee_up = callee.upper()
            if callee_up not in visited_ids:
                queue.append(callee_up)

    # Map back to source paths
    reachable = set()
    for pid in visited_ids:
        src = id_to_src.get(pid)
        if src:
            reachable.add(src)
    # If entry itself has no source in id_to_src, include all sources as fallback
    if not reachable:
        reachable = set(program_ids.keys())
    return reachable


def detect_interactivity(repo_dir: str, discover_data: dict) -> str:
    """Analyse reachable COBOL sources and classify the application.

    Args:
        repo_dir:       Absolute path to the repository root.
        discover_data:  The "discover" dict from pipeline state.

    Returns:
        "NON_INTERACTIVE" | "INTERACTIVE" | "UNKNOWN"
    """
    entry = discover_data.get("entry", "")
    program_ids = discover_data.get("program_ids", {})
    call_graph = discover_data.get("call_graph", {})
    sources = discover_data.get("sources", [])
    has_dynamic = bool(call_graph.get("dynamic_callers", []))

    reachable = _sources_reachable_from(entry, call_graph, program_ids)
    if not reachable:
        reachable = set(sources)

    found_interactive = False
    for src in reachable:
        path = os.path.join(repo_dir, src)
        if not os.path.isfile(path):
            continue
        try:
            text = open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            continue

        for m in _RE_ACCEPT.finditer(text):
            identifier = m.group(1)
            from_source = m.group(2)
            if _is_interactive_accept(identifier, from_source):
                found_interactive = True
                break
        if found_interactive:
            break

    if found_interactive:
        return "INTERACTIVE"
        
    # If no source in the entire repo has any stdin-consuming ACCEPT, it is non-interactive.
    any_accept = False
    for src in sources:
        path = os.path.join(repo_dir, src)
        if not os.path.isfile(path):
            continue
        try:
            text = open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        for m in _RE_ACCEPT.finditer(text):
            if _is_interactive_accept(m.group(1), m.group(2)):
                any_accept = True
                break
        if any_accept:
            break
            
    if not any_accept:
        return "NON_INTERACTIVE"

    if has_dynamic:
        # Dynamic CALLs mean we couldn't traverse the full graph and at least one ACCEPT exists
        return "UNKNOWN"
    return "NON_INTERACTIVE"
