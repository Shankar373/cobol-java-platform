"""Process runner with mandatory watchdog protection.

Every external execution (COBOL baseline, Java execute) goes through this runner.
It enforces:
  - configurable timeout_seconds (default 120)
  - configurable max_output_bytes (default 5 MB)
  - process-tree cleanup after timeout or limit exceeded
  - clear termination_status codes (per approved spec)

Termination status values:
    normal          — process exited 0 within timeout, output within limits
    nonzero_exit    — process exited non-zero within timeout
    timeout         — watchdog killed process (BASELINE_EXECUTION_TIMEOUT / JAVA_EXECUTION_TIMEOUT)
    output_limit    — output-size cap exceeded (EXECUTION_OUTPUT_LIMIT_EXCEEDED)
    input_exhausted — program requested stdin after all values consumed
    killed          — process killed by user or OS signal
    error           — unexpected runner error

Public API:
    result = run_cobol_with_scenario(repo_dir, scenario, discover_data, out_dir, cfg)
    result = run_java_with_scenario(repo_dir, scenario, discover_data, out_dir, cfg)
"""

import os
import re
import signal
import subprocess
import sys
import time

from .artifacts import write_execution_artifacts
from .models import (
    ExecutionResult,
    ExecutionScenario,
    ExecutionTimeout,
    InputExhausted,
    OutputLimitExceeded,
)
from .scenario_discovery import restore_stdin_file

# Docker images (imported from cobol_migrate — avoids duplication)
# We access them via a late import to avoid circular dependency at module load.
_DEFAULT_GNUCOBOL = "hurriedreformist/gnucobol:3.1-builder"
_DEFAULT_COBJ     = "opensourcecobol/opensourcecobol4j:2.0.0"


# ---------------------------------------------------------------------------
# Low-level subprocess runner with output watchdog
# ---------------------------------------------------------------------------

def _run_with_watchdog(
    cmd: list,
    stdin_path: str,
    timeout_seconds: int,
    max_output_bytes: int,
    env: dict = None,
) -> tuple:
    """Run a subprocess with stdin from a file and a dual watchdog (time + bytes).

    Uses background reader threads so stdout/stderr never block the watchdog
    loop — required for correct behaviour on Windows where pipes block.

    Returns:
        (rc, stdout_str, stderr_str, duration, termination_status)
    """
    import threading

    with open(stdin_path, "rb") as stdin_fh:
        try:
            proc = subprocess.Popen(
                cmd,
                stdin=stdin_fh,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                start_new_session=(sys.platform != "win32"),
            )
        except Exception as exc:
            return -1, "", str(exc), 0.0, "error"

    t_start = time.monotonic()
    stdout_chunks: list = []
    stderr_chunks: list = []
    byte_counter = [0]      # mutable so threads can update it
    limit_exceeded = [False]
    lock = threading.Lock()

    def _reader(pipe, collector):
        """Drain pipe into collector; track bytes."""
        while True:
            try:
                chunk = pipe.read(8192)
            except (OSError, ValueError):
                break
            if not chunk:
                break
            with lock:
                collector.append(chunk)
                byte_counter[0] += len(chunk)

    t_out = threading.Thread(target=_reader, args=(proc.stdout, stdout_chunks), daemon=True)
    t_err = threading.Thread(target=_reader, args=(proc.stderr, stderr_chunks), daemon=True)
    t_out.start()
    t_err.start()

    termination_status = "normal"
    POLL_INTERVAL = 0.1  # seconds

    while True:
        elapsed = time.monotonic() - t_start

        # -- Timeout watchdog --
        if elapsed >= timeout_seconds:
            termination_status = "timeout"
            _kill_tree(proc)
            break

        # -- Output-size watchdog --
        with lock:
            current_bytes = byte_counter[0]
        if current_bytes > max_output_bytes:
            termination_status = "output_limit"
            _kill_tree(proc)
            break

        rc = proc.poll()
        if rc is not None:
            # Process finished — wait for readers to drain
            t_out.join(timeout=5)
            t_err.join(timeout=5)
            with lock:
                final_bytes = byte_counter[0]
            if final_bytes > max_output_bytes:
                termination_status = "output_limit"
            elif rc == 0:
                termination_status = "normal"
            elif rc < 0:
                termination_status = "killed"
            else:
                termination_status = "nonzero_exit"
            break

        time.sleep(POLL_INTERVAL)

    duration = time.monotonic() - t_start

    # Ensure process is dead and readers have stopped
    _kill_tree(proc, force=True)
    t_out.join(timeout=2)
    t_err.join(timeout=2)

    try:
        stdout_str = b"".join(stdout_chunks).decode("utf-8", errors="replace")
        stderr_str = b"".join(stderr_chunks).decode("utf-8", errors="replace")
    except Exception:
        stdout_str = stderr_str = ""

    return (
        proc.returncode if proc.returncode is not None else -1,
        stdout_str,
        stderr_str,
        duration,
        termination_status,
    )


