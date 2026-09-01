"""Logical indexed-file comparator verification — SELF-CONTAINED.

This test previously depended on stale pipeline leftovers under gitignored
target/baseline/legacy/, which made it fail on any fresh clone. It now
generates its own REAL evidence:

  * baseline side : CCLOAD01 compiled+run under GnuCOBOL (Docker)
  * java side     : CCLOAD01 transpiled+run under OpenSource COBOL 4J (Docker)

It then verifies the comparator detects mutated fields, missing records and
extra records on the Java-side SQLite store.

If Docker or the required images are unavailable the test is reported as
ENVIRONMENT_BLOCKED (skip) — it is never silently converted to PASS.
"""
import os
import shutil
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cobol_migrate as engine


def _image_available(image):
    if not engine.docker_available():
        return False
    try:
        engine.ensure_image(image, pull=False)
        return True
    except Exception:
        return False


@pytest.fixture(scope="module")
def generated_fixtures(tmp_path_factory):
    """Generate baseline + java indexed files by actually running the legacy loader."""
    gnucobol_ok = _image_available(engine.DEFAULT_GNUCOBOL_IMAGE)
    cobj_ok = _image_available(engine.DEFAULT_COBJ_IMAGE)
    if not (gnucobol_ok and cobj_ok):
        pytest.skip(
            "ENVIRONMENT_BLOCKED: Docker with GnuCOBOL and opensourcecobol4j "
            f"images is required (gnucobol={gnucobol_ok}, cobj={cobj_ok})")

    root = tmp_path_factory.mktemp("logical_audit")
    src_repo = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "legacy")

    discover_data = {
        "file_assigns": {
            "src/CCLOAD01.cob": [
                {
                    "assign_path": "data/work/customer.dat",
                    "logical_name": "CUSTOMER-MASTER",
                    "organization": "indexed"
                },
                {
                    "assign_path": "data/work/policy.dat",
                    "logical_name": "POLICY-MASTER",
                    "organization": "indexed"
                }
            ]
        },
        "copybook_dirs": ["copybooks"]
    }

    def _make_copy(name):
        dst = root / name
        shutil.copytree(src_repo, str(dst), ignore=shutil.ignore_patterns(
            "generated", "_preprocessed", "bin", ".git"))
        return str(dst)

    baseline_repo = _make_copy("baseline_repo")
    java_repo = _make_copy("java_repo")

    # Detect format dynamically — same as the pipeline's discover stage.
    fmt = engine.detect_format({
        "src/CCLOAD01.cob": open(os.path.join(baseline_repo, "src", "CCLOAD01.cob"),
                                 encoding="utf-8", errors="replace").read()
    })
    fmt_flag = "-free" if fmt == "free" else ""

    # --- 1. GnuCOBOL baseline ---
    build = engine.docker_run(
        engine.DEFAULT_GNUCOBOL_IMAGE, [(baseline_repo, "/repo")], "/repo",
        f"cd /repo && cobc -x {fmt_flag} -I copybooks -o load01.exe src/CCLOAD01.cob && ./load01.exe",
        shell="sh",
    )
    assert build.returncode == 0, f"GnuCOBOL fixture generation failed: {build.stderr[-500:]}"
    baseline_dir = root / "baseline" / "legacy"
    os.makedirs(baseline_dir / "data" / "work", exist_ok=True)
    for rel in ("customer.dat", "policy.dat"):
        src_f = os.path.join(baseline_repo, "data", "work", rel)
        assert os.path.isfile(src_f), f"GnuCOBOL did not produce {rel}"
        shutil.copy2(src_f, baseline_dir / "data" / "work" / rel)

    # --- 2. COBOL 4J java side ---
    rc, status, out, err = engine.transpile(java_repo, ["src/CCLOAD01.cob"], ["copybooks"], fmt)
    assert any(status.values()), f"cobj transpile produced no Java: {err[-500:]}"
    jrun = engine.docker_run(
        engine.DEFAULT_COBJ_IMAGE, [(java_repo, "/repo")], "/repo",
        ("cd /repo && rm -rf data/work && mkdir -p data/work && "
         "java -cp generated:/usr/lib/opensourcecobol4j/libcobj.jar CCLOAD01"),
        shell="sh",
    )
    assert jrun.returncode == 0, f"Java fixture run failed: {jrun.stderr[-500:]}"
    results_dir = root / "results" / "java"
    os.makedirs(results_dir / "data" / "work", exist_ok=True)
    cust_java_src = os.path.join(java_repo, "data", "work", "customer.dat")
    assert os.path.isfile(cust_java_src), "Java run did not produce customer.dat"
    shutil.copy2(cust_java_src, results_dir / "data" / "work" / "customer.dat")

    return {
        "root": str(root),
        "baseline_repo": baseline_repo,
        "discover_data": discover_data,
        "baseline_dir": str(baseline_dir),
        "results_dir": str(results_dir),
    }


