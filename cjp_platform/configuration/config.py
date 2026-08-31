"""
platform/configuration/config.py

Loads and validates migration_config.json.

Every COBOL repository being migrated may contain a migration_config.json
at its root. This loader validates the schema, resolves paths relative to
the repo root, and returns a typed MigrationConfig object.

Configuration is the single source of truth for:
  - which COBOL sources to migrate
  - where to find copybooks
  - what the main program entry point is
  - format (fixed / free)
  - database configuration
  - output directories

Nothing in the generator or pipeline may hardcode repository-specific
names (program IDs, schema names, table names, package names) except
values read from this config.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class MigrationConfig:
    """Typed representation of a migration_config.json file."""

    # Repository root (set by loader, not from JSON)
    repo_root: str = ""

    # --- Source discovery ---
    sources: list[str] = field(default_factory=list)
    """Relative paths to COBOL source files within the repo."""

    copybook_dirs: list[str] = field(default_factory=list)
    """Relative paths to directories containing copybooks."""

    main_program: Optional[str] = None
    """Relative path to the main/entry program source file."""

    # --- Format ---
    format: str = "fixed"
    """'fixed' or 'free'."""

    # --- Metadata ---
    repo_name: str = ""
    """Human-readable repository name."""

    # --- Output ---
    output_dirs: list[str] = field(default_factory=list)
    """Relative paths to directories the COBOL program writes output files into."""

    # --- Database ---
    db_dialect: str = "postgresql"
    """Target SQL dialect: 'postgresql' (production) or 'h2' (test-only mock)."""

    # --- Java generation ---
    base_package: str = "com.platform.modernized"
    """Base Java package name for generated code. NOT hardcoded; read from config."""

    # --- Raw remainder ---
    extra: dict = field(default_factory=dict)
    """Any additional keys from the config file, preserved for diagnostics."""

    def source_paths(self) -> list[str]:
        """Return absolute paths to all COBOL sources."""
        return [os.path.join(self.repo_root, s) for s in self.sources]

    def copybook_search_dirs(self) -> list[str]:
        """Return absolute paths to all copybook search directories."""
        dirs = []
        for d in self.copybook_dirs:
            dirs.append(os.path.join(self.repo_root, d))
        # Always include the repo root itself and a 'copybooks/' sibling
        dirs.append(self.repo_root)
        dirs.append(os.path.join(self.repo_root, "copybooks"))
        return [d for d in dirs if os.path.isdir(d)]

    def main_program_path(self) -> Optional[str]:
        if self.main_program:
            return os.path.join(self.repo_root, self.main_program)
        return None


_DEFAULTS: dict = {
    "sources": [],
    "copybook_dirs": [],
    "main_program": None,
    "format": "fixed",
    "repo_name": "",
    "output_dirs": [],
    "db_dialect": "postgresql",
    "base_package": "com.platform.modernized",
}


def load_config(repo_root: str) -> MigrationConfig:
    """
    Load migration_config.json from repo_root.

    If no config file exists, return a MigrationConfig with defaults.
    The caller (discovery stage) will perform its own source discovery.

    Parameters
    ----------
    repo_root:
        Absolute path to the COBOL repository root.

    Returns
    -------
    MigrationConfig

    Raises
    ------
    ValueError if the config file exists but contains invalid JSON or
    mandatory fields have invalid types.
    """
    repo_root = os.path.abspath(repo_root)
    config_path = os.path.join(repo_root, "migration_config.json")

    raw: dict = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in {config_path}: {exc}") from exc

    known_keys = set(_DEFAULTS.keys()) | {"repo_name"}
    extra = {k: v for k, v in raw.items() if k not in known_keys}

    cfg = MigrationConfig(
        repo_root=repo_root,
        sources=_coerce_list(raw.get("sources", [])),
        copybook_dirs=_coerce_list(raw.get("copybook_dirs", [])),
        main_program=raw.get("main_program") or None,
        format=raw.get("format", "fixed"),
        repo_name=raw.get("repo_name", os.path.basename(repo_root)),
        output_dirs=_coerce_list(raw.get("output_dirs", [])),
        db_dialect=raw.get("db_dialect", "postgresql"),
        base_package=raw.get("base_package", "com.platform.modernized"),
        extra=extra,
    )
    return cfg


def _coerce_list(v) -> list:
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        return [v]
    return []
