"""Tests conftest.py — test-suite configuration."""
import os
import sys
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

FIXTURES_DIR = os.path.join(ROOT, "tests", "fixtures")


def fixture_path(name: str) -> str:
    """Return absolute path to a named test fixture repository."""
    return os.path.join(FIXTURES_DIR, name)


def pytest_collection_modifyitems(config, items):
    """Auto-add markers based on test paths."""
    for item in items:
        fspath = str(item.fspath)
        if "differential" in fspath:
            item.add_marker(pytest.mark.differential)
