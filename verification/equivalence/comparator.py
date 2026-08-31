"""
verification/equivalence/comparator.py

Symmetric COBOL-vs-Java output comparator.

Rules (hard — cannot be relaxed):
  1. Identical input to both programs
  2. Equivalent initial DB/file state (restored before each run)
  3. Both stdout values captured from real execution
  4. Empty COBOL stdout vs non-empty Java stdout => FAIL (not PASS)
  5. Non-destructive normalisation only (trailing whitespace, line endings)
  6. Differences are reported, never silently absorbed

Output: EquivalenceResult with verdict EQUIVALENT or FAILED.
"""
from __future__ import annotations

import difflib
import json
import os
import re
from dataclasses import dataclass, field
from typing import Optional

from verification.evidence.verdict import (
    StageEvidence, Verdict, failed, equivalent
)


@dataclass
class EquivalenceResult:
    """Result of comparing COBOL and Java execution outputs."""

    verdict: Verdict

    cobol_stdout: str = ""
    java_stdout: str = ""
    cobol_exit_code: Optional[int] = None
    java_exit_code: Optional[int] = None

    # Differences found
    stdout_match: bool = False
    exit_code_match: bool = False
    stdout_diff: str = ""

    # File / DB comparisons
    file_comparisons: list[dict] = field(default_factory=list)
    db_comparisons: list[dict] = field(default_factory=list)

    notes: str = ""

    def to_stage_evidence(self) -> StageEvidence:
        if self.verdict == Verdict.EQUIVALENT:
            ev = equivalent(
                cobol_stdout=self.cobol_stdout,
                java_stdout=self.java_stdout,
                notes=self.notes,
            )
        else:
            ev = failed(
                "equivalence",
                exit_code=-1,
                notes=self.notes,
            )
            ev.artifacts["stdout_diff"] = self.stdout_diff
        return ev

    def save(self, out_dir: str) -> str:
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, "equivalence_result.json")
        data = {
            "verdict": self.verdict.value,
            "stdout_match": self.stdout_match,
            "exit_code_match": self.exit_code_match,
            "cobol_exit_code": self.cobol_exit_code,
            "java_exit_code": self.java_exit_code,
            "cobol_stdout_lines": self.cobol_stdout.count("\n"),
            "java_stdout_lines": self.java_stdout.count("\n"),
            "stdout_diff_preview": self.stdout_diff[:2000],
            "file_comparisons": self.file_comparisons,
            "db_comparisons": self.db_comparisons,
            "notes": self.notes,
        }
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        return path


