"""Discover an ExecutionScenario for an interactive COBOL application.

Priority order (per approved spec):
  1. Existing test/smoke scripts  (test/*.sh, test/*.bash, etc.)
  2. Existing stdin/input fixture files  (test/*.stdin, data/in/*.stdin, etc.)
  3. Explicit migration_config.json   "execution.interactive_scenario"
  4. README / docs   (interactive_scenario key)
  5. Static analysis → diagnostics only; DOES NOT auto-generate transactions
  6. INTERACTIVE_INPUT_REQUIRED — fail fast

Static analysis (step 5) produces a human-readable diagnostic about what
ACCEPT statements were found and what branches are reachable. It does NOT
invent business transactions or execute unvetted inputs.

Public API:
    scenario = discover_scenario(repo_dir, out_dir, discover_data, cfg)
    # raises InteractiveInputRequired if no safe scenario found
"""

import json
import os
import tempfile

from .models import ExecutionScenario, InteractiveInputRequired
from .scenario_parser import parse_stdin_from_script


# File name patterns for smoke/test scripts (case-insensitive)
_SMOKE_PATTERNS = ("smoke", "test", "demo", "run", "sample", "acceptance", "e2e")
_SMOKE_EXTS = (".sh", ".bash")
_FIXTURE_EXTS = (".stdin", ".input", ".in", ".txt")

# Subdirectories to search for test scenarios
_TEST_DIRS = ("test", "tests", "smoke", "acceptance", "scripts", "e2e", "demo", "examples")


def _find_smoke_scripts(repo_dir: str) -> list[str]:
    """Return all candidate smoke/test shell scripts under the repository."""
    candidates = []
    for sub in _TEST_DIRS:
        d = os.path.join(repo_dir, sub)
        if not os.path.isdir(d):
            continue
        for fname in sorted(os.listdir(d)):
            fl = fname.lower()
            if any(fl.endswith(ext) for ext in _SMOKE_EXTS):
                if any(pat in fl for pat in _SMOKE_PATTERNS):
                    candidates.append(os.path.join(d, fname))
    # Also search root-level scripts
    for fname in sorted(os.listdir(repo_dir)):
        fl = fname.lower()
        if any(fl.endswith(ext) for ext in _SMOKE_EXTS):
            if any(pat in fl for pat in _SMOKE_PATTERNS):
                candidates.append(os.path.join(repo_dir, fname))
    return candidates


def _find_fixture_files(repo_dir: str) -> list[str]:
    """Return stdin fixture files."""
    candidates = []
    for sub in _TEST_DIRS + ("data/in", "data", "fixtures", ""):
        d = os.path.join(repo_dir, sub) if sub else repo_dir
        if not os.path.isdir(d):
            continue
        for fname in sorted(os.listdir(d)):
            fl = fname.lower()
            if any(fl.endswith(ext) for ext in _FIXTURE_EXTS):
                if any(pat in fl for pat in _SMOKE_PATTERNS + ("stdin", "input")):
                    candidates.append(os.path.join(d, fname))
    return candidates


def _make_stdin_file(out_dir: str, scenario_id: str, input_values: list) -> str:
    """Write a deterministic stdin file; return its absolute path."""
    artifact_dir = os.path.join(out_dir, "execution", scenario_id)
    os.makedirs(artifact_dir, exist_ok=True)
    path = os.path.join(artifact_dir, "interactive_input.txt")
    content = "\n".join(input_values) + "\n"
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(content)
    return path


def _build_scenario(
    entrypoint: str,
    input_values: list,
    input_source: str,
    out_dir: str,
    timeout_seconds: int,
    max_output_bytes: int,
    expected_termination: str = "unknown",
    metadata: dict = None,
) -> ExecutionScenario:
    """Construct a fully-formed ExecutionScenario and write its stdin file."""
    sc = ExecutionScenario(
        entrypoint=entrypoint,
        input_source=input_source,
        input_values=input_values,
        stdin_path="",               # filled after id computation
        expected_termination=expected_termination,
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
        metadata=metadata or {},
    )
    # Now that scenario_id is computed, write the stdin file
    sc.stdin_path = _make_stdin_file(out_dir, sc.scenario_id, input_values)
    return sc


