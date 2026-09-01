"""Write execution artifacts to disk for auditability.

Artifacts written per execution:
  <out>/execution/<scenario_id>/
      scenario.json           — immutable scenario description
      interactive_input.txt   — stdin sent to the program (written by discovery)
      stdout.txt              — captured stdout
      stderr.txt              — captured stderr
      execution_metadata.json — timing, exit code, termination status

Artifacts are written after every execution attempt regardless of outcome,
so failed/timed-out runs are also auditable.
"""

import json
import os


def write_execution_artifacts(
    artifacts_dir: str,
    scenario,           # ExecutionScenario
    result,             # ExecutionResult
    stage: str = "",    # "baseline" or "execute"
) -> None:
    """Write all audit artifacts for one execution attempt."""
    os.makedirs(artifacts_dir, exist_ok=True)

    # scenario.json — written once; skip if already present (reuse detection)
    scenario_path = os.path.join(artifacts_dir, "scenario.json")
    if not os.path.isfile(scenario_path):
        _write_json(scenario_path, scenario.to_dict())

    # stdout / stderr — always overwrite with latest run
    _write_text(os.path.join(artifacts_dir, f"stdout_{stage}.txt" if stage else "stdout.txt"),
                result.stdout or "")
    _write_text(os.path.join(artifacts_dir, f"stderr_{stage}.txt" if stage else "stderr.txt"),
                result.stderr or "")

    # execution_metadata.json — per-stage metadata
    fname = f"execution_metadata_{stage}.json" if stage else "execution_metadata.json"
    meta = {
        "stage": stage,
        "mode": result.execution_mode,
        "scenario_id": scenario.scenario_id,
        "scenario_source": scenario.input_source,
        "entrypoint": scenario.entrypoint,
        "exit_code": result.rc,
        "termination": result.termination_status,
        "duration_seconds": round(result.duration_seconds, 3),
        "timeout_seconds": scenario.timeout_seconds,
        "max_output_bytes": scenario.max_output_bytes,
        "inputs_sent": len(scenario.input_values),
        "inputs_consumed": result.inputs_consumed,
    }
    _write_json(os.path.join(artifacts_dir, fname), meta)


def _write_json(path: str, obj: dict) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2)


def _write_text(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8", errors="replace") as fh:
        fh.write(text)
