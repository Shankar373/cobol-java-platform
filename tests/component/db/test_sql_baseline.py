import os
import shutil
import tempfile
import subprocess
import pytest
import json
from modernize.native_pipeline import NativePipeline

# ---------------------------------------------------------------------------
# CI-portable container name:  docker-compose uses "modernization-platform-db-1"
def _get_pg_container():
    c = os.environ.get("PG_CONTAINER_NAME")
    if c:
        return c
    for candidate in ("modernization-platform-db-1", "db", "postgres"):
        try:
            if subprocess.run(["docker", "inspect", candidate], capture_output=True, text=True, timeout=5).returncode == 0:
                return candidate
        except Exception:
            pass
    return "db"

_PG_CONTAINER = _get_pg_container()


def test_sql_baseline_differential():
    """Phase 1: Real ocesql + GnuCOBOL + PostgreSQL baseline vs modernized Spring Boot + PostgreSQL.
    Verifies execution parity of SELECT, INSERT, UPDATE, DELETE, and Cursors."""

    # Skip if there is no running PostgreSQL container to target.
    probe = subprocess.run(
        ["docker", "inspect", "--format", "{{.State.Running}}", _PG_CONTAINER],
        capture_output=True, text=True, timeout=10
    )
    if probe.returncode != 0 or probe.stdout.strip() != "true":
        pytest.skip(
            f"PostgreSQL container '{_PG_CONTAINER}' is not running — "
            "start it with docker-compose or the CI setup steps before running this test. "
            f"Set PG_CONTAINER_NAME env var to override (current={_PG_CONTAINER!r})."
        )

    # Seed the test schema and data into the running container.
    # NOTE: this is NON-DESTRUCTIVE. The shared `modernization_db` CUSTOMER table is
    # created by docker/ci-seed.sql with the full column set used across the DB2 E2E
    # repos (cust_id, cust_name, dept_id, status). We must NOT `DROP TABLE` it here:
    # doing so would wipe dept_id/status and break every later DB2 E2E test that
    # queries those columns (DB2LEFTJOIN01, DB2AGGREGATE01, DB2GROUPBY01).
    # `CREATE TABLE IF NOT EXISTS` matches void when the superset already exists.
    seed_cmd = [
        "docker", "exec", "-i", _PG_CONTAINER,
        "psql", "-U", "modernize", "-d", "modernization_db",
        "-c",
        ("CREATE TABLE IF NOT EXISTS CUSTOMER "
         "(CUST_ID INT PRIMARY KEY, CUST_NAME VARCHAR(100), DEPT_ID INT, STATUS VARCHAR(10)); "
         "INSERT INTO CUSTOMER (CUST_ID, CUST_NAME) VALUES (101, 'INITIAL CUSTOMER    ') "
         "ON CONFLICT (CUST_ID) DO NOTHING;"),
    ]
    subprocess.run(seed_cmd, check=True, timeout=30)

    # Remove any stale rows that the COBOL/Java program writes during its run.
    # The COBOL program inserts CUST_ID=102 and then deletes it at the end.
    # If a prior run aborted mid-way, row 102 can be left behind; the next
    # Java INSERT then fails with 23505 (duplicate key), which aborts the
    # PostgreSQL transaction block and causes 25P02 on the subsequent UPDATE
    # and DELETE. This cleanup is test-isolation only — COBOL and Java
    # transaction semantics are not changed.
    cleanup_cmd = [
        "docker", "exec", "-i", _PG_CONTAINER,
        "psql", "-U", "modernize", "-d", "modernization_db",
        "-c", "DELETE FROM CUSTOMER WHERE CUST_ID = 102;",
    ]
    subprocess.run(cleanup_cmd, check=True, timeout=30)

    # Use a repository-relative path so this test is portable across OS.
    repo_dir = os.path.join("tests", "repos", "sql_baseline_01")
    tmp_out = tempfile.mkdtemp(prefix="sql_baseline_")

    try:
        # Set PG connection parameters in environment for the host Java run.
        os.environ["PGHOST"] = "localhost"
        os.environ["PGPORT"] = "5432"
        os.environ["PGUSER"] = "modernize"
        os.environ["PGPASSWORD"] = "modernize"
        os.environ["PGDATABASE"] = "modernization_db"

        pipe = NativePipeline(repo_dir, tmp_out)
        verdict = pipe.run()

        if verdict != "NATIVE_JAVA_VERIFIED":
            print("Verdict:", verdict)
            obs_path = os.path.join(tmp_out, "generated", "native_execution_observation.json")
            if os.path.exists(obs_path):
                with open(obs_path, "r", encoding="utf-8") as f:
                    print("Observation:", f.read())
            legacy_path = os.path.join(tmp_out, "baseline", "legacy", "stdout.txt")
            if os.path.exists(legacy_path):
                with open(legacy_path, "r", encoding="utf-8") as f:
                    print("Legacy Stdout:\n", f.read())
            modern_path = os.path.join(tmp_out, "results", "native", "stdout.txt")
            if os.path.exists(modern_path):
                with open(modern_path, "r", encoding="utf-8") as f:
                    print("Modernized Stdout:\n", f.read())

        assert verdict == "NATIVE_JAVA_VERIFIED"
    finally:
        shutil.rmtree(tmp_out, ignore_errors=True)

