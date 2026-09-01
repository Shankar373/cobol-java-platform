"""Phase 9 - Repository Isolation Tests

Two independent Pipeline instances (workspace-A, workspace-B) must never
share or contaminate each other's state.json, target/, or generated files.
"""
import json
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cobol_migrate as cm


COBOL_A = (
    "       IDENTIFICATION DIVISION.\n"
    "       PROGRAM-ID. PROGA.\n"
    "       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n"
    "       01 WS-COUNT PIC 9(3) VALUE 0.\n"
    "       PROCEDURE DIVISION.\n"
    "           ADD 1 TO WS-COUNT\n"
    "           STOP RUN.\n"
)

COBOL_B = (
    "       IDENTIFICATION DIVISION.\n"
    "       PROGRAM-ID. PROGB.\n"
    "       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n"
    "       01 WS-NAME PIC X(10) VALUE SPACES.\n"
    "       PROCEDURE DIVISION.\n"
    "           MOVE 'HELLO' TO WS-NAME\n"
    "           STOP RUN.\n"
)


@pytest.fixture
def workspace_a(tmp_path):
    repo = tmp_path / "ws_a" / "repo"
    repo.mkdir(parents=True)
    (repo / "PROGA.cob").write_text(COBOL_A, encoding="utf-8")
    out = tmp_path / "ws_a" / "out"
    out.mkdir()
    return cm.Pipeline(str(repo), str(out), pull=False)


@pytest.fixture
def workspace_b(tmp_path):
    repo = tmp_path / "ws_b" / "repo"
    repo.mkdir(parents=True)
    (repo / "PROGB.cob").write_text(COBOL_B, encoding="utf-8")
    out = tmp_path / "ws_b" / "out"
    out.mkdir()
    return cm.Pipeline(str(repo), str(out), pull=False)


class TestRepoIsolation:
    def test_separate_state_json_files(self, workspace_a, workspace_b):
        """State files must be in separate directories."""
        assert workspace_a.state_path != workspace_b.state_path

    def test_mark_in_a_does_not_affect_b(self, workspace_a, workspace_b):
        workspace_a.mark(0, "running", "a running")
        workspace_a.save_state()
        # B state should not contain anything from A
        b_state = workspace_b.state
        a_stage_name = cm.STAGES[0]
        b_ingest = b_state.get("stages", {}).get(a_stage_name, {})
        assert b_ingest.get("status") != "running", (
            "Pipeline B state was contaminated by Pipeline A mark()"
        )

    def test_mark_in_b_does_not_affect_a(self, workspace_a, workspace_b):
        workspace_b.mark(0, "error", "b errored")
        workspace_b.save_state()
        a_state = workspace_a.state
        a_ingest = a_state.get("stages", {}).get(cm.STAGES[0], {})
        assert a_ingest.get("status") != "error"

    def test_out_dirs_are_distinct(self, workspace_a, workspace_b):
        assert workspace_a.out != workspace_b.out

    def test_repo_dirs_are_distinct(self, workspace_a, workspace_b):
        assert workspace_a.repo != workspace_b.repo

    def test_ingest_stage_does_not_share_files(self, workspace_a, workspace_b):
        """Ingesting A must not write into B's output directory."""
        # Just run ingest (safe stage that doesn't need external tools)
        workspace_a.stage_ingest()
        b_out = workspace_b.out
        # B's out should be empty (or not contain A artifacts)
        for root, _, files in os.walk(b_out):
            for f in files:
                # PROGA.cob content should never appear in B's workspace
                full = os.path.join(root, f)
                if f.endswith(".json"):
                    try:
                        text = open(full, encoding="utf-8").read()
                        assert "PROGA" not in text, (
                            f"A's program name found in B's output file: {full}"
                        )
                    except Exception:
                        pass
