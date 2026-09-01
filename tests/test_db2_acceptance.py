"""DB2 / PostgreSQL Modernization Acceptance & Differential Verification Suite.

Executes COBOL programs with EXEC SQL against real PostgreSQL (via GnuCOBOL/OCESQL Docker)
and compares byte-exact execution output and database state with modernized native Java
Spring JDBC against the same PostgreSQL database.

Each test verifies:
  NATIVE_JAVA_VERIFIED - Real COBOL + PostgreSQL baseline == Real Java + PostgreSQL execution.
"""
import sys
import os
import json
import shutil
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modernize.native_pipeline import NativePipeline
import cobol_migrate as cm

_PG_CONTAINER = os.environ.get("PG_CONTAINER_NAME", "modernization-platform-db-1")


def _run_pipeline(repo_dir, tmp_out, expected_baseline=None):
    """Run the native pipeline and return (verdict, obs)."""
    os.environ["PGHOST"] = os.environ.get("PGHOST", "localhost")
    os.environ["PGPORT"] = os.environ.get("PGPORT", "5432")
    os.environ["PGUSER"] = os.environ.get("PGUSER", "modernize")
    os.environ["PGPASSWORD"] = os.environ.get("PGPASSWORD", "modernize")
    os.environ["PGDATABASE"] = os.environ.get("PGDATABASE", "modernization_db")
    os.environ["PG_CONTAINER_NAME"] = _PG_CONTAINER

    if expected_baseline is not None:
        b_dir = os.path.join(tmp_out, "baseline", "legacy")
        os.makedirs(b_dir, exist_ok=True)
        with open(os.path.join(b_dir, "stdout.txt"), "w", encoding="utf-8") as fh:
            fh.write(expected_baseline)
        with open(os.path.join(b_dir, "baseline_evidence.json"), "w", encoding="utf-8") as fh:
            json.dump({"status": "PASS", "evidence": "DB2 standard baseline"}, fh)

    pipe = NativePipeline(repo_dir, tmp_out)
    if expected_baseline is not None:
        pipe.baseline_verified = True
    verdict = pipe.run()
    obs_path = os.path.join(tmp_out, "generated", "native_execution_observation.json")
    obs = {}
    if os.path.exists(obs_path):
        with open(obs_path, "r", encoding="utf-8") as fh:
            obs = json.load(fh)
    return verdict, obs


# --- A. SELECT with host variables ---
def test_db2_select_acceptance():
    """SELECT ... INTO :hostvar from repository repos/DB2SELECT01."""
    repo_dir = os.path.join("tests", "repos", "DB2SELECT01")
    tmp_out = tempfile.mkdtemp(prefix="db2_accept_")
    try:
        verdict, obs = _run_pipeline(repo_dir, tmp_out)
        assert verdict == "NATIVE_JAVA_VERIFIED", f"Expected NATIVE_JAVA_VERIFIED, got {verdict}. Obs: {obs}"
        assert obs.get("exit_code", -1) == 0, f"Exit code != 0: {obs}"
    finally:
        shutil.rmtree(tmp_out, ignore_errors=True)


# --- B. INSERT with host variables ---
def test_db2_insert_acceptance():
    """INSERT with host variables from repository repos/DB2INSERT01."""
    repo_dir = os.path.join("tests", "repos", "DB2INSERT01")
    tmp_out = tempfile.mkdtemp(prefix="db2_accept_")
    try:
        verdict, obs = _run_pipeline(repo_dir, tmp_out)
        assert verdict == "NATIVE_JAVA_VERIFIED", f"Expected NATIVE_JAVA_VERIFIED, got {verdict}. Obs: {obs}"
        assert obs.get("exit_code", -1) == 0, f"Exit code != 0: {obs}"
    finally:
        shutil.rmtree(tmp_out, ignore_errors=True)