def _kill_tree(proc: subprocess.Popen, force: bool = False) -> None:
    """Terminate process and wait briefly; force kill if still alive."""
    try:
        if sys.platform == "win32":
            proc.terminate()
        else:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                proc.terminate()
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            if sys.platform == "win32":
                proc.kill()
            else:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    proc.kill()
        except Exception:
            pass
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Docker command builder
# ---------------------------------------------------------------------------

_SHELL_SAFE_RE = re.compile(r"^[A-Za-z0-9_./=$,:\x2b@%-]+$")


def shell_safe(token: str, what: str = "value") -> str:
    """Validate a repo-derived token before it is interpolated into the
    container's `sh -c` string.

    Repo-derived values (program IDs, config paths, CLI args) must never be
    able to inject shell metacharacters into container command execution.
    """
    token = (token or "").strip()
    if not token or len(token) > 512 or not _SHELL_SAFE_RE.match(token):
        raise ValueError(
            f"UNSAFE_{what.upper()}: {token!r} contains characters that are not "
            f"permitted in container command interpolation"
        )
    return token


def _docker_cmd(image: str, mounts: list, workdir: str, inner_cmd: str) -> list:
    """Build a docker run command list with Docker-out-of-Docker translation."""
    network = "none"
    if os.environ.get("REAL_DB2_MODE") == "1" or os.environ.get("DOCKER_NETWORK"):
        network = os.environ.get("DOCKER_NETWORK", "bridge")

    full = ["docker", "run", "--rm",
            "--memory=2g", "--cpus=2", "--pids-limit=512",
            "--network", network,
            "--cap-drop=ALL", "--security-opt=no-new-privileges"]
    
    in_docker = os.path.exists("/.dockerenv")
    
    if in_docker:
        full += ["-v", "cobol-to-java-test_workspace:/app/workspace"]
        
        symlink_cmds = ["cd /"]
        for host, guest in mounts:
            host_posix = host.replace("\\", "/")
            symlink_cmds.append(f"rm -rf {guest}")
            symlink_cmds.append(f"mkdir -p $(dirname {guest})")
            symlink_cmds.append(f"ln -sf {host_posix} {guest}")
            
        if symlink_cmds:
            cd_back = f"cd {workdir}" if workdir else ""
            inner_cmd = " && ".join(symlink_cmds) + (f" && {cd_back}" if cd_back else "") + " && " + inner_cmd
    else:
        for host, guest in mounts:
            full += ["-v", f"{host}:{guest}"]
            
    if workdir:
        full += ["-w", workdir]
    full += [image, "sh", "-c", inner_cmd]
    return full


def run_command_with_watchdog(
    image: str,
    mounts: list,
    workdir: str,
    inner_cmd: str,
    timeout_seconds: int,
    max_output_bytes: int,
    stdin_path: str = None,
) -> tuple[int, str, str, float, str]:
    """Run a containerized command with timeout and output-size watchdogs.

    Used to wrap non-interactive/batch runs with the exact same watchdog
    protection as interactive runs.
    """
    import tempfile

    delete_stdin = False
    if not stdin_path:
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tf:
            tf.write("")
            stdin_path = tf.name
        delete_stdin = True

    cmd = _docker_cmd(image, mounts, workdir, inner_cmd)
    try:
        rc, stdout, stderr, duration, term_status = _run_with_watchdog(
            cmd, stdin_path, timeout_seconds, max_output_bytes
        )
    finally:
        if delete_stdin:
            try:
                os.remove(stdin_path)
            except OSError:
                pass

    return rc, stdout, stderr, duration, term_status


# ---------------------------------------------------------------------------
# COBOL baseline runner
# ---------------------------------------------------------------------------