def compare(
    cobol_stdout: str,
    java_stdout: str,
    *,
    cobol_exit_code: int = 0,
    java_exit_code: int = 0,
    cobol_files: Optional[dict[str, str]] = None,
    java_files: Optional[dict[str, str]] = None,
    cobol_db_rows: Optional[dict[str, list]] = None,
    java_db_rows: Optional[dict[str, list]] = None,
    out_dir: Optional[str] = None,
) -> EquivalenceResult:
    """
    Compare COBOL and Java execution outputs symmetrically.

    Parameters
    ----------
    cobol_stdout, java_stdout:
        Raw stdout from each execution.
    cobol_exit_code, java_exit_code:
        Exit codes from each execution.
    cobol_files, java_files:
        Dict mapping logical filename -> file content string.
    cobol_db_rows, java_db_rows:
        Dict mapping table_name -> list of row dicts.
    out_dir:
        If provided, save EquivalenceResult JSON here.

    Returns
    -------
    EquivalenceResult
    """
    result = EquivalenceResult(verdict=Verdict.UNVERIFIED)

    # --- Normalise stdout ---
    cobol_norm = _normalise_stdout(cobol_stdout)
    java_norm = _normalise_stdout(java_stdout)

    result.cobol_stdout = cobol_stdout
    result.java_stdout = java_stdout
    result.cobol_exit_code = cobol_exit_code
    result.java_exit_code = java_exit_code

    # Hard rule: empty COBOL output vs non-empty Java output => FAIL
    if not cobol_norm.strip() and java_norm.strip():
        result.verdict = Verdict.FAILED
        result.notes = (
            "FAIL: COBOL stdout is empty but Java stdout is non-empty. "
            "This is not equivalent."
        )
        result.stdout_match = False
        result.stdout_diff = f"COBOL: (empty)\nJAVA:\n{java_stdout[:500]}"
        if out_dir:
            result.save(out_dir)
        return result

    # Hard rule: non-empty COBOL output vs empty Java output => FAIL
    if cobol_norm.strip() and not java_norm.strip():
        result.verdict = Verdict.FAILED
        result.notes = (
            "FAIL: Java stdout is empty but COBOL stdout is non-empty. "
            "Generator likely missed DISPLAY statements."
        )
        result.stdout_match = False
        result.stdout_diff = f"COBOL:\n{cobol_stdout[:500]}\nJAVA: (empty)"
        if out_dir:
            result.save(out_dir)
        return result

    # Compare stdout
    stdout_match = cobol_norm == java_norm
    result.stdout_match = stdout_match

    if not stdout_match:
        diff_lines = list(difflib.unified_diff(
            cobol_norm.splitlines(keepends=True),
            java_norm.splitlines(keepends=True),
            fromfile="cobol_stdout",
            tofile="java_stdout",
            n=3,
        ))
        result.stdout_diff = "".join(diff_lines)
    else:
        result.stdout_diff = ""

    # Compare exit codes
    exit_match = cobol_exit_code == java_exit_code
    result.exit_code_match = exit_match

    # Compare output files
    file_match = True
    if cobol_files or java_files:
        cobol_files = cobol_files or {}
        java_files = java_files or {}
        for fname in set(list(cobol_files.keys()) + list(java_files.keys())):
            cf = _normalise_stdout(cobol_files.get(fname, ""))
            jf = _normalise_stdout(java_files.get(fname, ""))
            match = cf == jf
            file_match = file_match and match
            result.file_comparisons.append({
                "filename": fname,
                "match": match,
                "cobol_lines": cf.count("\n"),
                "java_lines": jf.count("\n"),
            })

    # Compare DB rows
    db_match = True
    if cobol_db_rows or java_db_rows:
        cobol_db_rows = cobol_db_rows or {}
        java_db_rows = java_db_rows or {}
        for table in set(list(cobol_db_rows.keys()) + list(java_db_rows.keys())):
            cr = cobol_db_rows.get(table, [])
            jr = java_db_rows.get(table, [])
            match = cr == jr
            db_match = db_match and match
            result.db_comparisons.append({
                "table": table,
                "match": match,
                "cobol_rows": len(cr),
                "java_rows": len(jr),
            })

    # Overall verdict
    all_match = stdout_match and exit_match and file_match and db_match
    if all_match:
        result.verdict = Verdict.EQUIVALENT
        result.notes = "All outputs match: stdout, exit codes, files, DB state."
    else:
        result.verdict = Verdict.FAILED
        parts = []
        if not stdout_match:
            parts.append("stdout differs")
        if not exit_match:
            parts.append(f"exit codes differ ({cobol_exit_code} vs {java_exit_code})")
        if not file_match:
            parts.append("output files differ")
        if not db_match:
            parts.append("DB rows differ")
        result.notes = "FAIL: " + "; ".join(parts)

    if out_dir:
        result.save(out_dir)

    return result


def _normalise_stdout(s: str) -> str:
    """
    Non-destructive normalisation for stdout comparison.

    Permitted:
      - Normalise Windows line endings to Unix (\r\n -> \n)
      - Strip trailing whitespace from each line
      - Strip trailing blank lines at EOF

    NOT permitted:
      - Removing or collapsing non-trailing whitespace
      - Case folding
      - Removing content
      - Ignoring encoding differences
    """
    if not s:
        return ""
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in s.split("\n")]
    # Strip trailing blank lines
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)
