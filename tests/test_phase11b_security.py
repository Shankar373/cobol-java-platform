"""Phase 11B - UI Security and Traversal Validation Tests
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
    # Find free port
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
def setup_mock_run(tmp_path_factory):
    """Creates a mock workspace on disk and registers it in ui.RUNS."""
    tmp_dir = tmp_path_factory.mktemp("sec-ws")
    out_dir = tmp_dir / "target"
    out_dir.mkdir(parents=True)
    
    # Write a test artifact inside the base directory
    (out_dir / "state.json").write_text('{"stages": {}, "data": {}}', encoding="utf-8")
    
    # Create modernized directory and file
    mod_dir = out_dir / "modernized"
    mod_dir.mkdir()
    (mod_dir / "Valid.java").write_text("public class Valid {}", encoding="utf-8")
    
    # Create report file
    (out_dir / "migration-report.md").write_text("# Report", encoding="utf-8")
    (out_dir / "pipeline_execution_manifest.json").write_text('{"execution_id": "123"}', encoding="utf-8")
    (out_dir / "modernized-package.zip").write_text("zipcontent", encoding="utf-8")
    
    # Register mock run in ui.RUNS
    run_id = "sec-run-01"
    ui.RUNS[run_id] = {
        "run_id": run_id,
        "status": "done",
        "repo": str(tmp_dir),
        "out": str(out_dir),
        "source": "test",
        "name": "Security Test Run",
        "last_stage": 0,
        "error": None,
        "log": []
    }
    
    return {
        "run_id": run_id,
        "out": str(out_dir)
    }


class TestUiSecurityE2E:

    def test_valid_access_works(self, test_server, setup_mock_run):
        base_url = test_server
        rid = setup_mock_run["run_id"]
        
        # Valid artifact content
        r = requests.get(f"{base_url}/api/artifact-content?run_id={rid}&name=state.json")
        assert r.status_code == 200
        assert "stages" in r.json()["content"]
        
        # Valid modernized file
        r = requests.get(f"{base_url}/api/modernized-file?run_id={rid}&path=Valid.java")
        assert r.status_code == 200
        assert "Valid" in r.json()["content"]
        
        # Valid report md
        r = requests.get(f"{base_url}/report?run_id={rid}")
        assert r.status_code == 200
        assert b"# Report" in r.content
        
        # Valid manifest
        r = requests.get(f"{base_url}/api/report-json?run_id={rid}&file=pipeline_execution_manifest.json")
        assert r.status_code == 200
        assert "execution_id" in r.json()
        
        # Valid package
        r = requests.get(f"{base_url}/package?run_id={rid}")
        assert r.status_code == 200
        assert r.content == b"zipcontent"

    def test_invalid_run_id_returns_error(self, test_server):
        base_url = test_server
        r = requests.get(f"{base_url}/api/artifact-content?run_id=invalid-run&name=state.json")
        assert r.status_code == 400
        assert "Artifact not available" in r.json().get("error", "")

    def test_traversal_escapes_rejected(self, test_server, setup_mock_run):
        base_url = test_server
        rid = setup_mock_run["run_id"]
        
        payloads = [
            "../ui.py",
            "../../ui.py",
            "modernized/../../../ui.py",
            "modernized/..\\..\\..\\ui.py",
            "unicode%2f..%2f..%2fui.py"
        ]
        
        for payload in payloads:
            # /api/artifact-content
            r = requests.get(f"{base_url}/api/artifact-content?run_id={rid}&name={payload}")
            assert r.status_code == 400
            assert "Artifact not available" in r.json().get("error", "")
            
            # /api/modernized-file
            r = requests.get(f"{base_url}/api/modernized-file?run_id={rid}&path={payload}")
            assert r.status_code == 400
            assert "Artifact not available" in r.json().get("error", "")

    def test_absolute_escapes_rejected(self, test_server, setup_mock_run):
        base_url = test_server
        rid = setup_mock_run["run_id"]
        
        payloads = [
            "/etc/passwd",
            "C:\\Windows\\win.ini",
            "/absolute/path/escaping/target"
        ]
        
        for payload in payloads:
            # /api/artifact-content
            r = requests.get(f"{base_url}/api/artifact-content?run_id={rid}&name={payload}")
            assert r.status_code == 400
            assert "Artifact not available" in r.json().get("error", "")
            
            # /api/modernized-file
            r = requests.get(f"{base_url}/api/modernized-file?run_id={rid}&path={payload}")
            assert r.status_code == 400
            assert "Artifact not available" in r.json().get("error", "")
