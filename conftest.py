"""Shared pytest fixtures.

Consolidates helpers previously copy-pasted across many test files:
  - project-root sys.path insertion
  - blank_pipeline / stubbed_pipeline factories

Existing per-file duplicates keep working; new tests should prefer these.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _make_pipeline(tmp_path, stub_all=False):
    import cobol_migrate as cm
    repo = tmp_path / "repo"
    repo.mkdir(exist_ok=True)
    out = tmp_path / "out"
    out.mkdir(exist_ok=True)
    p = cm.Pipeline(str(repo), str(out), pull=False)
    p._save_state = lambda: None
    if stub_all:
        p.state["stages"] = {s: {"status": "done"} for s in [
            "ingest", "discover", "analyze", "baseline", "transpile",
            "collect", "generate", "execute", "compare",
            "refactor", "validate", "report",
        ]}
    return p


@pytest.fixture
def blank_pipeline(tmp_path):
    """Minimal pipeline with empty repo/out dirs (verdict-level tests)."""
    return _make_pipeline(tmp_path)


@pytest.fixture
def stubbed_pipeline(tmp_path):
    """Pipeline with all 12 stages marked done (gate-evidence tests)."""
    return _make_pipeline(tmp_path, stub_all=True)
