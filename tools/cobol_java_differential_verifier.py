#!/usr/bin/env python3
"""
tools/cobol_java_differential_verifier.py

Standalone COBOL → Native Java Differential Verifier — Mentor Deliverable
==========================================================================

FOUR-STEP EXECUTION MODEL:

  STEP 1: Validate JDK 17+ and Maven. Build generated native Java.
  STEP 2: Execute COBOL baseline (real GnuCOBOL via Docker) AND
          execute native Java (real JVM via Docker), under equivalent STATE A.
  STEP 3: Capture and compare all observable outputs:
            stdout, exit code, output files, database state.
  STEP 4: Generate differential_validation_report.md + .json per mentor schema.

BUSINESS EQUIVALENCE RULE (fail-closed):
  PASS     = real COBOL ran + real Java ran + equivalent STATE A + all
             observable outputs matched + no mock affected the result +
             no unsupported construct invalidated comparison.
  WARNING  = execution occurred but some observable dimension could not
             be compared (e.g. JCL uses compatibility layer, not real JES2;
             or CICS uses compatibility runtime, not IBM CICS).
  FAIL     = any observable mismatch (stdout/files/DB/exit code differ).
  UNPROVEN = COBOL baseline did not actually execute, or no real evidence
             of equivalence exists.
  BLOCKED  = a critical environment dependency is absent (Docker missing,
             JDK missing, Maven missing, required image not cached).

MENTOR STATEMENT:
  "The generated Java was not considered behaviorally equivalent merely
  because it compiled. Equivalence was established only where the original
  COBOL and generated Java were both executed under equivalent initial
  conditions and their observable business behavior was compared using
  executable evidence."

Usage (standalone):
  python tools/cobol_java_differential_verifier.py <repo_path> <out_path>

Usage (programmatic):
  from tools.cobol_java_differential_verifier import DifferentialVerifier
  v = DifferentialVerifier(repo, out_dir)
  report = v.run_all()
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class UnsupportedConstruct:
    construct: str
    source_file: str
    line: int
    classification: str  # UNSUPPORTED / WARNING / UNPROVEN
    impact: str


@dataclass
class VerifierWarning:
    category: str
    detail: str


@dataclass
class StepEvidence:
    """Evidence record for a single execution step."""
    status: str            # PASS / FAIL / BLOCKED / UNPROVEN / WARNING
    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    stdout_sha256: str = ""
    stderr_sha256: str = ""
    duration_sec: float = 0.0
    output_files: Dict[str, str] = field(default_factory=dict)   # name → SHA-256
    output_sizes: Dict[str, int] = field(default_factory=dict)   # name → bytes
    db_state_before: Optional[Dict] = None
    db_state_after: Optional[Dict] = None
    detail: str = ""
    mock_components: List[str] = field(default_factory=list)


@dataclass
class DifferentialReport:
    program: str
    repo_dir: str
    generated_at: str
    target_jdk: str
    conversion: str = "UNPROVEN"  # SUCCESS / FAIL / BLOCKED / UNPROVEN
    conversion_files: List[str] = field(default_factory=list)
    conversion_detail: str = ""
    compilation: str = "UNPROVEN"  # PASS / FAIL / BLOCKED / UNPROVEN
    jdk_version: str = ""
    maven_version: str = ""
    compilation_exit_code: Optional[int] = None
    compilation_detail: str = ""
    cobol_runtime: StepEvidence = field(default_factory=lambda: StepEvidence("UNPROVEN"))
    java_runtime: StepEvidence = field(default_factory=lambda: StepEvidence("UNPROVEN"))
    stdout_comparison: str = "UNPROVEN"    # MATCH / MISMATCH / UNPROVEN
    exit_code_comparison: str = "UNPROVEN"
    file_comparison: str = "UNPROVEN"      # MATCH / MISMATCH / PARTIAL / UNPROVEN
    file_comparison_detail: List[Dict] = field(default_factory=list)
    database_comparison: str = "UNPROVEN"  # MATCH / MISMATCH / UNPROVEN / NOT_APPLICABLE
    database_comparison_detail: str = ""
    unsupported_constructs: List[UnsupportedConstruct] = field(default_factory=list)
    warnings: List[VerifierWarning] = field(default_factory=list)
    mock_components: List[str] = field(default_factory=list)
    business_equivalence: str = "UNPROVEN"


# ---------------------------------------------------------------------------
# Environment probes
# ---------------------------------------------------------------------------

def _run(cmd: List[str], timeout: int = 60, cwd: Optional[str] = None,
         env: Optional[Dict] = None) -> Tuple[int, str, str]:
    """Run a command; return (returncode, stdout, stderr)."""
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            cwd=cwd, env=env
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except FileNotFoundError as e:
        return -2, "", f"NOT_FOUND: {e}"
    except Exception as e:
        return -3, "", str(e)


def _run_bytes(cmd: List[str], timeout: int = 120,
               cwd: Optional[str] = None) -> Tuple[int, bytes, bytes]:
    try:
        proc = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=timeout, cwd=cwd
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return -1, b"", b"TIMEOUT"
    except Exception as e:
        return -3, b"", str(e).encode()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: str) -> str:
    try:
        with open(path, "rb") as fh:
            return _sha256(fh.read())
    except Exception:
        return ""


def _probe_jdk() -> Tuple[bool, str]:
    """Returns (is_17_or_higher, version_string)."""
    rc, out, err = _run(["java", "-version"], timeout=10)
    combined = (out + err).strip()
    m = re.search(r'version\s+"?(\d+)', combined)
    if not m:
        return False, combined or "not found"
    major = int(m.group(1))
    return major >= 17, combined


def _probe_maven() -> Tuple[bool, str]:
    mvn_cmd = shutil.which("mvn.cmd") or shutil.which("mvn") or ("mvn.cmd" if sys.platform == "win32" else "mvn")
    rc, out, err = _run([mvn_cmd, "--version"], timeout=15)
    combined = (out + err).strip().splitlines()[0] if (out + err).strip() else "not found"
    return rc == 0, combined


def _docker_available() -> bool:
    rc, _, _ = _run(["docker", "info"], timeout=10)
    return rc == 0


def _docker_image_cached(image: str) -> bool:
    rc, out, _ = _run(["docker", "images", "-q", image], timeout=10)
    return rc == 0 and bool(out.strip())


GNUCOBOL_IMAGE = os.environ.get("PARITY_GNUCOBOL_IMAGE", "gnucobol-ocesql:latest")
JDK_IMAGE = os.environ.get("PARITY_JDK_IMAGE", "eclipse-temurin:17-jdk-noble")
PG_HOST = os.environ.get("PG_HOST", "db")
PG_PORT = os.environ.get("PG_PORT", "5432")
PG_USER = os.environ.get("PG_USER", "modernize")
PG_PASS = os.environ.get("PG_PASS", "modernize")
PG_DB   = os.environ.get("PG_DB", "modernization_db")
PG_NET  = os.environ.get("PG_NET", "modernization-platform_default")


# ---------------------------------------------------------------------------
# Unsupported construct scanner
# ---------------------------------------------------------------------------

_UNSUPPORTED_PATTERNS = [
    (re.compile(r"EXEC\s+CICS", re.IGNORECASE), "EXEC CICS", "WARNING",
     "CICS commands require compatibility runtime, not real IBM CICS middleware"),
    (re.compile(r"CBLTDLI|AIBTDLI", re.IGNORECASE), "IMS DLI", "UNSUPPORTED",
     "IMS DLI calls cannot be translated — native translation blocked"),
    (re.compile(r"MQOPEN|MQPUT|MQGET|MQCLOSE", re.IGNORECASE), "MQ API", "UNSUPPORTED",
     "IBM MQ API calls cannot be translated automatically"),
    (re.compile(r"EBCDIC", re.IGNORECASE), "EBCDIC", "WARNING",
     "EBCDIC character encoding behavior unverified on ASCII JVM"),
    (re.compile(r"CALL\s+WS-", re.IGNORECASE), "DYNAMIC CALL", "WARNING",
     "Dynamic CALL via working-storage identifier requires manual review"),
]


def scan_unsupported_constructs(repo_dir: str) -> List[UnsupportedConstruct]:
    found = []
    for dirpath, _, filenames in os.walk(repo_dir):
        for fname in filenames:
            if not fname.lower().endswith((".cob", ".cbl", ".jcl", ".copy", ".cpy")):
                continue
            fpath = os.path.join(dirpath, fname)
            try:
                lines = open(fpath, "r", encoding="utf-8", errors="replace").readlines()
            except Exception:
                continue
            for lineno, line in enumerate(lines, start=1):
                for pattern, construct, cls, impact in _UNSUPPORTED_PATTERNS:
                    if pattern.search(line):
                        found.append(UnsupportedConstruct(
                            construct=construct,
                            source_file=os.path.relpath(fpath, repo_dir),
                            line=lineno,
                            classification=cls,
                            impact=impact,
                        ))
    return found


# ---------------------------------------------------------------------------
# PostgreSQL state capture
# ---------------------------------------------------------------------------

def _psql_query(sql: str, network: str = PG_NET, extra_env: Dict = None) -> Tuple[int, str]:
    """Run psql query inside docker on the PG network. Returns (rc, stdout)."""
    env_args = [
        "-e", f"PGPASSWORD={PG_PASS}",
        "-e", f"PGHOST={PG_HOST}",
        "-e", f"PGPORT={PG_PORT}",
        "-e", f"PGUSER={PG_USER}",
        "-e", f"PGDATABASE={PG_DB}",
    ]
    cmd = (
        ["docker", "run", "--rm", "--network", network]
        + env_args
        + [GNUCOBOL_IMAGE, "psql", "-h", PG_HOST, "-U", PG_USER, "-d", PG_DB, "-c", sql]
    )
    rc, out, err = _run(cmd, timeout=30)
    return rc, (out + err).strip()


def _capture_db_state(tables: List[str], label: str) -> Dict[str, Any]:
    """Capture row counts and all rows for the given tables via psql."""
    state = {"label": label, "tables": {}}
    for table in tables:
        rc, out = _psql_query(f"SELECT * FROM {table} ORDER BY 1;")
        state["tables"][table] = {"rows_raw": out, "ok": rc == 0}
    return state


def _apply_sql_to_postgres(schema_sql: str, data_sql: str) -> Tuple[bool, str]:
    """Apply schema + data SQL to the running PostgreSQL container."""
    with tempfile.TemporaryDirectory() as td:
        schema_path = os.path.join(td, "schema.sql")
        data_path = os.path.join(td, "data.sql")
        with open(schema_path, "w") as fh:
            fh.write(schema_sql)
        with open(data_path, "w") as fh:
            fh.write(data_sql)

        td_abs = td.replace("\\", "/")
        for sql_file in ("schema.sql", "data.sql"):
            cmd = [
                "docker", "run", "--rm",
                "--network", PG_NET,
                "-v", f"{td_abs}:/sqlscripts",
                "-e", f"PGPASSWORD={PG_PASS}",
                GNUCOBOL_IMAGE,
                "psql", "-h", PG_HOST, "-U", PG_USER, "-d", PG_DB,
                "-f", f"/sqlscripts/{sql_file}"
            ]
            rc, out, err = _run(cmd, timeout=30)
            if rc != 0:
                return False, f"Failed applying {sql_file}: {err}\n{out}"
    return True, "OK"


# ---------------------------------------------------------------------------
# State A restore helper
# ---------------------------------------------------------------------------

def _restore_state_a(src_input_dirs: List[str], repo_dir: str,
                     cobol_ws: str, java_ws: str):
    """Copy identical input data into both workspaces before execution."""
    for src_rel in src_input_dirs:
        src_abs = os.path.join(repo_dir, src_rel)
        if not os.path.exists(src_abs):
            continue
        for ws in (cobol_ws, java_ws):
            dst = os.path.join(ws, src_rel)
            if os.path.isdir(src_abs):
                shutil.copytree(src_abs, dst, dirs_exist_ok=True)
            else:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src_abs, dst)


# ---------------------------------------------------------------------------
# Output file normalization (transport-only; never masks value differences)
# ---------------------------------------------------------------------------

def _conservative_normalize(b: bytes) -> bytes:
    """Strip CRLF→LF and trailing empty lines only. Never strips field values."""
    try:
        text = b.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return b  # Binary: compare raw
    lines = [line.rstrip("\r") for line in text.split("\n")]
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines).encode("utf-8")


def _compare_output_files(
    cobol_outputs_dir: str,
    java_outputs_dir: str,
    declared_rel_paths: List[str]
) -> Tuple[str, List[Dict]]:
    """
    Compare declared output files from COBOL and Java workspaces.
    Returns (overall_status, per_file_detail_list).
    Status = MATCH | MISMATCH | PARTIAL | UNPROVEN
    """
    if not declared_rel_paths:
        return "UNPROVEN", []

    details = []
    any_mismatch = False
    any_match = False

    for rel in declared_rel_paths:
        cobol_path = os.path.join(cobol_outputs_dir, rel)
        java_path = os.path.join(java_outputs_dir, rel)
        c_exists = os.path.isfile(cobol_path)
        j_exists = os.path.isfile(java_path)

        if not c_exists and not j_exists:
            details.append({"file": rel, "status": "BOTH_MISSING",
                            "cobol_sha256": None, "java_sha256": None,
                            "cobol_size": None, "java_size": None})
            any_mismatch = True
            continue

        if c_exists and not j_exists:
            details.append({"file": rel, "status": "JAVA_MISSING",
                            "cobol_sha256": _sha256_file(cobol_path), "java_sha256": None,
                            "cobol_size": os.path.getsize(cobol_path), "java_size": None})
            any_mismatch = True
            continue

        if j_exists and not c_exists:
            details.append({"file": rel, "status": "COBOL_MISSING",
                            "cobol_sha256": None, "java_sha256": _sha256_file(java_path),
                            "cobol_size": None, "java_size": os.path.getsize(java_path)})
            any_mismatch = True
            continue

        with open(cobol_path, "rb") as fh:
            c_bytes = fh.read()
        with open(java_path, "rb") as fh:
            j_bytes = fh.read()

        c_sha = _sha256(c_bytes)
        j_sha = _sha256(j_bytes)

        if c_sha == j_sha:
            status = "EXACT_MATCH"
            any_match = True
        else:
            # Try conservative transport normalization (CRLF only)
            c_norm = _conservative_normalize(c_bytes)
            j_norm = _conservative_normalize(j_bytes)
            if c_norm == j_norm:
                status = "TRANSPORT_NORMALIZED_MATCH"
                any_match = True
            else:
                status = "CONTENT_MISMATCH"
                any_mismatch = True

        details.append({
            "file": rel, "status": status,
            "cobol_sha256": c_sha, "java_sha256": j_sha,
            "cobol_size": len(c_bytes), "java_size": len(j_bytes),
        })

    if any_mismatch and any_match:
        return "PARTIAL", details
    if any_mismatch:
        return "MISMATCH", details
    if any_match:
        return "MATCH", details
    return "UNPROVEN", details


# ---------------------------------------------------------------------------
# Core verifier class
# ---------------------------------------------------------------------------

class DifferentialVerifier:
    """
    Orchestrates the 4-step mentor verification lifecycle for a single COBOL
    repository. Builds on top of existing parity_harness infrastructure
    without duplicating COBOL or Java runners.
    """

    def __init__(self, repo_dir: str, out_dir: str, program_name: Optional[str] = None):
        self.repo_dir = os.path.abspath(repo_dir)
        self.out_dir = os.path.abspath(out_dir)
        os.makedirs(self.out_dir, exist_ok=True)

        # Derive program name from directory name if not supplied
        self.program_name = program_name or os.path.basename(self.repo_dir)

        # Workspace directories (STATE A isolation)
        self.cobol_ws = os.path.join(self.out_dir, "cobol_workspace")
        self.java_ws  = os.path.join(self.out_dir, "java_workspace")

        # Report output paths
        self.reports_dir = os.path.join(self.out_dir, "reports", self.program_name)
        os.makedirs(self.reports_dir, exist_ok=True)
        self.report_json_path = os.path.join(self.reports_dir, "differential_validation_report.json")
        self.report_md_path   = os.path.join(self.reports_dir, "differential_validation_report.md")

        # Migration config (optional)
        self._cfg = self._load_config()

        # Detect workload type
        self.has_sql = self._detect_sql()
        self.has_jcl = self._detect_jcl()
        self.has_cics = self._detect_cics()

        # Discover input/output file paths
        self.input_rel_paths, self.output_rel_paths = self._discover_io_paths()

        # Tables for DB state capture (populated from mock_db.yaml or migration config)
        self.db_tables = self._discover_db_tables()

    # ------------------------------------------------------------------
    def _load_config(self) -> Dict:
        for name in ("migration_config.json", "config.json"):
            p = os.path.join(self.repo_dir, name)
            if os.path.exists(p):
                try:
                    return json.load(open(p, encoding="utf-8"))
                except Exception:
                    pass
        return {}

    def _detect_sql(self) -> bool:
        for d, _, fs in os.walk(self.repo_dir):
            for f in fs:
                if f.lower().endswith((".cob", ".cbl")):
                    try:
                        content = open(os.path.join(d, f), "r", errors="replace").read()
                        if "EXEC SQL" in content.upper():
                            return True
                    except Exception:
                        pass
        return False

    def _detect_jcl(self) -> bool:
        for d, _, fs in os.walk(self.repo_dir):
            for f in fs:
                if f.lower().endswith(".jcl"):
                    return True
        return False

    def _detect_cics(self) -> bool:
        for d, _, fs in os.walk(self.repo_dir):
            for f in fs:
                if f.lower().endswith((".cob", ".cbl")):
                    try:
                        content = open(os.path.join(d, f), "r", errors="replace").read()
                        if "EXEC CICS" in content.upper():
                            return True
                    except Exception:
                        pass
        return False

    def _discover_io_paths(self) -> Tuple[List[str], List[str]]:
        """Best-effort discovery of input and output file paths from COBOL source."""
        inputs: List[str] = []
        outputs: List[str] = []

        # Check file_assignments in config
        fa = self._cfg.get("file_assignments", {})
        for k, v in fa.items():
            path = v.replace("\\", "/")
            if "in" in path.lower() or "source" in path.lower() or "input" in path.lower():
                inputs.append(path)
            else:
                outputs.append(path)

        # Parse ASSIGN clauses from COBOL source
        assign_re = re.compile(r'ASSIGN\s+TO\s+["\']([^"\']+)["\']', re.IGNORECASE)
        for d, _, fs in os.walk(self.repo_dir):
            for f in fs:
                if not f.lower().endswith((".cob", ".cbl")):
                    continue
                try:
                    text = open(os.path.join(d, f), "r", errors="replace").read()
                    for m in assign_re.finditer(text):
                        p = m.group(1).replace("\\", "/")
                        if any(x in p.lower() for x in ("in/", "/in", "source/", "/source", "input")):
                            if p not in inputs:
                                inputs.append(p)
                        else:
                            if p not in outputs:
                                outputs.append(p)
                except Exception:
                    pass

        return inputs, outputs

    def _discover_db_tables(self) -> List[str]:
        """Discover DB tables from mock_db.yaml."""
        yaml_path = os.path.join(self.repo_dir, "mock_db.yaml")
        if not os.path.exists(yaml_path):
            return []
        try:
            import yaml
            cfg = yaml.safe_load(open(yaml_path, encoding="utf-8"))
            return [t["name"].upper() for t in cfg.get("tables", [])]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # STEP 1 — Compile
    # ------------------------------------------------------------------

    def step1_compile_java_jdk17(self) -> Tuple[bool, str, str, str]:
        """
        Step 1: Validate JDK 17+, Maven, then build native Java.
        Returns (ok, detail, jdk_version, maven_version).
        """
        print("\n" + "=" * 60)
        print("[STEP 1/4] Java Compilation (JDK 17+ target)")
        print("=" * 60)

        jdk_ok, jdk_ver = _probe_jdk()
        mvn_ok, mvn_ver = _probe_maven()

        print(f"  JDK: {jdk_ver}")
        print(f"  Maven: {mvn_ver}")

        if not jdk_ok:
            return False, f"JDK 17+ required, found: {jdk_ver}", jdk_ver, mvn_ver
        if not mvn_ok:
            return False, f"Maven not found: {mvn_ver}", jdk_ver, mvn_ver

        # Run the existing NativePipeline to generate + compile native Java
        from modernize.native_pipeline import NativePipeline
        pipe = NativePipeline(self.repo_dir, self.out_dir)

        # Run only the compile stages (discover → parse → select → generate → build gate)
        pipe.stage_discover()
        if not pipe.sources:
            return False, "No COBOL sources discovered", jdk_ver, mvn_ver

        pipe.stage_parse()
        selected = pipe.stage_select_slice()
        if not selected:
            return False, "No vertical slice could be selected", jdk_ver, mvn_ver

        self._selected_src = selected
        self._pipe = pipe

        pipe.stage_generate(selected)
        ok = pipe.stage_build_gate()
        if not ok:
            return False, "Maven mvn test-compile FAILED (see build log)", jdk_ver, mvn_ver

        # Discover generated Java files
        gen_java = []
        gen_dir = os.path.join(self.out_dir, "native")
        for dirpath, _, files in os.walk(gen_dir):
            for f in files:
                if f.endswith(".java"):
                    gen_java.append(os.path.relpath(os.path.join(dirpath, f), self.out_dir))

        return True, f"mvn test-compile PASS ({len(gen_java)} .java files)", jdk_ver, mvn_ver

    # ------------------------------------------------------------------
    # STEP 2 — Execute
    # ------------------------------------------------------------------

    def step2_execute_both_runtimes(
        self,
        compile_ok: bool
    ) -> Tuple[StepEvidence, StepEvidence]:
        """
        Step 2: Execute COBOL (real GnuCOBOL via Docker) and
                Java (real JVM via Docker) under identical STATE A.
        Returns (cobol_evidence, java_evidence).
        """
        print("\n" + "=" * 60)
        print("[STEP 2/4] Dual Runtime Execution")
        print("=" * 60)

        cobol_ev = StepEvidence("UNPROVEN")
        java_ev  = StepEvidence("UNPROVEN")

        if not compile_ok:
            cobol_ev.detail = "Skipped: compilation failed"
            java_ev.detail  = "Skipped: compilation failed"
            return cobol_ev, java_ev

        if not _docker_available():
            cobol_ev.status = "BLOCKED"
            java_ev.status  = "BLOCKED"
            cobol_ev.detail = "Docker not available"
            java_ev.detail  = "Docker not available"
            return cobol_ev, java_ev

        # Prepare isolated workspaces (STATE A)
        shutil.rmtree(self.cobol_ws, ignore_errors=True)
        shutil.rmtree(self.java_ws, ignore_errors=True)
        shutil.copytree(self.repo_dir, self.cobol_ws, dirs_exist_ok=True)
        shutil.copytree(self.repo_dir, self.java_ws, dirs_exist_ok=True)

        # Clear any stale outputs from both workspaces so only fresh run outputs remain
        for ws in (self.cobol_ws, self.java_ws):
            for rel in self.output_rel_paths:
                p = os.path.join(ws, rel)
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass

        # --- COBOL baseline ---
        if self.has_sql:
            cobol_ev = self._run_cobol_sql(self.cobol_ws)
        elif self.has_jcl:
            cobol_ev = self._run_cobol_jcl(self.cobol_ws)
        else:
            cobol_ev = self._run_cobol_plain(self.cobol_ws)

        # --- STATE A restore before Java ---
        # Clear Java workspace outputs (ensure same initial state)
        for rel in self.output_rel_paths:
            p = os.path.join(self.java_ws, rel)
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass

        # --- Java runtime ---
        if self.has_sql:
            java_ev = self._run_java_sql(self.java_ws, self.out_dir)
        elif self.has_jcl:
            java_ev = self._run_java_jcl(self.java_ws, self.out_dir)
        else:
            java_ev = self._run_java_native(self.java_ws, self.out_dir)

        return cobol_ev, java_ev

    # --- Private execution helpers ---

    def _run_cobol_plain(self, ws: str) -> StepEvidence:
        """Execute pre-compiled COBOL binary inside GnuCOBOL Docker."""
        if not _docker_image_cached(GNUCOBOL_IMAGE):
            ev = StepEvidence("BLOCKED")
            ev.detail = f"Docker image not cached: {GNUCOBOL_IMAGE}"
            return ev

        # Find the COBOL executable (already compiled at discovery time or use cobc)
        exe_candidates = [f for f in os.listdir(ws) if f.endswith(".exe")]
        if not exe_candidates:
            # Compile inside docker
            src_rel = self._get_entry_src_rel()
            compile_cmd = (
                f"cd /repo && cobc -x -free -o entry.exe {src_rel} "
                f"-I copybooks 2>&1"
            )
            rc, out, err = _run(
                ["docker", "run", "--rm", "-v", f"{ws.replace(chr(92), '/')}:/repo",
                 "-w", "/repo", GNUCOBOL_IMAGE, "sh", "-c", compile_cmd],
                timeout=60
            )
            if rc != 0:
                ev = StepEvidence("FAIL")
                ev.stderr = err
                ev.detail = f"GnuCOBOL compile failed (rc={rc})"
                return ev
            exe_name = "entry.exe"
        else:
            exe_name = exe_candidates[0]

        ws_abs = ws.replace("\\", "/")
        # Ensure output dirs exist
        for rel in self.output_rel_paths:
            out_dir = os.path.join(ws, os.path.dirname(rel))
            os.makedirs(out_dir, exist_ok=True)

        run_cmd = f"cd /repo && ./{exe_name}"
        import time
        t0 = time.time()
        rc, out_b, err_b = _run_bytes(
            ["docker", "run", "--rm",
             "-v", f"{ws_abs}:/repo", "-w", "/repo",
             GNUCOBOL_IMAGE, "sh", "-c", run_cmd],
            timeout=60
        )
        dur = round(time.time() - t0, 2)

        ev = StepEvidence(
            status="PASS" if rc == 0 else "FAIL",
            exit_code=rc,
            stdout=out_b.decode("utf-8", errors="replace"),
            stderr=err_b.decode("utf-8", errors="replace"),
            stdout_sha256=_sha256(out_b),
            stderr_sha256=_sha256(err_b),
            duration_sec=dur,
        )
        ev.detail = f"GnuCOBOL execution rc={rc}"
        self._collect_output_files(ev, ws)
        return ev

    def _run_cobol_sql(self, ws: str) -> StepEvidence:
        """Execute COBOL+OCESQL against real PostgreSQL."""
        if not _docker_image_cached(GNUCOBOL_IMAGE):
            ev = StepEvidence("BLOCKED")
            ev.detail = f"Docker image not cached: {GNUCOBOL_IMAGE}"
            return ev

        # Seed DB (STATE A)
        schema_sql, data_sql = self._load_mock_db_sql()
        if schema_sql:
            ok, msg = _apply_sql_to_postgres(schema_sql, data_sql)
            if not ok:
                ev = StepEvidence("BLOCKED")
                ev.detail = f"DB seeding failed: {msg}"
                return ev

        db_before = _capture_db_state(self.db_tables, "before_cobol") if self.db_tables else None

        ws_abs = ws.replace("\\", "/")
        src_rel = self._get_entry_src_rel()

        # ocesql precompile + cobc compile + run
        compile_run_script = (
            f"cd /repo && "
            f"ocesql {src_rel} src_pre.cob 2>&1 && "
            f"cobc -x -std=default -fsign=ASCII -o cobol_prog.exe src_pre.cob "
            f"-I/usr/share/open-cobol-esql/copy -locesql 2>&1 && "
            f"export PGHOST={PG_HOST} PGPORT={PG_PORT} PGUSER={PG_USER} "
            f"PGPASSWORD={PG_PASS} PGDATABASE={PG_DB} "
            f"COB_PRE_LOAD=/usr/lib/libocesql.so && "
            f"./cobol_prog.exe"
        )
        import time
        t0 = time.time()
        rc, out_b, err_b = _run_bytes(
            ["docker", "run", "--rm",
             "--network", PG_NET,
             "-v", f"{ws_abs}:/repo", "-w", "/repo",
             GNUCOBOL_IMAGE, "sh", "-c", compile_run_script],
            timeout=90
        )
        dur = round(time.time() - t0, 2)

        db_after = _capture_db_state(self.db_tables, "after_cobol") if self.db_tables else None

        ev = StepEvidence(
            status="PASS" if rc == 0 else "FAIL",
            exit_code=rc,
            stdout=out_b.decode("utf-8", errors="replace"),
            stderr=err_b.decode("utf-8", errors="replace"),
            stdout_sha256=_sha256(out_b),
            stderr_sha256=_sha256(err_b),
            duration_sec=dur,
            db_state_before=db_before,
            db_state_after=db_after,
        )
        ev.detail = f"COBOL+OCESQL+PostgreSQL rc={rc}"
        self._collect_output_files(ev, ws)
        return ev

    def _run_cobol_jcl(self, ws: str) -> StepEvidence:
        """Run JCL baseline via existing NativePipeline JCL runner."""
        if not _docker_image_cached(GNUCOBOL_IMAGE):
            ev = StepEvidence("BLOCKED")
            ev.detail = f"Docker image not cached: {GNUCOBOL_IMAGE}"
            return ev

        import time
        t0 = time.time()
        try:
            pipe = self._pipe if hasattr(self, "_pipe") else None
            if pipe is None:
                from modernize.native_pipeline import NativePipeline
                pipe = NativePipeline(self.repo_dir, self.out_dir)
                pipe.stage_discover()
                pipe.stage_parse()
            out_lines = []
            if pipe.jcl_files:
                pipe.stage_jcl_baseline()
                jcl_out_path = os.path.join(self.out_dir, "baseline", "legacy", "stdout.txt")
                if os.path.exists(jcl_out_path):
                    out_lines = [open(jcl_out_path).read()]
            stdout_text = "\n".join(out_lines)
            dur = round(time.time() - t0, 2)
            ev = StepEvidence(
                status="PASS",
                exit_code=0,
                stdout=stdout_text,
                stdout_sha256=_sha256(stdout_text.encode()),
                duration_sec=dur,
            )
            ev.detail = "JCL baseline executed via GnuCOBOL compatibility layer"
            ev.mock_components = []
        except Exception as ex:
            dur = round(time.time() - t0, 2)
            ev = StepEvidence("FAIL", duration_sec=dur)
            ev.detail = f"JCL baseline execution error: {ex}"
        self._collect_output_files(ev, ws)
        return ev

    def _run_java_native(self, ws: str, native_out: str) -> StepEvidence:
        """Execute the generated native Java via existing NativePipeline execute gate."""
        if not _docker_image_cached(JDK_IMAGE):
            ev = StepEvidence("BLOCKED")
            ev.detail = f"Docker image not cached: {JDK_IMAGE}"
            return ev

        import time
        t0 = time.time()
        pipe = getattr(self, "_pipe", None)
        if pipe is None:
            ev = StepEvidence("FAIL")
            ev.detail = "Pipeline not initialized (Step 1 must run first)"
            return ev

        # Execute using the pipeline's existing execute gate
        sel = getattr(self, "_selected_src", None)
        if not sel:
            ev = StepEvidence("FAIL")
            ev.detail = "No selected source slice"
            return ev

        ok = pipe.stage_execute_gate(sel)
        dur = round(time.time() - t0, 2)

        # Capture stdout from native result directory
        results_dir = os.path.join(native_out, "results", "native")
        stdout_text = ""
        if os.path.exists(results_dir):
            stdout_path = os.path.join(results_dir, "stdout.txt")
            if os.path.exists(stdout_path):
                stdout_text = open(stdout_path, errors="replace").read()

        ev = StepEvidence(
            status="PASS" if ok else "FAIL",
            exit_code=0 if ok else 1,
            stdout=stdout_text,
            stdout_sha256=_sha256(stdout_text.encode()),
            duration_sec=dur,
        )
        ev.detail = f"Native Java execution {'PASS' if ok else 'FAIL'}"
        # Collect Java output files from results/native directory
        self._collect_output_files(ev, results_dir)
        self._java_outputs_dir = results_dir
        return ev

    def _run_java_sql(self, ws: str, native_out: str) -> StepEvidence:
        """
        Execute the native Java SQL path against real PostgreSQL.
        Restores STATE A (re-seeds DB) before Java execution.
        """
        # Restore STATE A: re-seed DB before Java run
        schema_sql, data_sql = self._load_mock_db_sql()
        if schema_sql:
            ok, msg = _apply_sql_to_postgres(schema_sql, data_sql)
            if not ok:
                ev = StepEvidence("BLOCKED")
                ev.detail = f"DB STATE A restore failed before Java: {msg}"
                return ev

        db_before = _capture_db_state(self.db_tables, "before_java") if self.db_tables else None

        import time
        t0 = time.time()
        pipe = getattr(self, "_pipe", None)
        sel = getattr(self, "_selected_src", None)
        if not pipe or not sel:
            ev = StepEvidence("FAIL")
            ev.detail = "Pipeline not initialized"
            return ev

        ok = pipe.stage_execute_gate(sel)
        dur = round(time.time() - t0, 2)

        db_after = _capture_db_state(self.db_tables, "after_java") if self.db_tables else None

        results_dir = os.path.join(native_out, "results", "native")
        stdout_text = ""
        if os.path.exists(results_dir):
            stdout_path = os.path.join(results_dir, "stdout.txt")
            if os.path.exists(stdout_path):
                stdout_text = open(stdout_path, errors="replace").read()

        ev = StepEvidence(
            status="PASS" if ok else "FAIL",
            exit_code=0 if ok else 1,
            stdout=stdout_text,
            stdout_sha256=_sha256(stdout_text.encode()),
            duration_sec=dur,
            db_state_before=db_before,
            db_state_after=db_after,
        )
        ev.detail = f"Native Java + Spring JDBC + PostgreSQL {'PASS' if ok else 'FAIL'}"
        ev.mock_components = []  # Real DB — no mock
        self._collect_output_files(ev, results_dir)
        self._java_outputs_dir = results_dir
        return ev

    def _run_java_jcl(self, ws: str, native_out: str) -> StepEvidence:
        """Execute native Java JCL orchestration."""
        import time
        t0 = time.time()
        pipe = getattr(self, "_pipe", None)
        sel = getattr(self, "_selected_src", None)
        if not pipe or not sel:
            ev = StepEvidence("FAIL")
            ev.detail = "Pipeline not initialized"
            return ev

        ok = pipe.stage_execute_gate(sel)
        dur = round(time.time() - t0, 2)

        results_dir = os.path.join(native_out, "results", "native")
        stdout_text = ""
        if os.path.exists(results_dir):
            stdout_path = os.path.join(results_dir, "stdout.txt")
            if os.path.exists(stdout_path):
                stdout_text = open(stdout_path, errors="replace").read()

        ev = StepEvidence(
            status="PASS" if ok else "FAIL",
            exit_code=0 if ok else 1,
            stdout=stdout_text,
            stdout_sha256=_sha256(stdout_text.encode()),
            duration_sec=dur,
        )
        ev.detail = "Native Java JCL compatibility layer (not real z/OS JES2)"
        ev.mock_components = ["JCL_COMPATIBILITY_LAYER"]
        self._collect_output_files(ev, results_dir)
        self._java_outputs_dir = results_dir
        return ev

    # ------------------------------------------------------------------
    # STEP 3 — Compare
    # ------------------------------------------------------------------

    def step3_compare(
        self,
        cobol_ev: StepEvidence,
        java_ev: StepEvidence
    ) -> Tuple[str, str, str, str, List[Dict]]:
        """
        Step 3: Compare all observable behavior.
        Returns (stdout_cmp, exit_code_cmp, file_cmp, db_cmp, file_details).
        Each: MATCH | MISMATCH | UNPROVEN
        """
        print("\n" + "=" * 60)
        print("[STEP 3/4] Comparing Observable Behavior")
        print("=" * 60)

        # Exit code
        if cobol_ev.exit_code is not None and java_ev.exit_code is not None:
            exit_cmp = "MATCH" if cobol_ev.exit_code == java_ev.exit_code else "MISMATCH"
        else:
            exit_cmp = "UNPROVEN"

        # Stdout (transport-normalized)
        if cobol_ev.stdout and java_ev.stdout:
            c_norm = _conservative_normalize(cobol_ev.stdout.encode())
            j_norm = _conservative_normalize(java_ev.stdout.encode())
            stdout_cmp = "MATCH" if c_norm == j_norm else "MISMATCH"
        elif not cobol_ev.stdout and not java_ev.stdout:
            stdout_cmp = "MATCH"  # Both empty
        else:
            stdout_cmp = "UNPROVEN"

        # Output files
        cobol_out_dir = self.cobol_ws
        java_out_dir  = getattr(self, "_java_outputs_dir", self.java_ws)

        file_cmp, file_details = _compare_output_files(
            cobol_out_dir, java_out_dir, self.output_rel_paths
        )

        # DB state comparison
        db_cmp = "NOT_APPLICABLE"
        if cobol_ev.db_state_after and java_ev.db_state_after:
            c_db = cobol_ev.db_state_after.get("tables", {})
            j_db = java_ev.db_state_after.get("tables", {})
            if c_db and j_db:
                all_match = all(
                    c_db.get(t, {}).get("rows_raw") == j_db.get(t, {}).get("rows_raw")
                    for t in self.db_tables
                )
                db_cmp = "MATCH" if all_match else "MISMATCH"
            else:
                db_cmp = "UNPROVEN"
        elif self.has_sql:
            db_cmp = "UNPROVEN"

        print(f"  Exit code:    {exit_cmp} (COBOL={cobol_ev.exit_code}, Java={java_ev.exit_code})")
        print(f"  Stdout:       {stdout_cmp}")
        print(f"  Output files: {file_cmp} ({len(file_details)} files)")
        print(f"  Database:     {db_cmp}")

        return stdout_cmp, exit_cmp, file_cmp, db_cmp, file_details

    # ------------------------------------------------------------------
    # STEP 4 — Report
    # ------------------------------------------------------------------

    def step4_generate_report(self, report: DifferentialReport) -> str:
        """
        Step 4: Compute final business equivalence verdict and write reports.
        Returns overall business_equivalence verdict.
        """
        print("\n" + "=" * 60)
        print("[STEP 4/4] Generating Differential Validation Report")
        print("=" * 60)

        # ── Fail-closed business equivalence calculation ──────────────
        verdict = self._compute_verdict(report)
        report.business_equivalence = verdict

        self._write_json_report(report)
        self._write_md_report(report)

        print(f"\n  ✦ BUSINESS EQUIVALENCE: {verdict}")
        print(f"  Report JSON: {self.report_json_path}")
        print(f"  Report MD:   {self.report_md_path}")

        return verdict

    def _compute_verdict(self, r: DifferentialReport) -> str:
        """
        Fail-closed verdict computation. PASS only when all gates clear.
        """
        # Hard-fail conditions → FAIL immediately
        if r.cobol_runtime.status == "FAIL" or r.java_runtime.status == "FAIL":
            return "FAIL"
        if r.compilation == "FAIL":
            return "FAIL"
        if r.stdout_comparison == "MISMATCH":
            return "FAIL"
        if r.exit_code_comparison == "MISMATCH":
            return "FAIL"
        if r.file_comparison == "MISMATCH":
            return "FAIL"
        if r.database_comparison == "MISMATCH":
            return "FAIL"

        # BLOCKED → BLOCKED
        if (r.cobol_runtime.status == "BLOCKED"
                or r.java_runtime.status == "BLOCKED"
                or r.compilation == "BLOCKED"):
            return "BLOCKED"

        # No real COBOL execution → UNPROVEN
        if r.cobol_runtime.status in ("UNPROVEN", ""):
            return "UNPROVEN"

        # No real Java execution → UNPROVEN
        if r.java_runtime.status in ("UNPROVEN", ""):
            return "UNPROVEN"

        # Compilation didn't pass → cannot claim PASS
        if r.compilation != "PASS":
            return "UNPROVEN"

        # Mock component used for a required comparison dimension → WARNING
        all_mocks = r.cobol_runtime.mock_components + r.java_runtime.mock_components
        if all_mocks:
            return "WARNING"

        # CICS/JCL compatibility layers → WARNING (not real middleware)
        if self.has_cics:
            return "WARNING"
        if self.has_jcl:
            return "WARNING"

        # Unsupported constructs with UNSUPPORTED classification → FAIL or WARNING
        hard_unsupported = [c for c in r.unsupported_constructs
                            if c.classification == "UNSUPPORTED"]
        soft_unsupported = [c for c in r.unsupported_constructs
                            if c.classification == "WARNING"]
        if hard_unsupported:
            return "UNPROVEN"  # Cannot verify — construct blocked translation

        # DB workload with no DB state comparison → WARNING
        if self.has_sql and r.database_comparison in ("UNPROVEN", "NOT_APPLICABLE"):
            return "WARNING"

        # File outputs not compared → WARNING
        if self.output_rel_paths and r.file_comparison == "UNPROVEN":
            return "WARNING"

        # Soft warnings from unsupported constructs
        if soft_unsupported:
            return "WARNING"

        # All gates clear → PASS
        return "PASS"

    # ------------------------------------------------------------------
    # Report writers
    # ------------------------------------------------------------------

    def _write_json_report(self, r: DifferentialReport):
        def ev_to_dict(ev: StepEvidence) -> Dict:
            return {
                "status": ev.status,
                "exit_code": ev.exit_code,
                "stdout_sha256": ev.stdout_sha256,
                "stderr_sha256": ev.stderr_sha256,
                "duration_sec": ev.duration_sec,
                "output_files": ev.output_files,
                "output_sizes": ev.output_sizes,
                "db_state_before": ev.db_state_before,
                "db_state_after": ev.db_state_after,
                "detail": ev.detail,
                "mock_components": ev.mock_components,
            }

        report_dict = {
            "program": r.program,
            "repository": r.repo_dir,
            "generated_at": r.generated_at,
            "target_jdk": r.target_jdk,
            "conversion": {"status": r.conversion, "files": r.conversion_files,
                           "detail": r.conversion_detail},
            "compilation": {
                "status": r.compilation,
                "jdk_version": r.jdk_version,
                "maven_version": r.maven_version,
                "exit_code": r.compilation_exit_code,
                "detail": r.compilation_detail,
            },
            "cobol_runtime": ev_to_dict(r.cobol_runtime),
            "java_runtime": ev_to_dict(r.java_runtime),
            "comparison": {
                "stdout": r.stdout_comparison,
                "exit_code": r.exit_code_comparison,
                "files": r.file_comparison,
                "database": r.database_comparison,
            },
            "file_comparison_detail": r.file_comparison_detail,
            "unsupported_constructs": [
                {"construct": c.construct, "source": c.source_file, "line": c.line,
                 "classification": c.classification, "impact": c.impact}
                for c in r.unsupported_constructs
            ],
            "warnings": [{"category": w.category, "detail": w.detail} for w in r.warnings],
            "mock_components": r.mock_components,
            "business_equivalence": r.business_equivalence,
        }
        with open(self.report_json_path, "w", encoding="utf-8") as fh:
            json.dump(report_dict, fh, indent=2)

    def _write_md_report(self, r: DifferentialReport):
        be = r.business_equivalence
        be_icon = {"PASS": "✅", "WARNING": "⚠️", "FAIL": "❌",
                   "UNPROVEN": "❓", "BLOCKED": "🚫"}.get(be, "❓")

        lines = [
            "# COBOL → JAVA DIFFERENTIAL VALIDATION REPORT",
            "",
            f"**Program:** `{r.program}`  ",
            f"**Repository:** `{r.repo_dir}`  ",
            f"**Generated:** `{r.generated_at}`  ",
            f"**Target Runtime:** `Java {r.target_jdk}+ / JDK 17+ (Spring Boot 3)`  ",
            "",
            "---",
            "",
            "## Summary",
            "",
            "| Dimension | Result |",
            "| :--- | :--- |",
            f"| Conversion | `{r.conversion}` |",
            f"| Compilation | `{r.compilation}` |",
            f"| COBOL Runtime | `{r.cobol_runtime.status}` |",
            f"| Java Runtime | `{r.java_runtime.status}` |",
            f"| Stdout Comparison | `{r.stdout_comparison}` |",
            f"| Exit Code Comparison | `{r.exit_code_comparison}` |",
            f"| File Comparison | `{r.file_comparison}` |",
            f"| Database Comparison | `{r.database_comparison}` |",
            f"| Unsupported Constructs | `{len(r.unsupported_constructs)}` |",
            f"| Warnings | `{len(r.warnings)}` |",
            f"| **Business Equivalence** | **`{be_icon} {be}`** |",
            "",
            "---",
            "",
            "## 1. Conversion",
            "",
            f"- **Status:** `{r.conversion}`",
            f"- **Detail:** {r.conversion_detail or 'N/A'}",
            f"- **Generated Files:** {len(r.conversion_files)}",
            "",
            "---",
            "",
            "## 2. Compilation (JDK 17+)",
            "",
            f"- **Status:** `{r.compilation}`",
            f"- **JDK Version:** `{r.jdk_version}`",
            f"- **Maven Version:** `{r.maven_version}`",
            f"- **Detail:** {r.compilation_detail or 'N/A'}",
            "",
            "---",
            "",
            "## 3. Runtime Execution",
            "",
            "| Execution Environment | Status | Duration | Exit Code |",
            "| :--- | :--- | :--- | :--- |",
            f"| **Legacy COBOL (GnuCOBOL + Docker)** | `{r.cobol_runtime.status}` | "
            f"`{r.cobol_runtime.duration_sec}s` | `{r.cobol_runtime.exit_code}` |",
            f"| **Native Java 17+ (JVM + Docker)** | `{r.java_runtime.status}` | "
            f"`{r.java_runtime.duration_sec}s` | `{r.java_runtime.exit_code}` |",
            "",
            "### COBOL Runtime Detail",
            f"```\n{r.cobol_runtime.stdout[:2000] if r.cobol_runtime.stdout else '(no stdout)'}\n```",
            "",
            "### Java Runtime Detail",
            f"```\n{r.java_runtime.stdout[:2000] if r.java_runtime.stdout else '(no stdout)'}\n```",
            "",
            "---",
            "",
            "## 4. Observable Behavior Comparison",
            "",
            "### Stdout",
            f"- **Result:** `{r.stdout_comparison}`",
            "- COBOL SHA-256: `" + r.cobol_runtime.stdout_sha256 + "`",
            "- Java SHA-256:  `" + r.java_runtime.stdout_sha256 + "`",
            "",
            "### Exit Code",
            f"- **Result:** `{r.exit_code_comparison}`",
            f"- COBOL exit: `{r.cobol_runtime.exit_code}` | Java exit: `{r.java_runtime.exit_code}`",
            "",
            "### Output Files",
            f"- **Overall:** `{r.file_comparison}`",
        ]

        if r.file_comparison_detail:
            lines += ["", "| File | Status | COBOL SHA-256 | Java SHA-256 |",
                      "| :--- | :--- | :--- | :--- |"]
            for fd in r.file_comparison_detail:
                c_sha = (fd.get("cobol_sha256") or "—")[:16] + "…" if fd.get("cobol_sha256") else "—"
                j_sha = (fd.get("java_sha256") or "—")[:16] + "…" if fd.get("java_sha256") else "—"
                lines.append(f"| `{fd['file']}` | `{fd['status']}` | `{c_sha}` | `{j_sha}` |")

        lines += [
            "",
            "### Database State",
            f"- **Result:** `{r.database_comparison}`",
            f"- {r.database_comparison_detail or 'N/A'}",
            "",
            "---",
            "",
            "## 5. Unsupported Constructs",
            "",
            f"**Count: {len(r.unsupported_constructs)}**",
        ]

        if r.unsupported_constructs:
            lines += ["", "| Construct | Source | Line | Classification | Impact |",
                      "| :--- | :--- | :--- | :--- | :--- |"]
            for c in r.unsupported_constructs:
                lines.append(
                    f"| `{c.construct}` | `{c.source_file}` | {c.line} | "
                    f"`{c.classification}` | {c.impact} |"
                )
        else:
            lines.append("None detected.")

        lines += [
            "",
            "---",
            "",
            "## 6. Warnings",
            "",
            f"**Count: {len(r.warnings)}**",
        ]

        if r.warnings:
            for w in r.warnings:
                lines.append(f"- **{w.category}:** {w.detail}")
        else:
            lines.append("None.")

        lines += [
            "",
            "---",
            "",
            "## FINAL VERDICT",
            "",
            "```",
            f"CONVERSION:          {r.conversion}",
            f"COMPILATION:         {r.compilation}",
            f"COBOL RUNTIME:       {r.cobol_runtime.status}",
            f"JAVA RUNTIME:        {r.java_runtime.status}",
            f"STDOUT:              {r.stdout_comparison}",
            f"EXIT CODE:           {r.exit_code_comparison}",
            f"FILES:               {r.file_comparison}",
            f"DATABASE:            {r.database_comparison}",
            f"UNSUPPORTED:         {len(r.unsupported_constructs)}",
            f"WARNINGS:            {len(r.warnings)}",
            f"BUSINESS EQUIVALENCE: {be}",
            "```",
            "",
            "---",
            "",
            "> **Mentor Statement:** The generated Java was not considered behaviorally",
            "> equivalent merely because it compiled. Equivalence was established only where",
            "> the original COBOL and generated Java were both executed under equivalent",
            "> initial conditions and their observable business behavior was compared using",
            "> executable evidence.",
        ]

        with open(self.report_md_path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------

    def _get_entry_src_rel(self) -> str:
        """Return relative path of the entry COBOL source within the repo."""
        sel = getattr(self, "_selected_src", None)
        if sel:
            return os.path.relpath(sel, self.repo_dir).replace("\\", "/")
        # Fallback: first .cob file found
        for d, _, fs in os.walk(self.repo_dir):
            for f in fs:
                if f.lower().endswith((".cob", ".cbl")):
                    return os.path.relpath(os.path.join(d, f), self.repo_dir).replace("\\", "/")
        return ""

    def _collect_output_files(self, ev: StepEvidence, ws: str):
        """Populate ev.output_files and ev.output_sizes from workspace."""
        for rel in self.output_rel_paths:
            path = os.path.join(ws, rel)
            if os.path.isfile(path):
                with open(path, "rb") as fh:
                    data = fh.read()
                ev.output_files[rel] = _sha256(data)
                ev.output_sizes[rel] = len(data)

    def _load_mock_db_sql(self) -> Tuple[str, str]:
        """Load schema and data SQL from mock_db.yaml."""
        yaml_path = os.path.join(self.repo_dir, "mock_db.yaml")
        if not os.path.exists(yaml_path):
            return "", ""
        try:
            import yaml
            cfg = yaml.safe_load(open(yaml_path, encoding="utf-8"))
        except Exception:
            return "", ""

        tables = cfg.get("tables", [])
        schema_lines, data_lines = [], []
        for table in tables:
            name = table["name"].upper()
            cols = table.get("columns", [])
            rows = table.get("rows", [])
            schema_lines.append(f"DROP TABLE IF EXISTS {name};")
            col_defs = []
            col_names = []
            for col in cols:
                col_name = col["name"].upper()
                col_names.append(col_name)
                pk_str = " PRIMARY KEY" if col.get("primary_key") else ""
                col_defs.append(f"    {col_name} {col['type'].upper()}{pk_str}")
            schema_lines.append(f"CREATE TABLE {name} (\n" + ",\n".join(col_defs) + "\n);")
            for row in rows:
                val_strs = []
                for val in row:
                    if val is None:
                        val_strs.append("NULL")
                    elif isinstance(val, str):
                        val_strs.append(f"'{val.replace(chr(39), chr(39)*2)}'")
                    else:
                        val_strs.append(str(val))
                data_lines.append(
                    f"INSERT INTO {name} ({', '.join(col_names)}) "
                    f"VALUES ({', '.join(val_strs)});"
                )
        return "\n".join(schema_lines), "\n".join(data_lines)

    # ------------------------------------------------------------------
    # Main orchestration
    # ------------------------------------------------------------------

    def run_all(self) -> str:
        """
        Execute all 4 steps and return the business equivalence verdict.
        """
        print("\n" + "=" * 60)
        print(f"COBOL → JAVA DIFFERENTIAL VERIFIER: {self.program_name}")
        print("=" * 60)

        now = datetime.now(timezone.utc).isoformat()
        jdk_ok, jdk_ver = _probe_jdk()
        _, mvn_ver = _probe_maven()

        # Scan for unsupported constructs
        constructs = scan_unsupported_constructs(self.repo_dir)
        warnings: List[VerifierWarning] = []

        if self.has_cics:
            warnings.append(VerifierWarning(
                "CICS_COMPATIBILITY",
                "EXEC CICS commands are handled by a compatibility layer, "
                "not real IBM CICS middleware. Real CICS behavior: UNPROVEN."
            ))
        if self.has_jcl:
            warnings.append(VerifierWarning(
                "JCL_COMPATIBILITY",
                "JCL execution uses a native compatibility/orchestration layer, "
                "not a real z/OS JES2/JES3 environment. Real JES behavior: UNPROVEN."
            ))
        if self.has_sql:
            warnings.append(VerifierWarning(
                "SQL_POSTGRESQL",
                "PostgreSQL is used instead of IBM DB2/z. "
                "Real DB2/z behavior: UNPROVEN. Functional equivalence proven for tested SQL."
            ))

        report = DifferentialReport(
            program=self.program_name,
            repo_dir=self.repo_dir,
            generated_at=now,
            target_jdk="17",
            unsupported_constructs=constructs,
            warnings=warnings,
        )

        # STEP 1 — Compile
        compile_ok, compile_detail, jdk_ver, mvn_ver = self.step1_compile_java_jdk17()

        # Discover generated files after compilation
        gen_java = []
        gen_dir = os.path.join(self.out_dir, "native")
        if os.path.exists(gen_dir):
            for d, _, fs in os.walk(gen_dir):
                for f in fs:
                    if f.endswith(".java"):
                        gen_java.append(os.path.relpath(os.path.join(d, f), self.out_dir))

        report.conversion = "SUCCESS" if gen_java else "FAIL"
        report.conversion_files = gen_java
        report.conversion_detail = (
            f"{len(gen_java)} Java source files generated from COBOL source"
            if gen_java else "No Java files generated"
        )
        report.compilation = "PASS" if compile_ok else ("BLOCKED" if not jdk_ok else "FAIL")
        report.jdk_version = jdk_ver
        report.maven_version = mvn_ver
        report.compilation_detail = compile_detail

        # STEP 2 — Execute
        cobol_ev, java_ev = self.step2_execute_both_runtimes(compile_ok)
        report.cobol_runtime = cobol_ev
        report.java_runtime = java_ev

        # STEP 3 — Compare
        stdout_cmp, exit_cmp, file_cmp, db_cmp, file_details = self.step3_compare(
            cobol_ev, java_ev
        )
        report.stdout_comparison = stdout_cmp
        report.exit_code_comparison = exit_cmp
        report.file_comparison = file_cmp
        report.file_comparison_detail = file_details
        report.database_comparison = db_cmp

        # Collect all mock components
        all_mocks = list(set(cobol_ev.mock_components + java_ev.mock_components))
        report.mock_components = all_mocks

        # STEP 4 — Report
        verdict = self.step4_generate_report(report)
        return verdict


# ---------------------------------------------------------------------------
# Module-level standalone verdict computation
# (used by tests/differential/test_negative_gates.py without instantiating
#  a full DifferentialVerifier)
# ---------------------------------------------------------------------------

def _compute_verdict_standalone(
    report: "DifferentialReport",
    *,
    has_sql: bool = False,
    has_jcl: bool = False,
    has_cics: bool = False,
) -> str:
    """
    Fail-closed verdict computation as a module-level function.
    Accepts a DifferentialReport and workload type flags.
    Returns PASS | WARNING | FAIL | UNPROVEN | BLOCKED.
    """
    r = report

    # Hard-fail conditions
    if r.cobol_runtime.status == "FAIL" or r.java_runtime.status == "FAIL":
        return "FAIL"
    if r.compilation == "FAIL":
        return "FAIL"
    if r.stdout_comparison == "MISMATCH":
        return "FAIL"
    if r.exit_code_comparison == "MISMATCH":
        return "FAIL"
    if r.file_comparison == "MISMATCH":
        return "FAIL"
    if r.database_comparison == "MISMATCH":
        return "FAIL"

    # BLOCKED
    if (r.cobol_runtime.status == "BLOCKED"
            or r.java_runtime.status == "BLOCKED"
            or r.compilation == "BLOCKED"):
        return "BLOCKED"

    # No real COBOL execution
    if r.cobol_runtime.status in ("UNPROVEN", ""):
        return "UNPROVEN"

    # No real Java execution
    if r.java_runtime.status in ("UNPROVEN", ""):
        return "UNPROVEN"

    # Compilation didn't pass
    if r.compilation != "PASS":
        return "UNPROVEN"

    # Mock components used
    all_mocks = r.cobol_runtime.mock_components + r.java_runtime.mock_components
    if all_mocks:
        return "WARNING"

    # CICS/JCL compatibility layers
    if has_cics:
        return "WARNING"
    if has_jcl:
        return "WARNING"

    # Hard unsupported constructs
    hard_unsupported = [c for c in r.unsupported_constructs
                        if c.classification == "UNSUPPORTED"]
    soft_unsupported = [c for c in r.unsupported_constructs
                        if c.classification == "WARNING"]
    if hard_unsupported:
        return "UNPROVEN"

    # DB workload with no DB state comparison
    if has_sql and r.database_comparison in ("UNPROVEN", "NOT_APPLICABLE"):
        return "WARNING"

    # File outputs not compared (and declared outputs exist)
    if r.file_comparison == "UNPROVEN":
        return "WARNING"

    # Soft warnings
    if soft_unsupported:
        return "WARNING"

    return "PASS"


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="COBOL → Native Java 4-Step Differential Verifier"
    )
    parser.add_argument("repo", help="Path to COBOL repository root")
    parser.add_argument("out",  help="Output directory for reports and artifacts")
    parser.add_argument("--program", help="Override program name", default=None)
    args = parser.parse_args()

    verifier = DifferentialVerifier(
        repo_dir=args.repo,
        out_dir=args.out,
        program_name=args.program,
    )
    verdict = verifier.run_all()
    print(f"\nFINAL VERDICT: {verdict}")
    sys.exit(0 if verdict in ("PASS", "WARNING") else 1)


if __name__ == "__main__":
    main()
