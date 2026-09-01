"""Phase 9 - Failure Matrix Tests

Verifies the failure scenarios:
- stage failure must block dependent downstream stages.
- final verdict must not be PASS/MVP_CERTIFIED.
- correct error / terminal status is stored.
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cobol_migrate as cm


@pytest.fixture
def tmp_pipeline(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    out = tmp_path / "out"
    out.mkdir()
    (repo / "DUMMY.cob").write_text(
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. DUMMY.\n"
        "       PROCEDURE DIVISION.\n"
        "           STOP RUN.\n",
        encoding="utf-8",
    )
    p = cm.Pipeline(str(repo), str(out), pull=False)
    p.state["data"]["ingest_hashes"] = {}
    p.save_state()
    return p


class TestFailureMatrix:
    def test_case_1_ingest_fails(self, tmp_pipeline):
        p = tmp_pipeline
        p.stage_ingest = lambda: (False, "Ingest failed", [])
        with pytest.raises(RuntimeError):
            p.run()
        assert p.state["stages"].get("ingest", {}).get("status") == "error"
        assert p.state["stages"].get("transpile", {}).get("status", "pending") == "pending"
        assert p._compute_verdict() in ("UNVERIFIED", "FAILED", "PARTIAL")

    def test_case_2_transpile_fails(self, tmp_pipeline):
        p = tmp_pipeline
        p.stage_ingest = lambda: (True, "mock ingest", [])
        p.stage_discover = lambda: (True, "mock discover", [])
        p.stage_analyze = lambda: (True, "mock analyze", [])
        p.stage_baseline = lambda: (True, "mock baseline", [])
        p.stage_transpile = lambda: (False, "mock transpile failed", [])
        
        with pytest.raises(RuntimeError):
            p.run()
        assert p.state["stages"].get("transpile", {}).get("status") == "error"
        assert p.state["stages"].get("compare", {}).get("status", "pending") == "pending"
        assert p._compute_verdict() in ("PARTIAL", "FAILED")

    def test_case_3_baseline_unproducible(self, tmp_pipeline):
        p = tmp_pipeline
        p.state["stages"]["ingest"] = {"status": "done"}
        p.state["data"]["legacy"] = {"status": "BASELINE_UNPRODUCIBLE"}
        assert p._compute_verdict() == "BASELINE_UNPRODUCIBLE"

    def test_case_4_compile_failure(self, tmp_pipeline):
        p = tmp_pipeline
        p.state["stages"]["ingest"] = {"status": "done"}
        # Mock compilation / generate stage to fail (not executed, but marked error)
        p.state["stages"]["generate"] = {"status": "error"}
        assert p._compute_verdict() not in ("MVP_CERTIFIED", "CERTIFIED_WITH_REVIEW")

    def test_case_5_equivalence_mismatch(self, tmp_pipeline):
        p = tmp_pipeline
        p.state["stages"]["ingest"] = {"status": "done"}
        p.state["data"]["transpile"] = {"n_ok": 1, "n_total": 1}
        p.state["data"]["baseline_files"] = ["out.txt"]
        # equivalence mismatch (logical mismatch)
        p.state["data"]["compare"] = {
            "status": "FAIL",
            "checks": [{"ok": False}],
            "rows": [{"verdict": "differ", "logical": {"verdict": "LOGICAL_MISMATCH"}}],
        }
        assert p._compute_verdict() == "FAILED"

    def test_case_6_validation_failure(self, tmp_pipeline):
        p = tmp_pipeline
        p.state["stages"]["ingest"] = {"status": "done"}
        p.state["data"]["transpile"] = {"n_ok": 1, "n_total": 1}
        p.state["data"]["baseline_files"] = ["out.txt"]
        p.state["data"]["compare"] = {"status": "PASS", "checks": [{"ok": True}], "rows": []}
        # validate failed
        p.state["data"]["validate"] = {"status": "failed"}
        assert p._compute_verdict() == "FAILED"
