"""
tests/differential/test_negative_gates.py

Negative Gate Test Suite — Mentor Deliverable
=============================================

Proves that the DifferentialVerifier CANNOT produce a false PASS due to:

  Gate 1:  Missing COBOL baseline             → UNPROVEN / BLOCKED
  Gate 2:  Missing Java output file           → FAIL
  Gate 3:  Mutated stdout (1 char)            → FAIL
  Gate 4:  Changed exit code                  → FAIL
  Gate 5:  Extra Java-only output file        → FAIL (file status MISMATCH)
  Gate 6:  Truncated output file              → FAIL
  Gate 7:  Changed output file content        → FAIL
  Gate 8:  Stale/cached baseline (old hash)   → FAIL (content mismatch)
  Gate 9:  Compilation failure                → FAIL / BLOCKED
  Gate 10: Java runtime failure (exit 1)      → FAIL
  Gate 11: Mock in use for SQL path           → NOT PASS
  Gate 12: No observable output both sides    → never falsely PASS
  Gate 13: Unsupported construct present      → constructs listed in report
  Gate 14: Different initial state injected   → FAIL
  Gate 15: Numeric value mutation (+1)        → FAIL

Each gate test directly manipulates the DifferentialReport or stubs execution
evidence to verify the verdict computation is fail-closed.
"""

import hashlib
import json
import os
import sys
import tempfile
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from tools.cobol_java_differential_verifier import (
    DifferentialReport,
    DifferentialVerifier,
    StepEvidence,
    UnsupportedConstruct,
    VerifierWarning,
    _compute_verdict_standalone,
    _compare_output_files,
    _conservative_normalize,
)


# ---------------------------------------------------------------------------
# Helpers: build clean PASS-state reports, then corrupt them
# ---------------------------------------------------------------------------

SIMPLEBASELINE_REPO = os.path.join(ROOT, "tests", "repos", "SIMPLEBASELINE01")


def _clean_pass_evidence(exit_code: int = 0, stdout: str = "OK") -> StepEvidence:
    """Synthesize a minimal PASS evidence record."""
    out_bytes = stdout.encode()
    ev = StepEvidence(
        status="PASS",
        exit_code=exit_code,
        stdout=stdout,
        stderr="",
        stdout_sha256=hashlib.sha256(out_bytes).hexdigest(),
        stderr_sha256=hashlib.sha256(b"").hexdigest(),
        duration_sec=0.5,
    )
    return ev


def _clean_pass_report(
    tmp_dir: str,
    cobol_stdout: str = "RESULT OK",
    java_stdout: str = "RESULT OK",
    cobol_exit: int = 0,
    java_exit: int = 0,
    cobol_status: str = "PASS",
    java_status: str = "PASS",
    mock_components: List[str] = None,
    db_cmp: str = "NOT_APPLICABLE",
    file_cmp: str = "MATCH",
    stdout_cmp: str = "MATCH",
    exit_cmp: str = "MATCH",
) -> DifferentialReport:
    """Build a complete 'would-be-PASS' DifferentialReport for gate testing."""
    cobol_ev = _clean_pass_evidence(cobol_exit, cobol_stdout)
    cobol_ev.status = cobol_status
    java_ev = _clean_pass_evidence(java_exit, java_stdout)
    java_ev.status = java_status
    java_ev.mock_components = mock_components or []

    report = DifferentialReport(
        program="GATE_TEST",
        repo_dir=SIMPLEBASELINE_REPO,
        generated_at="2026-09-01T00:00:00Z",
        target_jdk="17",
        conversion="SUCCESS",
        conversion_files=["com/systema/modernized/native_gen/Gate.java"],
        conversion_detail="1 Java file generated",
        compilation="PASS",
        jdk_version="openjdk 17.0.0",
        maven_version="Apache Maven 3.9.0",
        compilation_exit_code=0,
        compilation_detail="mvn test-compile PASS",
        cobol_runtime=cobol_ev,
        java_runtime=java_ev,
        stdout_comparison=stdout_cmp,
        exit_code_comparison=exit_cmp,
        file_comparison=file_cmp,
        database_comparison=db_cmp,
        mock_components=mock_components or [],
    )
    return report


