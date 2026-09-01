"""Generic interactive COBOL/Java execution layer.

Public API consumed by cobol_migrate.py stage_baseline and stage_execute:

    from execution import (
        detect_interactivity,   # "NON_INTERACTIVE" | "INTERACTIVE" | "UNKNOWN"
        discover_scenario,      # -> ExecutionScenario | raises InteractiveInputRequired
        run_cobol_with_scenario,  # -> ExecutionResult
        run_java_with_scenario,   # -> ExecutionResult
        ExecutionScenario,
        ExecutionResult,
        InteractiveInputRequired,
        ExecutionTimeout,
        OutputLimitExceeded,
        InputExhausted,
    )

Design constraints (required by spec):
- No hardcoded program names (BANKMAIN, BCMAIN, etc.)
- ACCEPT FROM DATE/TIME/DAY-OF-WEEK is NOT classified as interactive
- Same ExecutionScenario is persisted after Stage 3 and reused verbatim in Stage 7
- deterministic scenario_id = SHA-256 of (entrypoint + source + input_values)
- Timeout and output-size limits are mandatory watchdogs, not expected outcomes
"""

from .interactive_detector import detect_interactivity
from .scenario_discovery import discover_scenario
from .scenario_runner import run_cobol_with_scenario, run_java_with_scenario, run_command_with_watchdog
from .models import (
    ExecutionScenario,
    ExecutionResult,
    InteractiveInputRequired,
    ExecutionTimeout,
    OutputLimitExceeded,
    InputExhausted,
)
from .observations import ExecutionObservation
from .contracts import ExecutionContract
from .results import ComparisonResult
from .equivalence import EquivalenceEngine
from .normalization import NormalizationRules
from .topology import detect_topology, observable_summary

__all__ = [
    "detect_interactivity",
    "discover_scenario",
    "run_cobol_with_scenario",
    "run_java_with_scenario",
    "run_command_with_watchdog",
    "ExecutionScenario",
    "ExecutionResult",
    "InteractiveInputRequired",
    "ExecutionTimeout",
    "OutputLimitExceeded",
    "InputExhausted",
    "ExecutionObservation",
    "ExecutionContract",
    "ComparisonResult",
    "EquivalenceEngine",
    "NormalizationRules",
    "detect_topology",
    "observable_summary",
]