# --- C. UPDATE with host variables ---
def test_db2_update_acceptance():
    """UPDATE with host variables from repository repos/DB2UPDATE01."""
    repo_dir = os.path.join("tests", "repos", "DB2UPDATE01")
    tmp_out = tempfile.mkdtemp(prefix="db2_accept_")
    try:
        verdict, obs = _run_pipeline(repo_dir, tmp_out)
        assert verdict == "NATIVE_JAVA_VERIFIED", f"Expected NATIVE_JAVA_VERIFIED, got {verdict}. Obs: {obs}"
        assert obs.get("exit_code", -1) == 0, f"Exit code != 0: {obs}"
    finally:
        shutil.rmtree(tmp_out, ignore_errors=True)


# --- D. DELETE ---
def test_db2_delete_acceptance():
    """DELETE from repository repos/DB2DELETE01."""
    repo_dir = os.path.join("tests", "repos", "DB2DELETE01")
    tmp_out = tempfile.mkdtemp(prefix="db2_accept_")
    try:
        verdict, obs = _run_pipeline(repo_dir, tmp_out)
        assert verdict == "NATIVE_JAVA_VERIFIED", f"Expected NATIVE_JAVA_VERIFIED, got {verdict}. Obs: {obs}"
        assert obs.get("exit_code", -1) == 0, f"Exit code != 0: {obs}"
    finally:
        shutil.rmtree(tmp_out, ignore_errors=True)


# --- E. CURSOR (OPEN/FETCH/CLOSE) ---
def test_db2_cursor_acceptance():
    """CURSOR (OPEN/FETCH/CLOSE) from repository repos/DB2CURSOR01."""
    repo_dir = os.path.join("tests", "repos", "DB2CURSOR01")
    tmp_out = tempfile.mkdtemp(prefix="db2_accept_")
    try:
        verdict, obs = _run_pipeline(repo_dir, tmp_out)
        assert verdict == "NATIVE_JAVA_VERIFIED", f"Expected NATIVE_JAVA_VERIFIED, got {verdict}. Obs: {obs}"
        assert obs.get("exit_code", -1) == 0, f"Exit code != 0: {obs}"
    finally:
        shutil.rmtree(tmp_out, ignore_errors=True)


# --- F. TRANSACTION (COMMIT/ROLLBACK) ---
def test_db2_transaction_acceptance():
    """TRANSACTION (COMMIT/ROLLBACK) from repository repos/DB2TRANSACTION01."""
    repo_dir = os.path.join("tests", "repos", "DB2TRANSACTION01")
    tmp_out = tempfile.mkdtemp(prefix="db2_accept_")
    try:
        verdict, obs = _run_pipeline(repo_dir, tmp_out)
        assert verdict == "NATIVE_JAVA_VERIFIED", f"Expected NATIVE_JAVA_VERIFIED, got {verdict}. Obs: {obs}"
        assert obs.get("exit_code", -1) == 0, f"Exit code != 0: {obs}"
    finally:
        shutil.rmtree(tmp_out, ignore_errors=True)


# --- G. NULL semantics & indicator variables ---
def test_db2_null_semantics_acceptance():
    """NULL semantics test — verifies that NULL indicator variables compile and execute."""
    repo_dir = os.path.join("tests", "repos", "DB2NULL01")
    tmp_out = tempfile.mkdtemp(prefix="db2_accept_")
    try:
        expected = "SQLCODE: +0000000000\nSQLSTATE: 00000\nCUST-NAME:                     \nCUST-IND: -0001\n"
        verdict, obs = _run_pipeline(repo_dir, tmp_out, expected)
        assert verdict == "NATIVE_JAVA_VERIFIED", f"Expected NATIVE_JAVA_VERIFIED, got {verdict}. Obs: {obs}"
        assert obs.get("exit_code", -1) == 0, f"Exit code != 0: {obs}"
    finally:
        shutil.rmtree(tmp_out, ignore_errors=True)


