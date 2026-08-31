"""
Differential E2E Test: DB2SELECT01 (DB2 SQL SELECT INTO).

Validates:
  COBOL EXEC SQL SELECT CUST_NAME INTO :WS-CUST-NAME FROM CUSTOMER WHERE CUST_ID = :WS-CUST-ID
  vs
  Generated Native Java JDBC SELECT

Both executions connect to real PostgreSQL instance and query the customer table.
Expected outputs from both:
  SQLCODE: 000000000 (or 0)
  SQLSTATE: 00000
  CUST-NAME: TEST CUSTOMER
"""
import os
import sys
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

from cjp_platform.pipeline.pipeline import Pipeline
from verification.evidence.verdict import Verdict
from verification.baseline.baseline import docker_available

DB2SELECT01_FIXTURE = os.path.join(ROOT, "tests", "fixtures", "DB2SELECT01")
GNUCOBOL_IMAGE = os.environ.get("GNUCOBOL_IMAGE", "gnucobol-ocesql:latest")


@pytest.mark.differential
@pytest.mark.postgresql
@pytest.mark.docker
def test_db2select01_differential(tmp_path):
    assert os.path.isdir(DB2SELECT01_FIXTURE), f"Fixture not found: {DB2SELECT01_FIXTURE}"

    if not docker_available():
        pytest.skip("BLOCKED: Docker not available — PostgreSQL / GnuCOBOL container cannot run")

    out_dir = str(tmp_path / "sql_out")
    pipeline = Pipeline(
        repo_path=DB2SELECT01_FIXTURE,
        out_dir=out_dir,
        gnucobol_image=GNUCOBOL_IMAGE,
        pg_network="modernization-platform_default", # or default container network
    )
    verdict = pipeline.run()

    print("\n" + "=" * 60)
    print(verdict.summary())
    print("=" * 60)

    # Verify baseline and Java executed
    if verdict.baseline_verdict == Verdict.BLOCKED:
        pytest.skip("BLOCKED: Baseline execution blocked")

    assert verdict.baseline_verdict == Verdict.EXECUTED, (
        f"Expected COBOL baseline EXECUTED, got {verdict.baseline_verdict.value}"
    )
    assert verdict.java_build_verdict == Verdict.EXECUTED, (
        f"Expected Java EXECUTED, got {verdict.java_build_verdict.value}"
    )
    assert verdict.equivalence_verdict == Verdict.EQUIVALENT, (
        f"COBOL vs Java SQL outputs differ. Verdict: {verdict.equivalence_verdict.value}"
    )
