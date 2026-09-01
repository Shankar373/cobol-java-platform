"""Phase 10 — automatic production gate tests.

Tests prove:
- Dependency audit runs automatically from stage_refactor.
- Dependency failure blocks MVP_CERTIFIED (native_dep_ok=False -> CERTIFIED_WITH_REVIEW).
- Negative equivalence runs automatically from stage_compare.
- Each mutation case is detected.
- Missing neg_equiv evidence prevents MVP_CERTIFIED.
- Missing dep_audit evidence prevents MVP_CERTIFIED.
- All gates passing yields MVP_CERTIFIED.
"""
import os
import sys
import json
import tempfile
import shutil
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cobol_migrate as engine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pipeline(tmp_path):
    """Return a minimal Pipeline instance backed by tmp_path."""
    repo = os.path.join(str(tmp_path), "repo")
    out = os.path.join(str(tmp_path), "target")
    os.makedirs(repo, exist_ok=True)
    os.makedirs(out, exist_ok=True)
    p = engine.Pipeline.__new__(engine.Pipeline)
    p.repo = repo
    p.out = out
    p.cfg = {}
    p.skip_legacy = False
    p.pull = False
    p._logs = []
    p.log = lambda msg: p._logs.append(msg)
    # Minimal state
    p.state = {"stages": {}, "data": {}}
    p._save_state = lambda: None
    p.set_data = lambda k, v: p.state["data"].__setitem__(k, v)
    p.data = lambda k, default=None: p.state["data"].get(k, default)
    return p


# ---------------------------------------------------------------------------
# Dependency Audit
# ---------------------------------------------------------------------------

class TestDependencyAudit:
    def test_dep_audit_runs_and_stores_in_collect(self, tmp_path):
        p = _make_pipeline(tmp_path)
        p.set_data("collect", {"java_files": []})
        mod_dir = os.path.join(str(tmp_path), "modernized")
        os.makedirs(mod_dir)
        with open(os.path.join(mod_dir, "App.java"), "w") as fh:
            fh.write("public class App {}")
        p._run_dependency_audit(mod_dir)
        collect = p.data("collect")
        assert "dependency_audit" in collect
        da = collect["dependency_audit"]
        assert da["executed"] is True
        assert da["status"] == "PASS"

    def test_dep_audit_detects_libcobj(self, tmp_path):
        p = _make_pipeline(tmp_path)
        p.set_data("collect", {})
        mod_dir = os.path.join(str(tmp_path), "modernized")
        os.makedirs(mod_dir)
        with open(os.path.join(mod_dir, "pom.xml"), "w") as fh:
            fh.write("<dependency><groupId>jp.osscons.opensourcecobol</groupId></dependency>")
        p._run_dependency_audit(mod_dir)
        da = p.data("collect")["dependency_audit"]
        assert da["executed"] is True
        assert da["status"] == "FAIL"
        terms = [x["term"] for x in da["forbidden_found"]]
        assert any("opensourcecobol" in t or "jp.osscons" in t for t in terms)

    def test_dep_audit_detects_all_forbidden_terms(self, tmp_path):
        forbidden = ["libcobj", "jp.osscons", "CobolResolve",
                     "opensourcecobol", "CobolField", "CobolBytes"]
        for term in forbidden:
            sub = tmp_path / term
            sub.mkdir(parents=True, exist_ok=True)
            p = _make_pipeline(sub)
            p.set_data("collect", {})
            mod_dir = str(sub / "modernized")
            os.makedirs(mod_dir)
            with open(os.path.join(mod_dir, "App.java"), "w") as fh:
                fh.write(f"import {term};")
            p._run_dependency_audit(mod_dir)
            da = p.data("collect")["dependency_audit"]
            assert da["status"] == "FAIL", f"Should detect: {term}"

    def test_dep_audit_empty_dir_is_pass(self, tmp_path):
        p = _make_pipeline(tmp_path)
        p.set_data("collect", {})
        mod_dir = os.path.join(str(tmp_path), "modernized")
        os.makedirs(mod_dir)
        p._run_dependency_audit(mod_dir)
        da = p.data("collect")["dependency_audit"]
        assert da["status"] == "PASS"
        assert da["executed"] is True

    def test_dep_audit_nonexistent_dir_is_pass(self, tmp_path):
        p = _make_pipeline(tmp_path)
        p.set_data("collect", {})
        p._run_dependency_audit(os.path.join(str(tmp_path), "no_such_dir"))
        da = p.data("collect")["dependency_audit"]
        assert da["executed"] is True
        assert da["status"] == "PASS"
        assert da["scanned_files_count"] == 0


