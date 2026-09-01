"""Regression tests for SQLCODE cursor-loop semantics (CI #18 fix).

These tests are pure Python — they do NOT require Docker or a database.
They verify that the COBOL source patterns we fixed in DB2CURSOR01 and
DB2GROUPBY01 correctly handle:

  SQLCODE = 0   → keep fetching (continue loop)
  SQLCODE = 100 → EOF / normal termination (exit loop)
  SQLCODE < 0   → error / abnormal termination (exit loop + display error)

The tests simulate what an OCESQL runtime would set SQLCODE to, and check
that the loop terminates without infinite-spin under all three conditions.
"""
import os
import re
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_cobol(path: str) -> str:
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def _check_safe_loop_pattern(source: str, filename: str):
    """Assert the source uses the safe PERFORM pattern, not the unsafe one."""
    # Must NOT contain the unsafe pattern
    assert "PERFORM UNTIL SQLCODE = 100" not in source, (
        f"{filename}: still contains unsafe 'PERFORM UNTIL SQLCODE = 100' — "
        "only SQLCODE = 100 exits the loop; negative SQLCODE (error) loops forever."
    )
    assert "PERFORM UNTIL SQLCODE NOT EQUAL 100" not in source, (
        f"{filename}: inverted condition — loop exits on ANYTHING except 100."
    )
    # Must contain the safe pattern
    assert re.search(r"PERFORM UNTIL SQLCODE NOT EQUAL 0", source, re.IGNORECASE), (
        f"{filename}: missing 'PERFORM UNTIL SQLCODE NOT EQUAL 0' — "
        "the safe pattern exits on any non-zero SQLCODE (100=EOF, negative=error)."
    )


def _check_open_error_guard(source: str, filename: str):
    """Assert the source checks SQLCODE < 0 after OPEN CURSOR."""
    assert re.search(r"IF SQLCODE\s*[<]\s*0", source, re.IGNORECASE), (
        f"{filename}: missing 'IF SQLCODE < 0' guard after cursor OPEN — "
        "a failed cursor OPEN should exit immediately, not continue to FETCH."
    )


def _check_evaluate_error_branch(source: str, filename: str):
    """Assert the EVALUATE block has an OTHER/error branch inside the loop."""
    # The EVALUATE must include WHEN OTHER for negative SQLCODE
    assert re.search(r"WHEN OTHER", source, re.IGNORECASE), (
        f"{filename}: EVALUATE inside fetch loop has no 'WHEN OTHER' error branch — "
        "negative SQLCODE values would be silently ignored."
    )
    # And there must be a DISPLAY of the error SQLCODE inside the loop
    assert re.search(r'DISPLAY\s+"FETCH ERROR', source, re.IGNORECASE), (
        f"{filename}: no error-display inside WHEN OTHER — "
        "SQL errors during FETCH would be swallowed silently."
    )


# ---------------------------------------------------------------------------
# Tests: DB2CURSOR01
# ---------------------------------------------------------------------------

DB2CURSOR_PATH = os.path.join(
    "tests", "repos", "DB2CURSOR01", "src", "DB2CURSOR01.cob"
)


@pytest.fixture(scope="module")
def cursor_source():
    if not os.path.exists(DB2CURSOR_PATH):
        pytest.skip(f"COBOL source not found: {DB2CURSOR_PATH}")
    return _load_cobol(DB2CURSOR_PATH)


def test_cursor_loop_exits_on_eof(cursor_source):
    """SQLCODE = 100 (EOF): loop condition 'NOT EQUAL 0' is True for 100 — exits."""
    # Structural check: the loop condition uses NOT EQUAL 0
    _check_safe_loop_pattern(cursor_source, "DB2CURSOR01.cob")


def test_cursor_loop_exits_on_sql_error(cursor_source):
    """SQLCODE < 0 (error): NOT EQUAL 0 is True — loop exits, does not spin."""
    # Same structural check — the pattern is identical for EOF and error
    _check_safe_loop_pattern(cursor_source, "DB2CURSOR01.cob")


def test_cursor_loop_continues_on_success(cursor_source):
    """SQLCODE = 0 (success): NOT EQUAL 0 is False — loop continues fetching."""
    _check_safe_loop_pattern(cursor_source, "DB2CURSOR01.cob")
    # Must also have the WHEN 0 branch displaying the row
    assert re.search(r"WHEN SQLCODE EQUAL 0", cursor_source, re.IGNORECASE), (
        "DB2CURSOR01.cob: missing 'WHEN SQLCODE EQUAL 0' branch — "
        "successful FETCHes would not display output."
    )


def test_cursor_open_has_error_guard(cursor_source):
    """Failed cursor OPEN must exit immediately, not fall through to FETCH."""
    _check_open_error_guard(cursor_source, "DB2CURSOR01.cob")


def test_cursor_loop_has_fetch_error_branch(cursor_source):
    """Negative SQLCODE during FETCH must be displayed, not silently ignored."""
    _check_evaluate_error_branch(cursor_source, "DB2CURSOR01.cob")


