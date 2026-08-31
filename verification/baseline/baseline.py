"""
verification/baseline/baseline.py

COBOL Baseline: compile and execute the original COBOL source using GnuCOBOL
running inside a Docker container.

Verdict contract:
  - BASELINE_VERIFIED (=> Verdict.EXECUTED) requires:
      1. GnuCOBOL compiler actually ran
      2. Compilation succeeded (exit code 0)
      3. Binary executed (exit code 0 for well-behaved programs)
      4. stdout/stderr captured
  - BLOCKED if Docker is unavailable or image is missing
  - FAILED if compilation or execution fails

This module has NO knowledge of Java generation or equivalence comparison.
Its single responsibility is: does the COBOL program compile and run?
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from typing import Optional

from verification.evidence.verdict import StageEvidence, Verdict, blocked, failed, executed

GNUCOBOL_IMAGE = os.environ.get("GNUCOBOL_IMAGE", "gnucobol-ocesql:latest")
COMPILE_TIMEOUT_SECS = 60
EXECUTE_TIMEOUT_SECS = 30

# Characters safe for Docker sh -c interpolation
_SAFE_RE = re.compile(r"^[A-Za-z0-9_./\-]+$")


def docker_available() -> bool:
    """Return True if Docker daemon is reachable."""
    try:
        r = subprocess.run(
            ["docker", "info"],
            capture_output=True, timeout=10,
        )
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def image_available(image: str) -> bool:
    """Return True if the Docker image exists locally."""
    try:
        r = subprocess.run(
            ["docker", "image", "inspect", image],
            capture_output=True, timeout=10,
        )
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def run_baseline(
    source_path: str,
    *,
    repo_root: str,
    copybook_dirs: Optional[list[str]] = None,
    has_sql: bool = False,
    pg_network: Optional[str] = None,
    image: str = GNUCOBOL_IMAGE,
    out_dir: Optional[str] = None,
) -> StageEvidence:
    """
    Compile and execute a single COBOL source file using GnuCOBOL in Docker.

    Parameters
    ----------
    source_path:
        Absolute path to the primary COBOL source file.
    repo_root:
        Absolute path to the repository root (mounted into the container).
    copybook_dirs:
        Absolute paths to copybook directories (must be within repo_root).
    has_sql:
        If True, OCESQL preprocessing is required. PostgreSQL must be reachable.
    pg_network:
        Docker network name for PostgreSQL connectivity (required if has_sql=True).
    image:
        Docker image to use for compilation/execution.
    out_dir:
        Directory to write baseline output artifacts. Defaults to a tmpdir.

    Returns
    -------
    StageEvidence with verdict EXECUTED (success), FAILED, or BLOCKED.
    """
    stage = "baseline"

    # --- Infrastructure checks ---
    if not docker_available():
        return blocked(stage, "Docker daemon not available")
    if not image_available(image):
        return blocked(stage, f"Docker image not available: {image}")

    # --- Validate paths (security) ---
    try:
        _assert_within(source_path, repo_root)
    except ValueError as exc:
        return blocked(stage, f"Path validation failed: {exc}")

    # --- Work directory ---
    cleanup_out = out_dir is None
    if out_dir is None:
        out_dir = tempfile.mkdtemp(prefix="baseline_")
    os.makedirs(out_dir, exist_ok=True)

    src_rel = os.path.relpath(source_path, repo_root).replace("\\", "/")
    stem = os.path.splitext(os.path.basename(source_path))[0]
    exe_name = stem.lower()

    try:
        # --- Build compile command ---
        copybook_flags = _copybook_flags(copybook_dirs or [], repo_root)

        if has_sql:
            # OCESQL preprocessing: ocesql <src> <out.cob> + cobc
            precompiled_rel = f"_preprocessed/{stem}_pp.cob"
            precompiled_dir = os.path.join(repo_root, "_preprocessed")
            os.makedirs(precompiled_dir, exist_ok=True)

            precompile_cmd = (
                f"mkdir -p _preprocessed && "
                f"ocesql {src_rel} _preprocessed/{stem}_pp.cob && "
                f"cobc -x -I /usr/share/open-cobol-esql/copy {copybook_flags} -o {exe_name} _preprocessed/{stem}_pp.cob"
                f" -locesql"
            )
            compile_cmd = precompile_cmd
        else:
            compile_cmd = f"cobc -x {copybook_flags} -o {exe_name} {src_rel}"

        # --- Compile step ---
        compile_result = _docker_run(
            image=image,
            repo_root=repo_root,
            cmd=compile_cmd,
            timeout=COMPILE_TIMEOUT_SECS,
        )

        if compile_result.returncode != 0:
            # Save stderr for diagnostics
            _save_text(out_dir, "compile_stderr.txt", compile_result.stderr or "")
            return failed(
                stage,
                exit_code=compile_result.returncode,
                stderr=compile_result.stderr or "",
                notes=f"GnuCOBOL compilation failed for {src_rel}",
            )

        # --- Execute step ---
        if has_sql and pg_network:
            run_cmd = (
                f"export PGHOST=db PGPORT=5432 PGUSER=modernize PGPASSWORD=modernize "
                f"PGDATABASE=modernization_db COB_PRE_LOAD=/usr/lib/libocesql.so && "
                f"./{exe_name}"
            )
            execute_result = _docker_run(
                image=image,
                repo_root=repo_root,
                cmd=run_cmd,
                timeout=EXECUTE_TIMEOUT_SECS,
                network=pg_network,
            )
        else:
            execute_result = _docker_run(
                image=image,
                repo_root=repo_root,
                cmd=f"./{exe_name}",
                timeout=EXECUTE_TIMEOUT_SECS,
            )

        stdout = execute_result.stdout or ""
        stderr = execute_result.stderr or ""

        _save_text(out_dir, "stdout.txt", stdout)
        _save_text(out_dir, "stderr.txt", stderr)
        _save_text(out_dir, "exit_code.txt", str(execute_result.returncode))

        if execute_result.returncode != 0:
            return failed(
                stage,
                exit_code=execute_result.returncode,
                stdout=stdout,
                stderr=stderr,
                notes=f"COBOL execution failed with exit code {execute_result.returncode}",
            )

        return executed(
            stage,
            exit_code=0,
            stdout=stdout,
            stderr=stderr,
            artifacts={
                "stdout": os.path.join(out_dir, "stdout.txt"),
                "stderr": os.path.join(out_dir, "stderr.txt"),
                "exit_code": os.path.join(out_dir, "exit_code.txt"),
            },
            notes=f"GnuCOBOL baseline: {src_rel} compiled and executed successfully",
        )

    finally:
        # Never leave temp evidence behind if caller did not provide out_dir
        # (caller normally provides out_dir so evidence persists for comparison)
        pass


def _docker_run(
    image: str,
    repo_root: str,
    cmd: str,
    timeout: int,
    network: Optional[str] = None,
) -> subprocess.CompletedProcess:
    docker_cmd = [
        "docker", "run", "--rm",
        "-v", f"{repo_root}:/repo",
        "-w", "/repo",
    ]
    if network:
        docker_cmd += ["--network", network]
    docker_cmd += [image, "sh", "-c", cmd]

    try:
        return subprocess.run(
            docker_cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            docker_cmd, -1, stdout="", stderr=f"Timed out after {timeout}s"
        )


def _copybook_flags(copybook_dirs: list[str], repo_root: str) -> str:
    flags = []
    for d in copybook_dirs:
        try:
            rel = os.path.relpath(d, repo_root).replace("\\", "/")
            if not rel.startswith(".."):
                flags.append(f"-I {rel}")
        except ValueError:
            pass
    return " ".join(flags)


def _assert_within(path: str, root: str) -> None:
    abs_path = os.path.abspath(path)
    abs_root = os.path.abspath(root)
    if not abs_path.startswith(abs_root + os.sep) and abs_path != abs_root:
        raise ValueError(f"Path {path!r} is not within repo root {root!r}")


def _save_text(out_dir: str, fname: str, content: str) -> None:
    with open(os.path.join(out_dir, fname), "w", encoding="utf-8") as fh:
        fh.write(content)