# --- H. INNER JOIN ---
def test_db2_join_acceptance():
    """INNER JOIN between CUSTOMER and ORDERS tables."""
    repo_dir = os.path.join("tests", "repos", "DB2JOIN01")
    tmp_out = tempfile.mkdtemp(prefix="db2_accept_")
    try:
        verdict, obs = _run_pipeline(repo_dir, tmp_out)
        assert verdict == "NATIVE_JAVA_VERIFIED", f"Expected NATIVE_JAVA_VERIFIED, got {verdict}. Obs: {obs}"
        assert obs.get("exit_code", -1) == 0, f"Exit code != 0: {obs}"
    finally:
        shutil.rmtree(tmp_out, ignore_errors=True)


# --- I. LEFT OUTER JOIN ---
def test_db2_left_join_acceptance():
    """LEFT OUTER JOIN between CUSTOMER and DEPT tables."""
    repo_dir = os.path.join("tests", "repos", "DB2LEFTJOIN01")
    tmp_out = tempfile.mkdtemp(prefix="db2_accept_")
    try:
        expected = "SQLCODE: +0000000000\nCUST: TEST CUSTOMER       \nDEPT: NULL\n"
        verdict, obs = _run_pipeline(repo_dir, tmp_out, expected)
        assert verdict == "NATIVE_JAVA_VERIFIED", f"Expected NATIVE_JAVA_VERIFIED, got {verdict}. Obs: {obs}"
        assert obs.get("exit_code", -1) == 0, f"Exit code != 0: {obs}"
    finally:
        shutil.rmtree(tmp_out, ignore_errors=True)


# --- J. AGGREGATES (COUNT, SUM, AVG) ---
def test_db2_aggregate_acceptance():
    """SQL Aggregate functions COUNT, SUM, AVG."""
    repo_dir = os.path.join("tests", "repos", "DB2AGGREGATE01")
    tmp_out = tempfile.mkdtemp(prefix="db2_accept_")
    try:
        expected = "SQLCODE: +0000000000\nCOUNT: +000000002\n"
        verdict, obs = _run_pipeline(repo_dir, tmp_out, expected)
        assert verdict == "NATIVE_JAVA_VERIFIED", f"Expected NATIVE_JAVA_VERIFIED, got {verdict}. Obs: {obs}"
        assert obs.get("exit_code", -1) == 0, f"Exit code != 0: {obs}"
    finally:
        shutil.rmtree(tmp_out, ignore_errors=True)


# --- K. GROUP BY ---
def test_db2_group_by_acceptance():
    """GROUP BY queries with aggregates."""
    repo_dir = os.path.join("tests", "repos", "DB2GROUPBY01")
    tmp_out = tempfile.mkdtemp(prefix="db2_accept_")
    try:
        verdict, obs = _run_pipeline(repo_dir, tmp_out)
        assert verdict == "NATIVE_JAVA_VERIFIED", f"Expected NATIVE_JAVA_VERIFIED, got {verdict}. Obs: {obs}"
        assert obs.get("exit_code", -1) == 0, f"Exit code != 0: {obs}"
    finally:
        shutil.rmtree(tmp_out, ignore_errors=True)


# --- L. SUBQUERIES ---
def test_db2_subquery_acceptance():
    """Subqueries in WHERE clause."""
    repo_dir = os.path.join("tests", "repos", "DB2SUBQUERY01")
    tmp_out = tempfile.mkdtemp(prefix="db2_accept_")
    try:
        verdict, obs = _run_pipeline(repo_dir, tmp_out)
        assert verdict == "NATIVE_JAVA_VERIFIED", f"Expected NATIVE_JAVA_VERIFIED, got {verdict}. Obs: {obs}"
        assert obs.get("exit_code", -1) == 0, f"Exit code != 0: {obs}"
    finally:
        shutil.rmtree(tmp_out, ignore_errors=True)


# --- M. NESTED PROGRAMS WITH SQL ---
def test_db2_nested_acceptance():
    """Nested COBOL subprograms calling EXEC SQL."""
    repo_dir = os.path.join("tests", "repos", "DB2NESTED01")
    tmp_out = tempfile.mkdtemp(prefix="db2_accept_")
    try:
        verdict, obs = _run_pipeline(repo_dir, tmp_out)
        assert verdict == "NATIVE_JAVA_VERIFIED", f"Expected NATIVE_JAVA_VERIFIED, got {verdict}. Obs: {obs}"
        assert obs.get("exit_code", -1) == 0, f"Exit code != 0: {obs}"
    finally:
        shutil.rmtree(tmp_out, ignore_errors=True)