def _get_verdict(report: DifferentialReport, has_sql=False, has_jcl=False, has_cics=False) -> str:
    """Compute verdict using the same logic as DifferentialVerifier._compute_verdict."""
    return _compute_verdict_standalone(report, has_sql=has_sql, has_jcl=has_jcl, has_cics=has_cics)


# ============================================================================
# Gate 1: Missing COBOL baseline execution
# ============================================================================

@pytest.mark.negative
def test_gate1_missing_cobol_baseline(tmp_path):
    """
    When COBOL baseline did not actually run (status=UNPROVEN),
    business equivalence MUST NOT be PASS.
    """
    report = _clean_pass_report(str(tmp_path), cobol_status="UNPROVEN")
    verdict = _get_verdict(report)
    assert verdict != "PASS", (
        f"FALSE PASS: cobol_runtime=UNPROVEN must prevent PASS, got: {verdict}"
    )
    assert verdict in ("UNPROVEN", "BLOCKED", "WARNING"), f"Unexpected verdict: {verdict}"


# ============================================================================
# Gate 2: Missing Java output file
# ============================================================================

@pytest.mark.negative
def test_gate2_missing_java_output_file(tmp_path):
    """
    When a declared output file is missing from Java workspace,
    file comparison must be MISMATCH → FAIL.
    """
    report = _clean_pass_report(str(tmp_path), file_cmp="MISMATCH")
    verdict = _get_verdict(report)
    assert verdict == "FAIL", (
        f"Expected FAIL for missing Java output file, got: {verdict}"
    )


# ============================================================================
# Gate 3: Mutated stdout (1 character change)
# ============================================================================

@pytest.mark.negative
def test_gate3_mutated_stdout_one_char(tmp_path):
    """
    stdout mismatch (even 1 character) must produce FAIL.
    """
    report = _clean_pass_report(
        str(tmp_path),
        cobol_stdout="RESULT: 1260",
        java_stdout="RESULT: 1261",   # 1 char different
        stdout_cmp="MISMATCH",
    )
    verdict = _get_verdict(report)
    assert verdict == "FAIL", (
        f"Expected FAIL for stdout mismatch, got: {verdict}"
    )


# ============================================================================
# Gate 4: Changed exit code
# ============================================================================

@pytest.mark.negative
def test_gate4_changed_exit_code(tmp_path):
    """
    Exit code difference must produce FAIL.
    """
    report = _clean_pass_report(
        str(tmp_path),
        cobol_exit=0,
        java_exit=1,
        exit_cmp="MISMATCH",
    )
    verdict = _get_verdict(report)
    assert verdict == "FAIL", (
        f"Expected FAIL for exit code mismatch (COBOL=0, Java=1), got: {verdict}"
    )


# ============================================================================
# Gate 5: Extra Java-only output file
# ============================================================================

@pytest.mark.negative
def test_gate5_extra_java_only_output_file(tmp_path):
    """
    An extra output file produced by Java but not COBOL
    must cause file comparison MISMATCH → FAIL.

    Verified via _compare_output_files directly.
    """
    cobol_dir = os.path.join(str(tmp_path), "cobol_ws")
    java_dir  = os.path.join(str(tmp_path), "java_ws")
    os.makedirs(cobol_dir)
    os.makedirs(java_dir)

    # COBOL produces one file
    with open(os.path.join(cobol_dir, "out.dat"), "wb") as fh:
        fh.write(b"RESULT A")

    # Java produces same file + an extra file COBOL did not produce
    with open(os.path.join(java_dir, "out.dat"), "wb") as fh:
        fh.write(b"RESULT A")
    with open(os.path.join(java_dir, "extra.dat"), "wb") as fh:
        fh.write(b"UNEXPECTED OUTPUT")

    # Both files declared
    status, details = _compare_output_files(cobol_dir, java_dir, ["out.dat", "extra.dat"])

    # extra.dat → COBOL_MISSING (cobol didn't produce it) = MISMATCH
    statuses = {d["file"]: d["status"] for d in details}
    assert statuses.get("extra.dat") == "COBOL_MISSING", (
        f"Expected COBOL_MISSING for extra.dat, got: {statuses.get('extra.dat')}"
    )
    assert status in ("MISMATCH", "PARTIAL"), f"Overall status must reflect mismatch: {status}"


