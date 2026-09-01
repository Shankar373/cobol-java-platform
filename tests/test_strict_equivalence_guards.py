from pathlib import Path
from modernize.native_pipeline import NativePipeline


def make_pipeline(tmp_path: Path) -> NativePipeline:
    repo = tmp_path / "repo"
    out = tmp_path / "out"
    repo.mkdir()
    out.mkdir()
    return NativePipeline(str(repo), str(out))


def test_equivalence_requires_current_baseline_evidence(tmp_path):
    p = make_pipeline(tmp_path)
    baseline = Path(p.out) / "baseline" / "legacy"
    native = Path(p.out) / "results" / "native"
    baseline.mkdir(parents=True)
    native.mkdir(parents=True)
    (baseline / "stdout.txt").write_text("ok\n", encoding="utf-8")
    (native / "stdout.txt").write_text("ok\n", encoding="utf-8")
    assert p.stage_equivalence_gate("unused") == "UNVERIFIED"


def test_equivalence_compares_symmetric_file_sets(tmp_path):
    p = make_pipeline(tmp_path)
    p.baseline_verified = True
    baseline = Path(p.out) / "baseline" / "legacy"
    native = Path(p.out) / "results" / "native"
    baseline.mkdir(parents=True)
    native.mkdir(parents=True)
    (baseline / "stdout.txt").write_text("ok\n", encoding="utf-8")
    (native / "stdout.txt").write_text("ok\n", encoding="utf-8")
    (native / "extra.txt").write_text("unexpected\n", encoding="utf-8")
    assert p.stage_equivalence_gate("unused") == "FAIL"


def test_equivalence_does_not_strip_business_zeroes(tmp_path):
    p = make_pipeline(tmp_path)
    p.baseline_verified = True
    baseline = Path(p.out) / "baseline" / "legacy"
    native = Path(p.out) / "results" / "native"
    baseline.mkdir(parents=True)
    native.mkdir(parents=True)
    (baseline / "stdout.txt").write_text("000123\n", encoding="utf-8")
    (native / "stdout.txt").write_text("123\n", encoding="utf-8")
    assert p.stage_equivalence_gate("unused") == "FAIL"
