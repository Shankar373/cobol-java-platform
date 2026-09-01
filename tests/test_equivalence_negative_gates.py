"""Negative acceptance-gate tests.

Prove that each historical false-PASS / bypass path now produces an honest
negative verdict. Every test here corresponds to a documented finding in
docs/FINAL_GAP_ANALYSIS.md:

  1. missing baseline            -> EQUIVALENCE_UNVERIFIED (never VERIFIED)
  2. --skip-legacy with no seed  -> EQUIVALENCE_UNVERIFIED (never VERIFIED)
  3. compile failure             -> stage fails; PARTIAL/UNVERIFIED at best
  4. runtime failure             -> FAILED
  5. partial comparison          -> FAILED
  6. skipped mandatory stage     -> cannot reach MVP_CERTIFIED
  7. fabricated console neg-equiv-> UNVERIFIED, never PASS without execution
  8. corrupt diagnostics         -> UNSUPPORTED (fail-closed)
  9. missing stderr/stdout evidence -> gate failure (fail-closed defaults)

Pure unit level: no Docker required.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cobol_migrate as cm


@pytest.fixture
def pipeline(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    out = tmp_path / "out"
    out.mkdir()
    p = cm.Pipeline(str(repo), str(out), pull=False)
    return p


def _done(p, *names):
    for n in names:
        p.state["stages"].setdefault(n, {})["status"] = "done"


class TestMissingBaseline:
    def test_no_baseline_files_is_equivalence_unverified(self, pipeline):
        _done(pipeline, "ingest")
        pipeline.set_data("transpile", {"n_ok": 1, "n_total": 1})
        pipeline.set_data("baseline_files", [])
        pipeline.set_data("compare", {
            "status": "PASS", "checks": [], "rows": [],
            "topology": "NO_OBSERVABLE_OUTPUT", "stdout_equiv_ok": True,
        })
        assert pipeline._compute_verdict() == "EQUIVALENCE_UNVERIFIED"

    def test_skip_legacy_without_seed_cannot_be_verified(self, pipeline):
        """REGRESSION for C-1: --skip-legacy used to shortcut to VERIFIED."""
        _done(pipeline, "ingest")
        pipeline.skip_legacy = True
        pipeline.set_data("legacy", {"skipped": True, "seeded_baseline_files": []})
        pipeline.set_data("baseline_files", [])
        pipeline.set_data("transpile", {"n_ok": 1, "n_total": 1})
        assert pipeline._compute_verdict() != "VERIFIED"


class TestExecutionFailures:
    def test_compile_failure_yields_partial_not_pass(self, pipeline):
        _done(pipeline, "ingest")
        pipeline.state["stages"]["transpile"] = {"status": "error"}
        pipeline.set_data("transpile", {"n_ok": 0, "n_total": 2})
        v = pipeline._compute_verdict()
        assert v in ("PARTIAL", "UNVERIFIED")
        assert v not in ("VERIFIED", "MVP_CERTIFIED")

    def test_runtime_failure_rows_fail_gate(self, pipeline):
        """A java-only/baseline-only row without logical evidence must fail gate 1."""
        _done(pipeline, "ingest")
        pipeline.set_data("transpile", {"n_ok": 1, "n_total": 1})
        pipeline.set_data("baseline_files", ["out.dat"])
        pipeline.set_data("compare", {
            "status": "FAIL", "checks": [{"ok": False}], "rows": [],
            "stdout_equiv_ok": False,
        })
        assert pipeline._compute_verdict() == "FAILED"


class TestPartialComparison:
    def test_differ_row_without_logical_evidence_fails(self, pipeline):
        _done(pipeline, "ingest")
        pipeline.set_data("transpile", {"n_ok": 1, "n_total": 1})
        pipeline.set_data("baseline_files", ["out.dat"])
        pipeline.set_data("compare", {
            "status": "PASS",
            "checks": [{"ok": True}],
            "rows": [{"file": "out.dat", "verdict": "differ", "logical": None}],
            "stdout_equiv_ok": True,
        })
        assert pipeline._compute_verdict() == "FAILED"

    def test_unable_to_compare_is_never_pass(self, pipeline):
        _done(pipeline, "ingest")
        pipeline.set_data("transpile", {"n_ok": 1, "n_total": 1})
        pipeline.set_data("baseline_files", ["idx.dat"])
        pipeline.set_data("compare", {
            "status": "PASS",
            "checks": [{"ok": True}],
            "rows": [{"file": "idx.dat", "verdict": "differ",
                      "logical": {"verdict": "UNABLE_TO_COMPARE"}}],
            "stdout_equiv_ok": True,
        })
        v = pipeline._compute_verdict()
        assert v in ("FAILED", "UNVERIFIED")


class TestSkippedStages:
    def test_missing_neg_equiv_blocks_production_ready(self, pipeline):
        _done(pipeline, "ingest", "generate", "execute", "compare", "validate")
        pipeline.set_data("transpile", {"n_ok": 1, "n_total": 1})
        pipeline.set_data("baseline_files", ["o.dat"])
        pipeline.set_data("compare", {"status": "PASS", "checks": [{"ok": True}],
                                      "rows": [], "stdout_equiv_ok": True})
        pipeline.set_data("collect", {"dependency_audit": {"executed": True, "status": "PASS"}})
        pipeline.set_data("generate", {"dependency_audit": {"executed": True, "status": "PASS"}})
        # neg_equiv deliberately absent
        v = pipeline._compute_verdict()
        assert v != "MVP_CERTIFIED"
        assert v in ("CERTIFIED_WITH_REVIEW", "NATIVE_SPRING_UNIFIED")

    def test_skip_legacy_flag_alone_grants_nothing(self, pipeline):
        """The flag must never appear as positive evidence anywhere."""
        _done(pipeline, "ingest")
        pipeline.set_data("legacy", {"skipped": True})
        pipeline.set_data("transpile", {"n_ok": 1, "n_total": 1})
        pipeline.set_data("baseline_files", [])
        v = pipeline._compute_verdict()
        pass_tiers = {"MVP_CERTIFIED", "CERTIFIED_WITH_REVIEW", "NATIVE_JAVA_VERIFIED",
                      "NATIVE_SPRING_UNIFIED"}
        assert v not in pass_tiers


class TestFabricatedEvidence:
    def test_console_neg_equiv_requires_execution_evidence(self, pipeline):
        """The old stub wrote PASS/1/1 without running anything — now impossible."""
        pipeline.set_data("execution_scenario", None)
        pipeline._run_neg_equiv_console()
        ne = pipeline.data("neg_equiv")
        assert ne["status"] == "UNVERIFIED"
        assert ne["mutations_tested"] == 0

    def test_corrupt_diagnostics_block_support(self, pipeline, tmp_path):
        """Corrupt diagnostics JSON must fail CLOSED to UNSUPPORTED."""
        _done(pipeline, "ingest", "discover", "analyze", "baseline", "transpile")
        gen = tmp_path / "out" / "generated"
        gen.mkdir()
        (gen / "native_translation_diagnostics.json").write_text(
            "{ this is not valid json ", encoding="utf-8")
        assert pipeline._compute_verdict() == "UNSUPPORTED"

    def test_blocked_diagnostic_entry_returns_unsupported(self, pipeline, tmp_path):
        _done(pipeline, "ingest", "discover", "analyze", "baseline", "transpile")
        gen = tmp_path / "out" / "generated"
        gen.mkdir()
        (gen / "native_translation_diagnostics.json").write_text(
            json.dumps([{"program": "X", "status": "NATIVE_TRANSLATION_BLOCKED"}]),
            encoding="utf-8")
        assert pipeline._compute_verdict() == "UNSUPPORTED"


class TestEquivalenceEngineFailClosed:
    def _obs(self, **kw):
        from execution import ExecutionObservation
        return ExecutionObservation(**kw)

    def _contract(self, modes):
        from execution import ExecutionContract
        return ExecutionContract(expected_output_modes=modes)

    def test_abnormal_baseline_termination_is_fail(self):
        from execution import EquivalenceEngine
        b = self._obs(scenario_id="S", exit_code=-9, execution_status="timeout")
        j = self._obs(scenario_id="S", exit_code=0, execution_status="normal")
        res = EquivalenceEngine.compare(b, j, self._contract(["EXPECTED_EXIT_STATUS"]))
        assert res.status == "FAIL"
        assert any(d["type"] == "abnormal_termination" for d in res.differences)

    def test_stderr_mismatch_detected(self):
        from execution import EquivalenceEngine
        b = self._obs(scenario_id="S", exit_code=0, stderr="")
        j = self._obs(scenario_id="S", exit_code=0, stderr="Exception in thread main")
        res = EquivalenceEngine.compare(b, j,
                                        self._contract(["EXPECTED_STDOUT", "EXPECTED_STDERR"]))
        assert res.checks["stderr"] == "FAIL"
        assert res.status == "FAIL"

    def test_non_applicable_modes_are_not_applicable_not_pass(self):
        from execution import EquivalenceEngine
        b = self._obs(scenario_id="S", exit_code=0, stdout="hi")
        j = self._obs(scenario_id="S", exit_code=0, stdout="hi")
        res = EquivalenceEngine.compare(b, j, self._contract(["EXPECTED_STDOUT"]))
        assert res.checks["database_state"] == "NOT_APPLICABLE"
        assert res.checks["stderr"] == "NOT_APPLICABLE"
        assert res.status == "PASS"  # stdout matched, nothing else requested

    def test_deep_db_state_mismatch_detected(self):
        from execution import EquivalenceEngine
        db_b = {"t": {"db_type": "sqlite", "affected_tables": ["a"],
                      "row_counts": {"a": 3}, "relevant_keys": {},
                      "before_after_state": {}, "transaction_status": "normal"}}
        db_j = {"t": {"db_type": "sqlite", "affected_tables": ["a"],
                      "row_counts": {"a": 2}, "relevant_keys": {},
                      "before_after_state": {}, "transaction_status": "normal"}}
        b = self._obs(scenario_id="S", exit_code=0, database_state=db_b)
        j = self._obs(scenario_id="S", exit_code=0, database_state=db_j)
        res = EquivalenceEngine.compare(b, j,
                                        self._contract(["EXPECTED_DATABASE_STATE"]))
        assert res.status == "FAIL"
        assert any(d["type"] == "database_row_counts_mismatch" for d in res.differences)

    def test_transaction_status_mismatch_detected(self):
        from execution import EquivalenceEngine
        db_b = {"t": {"db_type": "sqlite", "affected_tables": ["a"], "row_counts": {},
                      "relevant_keys": {}, "before_after_state": {},
                      "transaction_status": "committed"}}
        db_j = {"t": {"db_type": "sqlite", "affected_tables": ["a"], "row_counts": {},
                      "relevant_keys": {}, "before_after_state": {},
                      "transaction_status": "rolled_back"}}
        b = self._obs(scenario_id="S", exit_code=0, database_state=db_b)
        j = self._obs(scenario_id="S", exit_code=0, database_state=db_j)
        res = EquivalenceEngine.compare(b, j,
                                        self._contract(["EXPECTED_DATABASE_STATE"]))
        assert res.status == "FAIL"

    def test_missing_file_produces_diagnostic(self):
        from execution import EquivalenceEngine
        b = self._obs(scenario_id="S", exit_code=0,
                      files={"a.dat": "PRESENT_NONEMPTY"},
                      file_contents={"a.dat": "x"}, record_counts={})
        j = self._obs(scenario_id="S", exit_code=0,
                      files={}, file_contents={}, record_counts={})
        res = EquivalenceEngine.compare(b, j,
                                        self._contract(["EXPECTED_FILES", "EXPECTED_EXIT_STATUS"]))
        assert res.status == "FAIL"
        assert any(d["type"] == "file_missing_on_one_side" for d in res.differences)


class TestAuditEngineFileSetMismatch:
    def test_baseline_only_rows_block_green(self):
        import audit_engine as ae
        state = {"data": {"compare": {
            "checks": [],
            "rows": [{"file": "dropped.dat", "verdict": "baseline-only"}],
        }}}
        beh = ae.audit_behavioral_comparison(state)
        verdict = ae.compute_final_verdict(state, "OK", [], beh)
        assert verdict["verdict"] != "AUTOMATED AND VERIFIED"
        assert verdict["color"] != "GREEN"

    def test_java_only_rows_block_green(self):
        import audit_engine as ae
        state = {"data": {"compare": {
            "checks": [],
            "rows": [{"file": "invented.dat", "verdict": "java-only"}],
        }}}
        beh = ae.audit_behavioral_comparison(state)
        verdict = ae.compute_final_verdict(state, "OK", [], beh)
        assert verdict["color"] != "GREEN"