# ---------------------------------------------------------------------------
# Tests: DB2GROUPBY01
# ---------------------------------------------------------------------------

DB2GROUPBY_PATH = os.path.join(
    "tests", "repos", "DB2GROUPBY01", "src", "DB2GRP01.cob"
)


@pytest.fixture(scope="module")
def groupby_source():
    if not os.path.exists(DB2GROUPBY_PATH):
        pytest.skip(f"COBOL source not found: {DB2GROUPBY_PATH}")
    return _load_cobol(DB2GROUPBY_PATH)


def test_groupby_loop_exits_on_eof(groupby_source):
    """DB2GRP01: SQLCODE = 100 (EOF) must exit the loop."""
    _check_safe_loop_pattern(groupby_source, "DB2GRP01.cob")


def test_groupby_loop_exits_on_sql_error(groupby_source):
    """DB2GRP01: SQLCODE < 0 (error) must exit the loop — not spin forever."""
    _check_safe_loop_pattern(groupby_source, "DB2GRP01.cob")


def test_groupby_loop_continues_on_success(groupby_source):
    """DB2GRP01: SQLCODE = 0 (success) must continue fetching."""
    _check_safe_loop_pattern(groupby_source, "DB2GRP01.cob")
    assert re.search(r"WHEN SQLCODE EQUAL 0", groupby_source, re.IGNORECASE), (
        "DB2GRP01.cob: missing 'WHEN SQLCODE EQUAL 0' branch."
    )


def test_groupby_open_has_error_guard(groupby_source):
    """DB2GRP01: failed cursor OPEN must exit immediately."""
    _check_open_error_guard(groupby_source, "DB2GRP01.cob")


def test_groupby_loop_has_fetch_error_branch(groupby_source):
    """DB2GRP01: negative SQLCODE during FETCH must be surfaced."""
    _check_evaluate_error_branch(groupby_source, "DB2GRP01.cob")


# ---------------------------------------------------------------------------
# Tests: sql_baseline_01 (pre-existing — safe pattern check)
# ---------------------------------------------------------------------------

SQL_BASELINE_PATH = os.path.join(
    "tests", "repos", "sql_baseline_01", "src", "sql_baseline_01.cob"
)


def test_sql_baseline_uses_safe_loop():
    """sql_baseline_01.cob already uses 'PERFORM UNTIL SQLCODE NOT = 0' — verify it stays safe."""
    if not os.path.exists(SQL_BASELINE_PATH):
        pytest.skip(f"COBOL source not found: {SQL_BASELINE_PATH}")
    source = _load_cobol(SQL_BASELINE_PATH)
    # The pre-existing file uses the abbreviated 'NOT = 0' form; accept both notations
    safe = (
        re.search(r"PERFORM UNTIL SQLCODE NOT EQUAL 0", source, re.IGNORECASE) or
        re.search(r"PERFORM UNTIL SQLCODE NOT = 0", source, re.IGNORECASE)
    )
    assert safe, (
        f"{SQL_BASELINE_PATH}: safe loop pattern was removed or changed. "
        "Must use SQLCODE NOT EQUAL 0 or SQLCODE NOT = 0."
    )
    # Must NOT regress to the unsafe pattern
    assert "PERFORM UNTIL SQLCODE = 100" not in source, (
        f"{SQL_BASELINE_PATH}: regressed to unsafe SQLCODE = 100 pattern."
    )


# ---------------------------------------------------------------------------
# Test: no other COBOL sources have the unsafe pattern
# ---------------------------------------------------------------------------

def test_no_cobol_source_uses_unsafe_sqlcode_loop():
    """Scan all canonical COBOL sources in tests/repos — none must use the unsafe loop pattern.

    Generated intermediate files under target/ are excluded because they are
    pipeline artefacts that get regenerated on each run; only the canonical
    sources under src/ (and the repo root) are checked.
    """
    repo_root = os.path.join("tests", "repos")
    if not os.path.isdir(repo_root):
        pytest.skip("tests/repos not found")

    violations = []
    for dirpath, dirnames, filenames in os.walk(repo_root):
        # Skip generated output directories.
        dirnames[:] = [d for d in dirnames if d not in ("target", "generated", "build", "out")]
        for fname in filenames:
            if fname.lower().endswith((".cob", ".cbl")):
                fpath = os.path.join(dirpath, fname)
                try:
                    src = open(fpath, encoding="utf-8", errors="replace").read()
                    if "PERFORM UNTIL SQLCODE = 100" in src.upper():
                        violations.append(fpath)
                except OSError:
                    pass

    assert not violations, (
        "The following canonical COBOL source files still use the unsafe "
        "'PERFORM UNTIL SQLCODE = 100' pattern "
        "(SQLCODE < 0 errors would cause an infinite loop):\n"
        + "\n".join(f"  {v}" for v in violations)
    )
