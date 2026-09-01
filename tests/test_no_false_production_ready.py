import os
import sys
import pytest
import cobol_migrate as cm

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def base_pipeline(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    out = tmp_path / "out"
    out.mkdir()
    p = cm.Pipeline(str(repo), str(out), pull=False)
    p.state["stages"] = {s: {"status": "done"} for s in [
        "ingest", "discover", "analyze", "baseline", "transpile",
        "collect", "generate", "execute", "compare",
        "refactor", "validate", "report",
    ]}
    p.set_data("transpile", {"n_ok": 1, "n_total": 1})
    p.set_data("baseline_files", ["out.dat"])
    p.set_data("compare", {
        "status": "PASS",
        "checks": [{"ok": True}],
        "rows": [{"verdict": "exact", "logical": None}],
        "topology": "FILE_OUTPUT",
        "stdout_equiv_ok": True,
    })
    p.set_data("execute", {"status": "ok"})
    p.set_data("validate", {"status": "done", "gate2_passed": True})
    p.set_data("generate", {"status": "done", "dependency_audit": {
        "executed": True, "status": "PASS",
    }})
    p.set_data("legacy", {})
    p._save_state = lambda: None
    return p


def test_dependency_audit_missing(base_pipeline):
    p = base_pipeline
    p.set_data("collect", {})  # no dependency_audit
    p.set_data("neg_equiv", {"executed": True, "status": "PASS", "verdict": "PASS"})
    assert p._compute_verdict() != "MVP_CERTIFIED"


def test_dependency_audit_failed(base_pipeline):
    p = base_pipeline
    p.set_data("collect", {"dependency_audit": {"executed": True, "status": "FAIL"}})
    p.set_data("neg_equiv", {"executed": True, "status": "PASS", "verdict": "PASS"})
    assert p._compute_verdict() != "MVP_CERTIFIED"


def test_dependency_audit_not_executed(base_pipeline):
    p = base_pipeline
    p.set_data("collect", {"dependency_audit": {"executed": False, "status": "PASS"}})
    p.set_data("neg_equiv", {"executed": True, "status": "PASS", "verdict": "PASS"})
    assert p._compute_verdict() != "MVP_CERTIFIED"


def test_negative_equivalence_missing(base_pipeline):
    p = base_pipeline
    p.set_data("collect", {"dependency_audit": {"executed": True, "status": "PASS"}})
    p.set_data("neg_equiv", {})  # no negative equivalence data
    assert p._compute_verdict() != "MVP_CERTIFIED"


def test_negative_equivalence_failed(base_pipeline):
    p = base_pipeline
    p.set_data("collect", {"dependency_audit": {"executed": True, "status": "PASS"}})
    p.set_data("neg_equiv", {"executed": True, "status": "FAIL"})
    assert p._compute_verdict() != "MVP_CERTIFIED"


def test_negative_equivalence_not_executed(base_pipeline):
    p = base_pipeline
    p.set_data("collect", {"dependency_audit": {"executed": True, "status": "PASS"}})
    p.set_data("neg_equiv", {"executed": False, "status": "PASS"})
    assert p._compute_verdict() != "MVP_CERTIFIED"


def test_existing_file_output_behavior_remains(base_pipeline):
    p = base_pipeline
    p.set_data("collect", {"dependency_audit": {"executed": True, "status": "PASS"}})
    p.set_data("neg_equiv", {"executed": True, "status": "PASS", "verdict": "PASS"})
    assert p._compute_verdict() == "MVP_CERTIFIED"
