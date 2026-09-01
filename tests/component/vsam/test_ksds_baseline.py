import os
import shutil
import tempfile
import subprocess
import pytest
from modernize.native_pipeline import NativePipeline

def test_ksds_baseline_differential():
    """Phase 1: Real GnuCOBOL KSDS baseline vs modernized Spring Boot + PostgreSQL.
    Verifies execution parity of WRITE, READ, START, READ NEXT, REWRITE, and DELETE."""
    pg_container = os.environ.get("PG_CONTAINER_NAME", "db")

    # Skip if there is no running PostgreSQL container to target.
    probe = subprocess.run(
        ["docker", "inspect", "--format", "{{.State.Running}}", pg_container],
        capture_output=True, text=True, timeout=10
    )
    if probe.returncode != 0 or probe.stdout.strip() != "true":
        pytest.skip(
            f"PostgreSQL container '{pg_container}' is not running — "
            "start it with docker-compose or the CI setup steps before running this test. "
            f"Set PG_CONTAINER_NAME env var to override (current={pg_container!r})."
        )

    # Seed/Cleanup Postgres DB table for VSAM KSDS emulation
    cleanup_cmd = [
        "docker", "exec", "-i", pg_container,
        "psql", "-U", "modernize", "-d", "modernization_db",
        "-c", "DROP TABLE IF EXISTS customer_vsam;"
    ]
    subprocess.run(cleanup_cmd, check=True)

    repo_dir = os.path.join("tests", "repos", "ksds_baseline_01")

    tmp_out = tempfile.mkdtemp(prefix="ksds_baseline_")

    try:
        # Set PG connection parameters in environment for host Java run
        os.environ["PGHOST"] = "localhost"
        os.environ["PGPORT"] = "5432"
        os.environ["PGUSER"] = "modernize"
        os.environ["PGPASSWORD"] = "modernize"
        os.environ["PGDATABASE"] = "modernization_db"

        pipe = NativePipeline(repo_dir, tmp_out)
        verdict = pipe.run()

        # Print debug outputs if it fails
        if verdict != "NATIVE_JAVA_VERIFIED":
            print("Verdict:", verdict)
            obs_path = os.path.join(tmp_out, "generated", "native_execution_observation.json")
            if os.path.exists(obs_path):
                with open(obs_path, "r", encoding="utf-8") as f:
                    print("Observation:", f.read())

            # Print legacy stdout
            legacy_stdout_path = os.path.join(tmp_out, "baseline", "legacy", "stdout.txt")
            if os.path.exists(legacy_stdout_path):
                with open(legacy_stdout_path, "r", encoding="utf-8") as f:
                    print("Legacy Stdout:\n", f.read())

            # Print modernized stdout
            modernized_stdout_path = os.path.join(tmp_out, "results", "native", "stdout.txt")
            if os.path.exists(modernized_stdout_path):
                with open(modernized_stdout_path, "r", encoding="utf-8") as f:
                    print("Modernized Stdout:\n", f.read())

        assert verdict == "NATIVE_JAVA_VERIFIED"
    finally:
        shutil.rmtree(tmp_out, ignore_errors=True)
