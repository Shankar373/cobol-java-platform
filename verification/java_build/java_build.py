"""
verification/java_build/java_build.py

Java Build Verification: compile the generated Java project with Maven,
then execute it and capture output.

Verdict contract (hard rules):
  - mvn compile success alone => Verdict.COMPILED   (NOT EXECUTED, NOT EQUIVALENT)
  - Java execution success    => Verdict.EXECUTED
  - Both required before equivalence comparison
  - Missing Maven/JDK         => Verdict.BLOCKED
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from typing import Optional

from verification.evidence.verdict import (
    StageEvidence, Verdict, blocked, failed, compiled, executed
)

MVN_TIMEOUT_SECS = 120
EXEC_TIMEOUT_SECS = 30


def maven_available() -> bool:
    try:
        r = subprocess.run([shutil.which("mvn") or "mvn", "--version"], capture_output=True, timeout=10)
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def java_available() -> bool:
    try:
        r = subprocess.run(["java", "-version"], capture_output=True, timeout=10)
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def compile_java(project_dir: str, out_dir: Optional[str] = None) -> StageEvidence:
    """
    Run `mvn compile` in project_dir.

    Returns
    -------
    StageEvidence with verdict COMPILED or FAILED or BLOCKED.

    Note: COMPILED is NOT execution proof. Call execute_java() separately.
    """
    stage = "java_compile"

    if not maven_available():
        return blocked(stage, "Maven (mvn) not available on PATH")
    if not java_available():
        return blocked(stage, "Java (java) not available on PATH")

    pom = os.path.join(project_dir, "pom.xml")
    if not os.path.isfile(pom):
        return blocked(stage, f"pom.xml not found in {project_dir}")

    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    try:
        result = subprocess.run(
            [shutil.which("mvn") or "mvn", "-B", "-q", "compile"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=MVN_TIMEOUT_SECS,
        )
    except subprocess.TimeoutExpired:
        return blocked(stage, f"mvn compile timed out after {MVN_TIMEOUT_SECS}s")

    stdout = result.stdout or ""
    stderr = result.stderr or ""

    if out_dir:
        _write(os.path.join(out_dir, "mvn_compile_stdout.txt"), stdout)
        _write(os.path.join(out_dir, "mvn_compile_stderr.txt"), stderr)

    if result.returncode != 0:
        return failed(stage,
                      exit_code=result.returncode,
                      stdout=stdout,
                      stderr=stderr,
                      notes="Maven compile failed")

    return compiled(stage, stdout=stdout,
                    notes=f"mvn compile succeeded in {project_dir}")


def execute_java(
    project_dir: str,
    main_class: str,
    *,
    classpath_extra: Optional[list[str]] = None,
    env_extra: Optional[dict] = None,
    out_dir: Optional[str] = None,
    pg_host: Optional[str] = None,
    pg_port: int = 5432,
    pg_user: str = "modernize",
    pg_password: str = "modernize",
    pg_database: str = "modernization_db",
) -> StageEvidence:
    """
    Execute a compiled Java class via `java -cp target/classes <main_class>`.

    Parameters
    ----------
    project_dir:
        Maven project directory (contains pom.xml and target/classes/).
    main_class:
        Fully-qualified Java main class name.
    classpath_extra:
        Additional classpath entries (JARs, dirs).
    env_extra:
        Additional environment variables.
    out_dir:
        Directory to save stdout/stderr artifacts.
    pg_*:
        PostgreSQL connection parameters (used when program needs DB).

    Returns
    -------
    StageEvidence with verdict EXECUTED or FAILED or BLOCKED.
    """
    stage = "java_execute"

    if not java_available():
        return blocked(stage, "Java (java) not available on PATH")

    classes_dir = os.path.join(project_dir, "target", "classes")
    if not os.path.isdir(classes_dir):
        return blocked(stage, f"target/classes not found in {project_dir} — run compile first")

    # Build classpath
    cp_parts = [classes_dir]
    if classpath_extra:
        cp_parts.extend(classpath_extra)
    cp_sep = ";" if os.name == "nt" else ":"
    cp = cp_sep.join(cp_parts)

    env = dict(os.environ)
    if pg_host:
        env.update({
            "PGHOST": pg_host,
            "PGPORT": str(pg_port),
            "PGUSER": pg_user,
            "PGPASSWORD": pg_password,
            "PGDATABASE": pg_database,
        })
    if env_extra:
        env.update(env_extra)

    cmd = ["java", "-cp", cp, main_class]

    try:
        result = subprocess.run(
            cmd,
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=EXEC_TIMEOUT_SECS,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return blocked(stage, f"Java execution timed out after {EXEC_TIMEOUT_SECS}s")

    stdout = result.stdout or ""
    stderr = result.stderr or ""

    artifacts = {}
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        p_out = os.path.join(out_dir, "java_stdout.txt")
        p_err = os.path.join(out_dir, "java_stderr.txt")
        p_exit = os.path.join(out_dir, "java_exit_code.txt")
        _write(p_out, stdout)
        _write(p_err, stderr)
        _write(p_exit, str(result.returncode))
        artifacts = {"stdout": p_out, "stderr": p_err, "exit_code": p_exit}

    if result.returncode != 0:
        return failed(stage,
                      exit_code=result.returncode,
                      stdout=stdout,
                      stderr=stderr,
                      notes=f"Java execution failed: {main_class}")

    return executed(stage,
                    exit_code=0,
                    stdout=stdout,
                    stderr=stderr,
                    artifacts=artifacts,
                    notes=f"Java executed: {main_class}")


def _write(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
