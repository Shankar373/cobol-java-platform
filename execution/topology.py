"""Topology detection for the equivalence engine.

Classifies repository observable behaviour from execution evidence only.
No repository names, paths, or hardcoded identifiers are inspected.
"""


def detect_topology(baseline_files, results_files, baseline_stdout, java_stdout):
    """Return the topology that best describes what this program's execution produces.

    Rules (evidence-driven, no name inspection):
      MULTI_FILE_OUTPUT  — >=2 observable baseline flat files
      FILE_OUTPUT        — exactly 1 observable baseline flat file
      CONSOLE_OUTPUT     — 0 flat files + non-empty baseline stdout (strip to ignore
                           blank-only output that carries no information)
      NO_OBSERVABLE_OUTPUT — 0 flat files + empty/missing baseline stdout

    Args:
        baseline_files (dict[str, bytes]): flat files produced by the legacy baseline.
        results_files  (dict[str, bytes]): flat files produced by the native execution.
        baseline_stdout (str): stdout captured from the legacy baseline run.
        java_stdout     (str): stdout captured from the native Java run.

    Returns:
        str: one of the four topology constants above.
    """
    n_baseline = len(baseline_files) if baseline_files else 0

    if n_baseline >= 2:
        return "MULTI_FILE_OUTPUT"
    if n_baseline == 1:
        return "FILE_OUTPUT"
    if (baseline_stdout or "").strip():
        return "CONSOLE_OUTPUT"
    return "NO_OBSERVABLE_OUTPUT"


def observable_summary(baseline_files, results_files, baseline_stdout, java_stdout):
    """Return a dict with topology + observable descriptions for both sides.

    Used in the manifest and audit reports to prove what each side produced
    without fabricating equivalence evidence.
    """
    topology = detect_topology(baseline_files, results_files, baseline_stdout, java_stdout)

    def _describe(files, stdout):
        if files:
            total = sum(len(v) for v in files.values())
            return {"type": "files", "count": len(files), "total_bytes": total}
        if (stdout or "").strip():
            return {"type": "stdout", "chars": len(stdout)}
        return {"type": "none"}

    return {
        "topology": topology,
        "legacy_observable": _describe(baseline_files, baseline_stdout),
        "native_observable": _describe(results_files, java_stdout),
    }