def test_logical_comparator_verification(generated_fixtures):
    fx = generated_fixtures
    repo = fx["baseline_repo"]
    discover_data = fx["discover_data"]
    baseline_dir = fx["baseline_dir"]
    results_dir = fx["results_dir"]

    cust_baseline = os.path.join(baseline_dir, "data/work/customer.dat")
    cust_java = os.path.join(results_dir, "data/work/customer.dat")

    # 1. Verify files exist
    assert os.path.isfile(cust_baseline), "Baseline customer.dat missing"
    assert os.path.isfile(cust_java), "Java customer.dat missing"

    # Backup Java customer.dat to allow mutation safety
    cust_java_bak = cust_java + ".bak"
    shutil.copy2(cust_java, cust_java_bak)

    try:
        # Load schema
        schema = engine.find_indexed_layout(repo, discover_data, "data/work/customer.dat")
        assert schema is not None, "Schema parsing failed for customer.dat"

        # A. Positive case: run logical compare and check verdict
        res = engine.logical_indexed_compare(cust_baseline, cust_java,
                                             "data/work/customer.dat", repo,
                                             discover_data, baseline_dir)
        print("\n=== POSITIVE CASE EVIDENCE ===")
        print(f"res dict: {res}")
        assert res["verdict"] == "LOGICAL_MATCH", f"Expected LOGICAL_MATCH, got: {res.get('reason')}"

        # B. Negative mutation case: modify field value
        print("\n=== NEGATIVE CASE 1: MUTATED FIELD VALUE ===")
        conn = sqlite3.connect(cust_java)
        row = conn.execute("SELECT key, value FROM table0 LIMIT 1").fetchone()
        orig_key = row[0]
        orig_val = bytearray(row[1])

        orig_val[12] = ord('X')  # offset 12 = first char of CUS-NAME
        conn.execute("UPDATE table0 SET value = ? WHERE key = ?", (bytes(orig_val), orig_key))
        conn.commit()
        conn.close()

        res_mut = engine.logical_indexed_compare(cust_baseline, cust_java,
                                                 "data/work/customer.dat", repo,
                                                 discover_data, baseline_dir)
        print(f"Mutated Verdict: {res_mut['verdict']}")
        print(f"Differences details: {res_mut.get('diffs')}")
        assert res_mut["verdict"] == "LOGICAL_MISMATCH", "Failed to detect mutated field value"

        # C. Missing record mutation: delete a record
        print("\n=== NEGATIVE CASE 2: MISSING RECORD ===")
        shutil.copy2(cust_java_bak, cust_java)

        conn = sqlite3.connect(cust_java)
        conn.execute("DELETE FROM table0 WHERE key = (SELECT key FROM table0 LIMIT 1)")
        conn.commit()
        conn.close()

        res_miss = engine.logical_indexed_compare(cust_baseline, cust_java,
                                                  "data/work/customer.dat", repo,
                                                  discover_data, baseline_dir)
        print(f"Missing Record Verdict: {res_miss['verdict']}")
        print(f"Missing keys: {res_miss.get('missing_keys')}")
        assert res_miss["verdict"] == "LOGICAL_MISMATCH", "Failed to detect missing record"

        # D. Extra record mutation: add a dummy record
        print("\n=== NEGATIVE CASE 3: EXTRA RECORD ===")
        shutil.copy2(cust_java_bak, cust_java)

        conn = sqlite3.connect(cust_java)
        row = conn.execute("SELECT value FROM table0 LIMIT 1").fetchone()
        conn.execute("INSERT INTO table0 (key, value) VALUES (?, ?)", (b"999999", row[0]))
        conn.commit()
        conn.close()

        res_extra = engine.logical_indexed_compare(cust_baseline, cust_java,
                                                   "data/work/customer.dat", repo,
                                                   discover_data, baseline_dir)
        print(f"Extra Record Verdict: {res_extra['verdict']}")
        print(f"Extra keys: {res_extra.get('extra_keys')}")
        assert res_extra["verdict"] == "LOGICAL_MISMATCH", "Failed to detect extra record"

    finally:
        shutil.copy2(cust_java_bak, cust_java)
        if os.path.exists(cust_java_bak):
            os.remove(cust_java_bak)
        print("\n=== CLEANUP COMPLETE ===")