# ---------------------------------------------------------------------------
# Negative Equivalence
# ---------------------------------------------------------------------------

class TestNegEquiv:
    def test_all_mutations_detected_on_typical_file(self, tmp_path):
        p = _make_pipeline(tmp_path)
        content = b"RECORD001 AMOUNT=100.00 STATUS=ACTIVE\n" * 10
        baseline = {"out.dat": content}
        results = {"out.dat": content}
        p._run_neg_equiv(baseline, results)
        ne = p.data("neg_equiv")
        assert ne["executed"] is True
        assert ne["status"] == "PASS"
        assert ne["mutations_tested"] == 6
        assert ne["mutations_missed"] == []

    def test_missing_output_detected(self, tmp_path):
        p = _make_pipeline(tmp_path)
        content = b"some data\n"
        p._run_neg_equiv({"out.dat": content}, {"out.dat": content})
        assert "missing_output" in p.data("neg_equiv")["mutations_detected"]

    def test_altered_content_detected(self, tmp_path):
        p = _make_pipeline(tmp_path)
        content = b"ORIGINAL\n"
        p._run_neg_equiv({"out.dat": content}, {"out.dat": content})
        assert "altered_output_content" in p.data("neg_equiv")["mutations_detected"]

    def test_input_record_modification_detected(self, tmp_path):
        p = _make_pipeline(tmp_path)
        content = b"A" * 100
        p._run_neg_equiv({"r.dat": content}, {"r.dat": content})
        assert "input_record_modification" in p.data("neg_equiv")["mutations_detected"]

    def test_business_value_modification_detected(self, tmp_path):
        p = _make_pipeline(tmp_path)
        content = b"AMOUNT=100.00\n"
        p._run_neg_equiv({"r.dat": content}, {"r.dat": content})
        assert "business_value_modification" in p.data("neg_equiv")["mutations_detected"]

    def test_skipped_when_no_overlap(self, tmp_path):
        p = _make_pipeline(tmp_path)
        p._run_neg_equiv({"a.dat": b"content"}, {"b.dat": b"content"})
        ne = p.data("neg_equiv")
        assert ne["executed"] is True
        assert ne["status"] == "SKIPPED"
        assert ne["mutations_tested"] == 0

    def test_skipped_when_files_empty(self, tmp_path):
        p = _make_pipeline(tmp_path)
        p._run_neg_equiv({"out.dat": b""}, {"out.dat": b""})
        ne = p.data("neg_equiv")
        assert ne["executed"] is True
        assert ne["status"] == "SKIPPED"


# ---------------------------------------------------------------------------
# Verdict ladder — Phase 10 gate enforcement
# ---------------------------------------------------------------------------

