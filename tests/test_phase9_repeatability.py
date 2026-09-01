"""Phase 9 - Repeatability & Clean State Tests

Verifies running stages twice does not accumulate duplicate artifacts,
and doesn't result in corrupted state JSON or multiple zip entries.
"""
import os
import sys
import zipfile
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
    p = cm.Pipeline(str(repo), str(out), pull=False)
    p.state["data"]["ingest_hashes"] = {}
    p.state["data"]["discover"] = {
        "programs": [{"source": "DUMMY.cob", "program_id": "DUMMY", "lines": 10}],
        "format": "free",
        "entry": "DUMMY",
        "copybook_dirs": [],
        "copy_deps": {},
        "missing_copybooks": [],
        "call_graph": {},
        "file_assigns": {}
    }
    p.state["data"]["transpile"] = {
        "status": {"DUMMY.cob": True},
        "image": "opensourcecobol/opensourcecobol4j:2.0.0",
        "all_at_once_rc": 0,
        "n_ok": 1,
        "n_total": 1
    }
    p.state["data"]["collect"] = {
        "stub_flags": [],
        "java_files": ["DUMMY.java"],
        "loc_generated": 100
    }
    p.state["data"]["preserve"] = {
        "jar": "libcobj.jar",
        "version": "2.0.0",
        "size": 1000,
        "sha256": "123456789"
    }
    p.state["data"]["execute"] = {
        "command": "java -jar",
        "rc": 0,
        "stdout_tail": "success"
    }
    p.state["data"]["compare"] = {
        "rows": [],
        "verdict_counts": {"match": 0, "differ": 0},
        "checks": []
    }
    p.save_state()
    return p, out


class TestRepeatability:
    def test_run_stage_twice_no_state_corruption(self, tmp_pipeline):
        p, out = tmp_pipeline
        # Run stage_ingest once
        ok1, msg1, art1 = p.stage_ingest()
        assert ok1
        h1 = p.state["data"]["ingest_hashes"].copy()

        # Run stage_ingest again
        ok2, msg2, art2 = p.stage_ingest()
        assert ok2
        h2 = p.state["data"]["ingest_hashes"]
        assert h1 == h2
        
        # Verify that running again didn't corrupt the data structure
        assert isinstance(p.state["data"]["ingest_hashes"], dict)

    def test_stage_package_twice_no_duplicate_zip_entries(self, tmp_pipeline):
        p, out = tmp_pipeline
        p.stage_report()
        (out / "generated").mkdir(exist_ok=True)
        
        # Package first time
        ok1, msg1, art1 = p.stage_package()
        assert ok1
        pkg_zip = out / "modernized-package.zip"
        assert pkg_zip.exists()
        
        with zipfile.ZipFile(str(pkg_zip)) as zf:
            namelist1 = zf.namelist()
            # No duplicate entries should be returned by namelist
            assert len(namelist1) == len(set(namelist1))

        # Package second time
        ok2, msg2, art2 = p.stage_package()
        assert ok2
        with zipfile.ZipFile(str(pkg_zip)) as zf:
            namelist2 = zf.namelist()
            assert len(namelist2) == len(set(namelist2))
            assert "reports/pipeline_execution_manifest.json" in namelist2
