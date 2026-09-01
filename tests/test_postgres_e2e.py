import os
import shutil
import tempfile
import json
import pytest
from modernize.native_pipeline import NativePipeline

def test_postgres_integration_e2e(monkeypatch):
    """Verify Track B generated Spring Boot code executes against a live PostgreSQL database."""
    # Only run if a local PostgreSQL container is reachable on port 5432
    import socket
    s = socket.socket()
    s.settimeout(2.0)
    try:
        s.connect(("127.0.0.1", 5432))
        s.close()
    except Exception:
        pytest.skip("PostgreSQL container is not reachable on localhost:5432 — skipping PostgreSQL integration test")

    # Configure environmental variables to override H2 defaults and direct Spring Boot to PostgreSQL
    monkeypatch.setenv("SPRING_DATASOURCE_URL", "jdbc:postgresql://127.0.0.1:5432/postgres")
    monkeypatch.setenv("SPRING_DATASOURCE_USERNAME", "postgres")
    monkeypatch.setenv("SPRING_DATASOURCE_PASSWORD", "postgres")
    monkeypatch.setenv("SPRING_DATASOURCE_DRIVER", "org.postgresql.Driver")
    monkeypatch.setenv("SPRING_JPA_DIALECT", "org.hibernate.dialect.PostgreSQLDialect")

    repo_dir = os.path.join("tests", "repos", "DB2SELECT01")
    temp_out = tempfile.mkdtemp(prefix="pg_e2e_")

    try:
        # Pre-seed baseline stdout
        baseline_dir = os.path.join(temp_out, "baseline", "legacy")
        os.makedirs(baseline_dir, exist_ok=True)
        expected = "SQLCODE: +0000000000\nSQLSTATE: 00000\nCUST-NAME: TEST CUSTOMER       \n"
        with open(os.path.join(baseline_dir, "stdout.txt"), "w", encoding="utf-8") as fh:
            fh.write(expected)
        with open(os.path.join(baseline_dir, "baseline_evidence.json"), "w", encoding="utf-8") as fh:
            json.dump({"status": "PASS", "evidence": "DB2 standard baseline"}, fh)

        p = NativePipeline(repo_dir, temp_out)
        p.baseline_verified = True
        verdict = p.run()

        # Assert successful validation against the real PostgreSQL container
        assert verdict == "NATIVE_JAVA_VERIFIED", f"PostgreSQL integration pipeline failed: {verdict}"

        obs_file = os.path.join(temp_out, "generated", "native_execution_observation.json")
        assert os.path.exists(obs_file)
        with open(obs_file, "r", encoding="utf-8") as fh:
            obs = json.load(fh)
            assert obs["exit_code"] == 0

    finally:
        shutil.rmtree(temp_out, ignore_errors=True)