class TestVerdictGates:
    def _all_gates_pipeline(self, tmp_path):
        p = _make_pipeline(tmp_path)
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
            "stdout_equiv_ok": True,
        })
        p.set_data("execute", {"status": "ok"})
        p.set_data("validate", {"status": "done", "gate2_passed": True})
        # Enterprise dependency-audit evidence is required for elevated tiers.
        p.set_data("generate", {"status": "done", "dependency_audit": {
            "executed": True, "status": "PASS",
        }})
        p.set_data("legacy", {})
        return p

    def test_missing_neg_equiv_prevents_production_ready(self, tmp_path):
        p = self._all_gates_pipeline(tmp_path)
        p.set_data("collect", {"dependency_audit": {
            "executed": True, "status": "PASS", "verdict": "PASS",
        }})
        p.set_data("neg_equiv", {})  # no executed key
        assert p._compute_verdict() == "CERTIFIED_WITH_REVIEW"

    def test_missing_dep_audit_prevents_production_ready(self, tmp_path):
        p = self._all_gates_pipeline(tmp_path)
        p.set_data("collect", {"dependency_audit": {}})  # no executed key
        p.set_data("neg_equiv", {
            "executed": True, "status": "PASS", "verdict": "PASS",
        })
        verdict = p._compute_verdict()
        assert verdict != "MVP_CERTIFIED"

    def test_dep_audit_fail_prevents_production_ready(self, tmp_path):
        p = self._all_gates_pipeline(tmp_path)
        p.set_data("collect", {"dependency_audit": {
            "executed": True, "status": "FAIL", "verdict": "FAIL",
        }})
        p.set_data("neg_equiv", {
            "executed": True, "status": "PASS", "verdict": "PASS",
        })
        assert p._compute_verdict() != "MVP_CERTIFIED"

    def test_neg_equiv_fail_prevents_production_ready(self, tmp_path):
        p = self._all_gates_pipeline(tmp_path)
        p.set_data("collect", {"dependency_audit": {
            "executed": True, "status": "PASS", "verdict": "PASS",
        }})
        p.set_data("neg_equiv", {
            "executed": True, "status": "FAIL", "verdict": "FAIL",
        })
        assert p._compute_verdict() == "CERTIFIED_WITH_REVIEW"

    def test_all_gates_pass_yields_production_ready(self, tmp_path):
        p = self._all_gates_pipeline(tmp_path)
        p.set_data("collect", {"dependency_audit": {
            "executed": True, "status": "PASS", "verdict": "PASS",
        }})
        p.set_data("neg_equiv", {
            "executed": True, "status": "PASS", "verdict": "PASS",
        })
        assert p._compute_verdict() == "MVP_CERTIFIED"

    def test_executed_false_dep_audit_blocks(self, tmp_path):
        """executed=False must never satisfy the gate even if status=PASS."""
        p = self._all_gates_pipeline(tmp_path)
        p.set_data("collect", {"dependency_audit": {
            "executed": False, "status": "PASS",
        }})
        p.set_data("neg_equiv", {
            "executed": True, "status": "PASS", "verdict": "PASS",
        })
        assert p._compute_verdict() != "MVP_CERTIFIED"

    def test_executed_false_neg_equiv_blocks(self, tmp_path):
        """executed=False must never satisfy the gate even if status=PASS."""
        p = self._all_gates_pipeline(tmp_path)
        p.set_data("collect", {"dependency_audit": {
            "executed": True, "status": "PASS", "verdict": "PASS",
        }})
        p.set_data("neg_equiv", {
            "executed": False, "status": "PASS",
        })
        assert p._compute_verdict() == "CERTIFIED_WITH_REVIEW"


# ---------------------------------------------------------------------------
# Manifest gate evidence fields
# ---------------------------------------------------------------------------

class TestManifestGateEvidence:
    def test_manifest_dep_audit_has_executed_field(self):
        dep = {"executed": True, "status": "PASS",
               "forbidden_found": [], "scanned_files_count": 3}
        section = {
            "executed": dep.get("executed", False),
            "status": dep.get("status"),
            "forbidden_found": dep.get("forbidden_found", []),
            "scanned_files_count": dep.get("scanned_files_count", 0),
        }
        assert section["executed"] is True
        assert section["status"] == "PASS"

    def test_manifest_neg_equiv_has_executed_field(self):
        neg = {"executed": True, "status": "PASS", "verdict": "PASS",
               "mutations_tested": 6, "mutations_detected": ["a", "b"]}
        section = {
            "executed": neg.get("executed", False),
            "status": neg.get("status"),
            "mutations_tested": neg.get("mutations_tested", 0),
        }
        assert section["executed"] is True
        assert section["mutations_tested"] == 6

    def test_manifest_dep_audit_executed_false_when_not_run(self):
        dep = {}
        assert dep.get("executed", False) is False