def run_cobol_with_scenario(
    repo_dir: str,
    scenario: ExecutionScenario,
    discover_data: dict,
    out_dir: str,
    cfg: dict,
    gnucobol_image: str = None,
    exe_name: str = None,
) -> ExecutionResult:
    """Run the pre-built GnuCOBOL binary with the scripted scenario.

    The binary must already have been compiled by stage_baseline before calling this.
    The scenario stdin file is always created fresh (or restored if missing).

    Args:
        exe_name:   Relative path inside the container's /repo mount.
                    Defaults to a name derived from the scenario entrypoint.
    """
    image = gnucobol_image or _DEFAULT_GNUCOBOL
    exec_cfg = cfg.get("execution", {})
    timeout = scenario.timeout_seconds
    max_out = scenario.max_output_bytes

    if not exe_name:
        entry_id = (scenario.entrypoint or "program").lower().replace("-", "_")
        exe_name = f"{entry_id}.exe"
    # SECURITY: repo-derived executable path is shell-interpolated below.
    exe_name = shell_safe(exe_name, "executable name")

    # Ensure stdin file exists (may have been cleaned up between runs)
    stdin_path_host = restore_stdin_file(scenario, out_dir)

    artifacts_dir = os.path.join(out_dir, "execution", scenario.scenario_id)
    os.makedirs(artifacts_dir, exist_ok=True)

    # The stdin file is inside artifacts_dir; mount it into the container
    stdin_guest = f"/execution_input/interactive_input.txt"
    inner_cmd = f"cd /repo && export COB_LIBRARY_PATH=. && ./{exe_name} < {stdin_guest}"

    cmd = _docker_cmd(
        image,
        [(repo_dir, "/repo"), (artifacts_dir, "/execution_input")],
        "/repo",
        inner_cmd,
    )

    rc, stdout, stderr, duration, term_status = _run_with_watchdog(
        cmd, stdin_path_host, timeout, max_out,
    )

    result = ExecutionResult(
        rc=rc,
        stdout=stdout,
        stderr=stderr,
        duration_seconds=duration,
        termination_status=term_status,
        scenario_id=scenario.scenario_id,
        artifacts_dir=artifacts_dir,
        command=inner_cmd,
        execution_mode="interactive-scripted",
        inputs_consumed=len(scenario.input_values),
    )

    write_execution_artifacts(artifacts_dir, scenario, result, stage="baseline")

    if term_status == "timeout":
        raise ExecutionTimeout(
            f"BASELINE_EXECUTION_TIMEOUT\n"
            f"GnuCOBOL execution exceeded {timeout}s timeout.\n"
            f"Scenario: {scenario.scenario_id}\n"
            f"Entry: {scenario.entrypoint}"
        )
    if term_status == "output_limit":
        raise OutputLimitExceeded(
            f"EXECUTION_OUTPUT_LIMIT_EXCEEDED\n"
            f"GnuCOBOL output exceeded {max_out} bytes.\n"
            f"Scenario: {scenario.scenario_id}"
        )

    return result


# ---------------------------------------------------------------------------
# Java execute runner
# ---------------------------------------------------------------------------

def run_java_with_scenario(
    repo_dir: str,
    scenario: ExecutionScenario,
    discover_data: dict,
    out_dir: str,
    cfg: dict,
    cobj_image: str = None,
    entry_args: str = "",
) -> ExecutionResult:
    """Run the transpiled Java program using the EXACT same scenario as COBOL.

    No rediscovery. No re-parsing. The scenario object is provided by the caller
    and was originally created (and persisted to state.json) by stage_baseline.
    """
    image = cobj_image or _DEFAULT_COBJ
    entry = discover_data.get("entry", "")
    timeout = scenario.timeout_seconds
    max_out = scenario.max_output_bytes

    # Ensure stdin file exists
    stdin_path_host = restore_stdin_file(scenario, out_dir)

    artifacts_dir = os.path.join(out_dir, "execution", scenario.scenario_id)
    os.makedirs(artifacts_dir, exist_ok=True)

    stdin_guest = "/execution_input/interactive_input.txt"
    java_cp = "/target/generated:/target/libcobj.jar"
    # SECURITY: repo-derived identifiers are shell-interpolated below.
    entry = shell_safe(entry, "entry point")
    args_str = entry_args.strip()
    if args_str:
        args_str = shell_safe(args_str, "entry arguments")
    inner_cmd = (
        f"cd /repo && export COB_PACKAGE_PATH=com.systema.modernized.generated && java -cp '{java_cp}' {entry}"
        + (f" {args_str}" if args_str else "")
        + f" < {stdin_guest}"
    )

    cmd = _docker_cmd(
        image,
        [(repo_dir, "/repo"), (out_dir, "/target"), (artifacts_dir, "/execution_input")],
        "/repo",
        inner_cmd,
    )

    rc, stdout, stderr, duration, term_status = _run_with_watchdog(
        cmd, stdin_path_host, timeout, max_out,
    )

    result = ExecutionResult(
        rc=rc,
        stdout=stdout,
        stderr=stderr,
        duration_seconds=duration,
        termination_status=term_status,
        scenario_id=scenario.scenario_id,
        artifacts_dir=artifacts_dir,
        command=inner_cmd,
        execution_mode="interactive-scripted",
        inputs_consumed=len(scenario.input_values),
    )

    write_execution_artifacts(artifacts_dir, scenario, result, stage="execute")

    if term_status == "timeout":
        raise ExecutionTimeout(
            f"JAVA_EXECUTION_TIMEOUT\n"
            f"Java execution exceeded {timeout}s timeout.\n"
            f"Scenario: {scenario.scenario_id}\n"
            f"Entry: {scenario.entrypoint}"
        )
    if term_status == "output_limit":
        raise OutputLimitExceeded(
            f"EXECUTION_OUTPUT_LIMIT_EXCEEDED\n"
            f"Java output exceeded {max_out} bytes.\n"
            f"Scenario: {scenario.scenario_id}"
        )

    return result