def discover_scenario(
    repo_dir: str,
    out_dir: str,
    discover_data: dict,
    cfg: dict,
) -> ExecutionScenario:
    """Discover the best available ExecutionScenario for this application.

    Args:
        repo_dir:       Repository root.
        out_dir:        Pipeline output directory (for writing stdin artifacts).
        discover_data:  The "discover" dict from pipeline state.
        cfg:            The migration config dict (migration_config.json contents).

    Returns:
        ExecutionScenario

    Raises:
        InteractiveInputRequired: when no safe scenario can be identified.
    """
    entry = discover_data.get("entry", "UNKNOWN")
    exec_cfg = cfg.get("execution", {})
    timeout = int(exec_cfg.get("timeout_seconds", 120))
    max_out = int(exec_cfg.get("max_output_bytes", 5 * 1024 * 1024))

    # -- Priority 1: Existing smoke/test shell scripts ---
    for script in _find_smoke_scripts(repo_dir):
        values = parse_stdin_from_script(script)
        if values:
            rel = os.path.relpath(script, repo_dir).replace("\\", "/")
            return _build_scenario(
                entrypoint=entry,
                input_values=values,
                input_source=rel,
                out_dir=out_dir,
                timeout_seconds=timeout,
                max_output_bytes=max_out,
                expected_termination="unknown",
                metadata={"discovery_method": "smoke_script", "script": rel},
            )

    # -- Priority 2: Stdin fixture files ---
    for fixture in _find_fixture_files(repo_dir):
        try:
            content = open(fixture, encoding="utf-8", errors="replace").read().splitlines()
            values = [l.strip() for l in content if l.strip()]
        except OSError:
            continue
        if values:
            rel = os.path.relpath(fixture, repo_dir).replace("\\", "/")
            return _build_scenario(
                entrypoint=entry,
                input_values=values,
                input_source=rel,
                out_dir=out_dir,
                timeout_seconds=timeout,
                max_output_bytes=max_out,
                expected_termination="unknown",
                metadata={"discovery_method": "fixture_file", "file": rel},
            )

    # -- Priority 3: Explicit migration config ---
    scenario_path = exec_cfg.get("interactive_scenario")
    if scenario_path:
        full = os.path.join(repo_dir, scenario_path)
        if os.path.isfile(full):
            fl = full.lower()
            if any(full.endswith(ext) for ext in _SMOKE_EXTS):
                values = parse_stdin_from_script(full)
            else:
                # treat as raw stdin file
                try:
                    content = open(full, encoding="utf-8", errors="replace").read().splitlines()
                    values = [l.strip() for l in content if l.strip()]
                except OSError:
                    values = None
            if values:
                rel = os.path.relpath(full, repo_dir).replace("\\", "/")
                return _build_scenario(
                    entrypoint=entry,
                    input_values=values,
                    input_source=rel,
                    out_dir=out_dir,
                    timeout_seconds=timeout,
                    max_output_bytes=max_out,
                    expected_termination="unknown",
                    metadata={"discovery_method": "config", "path": rel},
                )

    # -- Priority 4: README / documentation ---
    for readme in ("README.md", "README.txt", "README.rst", "README"):
        rpath = os.path.join(repo_dir, readme)
        if os.path.isfile(rpath):
            try:
                rdtext = open(rpath, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            # Look for a code fence that contains a heredoc
            fence_re = __import__("re").compile(
                r"```(?:bash|sh|shell)?\n(.*?)```", __import__("re").DOTALL
            )
            for fm in fence_re.finditer(rdtext):
                block = fm.group(1)
                # Write to temp file and parse
                with __import__("tempfile").NamedTemporaryFile(
                    mode="w", suffix=".sh", delete=False, encoding="utf-8"
                ) as tmp:
                    tmp.write(block)
                    tmp_path = tmp.name
                try:
                    values = parse_stdin_from_script(tmp_path)
                finally:
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass
                if values:
                    return _build_scenario(
                        entrypoint=entry,
                        input_values=values,
                        input_source=readme,
                        out_dir=out_dir,
                        timeout_seconds=timeout,
                        max_output_bytes=max_out,
                        expected_termination="unknown",
                        metadata={"discovery_method": "readme", "file": readme},
                    )

    # -- Priority 5: Static analysis → diagnostics only, NO execution ---
    # Build a human-readable diagnostic and fail fast.
    _fail_fast(entry, repo_dir, discover_data)


def _fail_fast(entry: str, repo_dir: str, discover_data: dict) -> None:
    """Raise InteractiveInputRequired with a useful diagnostic message."""
    # Produce a minimal diagnostic listing the ACCEPT statements found
    sources = discover_data.get("sources", [])
    accept_hints = []
    import re as _re
    re_accept = _re.compile(r'\bACCEPT\s+\S+', _re.IGNORECASE)
    for src in sources[:10]:  # limit to first 10 to keep message short
        path = os.path.join(repo_dir, src)
        if not os.path.isfile(path):
            continue
        try:
            text = open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        for m in re_accept.finditer(text):
            accept_hints.append(f"  {src}: {m.group().strip()[:60]}")
        if len(accept_hints) >= 5:
            break

    hint_text = "\n".join(accept_hints[:5]) or "  (none found in accessible sources)"
    raise InteractiveInputRequired(
        f"INTERACTIVE_INPUT_REQUIRED\n\n"
        f"The selected COBOL entry point '{entry}' requires stdin input,\n"
        f"but no deterministic test scenario was discovered.\n\n"
        f"Reachable ACCEPT statements:\n{hint_text}\n\n"
        f"Provide one of:\n"
        f"  - An existing test/smoke script (test/*.sh) with a heredoc or pipe\n"
        f"  - A stdin fixture file (test/*.stdin)\n"
        f"  - An explicit scenario path in migration_config.json:\n"
        f"      {{\"execution\": {{\"interactive_scenario\": \"test/my_script.sh\"}}}}\n"
    )


def restore_stdin_file(scenario: ExecutionScenario, out_dir: str) -> str:
    """Ensure scenario.stdin_path exists and return its path.

    When a scenario is loaded from state.json on a subsequent run the original
    file may have been cleaned up. Recreate it from input_values if needed.
    """
    if scenario.stdin_path and os.path.isfile(scenario.stdin_path):
        return scenario.stdin_path
    path = _make_stdin_file(out_dir, scenario.scenario_id, scenario.input_values)
    scenario.stdin_path = path
    return path
