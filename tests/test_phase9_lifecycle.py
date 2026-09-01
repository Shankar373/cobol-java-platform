"""Phase 9 - Pipeline Lifecycle Tests

Verifies:
- mark(running) sets started_at
- mark(done) sets completed_at + duration_seconds
- mark(error) sets completed_at
- warnings and errors fields are stored
- a failed stage raises RuntimeError and downstream stages cannot become done
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cobol_migrate as cm


@pytest.fixture
def tmp_pipeline(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    out = tmp_path / "out"
    out.mkdir()
    (repo / "DUMMY.cob").write_text(
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. DUMMY.\n"
        "       PROCEDURE DIVISION.\n"
        "           STOP RUN.\n",
        encoding="utf-8",
    )
    return cm.Pipeline(str(repo), str(out), pull=False)


class TestMarkLifecycle:
    def test_mark_running_sets_started_at(self, tmp_pipeline):
        p = tmp_pipeline
        p.mark(0, "running", "in progress")
        st = p.state["stages"][cm.STAGES[0]]
        assert st["status"] == "running"
        assert st.get("started_at"), "started_at must be set when status=running"
        assert not st.get("completed_at"), "completed_at must NOT be set while running"

    def test_mark_done_sets_completed_at_and_duration(self, tmp_pipeline):
        p = tmp_pipeline
        p.mark(0, "running", "starting")
        p.mark(0, "done", "finished", artifacts=["a.jar"])
        st = p.state["stages"][cm.STAGES[0]]
        assert st["status"] == "done"
        assert st.get("completed_at"), "completed_at required after done"
        dur = st.get("duration_seconds")
        assert dur is not None and isinstance(dur, (int, float)) and dur >= 0

    def test_mark_error_sets_completed_at(self, tmp_pipeline):
        p = tmp_pipeline
        p.mark(0, "running", "starting")
        p.mark(0, "error", "exploded")
        st = p.state["stages"][cm.STAGES[0]]
        assert st["status"] == "error"
        assert st.get("completed_at"), "completed_at required after error"

    def test_warnings_stored(self, tmp_pipeline):
        p = tmp_pipeline
        p.mark(0, "running")
        p.mark(0, "done", "ok", warnings=["w1", "w2"])
        st = p.state["stages"][cm.STAGES[0]]
        assert st["warnings"] == ["w1", "w2"]

    def test_errors_stored(self, tmp_pipeline):
        p = tmp_pipeline
        p.mark(0, "running")
        p.mark(0, "error", "bad", errors=["e1"])
        st = p.state["stages"][cm.STAGES[0]]
        assert st["errors"] == ["e1"]

    def test_running_does_not_set_completed_at(self, tmp_pipeline):
        p = tmp_pipeline
        p.mark(0, "running", "going")
        st = p.state["stages"][cm.STAGES[0]]
        assert not st.get("completed_at")

    def test_duration_nonnegative(self, tmp_pipeline):
        p = tmp_pipeline
        p.mark(0, "running")
        p.mark(0, "done", "fast")
        dur = p.state["stages"][cm.STAGES[0]].get("duration_seconds")
        assert dur is not None and dur >= 0


class TestDownstreamBlocking:
    def test_failed_stage_prevents_downstream(self, tmp_pipeline):
        """Pipeline.run() raises RuntimeError on stage failure; no later stage runs."""
        p = tmp_pipeline
        original = p.stage_ingest

        def _failing():
            return False, "injected failure", []

        p.stage_ingest = _failing
        with pytest.raises(RuntimeError, match="ingest"):
            p.run()
        stages = p.state.get("stages", {})
        for name in cm.STAGES[1:]:
            st = stages.get(name, {})
            assert st.get("status") != "done", (
                f"Downstream stage '{name}' must not be done after ingest failure"
            )

    def test_failed_stage_records_error_status(self, tmp_pipeline):
        p = tmp_pipeline

        def _failing():
            return False, "deliberate failure", []

        p.stage_ingest = _failing
        try:
            p.run()
        except RuntimeError:
            pass
        st = p.state["stages"].get(cm.STAGES[0], {})
        assert st.get("status") == "error"
