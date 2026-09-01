"""Phase 11B - UI End-to-End Browser Acceptance Tests
"""
import os
import sys
import pytest
import socket
import threading
import zipfile
import io
import time
from playwright.sync_api import sync_playwright
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
def minimal_cobol_zip(tmp_path_factory):
    """Generates a minimal valid COBOL repository ZIP file."""
    tmp_dir = tmp_path_factory.mktemp("test-repo")
    zip_path = tmp_dir / "smoke-repo.zip"
    
    # Create simple HELLO program
    cobol_code = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. SMOKE.
       PROCEDURE DIVISION.
           DISPLAY "SMOKE TEST SUCCESSFUL".
           GOBACK.
"""
    
    with zipfile.ZipFile(zip_path, 'w') as zf:
        # Write to subfolder
        zf.writestr("smoke/cobol/SMOKE.cob", cobol_code)
        
    return str(zip_path)


def test_empty_workspace_acceptance(test_server):
    """1. Open empty workspace and verify that no stale state or fabricated passes appear."""
    base_url = test_server
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(base_url)
        
        # Verify landing page displays ingest card and no running state
        page.wait_for_selector("text=Select Modernization Input Source")
        
        # Check verdict is not fabricated
        assert page.locator(".verdict-panel").count() == 0
        assert page.locator(".evidence-grid").count() == 0
        
        browser.close()


def test_e2e_modernization_lifecycle(test_server, minimal_cobol_zip):
    """Runs the complete E2E workflow: Ingest -> Run -> Verify stages -> View Artifacts."""
    base_url = test_server
    zip_path = minimal_cobol_zip
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Set up alerts handler for the Stop button check
        dialog_messages = []
        page.on("dialog", lambda dialog: [dialog_messages.append(dialog.message), dialog.accept()])
        
        page.goto(base_url)
        
        # --- 1. Repository Ingestion ---
        # Select and upload minimal ZIP
        page.locator("#zipFile").set_input_files(zip_path)
        page.wait_for_selector("text=smoke-repo.zip")
        
        # Click ingest
        page.click("#analyzeBtn")
        
        # Wait for workspace loading
        page.wait_for_selector("text=Workspace Name:")
        
        # Verify repository details
        assert page.locator("text=Workspace Name:").count() > 0
        assert "smoke-repo.zip" in page.locator(".repo-card").inner_text()
        
        # --- 2. Empty/Ready State Check ---
        # Verdict must initially be UNVERIFIED
        page.wait_for_selector("text=UNVERIFIED")
        assert "UNVERIFIED" in page.locator(".verdict-panel").inner_text()
        
        # --- 3. Pipeline Trigger ---
        # Click Run
        page.click("text=Run pipeline")
        
        # Wait for stages to progress and finish
        # We poll until status becomes 'done' or 'error' in runs list sidebar
        page.wait_for_selector(".run-item.active .chip-done, .run-item.active .chip-error", timeout=240000)
        
        # Verify program name is populated after discovery
        assert "SMOKE" in page.locator(".repo-card").inner_text()
        
        # --- 4. Logs Streaming Check ---
        # Navigate to logs tab and confirm log content is present
        page.click("text=Console Log")
        page.wait_for_selector("#logWindow span")
        logs_text = page.locator("#logWindow").inner_text()
        assert len(logs_text) > 0
        
        # --- 5. Stop button validation ---
        # Click Stop
        page.click("text=Stop")
        for _ in range(30):
            if len(dialog_messages) >= 2:
                break
            page.wait_for_timeout(100)
        assert len(dialog_messages) >= 2
        assert "Are you sure you want to cancel the running pipeline?" in dialog_messages[0]
        assert "Stop failed: run is not actively executing" in dialog_messages[1]
        
        # --- 6. Artifact Explorer ---
        page.click("text=Unified Explorer")
        page.wait_for_selector(".tree-node")
        
        # Click the manifest file if visible
        manifest_node = page.locator("#explorerFilesList").locator("text=pipeline_execution_manifest.json")
        if manifest_node.count() > 0:
            manifest_node.first.click()
            page.wait_for_selector("#explorerCodeWindow")
            # Wait for content to load
            for _ in range(50):
                code_text = page.locator("#explorerCodeWindow").inner_text()
                if "Retrieving file content..." not in code_text:
                    break
                page.wait_for_timeout(100)
            assert "verdict" in code_text or "stages" in code_text
            
        # --- 7. Responsive layout checks ---
        # Desktop check
        page.set_viewport_size({"width": 1366, "height": 768})
        assert page.locator(".header").is_visible()
        
        # Tablet check
        page.set_viewport_size({"width": 1024, "height": 768})
        assert page.locator(".header").is_visible()
        
        # --- 8. Reset Workspace ---
        page.click("text=Reset Workspace")
        
        # Confirm landing upload page is restored
        page.wait_for_selector("text=Select Modernization Input Source")
        
        browser.close()