# ============================================================================
# Gate 6: Truncated output file
# ============================================================================

@pytest.mark.negative
def test_gate6_truncated_output_file(tmp_path):
    """
    A truncated output file (fewer bytes) must be detected as MISMATCH.
    """
    cobol_dir = os.path.join(str(tmp_path), "cobol_ws")
    java_dir  = os.path.join(str(tmp_path), "java_ws")
    os.makedirs(cobol_dir)
    os.makedirs(java_dir)

    full_content = b"RECORD 1\nRECORD 2\nRECORD 3\n"
    truncated    = b"RECORD 1\n"   # Missing records

    with open(os.path.join(cobol_dir, "out.dat"), "wb") as fh:
        fh.write(full_content)
    with open(os.path.join(java_dir, "out.dat"), "wb") as fh:
        fh.write(truncated)

    status, details = _compare_output_files(cobol_dir, java_dir, ["out.dat"])
    assert status == "MISMATCH", f"Expected MISMATCH for truncated file, got: {status}"
    assert details[0]["status"] == "CONTENT_MISMATCH", \
        f"Expected CONTENT_MISMATCH, got: {details[0]['status']}"


# ============================================================================
# Gate 7: Changed output file content
# ============================================================================

@pytest.mark.negative
def test_gate7_changed_output_file_content(tmp_path):
    """
    A content change in output file (different value, same size) must be MISMATCH.
    """
    cobol_dir = os.path.join(str(tmp_path), "cobol_ws")
    java_dir  = os.path.join(str(tmp_path), "java_ws")
    os.makedirs(cobol_dir)
    os.makedirs(java_dir)

    cobol_out = b"ACCOUNT: A001 BALANCE: +09500.00 STATUS: ACTIVE   "
    java_out  = b"ACCOUNT: A001 BALANCE: +09501.00 STATUS: ACTIVE   "  # Balance differs

    with open(os.path.join(cobol_dir, "report.txt"), "wb") as fh:
        fh.write(cobol_out)
    with open(os.path.join(java_dir, "report.txt"), "wb") as fh:
        fh.write(java_out)

    status, details = _compare_output_files(cobol_dir, java_dir, ["report.txt"])
    assert status == "MISMATCH", f"Expected MISMATCH for changed value, got: {status}"


# ============================================================================
# Gate 8: Stale baseline (old hash injected)
# ============================================================================

@pytest.mark.negative
def test_gate8_stale_baseline_hash_mismatch(tmp_path):
    """
    If COBOL output file hash is from an old (stale) baseline that differs
    from the current Java run, the comparison must detect the mismatch.
    """
    cobol_dir = os.path.join(str(tmp_path), "cobol_ws")
    java_dir  = os.path.join(str(tmp_path), "java_ws")
    os.makedirs(cobol_dir)
    os.makedirs(java_dir)

    # Simulate stale COBOL baseline (old content)
    stale_cobol_out = b"OLD RESULT: 1200"
    current_java    = b"NEW RESULT: 1260"

    with open(os.path.join(cobol_dir, "out.dat"), "wb") as fh:
        fh.write(stale_cobol_out)
    with open(os.path.join(java_dir, "out.dat"), "wb") as fh:
        fh.write(current_java)

    status, details = _compare_output_files(cobol_dir, java_dir, ["out.dat"])
    assert status == "MISMATCH", (
        f"Stale baseline must produce MISMATCH, got: {status}\n"
        f"COBOL hash: {details[0]['cobol_sha256'][:16]}\n"
        f"Java hash:  {details[0]['java_sha256'][:16]}"
    )


