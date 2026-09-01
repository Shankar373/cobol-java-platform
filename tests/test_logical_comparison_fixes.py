"""Tests for P0 logical comparison propagation and P1 UI status model.
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cobol_migrate as cm
import ui

@pytest.fixture
def blank_pipeline(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    out = tmp_path / "out"
    out.mkdir()
    return cm.Pipeline(str(repo), str(out), pull=False)

def _set_stage_done(p, name):
    p.state["stages"].setdefault(name, {})["status"] = "done"

def _set_data(p, key, value):
    p.state["data"][key] = value

class TestLogicalComparisonPropagation:
    def test_physical_diff_logical_match_business_match(self, blank_pipeline):
        """Physical difference + Logical Match + Business match -> PASS_WITH_LIMITATIONS"""
        p = blank_pipeline
        _set_stage_done(p, "ingest")
        _set_data(p, "transpile", {"n_ok": 1, "n_total": 1})
        _set_data(p, "baseline_files", ["customer.dat"])
        _set_data(p, "compare", {
            "status": "FAIL",
            "stdout_equiv_ok": True,
            "checks": [{"ok": True, "name": "custom"}],
            "rows": [
                {
                    "file": "customer.dat",
                    "verdict": "differ",
                    "logical": {"verdict": "LOGICAL_MATCH"}
                }
            ]
        })
        v = p._compute_verdict()
        assert v == "VERIFIED_WITH_LIMITATIONS"

    def test_physical_diff_logical_mismatch(self, blank_pipeline):
        """Physical difference + Logical Mismatch -> FAILED"""
        p = blank_pipeline
        _set_stage_done(p, "ingest")
        _set_data(p, "transpile", {"n_ok": 1, "n_total": 1})
        _set_data(p, "baseline_files", ["customer.dat"])
        _set_data(p, "compare", {
            "status": "FAIL",
            "stdout_equiv_ok": True,
            "checks": [{"ok": True, "name": "custom"}],
            "rows": [
                {
                    "file": "customer.dat",
                    "verdict": "differ",
                    "logical": {"verdict": "LOGICAL_MISMATCH"}
                }
            ]
        })
        v = p._compute_verdict()
        assert v == "FAILED"

    def test_physical_diff_logical_unavailable(self, blank_pipeline):
        """Physical difference + Logical Unavailable -> UNVERIFIED"""
        p = blank_pipeline
        _set_stage_done(p, "ingest")
        _set_data(p, "transpile", {"n_ok": 1, "n_total": 1})
        _set_data(p, "baseline_files", ["customer.dat"])
        _set_data(p, "compare", {
            "status": "FAIL",
            "stdout_equiv_ok": True,
            "checks": [{"ok": True, "name": "custom"}],
            "rows": [
                {
                    "file": "customer.dat",
                    "verdict": "differ",
                    "logical": {"verdict": "UNABLE_TO_COMPARE"}
                }
            ]
        })
        v = p._compute_verdict()
        assert v == "UNVERIFIED"

    def test_business_output_mismatch(self, blank_pipeline):
        """Business output mismatch -> FAILED"""
        p = blank_pipeline
        _set_stage_done(p, "ingest")
        _set_data(p, "transpile", {"n_ok": 1, "n_total": 1})
        _set_data(p, "baseline_files", ["customer.dat"])
        _set_data(p, "compare", {
            "status": "FAIL",
            "stdout_equiv_ok": False,
            "checks": [{"ok": True, "name": "custom"}],
            "rows": [
                {
                    "file": "customer.dat",
                    "verdict": "differ",
                    "logical": {"verdict": "LOGICAL_MATCH"}
                }
            ]
        })
        v = p._compute_verdict()
        assert v == "FAILED"

    def test_physical_match_logical_match(self, blank_pipeline):
        """Physical match + Logical match -> PASS/VERIFIED style response"""
        p = blank_pipeline
        _set_stage_done(p, "ingest")
        _set_data(p, "transpile", {"n_ok": 1, "n_total": 1})
        _set_data(p, "baseline_files", ["customer.dat"])
        _set_data(p, "compare", {
            "status": "PASS",
            "stdout_equiv_ok": True,
            "checks": [{"ok": True, "name": "custom"}],
            "rows": [
                {
                    "file": "customer.dat",
                    "verdict": "exact",
                    "logical": None
                }
            ]
        })
        # Stays VERIFIED because no native Spring / packaging evidence is simulated
        v = p._compute_verdict()
        assert v == "VERIFIED"

class TestUiStatusMappings:
    def test_get_run_verdict_maps_correctly(self, monkeypatch):
        run = {
            "run_id": "test_ui_run",
            "repo": "somerepo",
            "out": "someout"
        }
        monkeypatch.setattr(cm.Pipeline, "_compute_verdict", lambda self: "VERIFIED_WITH_LIMITATIONS")
        verd = ui.get_run_verdict(run)
        assert verd == "VERIFIED_WITH_LIMITATIONS"
