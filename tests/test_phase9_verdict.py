"""Phase 9 - Evidence-driven Verdict Tests

Verifies _compute_verdict() never returns MVP_CERTIFIED without gate evidence,
returns correct tier based on what evidence is present.
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cobol_migrate as cm


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


class TestVerdictTiers:
    def test_no_evidence_returns_unverified(self, blank_pipeline):
        """Fresh pipeline with no done stages must return UNVERIFIED."""
        v = blank_pipeline._compute_verdict()
        assert v == "UNVERIFIED"

    def test_partial_when_transpile_incomplete(self, blank_pipeline):
        p = blank_pipeline
        _set_stage_done(p, "ingest")  # at least one done stage
        _set_data(p, "transpile", {"n_ok": 1, "n_total": 3})
        v = p._compute_verdict()
        assert v == "PARTIAL"

    def test_equivalence_unverified_when_no_baseline_files(self, blank_pipeline):
        p = blank_pipeline
        _set_stage_done(p, "ingest")
        _set_data(p, "transpile", {"n_ok": 2, "n_total": 2})
        _set_data(p, "baseline_files", [])
        v = p._compute_verdict()
        assert v == "EQUIVALENCE_UNVERIFIED"

    def test_failed_on_logical_mismatch(self, blank_pipeline):
        p = blank_pipeline
        _set_stage_done(p, "ingest")
        _set_data(p, "transpile", {"n_ok": 1, "n_total": 1})
        _set_data(p, "baseline_files", ["out.txt"])
        _set_data(p, "compare", {
            "status": "PASS",
            "checks": [{"ok": True}],
            "rows": [{"verdict": "differ", "logical": {"verdict": "LOGICAL_MISMATCH"}}],
        })
        v = p._compute_verdict()
        assert v == "FAILED"

    def test_verified_when_core_gates_pass_no_dep_audit(self, blank_pipeline):
        p = blank_pipeline
        _set_stage_done(p, "ingest")
        _set_data(p, "transpile", {"n_ok": 1, "n_total": 1})
        _set_data(p, "baseline_files", ["out.txt"])
        _set_data(p, "compare", {
            "status": "PASS",
            "checks": [{"ok": True}],
            "rows": [{"verdict": "match"}],
            "stdout_equiv_ok": True,
        })
        # No dep_audit -> stays VERIFIED
        _set_data(p, "collect", {})
        v = p._compute_verdict()
        assert v == "VERIFIED"

    def test_missing_stdout_equiv_evidence_blocks_verified(self, blank_pipeline):
        """Fail-closed: compare data lacking stdout equivalence evidence must not
        reach VERIFIED even when all file rows match."""
        p = blank_pipeline
        _set_stage_done(p, "ingest")
        _set_data(p, "transpile", {"n_ok": 1, "n_total": 1})
        _set_data(p, "baseline_files", ["out.txt"])
        _set_data(p, "compare", {
            "status": "PASS",
            "checks": [{"ok": True}],
            "rows": [{"verdict": "match"}],
            # stdout_equiv_ok deliberately absent -> no evidence
        })
        v = p._compute_verdict()
        assert v == "FAILED"

    def test_native_java_verified_with_dep_audit_pass(self, blank_pipeline):
        p = blank_pipeline
        _set_stage_done(p, "ingest")
        _set_data(p, "transpile", {"n_ok": 1, "n_total": 1})
        _set_data(p, "baseline_files", ["out.txt"])
        _set_data(p, "compare", {"status": "PASS", "checks": [{"ok": True}], "rows": [],
                                 "stdout_equiv_ok": True})
        _set_data(p, "collect", {"dependency_audit": {"status": "PASS"}})
        # No generate stage done -> NATIVE_JAVA_VERIFIED
        v = p._compute_verdict()
        assert v == "NATIVE_JAVA_VERIFIED"

    def test_native_spring_unified_with_generate_done(self, blank_pipeline):
        p = blank_pipeline
        _set_stage_done(p, "ingest")
        _set_stage_done(p, "generate")
        _set_data(p, "transpile", {"n_ok": 1, "n_total": 1})
        _set_data(p, "baseline_files", ["out.txt"])
        _set_data(p, "compare", {"status": "PASS", "checks": [{"ok": True}], "rows": [],
                                 "stdout_equiv_ok": True})
        _set_data(p, "collect", {"dependency_audit": {"status": "PASS"}})
        _set_data(p, "generate", {"dependency_audit": {"executed": True, "status": "PASS"}})
        # execute not done -> NATIVE_SPRING_UNIFIED
        v = p._compute_verdict()
        assert v in ("NATIVE_SPRING_UNIFIED", "CERTIFIED_WITH_REVIEW")

    def test_enterprise_gate_requires_real_audit_evidence(self, blank_pipeline):
        """Generating a Spring project without dependency-audit evidence caps the
        verdict at NATIVE_JAVA_VERIFIED — existence is not evidence."""
        p = blank_pipeline
        for s in ("ingest", "generate"):
            _set_stage_done(p, s)
        _set_data(p, "transpile", {"n_ok": 1, "n_total": 1})
        _set_data(p, "baseline_files", ["out.txt"])
        _set_data(p, "compare", {"status": "PASS", "checks": [{"ok": True}], "rows": [],
                                 "stdout_equiv_ok": True})
        _set_data(p, "collect", {"dependency_audit": {"status": "PASS"}})
        _set_data(p, "generate", {})  # no audit evidence at all
        v = p._compute_verdict()
        assert v == "NATIVE_JAVA_VERIFIED"

    def test_production_ready_requires_all_gates(self, blank_pipeline):
        """MVP_CERTIFIED must never be returned when neg_equiv is absent."""
        p = blank_pipeline
        _set_stage_done(p, "ingest")
        _set_stage_done(p, "generate")
        _set_stage_done(p, "execute")
        _set_stage_done(p, "compare")
        _set_stage_done(p, "validate")
        _set_data(p, "transpile", {"n_ok": 1, "n_total": 1})
        _set_data(p, "baseline_files", ["out.txt"])
        _set_data(p, "compare", {"status": "PASS", "checks": [{"ok": True}], "rows": []})
        _set_data(p, "collect", {"dependency_audit": {"status": "PASS"}})
        _set_data(p, "generate", {})
        _set_data(p, "execute", {"status": "ok"})
        _set_data(p, "validate", {"status": "passed"})
        # neg_equiv missing -> NOT MVP_CERTIFIED
        v = p._compute_verdict()
        assert v != "MVP_CERTIFIED", (
            f"Expected CERTIFIED_WITH_REVIEW not MVP_CERTIFIED without neg_equiv; got {v}"
        )

    def test_production_ready_with_all_gates(self, blank_pipeline):
        """MVP_CERTIFIED when every gate has positive evidence (Phase 10: executed=True required)."""
        p = blank_pipeline
        _set_stage_done(p, "ingest")
        _set_stage_done(p, "generate")
        _set_stage_done(p, "execute")
        _set_stage_done(p, "compare")
        _set_stage_done(p, "validate")
        _set_data(p, "transpile", {"n_ok": 1, "n_total": 1})
        _set_data(p, "baseline_files", ["out.txt"])
        _set_data(p, "compare", {"status": "PASS", "checks": [{"ok": True}], "rows": [],
                                 "stdout_equiv_ok": True})
        # Phase 10: executed=True is required for both gates to reach MVP_CERTIFIED.
        _set_data(p, "collect", {"dependency_audit": {
            "executed": True, "status": "PASS", "verdict": "PASS",
        }})
        _set_data(p, "generate", {"dependency_audit": {
            "executed": True, "status": "PASS",
        }})
        _set_data(p, "execute", {"status": "ok"})
        _set_data(p, "validate", {"status": "passed"})
        _set_data(p, "neg_equiv", {
            "executed": True, "status": "PASS", "verdict": "PASS",
        })
        v = p._compute_verdict()
        assert v == "MVP_CERTIFIED"

    def test_baseline_unproducible_verdict(self, blank_pipeline):
        p = blank_pipeline
        _set_stage_done(p, "ingest")
        _set_data(p, "legacy", {"status": "BASELINE_UNPRODUCIBLE"})
        v = p._compute_verdict()
        assert v == "BASELINE_UNPRODUCIBLE"

    def test_verdict_never_fabricates_pass_on_fresh_run(self, blank_pipeline):
        """Absolutely no pass-equivalent on a fresh pipeline."""
        v = blank_pipeline._compute_verdict()
        pass_equiv = {"MVP_CERTIFIED", "CERTIFIED_WITH_REVIEW", "VERIFIED", "NATIVE_JAVA_VERIFIED"}
        assert v not in pass_equiv, f"Fresh pipeline must not return pass-tier verdict; got {v}"
