"""Phase 11B - UI/API Workspace Isolation Tests
"""
import os
import sys
import pytest
import socket
import threading
import requests

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
def setup_isolation_runs(tmp_path_factory):
    """Creates Run A and Run B workspaces on disk and registers them."""
    tmp_dir = tmp_path_factory.mktemp("iso-ws")
    
    # Run A Setup
    out_a = tmp_dir / "run-a" / "target"
    out_a.mkdir(parents=True)
    (out_a / "state.json").write_text('{"stages": {}, "data": {"discover": {"format": "free"}}}', encoding="utf-8")
    (out_a / "migration-report.md").write_text("# Report A", encoding="utf-8")
    
    # Run B Setup
    out_b = tmp_dir / "run-b" / "target"
    out_b.mkdir(parents=True)
    (out_b / "state.json").write_text('{"stages": {}, "data": {"discover": {"format": "fixed"}}}', encoding="utf-8")
    (out_b / "migration-report.md").write_text("# Report B", encoding="utf-8")
    
    # Register runs
    ui.RUNS["run-a"] = {
        "run_id": "run-a",
        "status": "done",
        "repo": str(tmp_dir / "run-a" / "repo"),
        "out": str(out_a),
        "source": "test",
        "name": "Workspace Run A",
        "last_stage": 0,
        "error": None,
        "log": ["log from A"]
    }
    
    ui.RUNS["run-b"] = {
        "run_id": "run-b",
        "status": "done",
        "repo": str(tmp_dir / "run-b" / "repo"),
        "out": str(out_b),
        "source": "test",
        "name": "Workspace Run B",
        "last_stage": 0,
        "error": None,
        "log": ["log from B"]
    }
    
    return {
        "run_a": "run-a",
        "run_b": "run-b"
    }


class TestWorkspaceIsolation:

    def test_run_states_independent(self, test_server, setup_isolation_runs):
        base_url = test_server
        
        # Poll state
        r = requests.get(f"{base_url}/api/state")
        assert r.status_code == 200
        runs = {x["run_id"]: x for x in r.json()["runs"]}
        
        # Verify A vs B isolation
        assert "run-a" in runs
        assert "run-b" in runs
        
        assert runs["run-a"]["data"]["discover"]["format"] == "free"
        assert runs["run-b"]["data"]["discover"]["format"] == "fixed"
        
        assert runs["run-a"]["log"] == ["log from A"]
        assert runs["run-b"]["log"] == ["log from B"]

    def test_report_artifacts_isolation(self, test_server, setup_isolation_runs):
        base_url = test_server
        
        # Fetch report from A
        r_a = requests.get(f"{base_url}/report?run_id=run-a")
        assert r_a.status_code == 200
        assert b"# Report A" in r_a.content
        
        # Fetch report from B
        r_b = requests.get(f"{base_url}/report?run_id=run-b")
        assert r_b.status_code == 200
        assert b"# Report B" in r_b.content

    def test_workspace_reset_isolation(self, test_server, setup_isolation_runs):
        base_url = test_server
        
        # Reset run A
        r = requests.post(f"{base_url}/api/reset", json={"run_id": "run-a"})
        assert r.status_code == 200
        
        # Poll state again
        r_state = requests.get(f"{base_url}/api/state")
        runs = {x["run_id"]: x for x in r_state.json()["runs"]}
        
        # Run A should be gone completely
        assert "run-a" not in runs
        # Run B should remain untouched
        assert "run-b" in runs
        assert runs["run-b"]["data"]["discover"]["format"] == "fixed"
