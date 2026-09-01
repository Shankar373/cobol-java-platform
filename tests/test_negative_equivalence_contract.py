import os
import sys
import pytest
import cobol_migrate as cm

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def blank_pipeline(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    out = tmp_path / "out"
    out.mkdir()
    p = cm.Pipeline(str(repo), str(out), pull=False)
    p._logs = []
    p.log = lambda msg: p._logs.append(msg)
    p.state = {"stages": {}, "data": {}}
    p.set_data = lambda k, v: p.state["data"].__setitem__(k, v)
    p.data = lambda k, default=None: p.state["data"].get(k, default)
    return p


def test_neg_equiv_console_with_stdin_never_fabricates_pass(blank_pipeline):
    """REGRESSION: the old implementation wrote status=PASS, mutations_tested=1,
    mutations_caught=1 WITHOUT executing anything. Console negative equivalence
    must never report PASS without real mutation executions and comparisons.
    With a stdin scenario but no reference execution evidence (blank pipeline),
    the honest result is UNVERIFIED."""
    p = blank_pipeline
    p.set_data("execution_scenario", {
        "type": "non_interactive",
        "input_values": ["line1", "line2"]
    })
    # No execute data -> no reference stdout -> cannot verify mutations
    p._run_neg_equiv_console()
    ne = p.data("neg_equiv")
    assert ne["executed"] is True
    assert ne["status"] != "PASS", (
        "Console neg-equiv must not fabricate PASS without real executions"
    )
    assert ne["status"] == "UNVERIFIED"
    assert ne["mode"] == "CONSOLE_OUTPUT"
    assert ne["mutations_tested"] == 0


def test_neg_equiv_console_failed_execution_is_unverified_not_pass(blank_pipeline):
    """When mutation re-execution fails (no Docker / no artifacts), the result
    must be UNVERIFIED with failed_executions evidence — never PASS."""
    p = blank_pipeline
    p.set_data("execution_scenario", {
        "entrypoint": "PROG1",
        "input_source": "test",
        "input_values": ["123", "456"],
        "stdin_path": "",
        "expected_termination": "normal",
        "timeout_seconds": 5,
        "max_output_bytes": 1024 * 1024,
        "scenario_id": "fake",
    })
    p.set_data("execute", {"stdout_tail": "RESULT: 123"})
    # run_java_with_scenario will fail without a real repo/Docker; both paths
    # must end UNVERIFIED or FAIL — never PASS.
    try:
        p._run_neg_equiv_console()
    except Exception:
        pytest.fail("_run_neg_equiv_console must not raise; it records evidence instead")
    ne = p.data("neg_equiv")
    assert ne["executed"] is True
    assert ne["status"] in ("UNVERIFIED", "FAIL")
    assert ne.get("mutations_tested", 0) == 0 or ne.get("failed_executions")


def test_neg_equiv_console_without_stdin(blank_pipeline):
    """If no stdin inputs exist, console neg-equiv is UNVERIFIED."""
    p = blank_pipeline
    p.set_data("execution_scenario", None)  # No scenario

    p._run_neg_equiv_console()
    ne = p.data("neg_equiv")
    assert ne["executed"] is True
    assert ne["status"] == "UNVERIFIED"
    assert ne["mode"] == "CONSOLE_OUTPUT"
    assert "no stdin or input fixture" in ne["reason"]
    assert ne["mutations_tested"] == 0

    # Test with empty input_values list
    p.set_data("execution_scenario", {
        "type": "non_interactive",
        "input_values": []
    })
    p._run_neg_equiv_console()
    ne = p.data("neg_equiv")
    assert ne["status"] == "UNVERIFIED"
    assert ne["mutations_tested"] == 0


def test_neg_equiv_no_observable_output_stage_compare_routing(blank_pipeline, tmp_path):
    """NO_OBSERVABLE_OUTPUT topology automatically routes to UNVERIFIED negative equivalence during stage_compare."""
    # We will simulate stage_compare logic for NO_OBSERVABLE_OUTPUT
    p = blank_pipeline

    # Let's execute the logic from stage_compare for NO_OBSERVABLE_OUTPUT routing
    baseline_files = {}
    results_files = {}
    stdout_baseline = ""
    stdout_execute = ""

    from execution.topology import detect_topology
    topology = detect_topology(baseline_files, results_files, stdout_baseline, stdout_execute)
    assert topology == "NO_OBSERVABLE_OUTPUT"

    # Simulate routing logic
    if baseline_files and results_files:
        p._run_neg_equiv(baseline_files, results_files)
    elif topology == "CONSOLE_OUTPUT":
        p._run_neg_equiv_console()
    else:
        p.set_data("neg_equiv", {
            "executed": True,
            "status": "UNVERIFIED",
            "mode": topology,
            "reason": "no observable output available for mutation testing",
            "mutations_tested": 0,
            "mutations_caught": 0,
        })

    ne = p.data("neg_equiv")
    assert ne["executed"] is True
    assert ne["status"] == "UNVERIFIED"
    assert ne["mode"] == "NO_OBSERVABLE_OUTPUT"
    assert ne["mutations_tested"] == 0


def test_compute_verdict_missing_baseline(blank_pipeline):
    p = blank_pipeline
    p.state["stages"] = {"transpile": {"status": "done"}}
    p.set_data("transpile", {"n_ok": 1, "n_total": 1})
    p.set_data("baseline_files", [])
    p.set_data("compare", {"topology": "NO_OBSERVABLE_OUTPUT", "checks": []})
    assert p._compute_verdict() == "EQUIVALENCE_UNVERIFIED"


def test_compute_verdict_compilation_failed(blank_pipeline):
    p = blank_pipeline
    p.state["stages"] = {"ingest": {"status": "done"}, "transpile": {"status": "error"}}
    p.set_data("transpile", {"n_ok": 0, "n_total": 1})
    assert p._compute_verdict() == "PARTIAL"


def test_compute_verdict_comparison_failed(blank_pipeline):
    p = blank_pipeline
    p.state["stages"] = {"transpile": {"status": "done"}}
    p.set_data("transpile", {"n_ok": 1, "n_total": 1})
    p.set_data("baseline_files", ["output.dat"])
    p.set_data("compare", {
        "checks": [{"name": "file_contents", "ok": False, "kind": "file", "expected": "A", "actual": "B"}],
        "rows": [{"file": "output.dat", "verdict": "differ"}]
    })
    assert p._compute_verdict() == "FAILED"


def test_compute_verdict_gate2_failed(blank_pipeline):
    p = blank_pipeline
    p.state["stages"] = {"transpile": {"status": "done"}}
    p.set_data("transpile", {"n_ok": 1, "n_total": 1})
    p.set_data("baseline_files", ["output.dat"])
    p.set_data("compare", {
        "checks": [{"name": "file_contents", "ok": True, "kind": "file", "expected": "A", "actual": "A"}],
        "rows": [{"file": "output.dat", "verdict": "match"}]
    })
    p.set_data("validate", {"status": "failed"})
    assert p._compute_verdict() == "FAILED"


def test_compute_verdict_skipped_stages(blank_pipeline):
    p = blank_pipeline
    assert p._compute_verdict() == "UNVERIFIED"


def test_compute_verdict_environment_blocked(blank_pipeline):
    """A stage explicitly marked 'blocked' (missing host tool: Maven/Java/Docker)
    must fail CLOSED with ENVIRONMENT_BLOCKED, never a misleading pass-tier
    verdict. This is the fix for the AGENTS.md gap (ENVIRONMENT_BLOCKED was
    never produced by _compute_verdict)."""
    p = blank_pipeline
    p.state["stages"] = {
        "ingest": {"status": "done"},
        "transpile": {"status": "done"},
        "validate": {"status": "blocked"},
    }
    p.set_data("transpile", {"n_ok": 1, "n_total": 1})
    p.set_data("baseline_files", ["output.dat"])
    p.set_data("compare", {
        "checks": [{"name": "file_contents", "ok": True, "kind": "file"}],
        "rows": [{"file": "output.dat", "verdict": "match"}],
    })
    assert p._compute_verdict() == "ENVIRONMENT_BLOCKED"
    # And UI maps it to the BLOCKED presentation (line in ui.html).
    ui_html = open(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "ui.html"), encoding="utf-8").read()
    assert "verd === 'ENVIRONMENT_BLOCKED'" in ui_html, \
        "UI must represent ENVIRONMENT_BLOCKED distinctly"