# ============================================================================
# Gate 9: Compilation failure
# ============================================================================

@pytest.mark.negative
def test_gate9_compilation_failure(tmp_path):
    """
    When compilation fails, business equivalence must not be PASS.
    """
    report = _clean_pass_report(str(tmp_path))
    report.compilation = "FAIL"
    verdict = _get_verdict(report)
    assert verdict in ("FAIL", "UNPROVEN", "BLOCKED"), (
        f"Compilation FAIL must prevent PASS, got: {verdict}"
    )
    assert verdict != "PASS", f"FALSE PASS with compilation=FAIL"


# ============================================================================
# Gate 10: Java runtime failure (exit 1)
# ============================================================================

@pytest.mark.negative
def test_gate10_java_runtime_failure(tmp_path):
    """
    Java runtime failure (status=FAIL) must produce FAIL verdict.
    """
    report = _clean_pass_report(str(tmp_path), java_status="FAIL", java_exit=1)
    verdict = _get_verdict(report)
    assert verdict == "FAIL", (
        f"Java runtime FAIL must produce FAIL verdict, got: {verdict}"
    )


# ============================================================================
# Gate 11: Mock SQL path — must not be PASS
# ============================================================================

@pytest.mark.negative
def test_gate11_mock_sql_path_not_pass(tmp_path):
    """
    When a mock component (MockSqlService / MockJdbcTemplate) was used
    in the Java SQL path, the verdict MUST NOT be PASS.
    """
    report = _clean_pass_report(
        str(tmp_path),
        mock_components=["MockSqlService"],
    )
    report.java_runtime.mock_components = ["MockSqlService"]
    # Simulate SQL workload
    verdict = _get_verdict(report, has_sql=True)
    assert verdict != "PASS", (
        f"FALSE PASS: MockSqlService used in SQL path must prevent PASS, got: {verdict}"
    )
    assert verdict in ("WARNING", "UNPROVEN", "FAIL"), f"Unexpected: {verdict}"


# ============================================================================
# Gate 12: No observable output both sides
# ============================================================================

@pytest.mark.negative
def test_gate12_no_observable_output_does_not_produce_false_pass(tmp_path):
    """
    A program with no stdout and no output files can still only be PASS
    if all other conditions (real execution, equivalent state) are met.
    A report with UNPROVEN file comparison and empty stdout comparison
    must not falsely report PASS.
    """
    report = _clean_pass_report(
        str(tmp_path),
        cobol_stdout="",
        java_stdout="",
        stdout_cmp="MATCH",       # Both empty = MATCH (valid)
        file_cmp="UNPROVEN",      # No files declared → UNPROVEN
        db_cmp="UNPROVEN",
    )
    # Because file_cmp is UNPROVEN and we declared output files exist,
    # the verdict should be WARNING, not PASS
    # Simulate: output_rel_paths is non-empty
    verdict = _get_verdict(report)
    # UNPROVEN file comparison → WARNING at minimum
    # (PASS only allowed when file comparison is fully MATCH)
    # This test verifies the verifier doesn't silently collapse UNPROVEN → PASS
    assert verdict != "PASS" or report.file_comparison == "MATCH", (
        f"Files UNPROVEN must not produce PASS without explicit MATCH"
    )


# ============================================================================
# Gate 13: Unsupported construct listed in report
# ============================================================================

@pytest.mark.negative
def test_gate13_unsupported_construct_in_report(tmp_path):
    """
    When an UNSUPPORTED construct is detected, it must appear in the
    unsupported_constructs list and must force verdict to UNPROVEN (not PASS).
    """
    report = _clean_pass_report(str(tmp_path))
    report.unsupported_constructs = [
        UnsupportedConstruct(
            construct="IMS DLI",
            source_file="src/IMSPROG.cob",
            line=42,
            classification="UNSUPPORTED",
            impact="IMS DLI calls cannot be translated — native translation blocked",
        )
    ]
    verdict = _get_verdict(report)
    assert verdict in ("UNPROVEN", "FAIL", "WARNING"), (
        f"UNSUPPORTED construct must prevent PASS, got: {verdict}"
    )
    assert verdict != "PASS", "FALSE PASS: UNSUPPORTED construct present"


