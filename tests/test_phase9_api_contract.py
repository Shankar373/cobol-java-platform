"""Phase 9 - API Contract Tests

Verifies ui.py build_state() exposes lifecycle fields per stage
and does not produce false PASS defaults.
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cobol_migrate as cm


@pytest.fixture
def mock_run(tmp_path, monkeypatch):
    """Monkeypatch ui.RUNS and ui.WORKSPACE so build_state() works without HTTP."""
    repo = tmp_path / "repo"
    repo.mkdir()
    out = tmp_path / "out"
    out.mkdir()

    # Write a minimal state.json
    import json
    state = {
        "stages": {
            "ingest": {
                "status": "done",
                "at": "2026-01-01T00:01:00",
                "detail": "ingested 1 file",
                "started_at": "2026-01-01T00:00:00+00:00",
                "completed_at": "2026-01-01T00:01:00+00:00",
                "duration_seconds": 60.0,
                "warnings": [],
                "errors": [],
            }
        },
        "data": {}
    }
    (out / "state.json").write_text(json.dumps(state), encoding="utf-8")

    import ui
    run_id = "test-run-01"
    monkeypatch.setattr(ui, "RUNS", {
        run_id: {
            "out": str(out),
            "status": "done",
            "source": "test",
            "name": "test-run-01",
            "last_stage": 0,
            "error": None,
            "verdict": None,
            "log": [],
        }
    })
    return run_id, out


class TestApiStateContract:
    def test_stage_has_lifecycle_fields(self, mock_run):
        import ui
        run_id, out = mock_run
        result = ui.build_state()
        runs = {r["run_id"]: r for r in result["runs"]}
        assert run_id in runs
        stages = {s["label"]: s for s in runs[run_id]["stages"]}
        # ingest is STAGES[0]; find its label
        first_stage = runs[run_id]["stages"][0]
        assert "started_at" in first_stage, "started_at must be in stage record"
        assert "completed_at" in first_stage, "completed_at must be in stage record"
        assert "duration_seconds" in first_stage, "duration_seconds must be in stage record"
        assert "warnings" in first_stage, "warnings must be in stage record"
        assert "errors" in first_stage, "errors must be in stage record"

    def test_stage_lifecycle_values_correct(self, mock_run):
        import ui
        run_id, out = mock_run
        result = ui.build_state()
        first = result["runs"][0]["stages"][0]
        assert first["started_at"] == "2026-01-01T00:00:00+00:00"
        assert first["completed_at"] == "2026-01-01T00:01:00+00:00"
        assert first["duration_seconds"] == 60.0

    def test_fresh_run_verdict_not_pass(self, mock_run):
        import ui
        run_id, out = mock_run
        result = ui.build_state()
        run = result["runs"][0]
        # verdict is None in RUNS fixture (no actual verdict set)
        assert run.get("verdict") != "PASS", "Fresh run must not have PASS verdict"

    def test_manifest_exists_field_present(self, mock_run):
        import ui
        run_id, out = mock_run
        result = ui.build_state()
        run = result["runs"][0]
        assert "manifest_exists" in run, "manifest_exists field must be in run record"

    def test_manifest_exists_false_without_file(self, mock_run):
        import ui
        run_id, out = mock_run
        result = ui.build_state()
        run = result["runs"][0]
        assert run["manifest_exists"] is False, (
            "manifest_exists must be False when pipeline_execution_manifest.json does not exist"
        )

    def test_manifest_exists_true_with_file(self, mock_run):
        import ui
        run_id, out = mock_run
        (out / "pipeline_execution_manifest.json").write_text("{}", encoding="utf-8")
        result = ui.build_state()
        run = result["runs"][0]
        assert run["manifest_exists"] is True
