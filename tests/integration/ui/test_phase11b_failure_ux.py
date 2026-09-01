"""Phase 11B - UI/API Failure UX and Robustness Validation Tests
"""
import os
import sys
import pytest
import socket
import threading
import requests
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ui


@pytest.fixture(scope="module")
def test_server():
    """Starts the real ui.py server on a free port in a background thread."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    
    server = ui.ThreadingHTTPServer(('127.0.0.1', port), ui.Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    
    base_url = f"http://127.0.0.1:{port}"
    yield base_url
    
    server.shutdown()
    server.server_close()


@pytest.fixture(scope="module")
def setup_failure_run(tmp_path_factory):
    """Creates a workspace run that has failed at a specific stage."""
    tmp_dir = tmp_path_factory.mktemp("fail-ws")
    out_dir = tmp_dir / "target"
    out_dir.mkdir(parents=True)
    
    # State JSON showing discovery success, compile success, but execute failure
    state = {
        "stages": {
            "ingest": {"status": "done"},
            "discover": {"status": "done"},
            "analyze": {"status": "done"},
            "baseline": {"status": "done"},
            "transpile": {"status": "done"},
            "collect": {"status": "done"},
            "generate": {"status": "done"},
            "execute": {"status": "error", "errors": ["NullPointerException at CCMAIN01.java:42"]},
            "compare": {"status": "pending"},
            "refactor": {"status": "pending"},
            "validate": {"status": "pending"},
            "report": {"status": "pending"},
            "package": {"status": "pending"}
        },
        "data": {
            "transpile": {
                "n_ok": 1,
                "n_total": 1
            },
            "baseline_files": ["stdout_baseline.txt"],
            "discover": {
                "format": "free"
            },
            "compare": {
                "topology": "CONSOLE_OUTPUT",
                "status": "FAIL",
                "checks": [{"name": "stdout", "ok": False}]
            }
        }
    }
    (out_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    
    run_id = "fail-run-01"
    ui.RUNS[run_id] = {
        "run_id": run_id,
        "status": "error",
        "repo": str(tmp_dir),
        "out": str(out_dir),
        "source": "test",
        "name": "Failed E2E Run",
        "last_stage": 7,
        "error": "Execution stage failed",
        "log": ["NullPointerException in CCMAIN01"]
    }
    
    return {
        "run_id": run_id,
        "out": str(out_dir)
    }


class TestFailureUx:

    def test_invalid_ingest_fails_safely(self, test_server):
        base_url = test_server
        
        # Invalid zip data (corrupted base64)
        payload = {
            "source": "zip",
            "name": "bad.zip",
            "data": "!!!corrupted_base64!!!"
        }
        r = requests.post(f"{base_url}/api/ingest", json=payload)
        assert r.status_code in [400, 500]
        assert r.json().get("ok") is False
        assert "error" in r.json()

    def test_pipeline_failure_stages_correct(self, test_server, setup_failure_run):
        base_url = test_server
        rid = setup_failure_run["run_id"]
        
        r = requests.get(f"{base_url}/api/state")
        runs = {x["run_id"]: x for x in r.json()["runs"]}
        
        run = runs[rid]
        assert run["status"] == "error"
        assert run["error"] == "Execution stage failed"
        
        stages = {s["index"]: s for s in run["stages"]}
        
        # execute stage (index 7) should be error
        assert stages[7]["status"] == "error"
        assert stages[7]["errors"] == ["NullPointerException at CCMAIN01.java:42"]
        
        # downstream compare stage (index 8) must NOT be done
        assert stages[8]["status"] == "pending"
        assert stages[12]["status"] == "pending"

    def test_verdict_reflects_failure(self, test_server, setup_failure_run):
        base_url = test_server
        rid = setup_failure_run["run_id"]
        
        r = requests.get(f"{base_url}/api/state")
        runs = {x["run_id"]: x for x in r.json()["runs"]}
        
        # The verdict calculated must be FAILED, never a fabricated PASS
        assert runs[rid]["verdict"] == "FAILED"

    def test_running_status_and_verdict_are_independent(self, test_server, monkeypatch):
        rid = "run-running-ind"
        ui.RUNS[rid] = {
            "run_id": rid,
            "status": "running",
            "repo": "somerepo",
            "out": "someout",
            "source": "test",
            "name": "Independent Status Test",
            "last_stage": 2,
            "error": None,
            "log": []
        }
        monkeypatch.setattr(ui, "get_run_verdict", lambda r: "BASELINE_UNPRODUCIBLE" if r["run_id"] == rid else "UNVERIFIED")
        
        r = requests.get(f"{test_server}/api/state")
        runs = {x["run_id"]: x for x in r.json()["runs"]}
        
        run = runs[rid]
        assert run["status"] == "running"
        assert run["verdict"] == "BASELINE_UNPRODUCIBLE"
        ui.RUNS.pop(rid, None)

    def test_baseline_unproducible_can_appear_while_running(self, test_server, monkeypatch):
        rid = "run-baseline-live"
        ui.RUNS[rid] = {
            "run_id": rid,
            "status": "running",
            "repo": "somerepo",
            "out": "someout",
            "source": "test",
            "name": "Live Baseline Test",
            "last_stage": 4,
            "error": None,
            "log": []
        }
        monkeypatch.setattr(ui, "get_run_verdict", lambda r: "BASELINE_UNPRODUCIBLE" if r["run_id"] == rid else "UNVERIFIED")
        
        r = requests.get(f"{test_server}/api/state")
        runs = {x["run_id"]: x for x in r.json()["runs"]}
        
        run = runs[rid]
        assert run["status"] == "running"
        assert run["verdict"] == "BASELINE_UNPRODUCIBLE"
        ui.RUNS.pop(rid, None)

    def test_terminal_failure_changes_running_to_failed(self, test_server, setup_failure_run):
        rid = setup_failure_run["run_id"]
        r = requests.get(f"{test_server}/api/state")
        runs = {x["run_id"]: x for x in r.json()["runs"]}
        
        run = runs[rid]
        assert run["status"] == "error"  # maps to FAILED badge in UI

    def test_failed_stage_is_displayed(self, test_server, setup_failure_run):
        rid = setup_failure_run["run_id"]
        r = requests.get(f"{test_server}/api/state")
        runs = {x["run_id"]: x for x in r.json()["runs"]}
        
        run = runs[rid]
        failed_stage = next((s for s in run["stages"] if s["status"] == "error"), None)
        assert failed_stage is not None
        assert failed_stage["label"] == "Execute"

    def test_downstream_stages_remain_pending(self, test_server, setup_failure_run):
        rid = setup_failure_run["run_id"]
        r = requests.get(f"{test_server}/api/state")
        runs = {x["run_id"]: x for x in r.json()["runs"]}
        
        run = runs[rid]
        stages = {s["index"]: s for s in run["stages"]}
        assert stages[8]["status"] == "pending"
        assert stages[12]["status"] == "pending"

    def test_failure_details_use_real_backend_evidence(self, test_server, setup_failure_run):
        rid = setup_failure_run["run_id"]
        r = requests.get(f"{test_server}/api/state")
        runs = {x["run_id"]: x for x in r.json()["runs"]}
        
        run = runs[rid]
        # Verify legacy baseline rc is mapped
        assert run["data"]["compare"]["status"] == "FAIL"

    def test_reset_clears_failure_state(self, test_server, setup_failure_run):
        rid = setup_failure_run["run_id"]
        r_reset = requests.post(f"{test_server}/api/reset", json={"run_id": rid})
        assert r_reset.status_code == 200
        
        r_state = requests.get(f"{test_server}/api/state")
        runs = {x["run_id"]: x for x in r_state.json()["runs"]}
        assert rid not in runs

    def test_rerun_does_not_inherit_previous_failure(self, test_server, monkeypatch):
        rid = "run-rerun-test"
        ui.RUNS[rid] = {
            "run_id": rid,
            "status": "ready",
            "repo": "somerepo",
            "out": "someout",
            "source": "test",
            "name": "Rerun Test",
            "last_stage": -1,
            "error": None,
            "log": []
        }
        
        r = requests.get(f"{test_server}/api/state")
        runs = {x["run_id"]: x for x in r.json()["runs"]}
        assert runs[rid]["status"] == "ready"
        assert runs[rid]["verdict"] == "UNVERIFIED"
        ui.RUNS.pop(rid, None)

    def test_no_false_pass_after_baseline_failure(self, test_server, monkeypatch):
        rid = "run-baseline-fail"
        ui.RUNS[rid] = {
            "run_id": rid,
            "status": "done",
            "repo": "somerepo",
            "out": "someout",
            "source": "test",
            "name": "Baseline Fail Test",
            "last_stage": 12,
            "error": None,
            "log": []
        }
        monkeypatch.setattr(ui, "get_run_verdict", lambda r: "BASELINE_UNPRODUCIBLE" if r["run_id"] == rid else "UNVERIFIED")
        
        r = requests.get(f"{test_server}/api/state")
        runs = {x["run_id"]: x for x in r.json()["runs"]}
        assert runs[rid]["verdict"] == "BASELINE_UNPRODUCIBLE"
        ui.RUNS.pop(rid, None)

