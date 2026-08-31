"""
engine/discovery/discovery.py

Discovers COBOL sources, copybooks, JCL files, and SQL usage within a
repository. Works from a MigrationConfig; if the config does not enumerate
sources explicitly, falls back to file-system walk.

Output is a DiscoveryResult dataclass that all downstream pipeline stages
consume — nothing downstream re-discovers files independently.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Optional

SOURCE_EXTENSIONS = (".cob", ".cbl", ".COB", ".CBL")
COPYBOOK_EXTENSIONS = (".cpy", ".CPY", ".copy", ".COPY")
JCL_EXTENSIONS = (".jcl", ".JCL")

EXCLUDE_DIRS = {
    "generated", "target", "bin", ".git", "__pycache__",
    "node_modules", "normalized", "_preprocessed",
}


@dataclass
class DiscoveryResult:
    repo_root: str
    sources: list[str] = field(default_factory=list)
    """Absolute paths to COBOL source files."""

    copybooks: list[str] = field(default_factory=list)
    """Absolute paths to copybook files."""

    jcl_files: list[str] = field(default_factory=list)
    """Absolute paths to JCL files."""

    copybook_search_dirs: list[str] = field(default_factory=list)
    """Ordered list of directories to search when resolving COPY statements."""

    entrypoint: Optional[str] = None
    """Absolute path to the main program, or None if unknown."""

    has_sql: bool = False
    """True if any source contains EXEC SQL."""

    has_cics: bool = False
    """True if any source contains EXEC CICS."""

    has_vsam: bool = False
    """True if any source contains INDEXED organisation declarations."""

    has_jcl: bool = False
    """True if any JCL files were found."""

    technologies: list[str] = field(default_factory=list)
    """Human-readable list of detected technologies."""

    diagnostics: list[dict] = field(default_factory=list)


def discover(cfg) -> DiscoveryResult:
    """
    Run discovery against a repository described by cfg (MigrationConfig).

    Parameters
    ----------
    cfg : MigrationConfig

    Returns
    -------
    DiscoveryResult
    """
    repo_root = cfg.repo_root
    result = DiscoveryResult(repo_root=repo_root)

    # --- Source files ---
    if cfg.sources:
        # Config explicitly lists sources
        for rel in cfg.sources:
            abs_path = os.path.join(repo_root, rel)
            if os.path.isfile(abs_path):
                result.sources.append(abs_path)
            else:
                result.diagnostics.append({
                    "severity": "WARNING",
                    "detail": f"Configured source not found: {rel}",
                })
    else:
        # Walk the repo for COBOL sources
        result.sources = _walk_for_extensions(repo_root, SOURCE_EXTENSIONS)

    # --- Copybooks ---
    result.copybooks = _walk_for_extensions(repo_root, COPYBOOK_EXTENSIONS)

    # --- Copybook search dirs ---
    result.copybook_search_dirs = list(cfg.copybook_search_dirs())

    # --- JCL ---
    result.jcl_files = _walk_for_extensions(repo_root, JCL_EXTENSIONS)
    result.has_jcl = bool(result.jcl_files)

    # --- Entrypoint ---
    if cfg.main_program:
        ep = os.path.join(repo_root, cfg.main_program)
        result.entrypoint = ep if os.path.isfile(ep) else None
    elif len(result.sources) == 1:
        result.entrypoint = result.sources[0]
    else:
        # Try to find the main program heuristically
        result.entrypoint = _heuristic_entrypoint(result.sources)

    # --- Technology detection ---
    _detect_technologies(result)

    return result


def _walk_for_extensions(root: str, exts: tuple) -> list[str]:
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune excluded directories in-place
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for fname in filenames:
            if fname.endswith(exts):
                found.append(os.path.join(dirpath, fname))
    return found


def _heuristic_entrypoint(sources: list[str]) -> Optional[str]:
    """Return the source most likely to be the main program."""
    if not sources:
        return None
    # Prefer files with 'MAIN' or 'BATCH' in the name
    for s in sources:
        base = os.path.basename(s).upper()
        if "MAIN" in base or "BATCH" in base:
            return s
    return sources[0]


_EXEC_SQL_RE = re.compile(r"\bEXEC\s+SQL\b", re.IGNORECASE)
_EXEC_CICS_RE = re.compile(r"\bEXEC\s+CICS\b", re.IGNORECASE)
_INDEXED_RE = re.compile(r"\bORGANIZATION\s+IS\s+INDEXED\b", re.IGNORECASE)


def _detect_technologies(result: DiscoveryResult) -> None:
    techs = set()
    if result.jcl_files:
        techs.add("JCL")

    for src in result.sources:
        try:
            text = _read_safe(src)
        except OSError:
            continue
        upper = text.upper()
        if "EXEC SQL" in upper:
            result.has_sql = True
            techs.add("SQL/DB2")
        if "EXEC CICS" in upper:
            result.has_cics = True
            techs.add("CICS")
        if "ORGANIZATION IS INDEXED" in upper or "ORGANISATION IS INDEXED" in upper:
            result.has_vsam = True
            techs.add("VSAM-KSDS")
        if "ORGANIZATION IS RELATIVE" in upper or "ORGANISATION IS RELATIVE" in upper:
            result.has_vsam = True
            techs.add("VSAM-RRDS")
        if "SORT " in upper:
            techs.add("SORT")
        if "EXEC REPORT" in upper or "REPORT SECTION" in upper:
            techs.add("REPORT-WRITER")
        if "BMS" in upper or ".BMS" in src.upper():
            techs.add("BMS")

    result.technologies = sorted(techs)


def _read_safe(path: str, max_bytes: int = 512 * 1024) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        return fh.read(max_bytes)
