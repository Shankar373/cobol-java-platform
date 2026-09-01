import os
import sys
import pytest
import cobol_migrate as cm
from modernize.capability_matrix import classify_feature, get_unsupported_features, CapabilityStatus, EvidenceLevel

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

@pytest.fixture
def mock_pipeline(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    out = tmp_path / "out"
    out.mkdir()
    p = cm.Pipeline(str(repo), str(out), pull=False)
    p.state["stages"] = {s: {"status": "done"} for s in [
        "ingest", "discover", "analyze", "baseline", "transpile",
        "collect", "generate", "execute", "compare",
        "refactor", "validate", "report"
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
    p.set_data("generate", {
        "status": "done",
        "dependency_audit": {"executed": True, "status": "PASS"},
        "dep_audit_status": "PASS"
    })
    p.set_data("collect", {
        "dependency_audit": {"executed": True, "status": "PASS", "verdict": "PASS"}
    })
    p.set_data("neg_equiv", {"executed": True, "status": "PASS", "verdict": "PASS"})
    p.state["data"]["ingest_hashes"] = {}
    p.set_data("discover", {
        "sources": ["DUMMY.cob"],
        "format": "free",
        "entry": "DUMMY",
        "copybook_dirs": [],
        "copy_deps": {},
        "missing_copybooks": [],
        "call_graph": {},
        "file_assigns": {}
    })
    p.set_data("legacy", {})
    p._save_state = lambda: None
    return p

def test_capability_matrix():
    assert classify_feature("MOVE") == CapabilityStatus.SUPPORTED
    assert classify_feature("dynamic_CALL") == CapabilityStatus.PARTIAL
    assert classify_feature("EXEC_SQL") in (CapabilityStatus.SUPPORTED, EvidenceLevel.DIFFERENTIALLY_VERIFIED)
    assert classify_feature("IMS_MQ") == CapabilityStatus.UNSUPPORTED
    
    unsupported = get_unsupported_features(["MOVE", "IMS_MQ", "COMP-3"])
    assert unsupported == ["IMS_MQ"]

def test_verdict_mvp_certified(mock_pipeline):
    v = mock_pipeline._compute_verdict()
    assert v == "MVP_CERTIFIED"
    
    # Verify manifest data matches
    checks = mock_pipeline.data("certification_report")
    assert checks["INPUT_ANALYSIS"] == "PASS"
    assert checks["FEATURE_COVERAGE"] == "PASS"
    assert checks["BUILD_CHECK"] == "PASS"
    assert checks["EQUIVALENCE_CHECK"] == "PASS"
    assert checks["NEGATIVE_TEST_CHECK"] == "PASS"

def test_verdict_certified_with_review(mock_pipeline):
    p = mock_pipeline
    # Inject dynamic callers to trigger REVIEW check status
    p.state["data"]["discover"]["call_graph"] = {"dynamic_callers": ["SUBVAR"]}
    v = p._compute_verdict()
    assert v == "CERTIFIED_WITH_REVIEW"
    checks = p.data("certification_report")
    assert checks["FEATURE_COVERAGE"] == "REVIEW"

def test_verdict_not_certified_on_gate_failure(mock_pipeline):
    p = mock_pipeline
    # Make equivalence validation check fail
    p.state["data"]["compare"]["checks"] = [{"ok": False}]
    v = p._compute_verdict()
    assert v == "FAILED"
    checks = p.data("certification_report")
    assert checks["EQUIVALENCE_CHECK"] == "FAIL"

def test_verdict_not_certified_on_dependency_audit_failure(mock_pipeline):
    p = mock_pipeline
    # Make native classpath audit check fail (libcobj detected)
    p.state["data"]["collect"]["dependency_audit"] = {"executed": True, "status": "FAIL"}
    v = p._compute_verdict()
    assert v == "VERIFIED"
    checks = p.data("certification_report")
    assert checks["RUNTIME_DEPENDENCY_CHECK"] == "FAIL"