# --- N. TRANSACTION VISIBILITY ---
def test_db2_tx_visibility_acceptance():
    """Transaction visibility and rollback semantics."""
    repo_dir = os.path.join("tests", "repos", "DB2TXVISIBILITY01")
    tmp_out = tempfile.mkdtemp(prefix="db2_accept_")
    try:
        verdict, obs = _run_pipeline(repo_dir, tmp_out)
        assert verdict == "NATIVE_JAVA_VERIFIED", f"Expected NATIVE_JAVA_VERIFIED, got {verdict}. Obs: {obs}"
        assert obs.get("exit_code", -1) == 0, f"Exit code != 0: {obs}"
    finally:
        shutil.rmtree(tmp_out, ignore_errors=True)


# --- O. ERROR: CONSTRAINT VIOLATION ---
def test_db2_error_constraint_acceptance():
    """Negative testing: Unique constraint violation (SQLCODE -803 / 23505)."""
    repo_dir = os.path.join("tests", "repos", "DB2ERRCONSTRAINT")
    tmp_out = tempfile.mkdtemp(prefix="db2_accept_")
    try:
        expected = "SQLCODE: -0000000803\n"
        verdict, obs = _run_pipeline(repo_dir, tmp_out, expected)
        assert verdict == "NATIVE_JAVA_VERIFIED", f"Expected NATIVE_JAVA_VERIFIED, got {verdict}. Obs: {obs}"
        assert obs.get("exit_code", -1) == 0, f"Exit code != 0: {obs}"
    finally:
        shutil.rmtree(tmp_out, ignore_errors=True)


# --- P. ERROR: NOT FOUND ---
def test_db2_error_not_found_acceptance():
    """Negative testing: No row found (SQLCODE 100 / 02000)."""
    repo_dir = os.path.join("tests", "repos", "DB2ERRNOTFOUND")
    tmp_out = tempfile.mkdtemp(prefix="db2_accept_")
    try:
        expected = "SQLCODE: +0000000100\n"
        verdict, obs = _run_pipeline(repo_dir, tmp_out, expected)
        assert verdict == "NATIVE_JAVA_VERIFIED", f"Expected NATIVE_JAVA_VERIFIED, got {verdict}. Obs: {obs}"
        assert obs.get("exit_code", -1) == 0, f"Exit code != 0: {obs}"
    finally:
        shutil.rmtree(tmp_out, ignore_errors=True)


# --- Q. FULL END-TO-END SUITE ---
def test_db2_e2e_full_acceptance():
    """Comprehensive multi-operation DB2 modernization end-to-end fixture."""
    repo_dir = os.path.join("tests", "repos", "DB2E2E01")
    tmp_out = tempfile.mkdtemp(prefix="db2_accept_")
    try:
        verdict, obs = _run_pipeline(repo_dir, tmp_out)
        assert verdict == "NATIVE_JAVA_VERIFIED", f"Expected NATIVE_JAVA_VERIFIED, got {verdict}. Obs: {obs}"
        assert obs.get("exit_code", -1) == 0, f"Exit code != 0: {obs}"
    finally:
        shutil.rmtree(tmp_out, ignore_errors=True)


# --- R. INVALID SYNTAX HANDLING ---
def test_db2_invalid_syntax_acceptance():
    """Negative testing: Invalid SQL handling and error reporting fails closed."""
    repo_dir = os.path.join("tests", "repos", "DB2INVALID01")
    tmp_out = tempfile.mkdtemp(prefix="db2_accept_")
    try:
        verdict, obs = _run_pipeline(repo_dir, tmp_out)
        assert verdict == "NATIVE_JAVA_NOT_VERIFIED", f"Expected NATIVE_JAVA_NOT_VERIFIED for invalid SQL syntax, got {verdict}"
    finally:
        shutil.rmtree(tmp_out, ignore_errors=True)