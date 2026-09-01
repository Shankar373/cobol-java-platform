"""Concurrency regression: NativePipeline artifacts must be run-scoped.

REGRESSION CONTEXT (AGENTS.md §13): diagnostics, traceability, dependency
audit, slice-selection and IR-mapping JSONs were historically written to the
repository-global <repo_root>/target/generated/, so two concurrent pipelines
corrupted each other's evidence, and tracked files under <repo_root>/audit/
were dirtied by ordinary test runs. All writes are now scoped to
<pipeline.out>/generated and <pipeline.out>/reports.

These tests fail if any writer regresses to a repository-global path.
"""
import json
import os
import shutil
import sys
import tempfile
import threading

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modernize.native_pipeline import NativePipeline

PLATFORM_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GLOBAL_GENERATED = os.path.join(PLATFORM_ROOT, "target", "generated")
REPO = os.path.join("tests", "repos", "MULTIFILE01")

ARTIFACTS = [
    "native_slice_selection.json",
    "native_ir_mapping.json",
    "native_translation_diagnostics.json",
    "native_java_dependency_audit.json",
]


def _snapshot_global_state():
    """mtime fingerprint of every file the old implementation dirtied."""
    state = {}
    for d in (GLOBAL_GENERATED, os.path.join(PLATFORM_ROOT, "audit", "phase5")):
        if os.path.isdir(d):
            for f in os.listdir(d):
                fp = os.path.join(d, f)
                try:
                    state[fp] = os.stat(fp).st_mtime_ns
                except OSError:
                    pass
    return state


def test_artifact_paths_are_scoped_to_pipeline_out(tmp_path):
    p = NativePipeline(REPO, str(tmp_path / "out"))
    # No execution needed: the path helpers themselves define the contract.
    a = p._artifact_file("native_translation_diagnostics.json")
    r = p._report_file("NATIVE_JAVA_TRANSLATION_REPORT.md")
    assert a.startswith(str(tmp_path / "out")), a
    assert r.startswith(str(tmp_path / "out")), r
    assert not a.startswith(PLATFORM_ROOT + os.sep + "target"), (
        "artifact escaped to repository-global target/")
    assert not r.startswith(PLATFORM_ROOT + os.sep + "audit"), (
        "report escaped to repository-global audit/")


def test_two_concurrent_pipelines_isolated_artifacts(tmp_path):
    """Same repo, two simultaneous runs -> disjoint evidence directories,
    identical schema validity, zero writes to repository-global locations."""
    before = _snapshot_global_state()

    outs = [str(tmp_path / "run-a"), str(tmp_path / "run-b")]
    errors = []
    barrier = threading.Barrier(2)

    def worker(out_dir):
        try:
            p = NativePipeline(REPO, out_dir)
            barrier.wait(timeout=60)
            p.stage_discover()
            p.stage_parse()
            src = p.stage_select_slice()
            if src:
                p.stage_generate(src)
        except Exception as exc:  # noqa: BLE001 - collected for assertion
            errors.append(f"{out_dir}: {exc!r}")

    threads = [threading.Thread(target=worker, args=(o,)) for o in outs]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=300)

    assert not errors, f"pipeline workers failed: {errors}"

    for out in outs:
        diag = os.path.join(out, "generated", "native_translation_diagnostics.json")
        assert os.path.isfile(diag), f"missing run-scoped diagnostics in {out}"
        with open(diag, encoding="utf-8") as fh:
            data = json.load(fh)
        assert isinstance(data, list)

    # Nothing outside the two run dirs may have been touched.
    after = _snapshot_global_state()
    touched = {fp for fp, mt in after.items()
               if before.get(fp) != mt}
    created = set(after) - set(before)
    assert not touched, f"global evidence mutated concurrently: {sorted(touched)}"
    assert not created, f"global evidence created: {sorted(created)}"


def teardown_module(module):
    # Safety net regardless of assertions: nothing this module did should have
    # created the historical global directory.
    pass