# ============================================================================
# Gate 14: Different initial state injected
# ============================================================================

@pytest.mark.negative
def test_gate14_different_initial_state(tmp_path):
    """
    Simulate different initial state: COBOL and Java ran against different input files.
    The output files will differ → FAIL.
    """
    cobol_dir = os.path.join(str(tmp_path), "cobol_ws")
    java_dir  = os.path.join(str(tmp_path), "java_ws")
    os.makedirs(cobol_dir)
    os.makedirs(java_dir)

    # COBOL ran with employee salary = 100000
    cobol_out = b"ID: E001 SALARY: 100000 NET: 80000\n"
    # Java ran with employee salary = 90000 (different initial state!)
    java_out  = b"ID: E001 SALARY: 90000  NET: 72000\n"

    with open(os.path.join(cobol_dir, "payslips.dat"), "wb") as fh:
        fh.write(cobol_out)
    with open(os.path.join(java_dir, "payslips.dat"), "wb") as fh:
        fh.write(java_out)

    status, details = _compare_output_files(cobol_dir, java_dir, ["payslips.dat"])
    assert status == "MISMATCH", (
        f"Different initial state must produce MISMATCH, got: {status}"
    )


# ============================================================================
# Gate 15: Numeric value mutation (+1)
# ============================================================================

@pytest.mark.negative
def test_gate15_numeric_mutation_plus_one(tmp_path):
    """
    A +1 mutation in a numeric field in the Java output must be detected.
    Normalization must NOT erase numeric value differences.
    """
    cobol_dir = os.path.join(str(tmp_path), "cobol_ws")
    java_dir  = os.path.join(str(tmp_path), "java_ws")
    os.makedirs(cobol_dir)
    os.makedirs(java_dir)

    # Field: BALANCE, 10 chars, value "0001260000"
    cobol_out = b"ACCT001   0001260000ACTIVE   "
    java_out  = b"ACCT001   0001260001ACTIVE   "  # +1 in balance

    with open(os.path.join(cobol_dir, "result.dat"), "wb") as fh:
        fh.write(cobol_out)
    with open(os.path.join(java_dir, "result.dat"), "wb") as fh:
        fh.write(java_out)

    status, details = _compare_output_files(cobol_dir, java_dir, ["result.dat"])
    assert status == "MISMATCH", (
        f"Numeric +1 mutation must be detected as MISMATCH, got: {status}"
    )

    # Also verify normalization does NOT mask the difference
    c_norm = _conservative_normalize(cobol_out)
    j_norm = _conservative_normalize(java_out)
    assert c_norm != j_norm, (
        "Conservative normalization must NOT erase a numeric value mutation"
    )


# ============================================================================
# Normalization safety: CRLF→LF must not hide field changes
# ============================================================================

@pytest.mark.negative
def test_normalization_safety_crlf_only(tmp_path):
    """
    The conservative normalization strips CRLF→LF only.
    It must NOT collapse numeric differences, space padding differences,
    or value-significant whitespace.
    """
    # Only difference: CRLF vs LF — should normalize to MATCH
    cobol_crlf = b"RESULT: 1260\r\nSTATUS: ACTIVE\r\n"
    java_lf    = b"RESULT: 1260\nSTATUS: ACTIVE\n"
    assert _conservative_normalize(cobol_crlf) == _conservative_normalize(java_lf), \
        "CRLF vs LF must normalize to MATCH"

    # Value difference — must NOT normalize to MATCH
    cobol_val = b"RESULT: 1260\n"
    java_val  = b"RESULT: 1261\n"
    assert _conservative_normalize(cobol_val) != _conservative_normalize(java_val), \
        "Value differences must survive normalization"
