"""
verification/evidence/verdict.py

Defines the canonical verification verdict model.

Every stage in the pipeline emits a StageEvidence object.
The final pipeline verdict is derived from stage verdicts using
conservative rules: the weakest stage determines the overall verdict.

Verdict hierarchy (weakest to strongest):
  UNVERIFIED < BLOCKED < FAILED < JAVA_COMPILED < JAVA_EXECUTED < EQUIVALENT

Rules (hard):
  - COBOL compilation alone does NOT imply BASELINE_VERIFIED
  - Java compilation alone does NOT imply NATIVE_JAVA_VERIFIED
  - H2/mock DB state does NOT imply PostgreSQL/DB2 equivalence
  - Missing infrastructure => BLOCKED, never PASS
  - Empty COBOL output compared to non-empty Java output => FAIL (not PASS)
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class Verdict(str, Enum):
    """
    Ordered verdicts from weakest to strongest.

    Use .strength() to compare: higher = more confidence.
    """
    UNVERIFIED   = "UNVERIFIED"   # Not attempted or infrastructure missing
    BLOCKED      = "BLOCKED"      # Required tool/container/DB not available
    FAILED       = "FAILED"       # Executed but produced wrong result
    COMPILED     = "COMPILED"     # Compilation succeeded (Java or COBOL); not execution proof
    EXECUTED     = "EXECUTED"     # Program ran and exited (no equivalence claim)
    EQUIVALENT   = "EQUIVALENT"   # Both COBOL and Java ran, outputs match

    def strength(self) -> int:
        _ORDER = {
            Verdict.UNVERIFIED: 0,
            Verdict.BLOCKED:    1,
            Verdict.FAILED:     2,
            Verdict.COMPILED:   3,
            Verdict.EXECUTED:   4,
            Verdict.EQUIVALENT: 5,
        }
        return _ORDER[self]

    def is_positive(self) -> bool:
        return self in (Verdict.COMPILED, Verdict.EXECUTED, Verdict.EQUIVALENT)


@dataclass
class StageEvidence:
    """Evidence record for a single pipeline stage."""

    stage: str
    """Stage name, e.g. 'baseline', 'java_build', 'equivalence'."""

    verdict: Verdict
    """Outcome of this stage."""

    timestamp_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

    # Execution details
    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""

    # Collected artifacts
    artifacts: dict[str, str] = field(default_factory=dict)
    """Map of artifact name → absolute path on disk."""

    # Structured diagnostic messages
    diagnostics: list[dict] = field(default_factory=list)

    # Additional context
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "stage": self.stage,
            "verdict": self.verdict.value,
            "timestamp_utc": self.timestamp_utc,
            "exit_code": self.exit_code,
            "stdout_length": len(self.stdout),
            "stderr_length": len(self.stderr),
            "stdout_preview": self.stdout[:500] if self.stdout else "",
            "stderr_preview": self.stderr[:500] if self.stderr else "",
            "artifacts": self.artifacts,
            "diagnostics": self.diagnostics,
            "notes": self.notes,
        }


@dataclass
class PipelineVerdict:
    """Aggregated verdict for a complete pipeline run over one program."""

    program_name: str
    repo_path: str
    run_id: str

    stages: list[StageEvidence] = field(default_factory=list)

    @property
    def overall_verdict(self) -> Verdict:
        """
        Derives overall verdict from individual stage verdicts.

        Conservative rule: take the minimum strength verdict across all stages.
        A pipeline is only EQUIVALENT if every stage from baseline through
        equivalence succeeds.
        """
        if not self.stages:
            return Verdict.UNVERIFIED
        return min(self.stages, key=lambda s: s.verdict.strength()).verdict

    @property
    def baseline_verdict(self) -> Verdict:
        return self._stage_verdict("baseline")

    @property
    def java_build_verdict(self) -> Verdict:
        return self._stage_verdict("java_build")

    @property
    def java_execute_verdict(self) -> Verdict:
        return self._stage_verdict("java_execute")

    @property
    def equivalence_verdict(self) -> Verdict:
        return self._stage_verdict("equivalence")

    def _stage_verdict(self, name: str) -> Verdict:
        for s in self.stages:
            if s.stage == name:
                return s.verdict
        return Verdict.UNVERIFIED

    def add_stage(self, evidence: StageEvidence) -> None:
        self.stages.append(evidence)

    def save(self, out_dir: str) -> str:
        """Persist the verdict to disk as JSON. Returns the file path."""
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, "pipeline_verdict.json")
        data = {
            "program_name": self.program_name,
            "repo_path": self.repo_path,
            "run_id": self.run_id,
            "overall_verdict": self.overall_verdict.value,
            "stages": [s.to_dict() for s in self.stages],
        }
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        return path

    def summary(self) -> str:
        lines = [
            f"Program : {self.program_name}",
            f"Overall : {self.overall_verdict.value}",
        ]
        for s in self.stages:
            lines.append(f"  [{s.stage:20s}] {s.verdict.value}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Convenience builders
# ---------------------------------------------------------------------------

def blocked(stage: str, reason: str) -> StageEvidence:
    """Create a BLOCKED evidence record."""
    return StageEvidence(stage=stage, verdict=Verdict.BLOCKED, notes=reason)


def failed(stage: str, *, exit_code: int = -1, stdout: str = "", stderr: str = "", notes: str = "") -> StageEvidence:
    """Create a FAILED evidence record."""
    return StageEvidence(stage=stage, verdict=Verdict.FAILED, exit_code=exit_code,
                         stdout=stdout, stderr=stderr, notes=notes)


def compiled(stage: str, *, stdout: str = "", notes: str = "") -> StageEvidence:
    """Create a COMPILED evidence record (not execution proof)."""
    return StageEvidence(stage=stage, verdict=Verdict.COMPILED, exit_code=0,
                         stdout=stdout, notes=notes)


def executed(stage: str, *, exit_code: int = 0, stdout: str = "", stderr: str = "",
             artifacts: dict | None = None, notes: str = "") -> StageEvidence:
    """Create an EXECUTED evidence record."""
    return StageEvidence(stage=stage, verdict=Verdict.EXECUTED, exit_code=exit_code,
                         stdout=stdout, stderr=stderr, artifacts=artifacts or {}, notes=notes)


def equivalent(*, cobol_stdout: str, java_stdout: str, notes: str = "") -> StageEvidence:
    """Create an EQUIVALENT evidence record (strongest positive verdict)."""
    return StageEvidence(
        stage="equivalence",
        verdict=Verdict.EQUIVALENT,
        exit_code=0,
        notes=notes,
        artifacts={"cobol_stdout_len": str(len(cobol_stdout)),
                   "java_stdout_len": str(len(java_stdout))},
    )
