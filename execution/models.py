"""Shared data models for the execution layer.

Separated into its own module so all other modules can import without circular deps.
"""
import hashlib
import json
import os
from dataclasses import dataclass, field, asdict
from typing import Any


# ---------------------------------------------------------------------------
# Exceptions — all names match the spec error codes
# ---------------------------------------------------------------------------

class InteractiveInputRequired(RuntimeError):
    """Raised when an interactive program has no safe deterministic scenario.

    Message includes the diagnostic text defined in spec §6:
        INTERACTIVE_INPUT_REQUIRED
        ...
    """


class ExecutionTimeout(RuntimeError):
    """Raised when the watchdog kills a process that exceeded timeout_seconds."""


class OutputLimitExceeded(RuntimeError):
    """Raised when stdout+stderr exceed max_output_bytes."""


class InputExhausted(RuntimeError):
    """Raised when the program requests more input after stdin is fully consumed."""


# ---------------------------------------------------------------------------
# ExecutionScenario
# ---------------------------------------------------------------------------

@dataclass
class ExecutionScenario:
    """Immutable representation of a deterministic interactive execution scenario.

    scenario_id is a deterministic SHA-256 so the same logical scenario always
    produces the same ID — proving that COBOL and Java used identical input.
    """
    entrypoint: str               # program ID (e.g. "BANKMAIN")
    input_source: str             # human-readable origin (file path or "static-analysis")
    input_values: list            # ordered list of stdin lines
    stdin_path: str               # absolute path to the written temp file
    expected_termination: str     # "normal" | "unknown"
    timeout_seconds: int          # watchdog timeout
    max_output_bytes: int         # output-size cap
    scenario_id: str = field(default="")  # set post-init
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.scenario_id:
            self.scenario_id = self._compute_id()

    def _compute_id(self) -> str:
        """Deterministic content-hash so COBOL and Java IDs are always identical."""
        blob = json.dumps({
            "entrypoint": self.entrypoint,
            "input_source": self.input_source,
            "input_values": self.input_values,
            "timeout_seconds": self.timeout_seconds,
        }, sort_keys=True).encode()
        return hashlib.sha256(blob).hexdigest()[:32]

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ExecutionScenario":
        # stdin_path may not exist when reloaded on a different host; that is
        # intentional — stage_execute recreates the file from input_values.
        return cls(
            entrypoint=d["entrypoint"],
            input_source=d["input_source"],
            input_values=d["input_values"],
            stdin_path=d.get("stdin_path", ""),
            expected_termination=d.get("expected_termination", "unknown"),
            timeout_seconds=d.get("timeout_seconds", 120),
            max_output_bytes=d.get("max_output_bytes", 5 * 1024 * 1024),
            scenario_id=d.get("scenario_id", ""),
            metadata=d.get("metadata", {}),
        )


# ---------------------------------------------------------------------------
# ExecutionResult
# ---------------------------------------------------------------------------

@dataclass
class ExecutionResult:
    """Outcome of a single COBOL or Java execution attempt."""
    rc: int
    stdout: str
    stderr: str
    duration_seconds: float
    termination_status: str      # normal | timeout | input_exhausted | output_limit |
                                 #  nonzero_exit | killed | error
    scenario_id: str
    artifacts_dir: str           # absolute path where artifacts were written
    command: str = ""
    execution_mode: str = ""     # "non-interactive" | "interactive-scripted"
    inputs_consumed: int = 0     # best-effort count of stdin lines consumed
    extra: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.termination_status == "normal" and self.rc == 0

    def to_dict(self) -> dict:
        return asdict(self)
