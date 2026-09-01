import hashlib
import os
import re
import shutil
import tempfile
import subprocess
import pytest
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# Environment defaults
PARITY_RUNTIME = os.environ.get("PARITY_RUNTIME", "docker")
PARITY_JAVA_RUNTIME = os.environ.get("PARITY_JAVA_RUNTIME", "docker")
PARITY_GNUCOBOL_IMAGE = os.environ.get("PARITY_GNUCOBOL_IMAGE", "gnucobol-ocesql:latest")
PARITY_JDK_IMAGE = os.environ.get("PARITY_JDK_IMAGE", "eclipse-temurin:17-jdk-noble")
PARITY_ALLOW_SKIP = os.environ.get("PARITY_ALLOW_SKIP", "false").lower() == "true"
PARITY_KEEP_ARTIFACTS_ON_FAILURE = os.environ.get("PARITY_KEEP_ARTIFACTS_ON_FAILURE", "true").lower() == "true"
PARITY_ARTIFACT_DIR = os.environ.get("PARITY_ARTIFACT_DIR", "artifacts/parity-failures")

@dataclass
class ParityFixture:
    name: str
    program_name: str
    cobol_code: str
    input_files: Dict[str, bytes] = field(default_factory=dict)
    stdin_bytes: bytes = b""
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    declared_outputs: List[str] = field(default_factory=list)  # Output files to verify

@dataclass
class ExecutionResult:
    rc: int
    stdout: bytes
    stderr: bytes
    files: Dict[str, bytes] = field(default_factory=dict)
    duration_seconds: float = 0.0
    termination_status: str = "normal"  # "normal" | "timeout" | "nonzero_exit" | "error"
    error_message: str = ""
    # Phase A4 extensions
    file_hashes: Dict[str, str] = field(default_factory=dict)     # SHA-256 hex per output file
    file_sizes: Dict[str, int] = field(default_factory=dict)      # byte length per output file
    record_counts: Dict[str, int] = field(default_factory=dict)   # fixed-length record count (populated by caller)
    diagnostics: List[dict] = field(default_factory=list)         # structured diagnostic entries

@dataclass
class ParityMismatch:
    target: str  # "exit_code" | "stdout" | "stderr" | "file:<filename>"
    offset: int = -1
    cobol_val: bytes = b""
    java_val: bytes = b""
    cobol_hex: str = ""
    java_hex: str = ""
    explanation: str = ""
    # Phase A4 extensions
    record_number: int = -1      # 1-based record index for fixed-length files
    field_name: str = ""         # COBOL field name where mismatch occurred (if known)
    byte_offset: int = -1        # absolute byte offset within the record
    cobol_decoded: str = ""      # human-readable decoded COBOL value
    java_decoded: str = ""       # human-readable decoded Java value
    likely_cause: str = ""       # e.g. "COMP-3 encoding differs", "trailing space handling"
    relevant_paragraph: str = "" # COBOL paragraph or section name (if known)

@dataclass
class ParityComparison:
    status: str  # "PASS" | "FAIL" | "SKIP"
    mismatches: List[ParityMismatch] = field(default_factory=list)
    skip_reason: str = ""


# ---------------------------------------------------------------------------
# Phase A4: normalize_stderr — strip non-observable GnuCOBOL boilerplate
# ---------------------------------------------------------------------------

_GNUCOBOL_NOISE_PATTERNS = [
    re.compile(rb"^GnuCOBOL \d+\.\d+\.\d+.*$", re.MULTILINE),
    re.compile(rb"^cobc \(GnuCOBOL\).*$", re.MULTILINE),
    re.compile(rb"^\s*libcob .*$", re.MULTILINE),
    re.compile(rb"^\s*Build.*from.*$", re.MULTILINE),
    re.compile(rb"^\s*Packaged.*$", re.MULTILINE),
    re.compile(rb"^\s*C version.*$", re.MULTILINE),
    re.compile(rb"^\s*$", re.MULTILINE),  # blank lines
]


def normalize_stderr(b: bytes) -> bytes:
    """Strip GnuCOBOL version headers, timing, and blank lines from stderr
    before byte-exact comparison so only semantically observable lines differ.
    """
    for pat in _GNUCOBOL_NOISE_PATTERNS:
        b = pat.sub(b"", b)
    # Collapse consecutive newlines
    b = re.sub(rb"\n{2,}", b"\n", b)
    return b.strip()


# ---------------------------------------------------------------------------
# Phase 2 Task 3: normalize_display — strip cosmetic display spacing
# ---------------------------------------------------------------------------


def normalize_display(b: bytes) -> bytes:
    """Normalize display stdout bytes:
    1. Replace Windows CRLF with LF.
    2. Collapse multiple consecutive spaces to a single space.
    3. Trim leading/trailing whitespace from each line.
    4. Ignore empty lines at start/end.
    """
    if not b:
        return b""
    text = b.decode("utf-8", errors="replace")
    text = text.replace("\r\n", "\n")
    lines = []
    for line in text.split("\n"):
        line = line.strip()
        if line:
            # Collapse multiple spaces into one space
            line = re.sub(r" {2,}", " ", line)
            lines.append(line)
    return "\n".join(lines).encode("utf-8")


# ---------------------------------------------------------------------------
# Phase A4: compare_fixed_records — record-by-record binary comparison
# ---------------------------------------------------------------------------


def compare_fixed_records(
    target: str,
    record_len: int,
    cobol_bytes: bytes,
    java_bytes: bytes,
) -> List[ParityMismatch]:
    """Compare two fixed-length record files byte-by-byte, record-by-record.

    Returns a list of ParityMismatch objects — one per differing record.
    Each mismatch includes the record number, first differing byte offset,
    and hex context around the difference.
    """
    mismatches: List[ParityMismatch] = []

    if record_len <= 0:
        # Fall back to whole-file comparison
        m = compare_raw_bytes(target, cobol_bytes, java_bytes)
        return [m] if m else []

    cobol_records = [
        cobol_bytes[i: i + record_len]
        for i in range(0, len(cobol_bytes), record_len)
        if cobol_bytes[i: i + record_len]
    ]
    java_records = [
        java_bytes[i: i + record_len]
        for i in range(0, len(java_bytes), record_len)
        if java_bytes[i: i + record_len]
    ]

    max_records = max(len(cobol_records), len(java_records))
    for rec_idx in range(max_records):
        c_rec = cobol_records[rec_idx] if rec_idx < len(cobol_records) else b""
        j_rec = java_records[rec_idx] if rec_idx < len(java_records) else b""

        if c_rec == j_rec:
            continue

        # Find first differing byte within the record
        first_diff = 0
        for bi in range(min(len(c_rec), len(j_rec))):
            if c_rec[bi] != j_rec[bi]:
                first_diff = bi
                break
        else:
            first_diff = min(len(c_rec), len(j_rec))

        ctx_start = max(0, first_diff - 4)
        ctx_end_c = min(len(c_rec), first_diff + 8)
        ctx_end_j = min(len(j_rec), first_diff + 8)
        c_slice = c_rec[ctx_start:ctx_end_c]
        j_slice = j_rec[ctx_start:ctx_end_j]

        mismatches.append(
            ParityMismatch(
                target=target,
                offset=rec_idx * record_len + first_diff,
                cobol_val=c_slice,
                java_val=j_slice,
                cobol_hex=c_slice.hex(" "),
                java_hex=j_slice.hex(" "),
                explanation=(
                    f"Record {rec_idx + 1} differs at byte {first_diff} within record. "
                    f"COBOL record length: {len(c_rec)}, Java record length: {len(j_rec)}"
                ),
                record_number=rec_idx + 1,
                byte_offset=first_diff,
                likely_cause="Fixed-length record content mismatch — check COMP-3 encoding, sign handling, or trailing-space padding",
            )
        )

    return mismatches

def run_cmd_bytes(cmd: List[str], stdin_bytes: bytes = None, timeout: int = 120) -> Tuple[int, bytes, bytes, str]:
    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE if stdin_bytes is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = proc.communicate(input=stdin_bytes, timeout=timeout)
        term = "normal"
        if proc.returncode != 0:
            term = "nonzero_exit"
        return proc.returncode, stdout, stderr, term
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate()
        return -1, stdout, stderr, "timeout"
    except Exception as e:
        return -2, b"", str(e).encode("utf-8"), "error"

def check_docker_available() -> bool:
    try:
        res = subprocess.run(["docker", "info"], capture_output=True, timeout=10)
        return res.returncode == 0
    except Exception:
        return False

def check_docker_image_cached(image: str) -> bool:
    try:
        res = subprocess.run(["docker", "images", "-q", image], capture_output=True, text=True, timeout=10)
        return bool(res.stdout.strip())
    except Exception:
        return False

def preprocess_ocesql_source(cobol_code: str) -> str:
    lines = cobol_code.splitlines()
    new_lines = []
    in_sqlca_vars = False
    in_working_storage = False
    has_declare_section = False
    has_sqlca_copy = False
    
    for line in lines:
        upper_line = line.upper()
        
        # Detect working storage section
        if "WORKING-STORAGE SECTION" in upper_line:
            in_working_storage = True
            new_lines.append(line)
            # Inject DECLARE SECTION for connection parameters
            if not has_declare_section:
                new_lines.append("       EXEC SQL BEGIN DECLARE SECTION END-EXEC.")
                new_lines.append("       01  DBNAME PIC X(30) VALUE \"modernization_db\".")
                new_lines.append("       01  USERNAME PIC X(30) VALUE \"modernize\".")
                new_lines.append("       01  PASSWD PIC X(30) VALUE \"modernize\".")
                new_lines.append("       EXEC SQL END DECLARE SECTION END-EXEC.")
                has_declare_section = True
            continue
            
        # Strip manual SQLCODE/SQLSTATE if present, replacing with sqlca copybook
        if "SQLCA-VARIABLES" in upper_line or "SQLCA_VARIABLES" in upper_line:
            if not has_sqlca_copy:
                new_lines.append('            COPY "sqlca.cbl".')
                has_sqlca_copy = True
            in_sqlca_vars = True
            continue
            
        # Also catch standalone SQLCODE / SQLSTATE declarations
        if in_working_storage and ("01 SQLCODE" in upper_line or "01  SQLCODE" in upper_line or "05 SQLCODE" in upper_line or "05  SQLCODE" in upper_line or "01 SQLSTATE" in upper_line or "01  SQLSTATE" in upper_line or "05 SQLSTATE" in upper_line or "05  SQLSTATE" in upper_line):
            if not has_sqlca_copy:
                new_lines.append('            COPY "sqlca.cbl".')
                has_sqlca_copy = True
            continue
            
        if in_sqlca_vars:
            if "EXEC SQL" in upper_line:
                in_sqlca_vars = False
            # We skip SQLCODE and SQLSTATE declarations under the manual SQLCA group
            elif "05" in line and ("SQLCODE" in upper_line or "SQLSTATE" in upper_line):
                continue
            elif "01" in line or "PROCEDURE DIVISION" in upper_line:
                in_sqlca_vars = False
            else:
                continue
                
        # Remove COMP, COMP-5, BINARY usage clauses in host variables
        # Since ocesql precompiler has a strict limitation (only supports DISPLAY/COMP-3)
        if in_working_storage and not ("PROCEDURE DIVISION" in upper_line):
            # Check if this line declares variables
            # Replace USAGE COMP, USAGE COMP-5, COMP, COMP-5, BINARY
            line = re.sub(r'\bUSAGE\s+COMP-5\b', '', line, flags=re.IGNORECASE)
            line = re.sub(r'\bUSAGE\s+COMP\b', '', line, flags=re.IGNORECASE)
            line = re.sub(r'\bUSAGE\s+BINARY\b', '', line, flags=re.IGNORECASE)
            line = re.sub(r'\bCOMP-5\b', '', line, flags=re.IGNORECASE)
            line = re.sub(r'\bCOMP\b', '', line, flags=re.IGNORECASE)
            line = re.sub(r'\bBINARY\b', '', line, flags=re.IGNORECASE)
            
        new_lines.append(line)
        
        # Inject CONNECT statement at the start of PROCEDURE DIVISION
        if "PROCEDURE DIVISION" in upper_line:
            new_lines.append("            EXEC SQL")
            new_lines.append("                CONNECT :USERNAME IDENTIFIED BY :PASSWD USING :DBNAME")
            new_lines.append("            END-EXEC.")
            
    return "\n".join(new_lines)

def run_cobol_baseline(fixture: ParityFixture, run_dir: str) -> ExecutionResult:
    # Check if this contains EXEC SQL
    has_sql = "EXEC SQL" in fixture.cobol_code
    
    # Preprocess if SQL is present
    if has_sql:
        preprocessed_code = preprocess_ocesql_source(fixture.cobol_code)
        # Log to target/ocesql_transformed.cob or similar
        os.makedirs(os.path.join(run_dir, "target"), exist_ok=True)
        with open(os.path.join(run_dir, "target", "ocesql_transformed.cob"), "wb") as f:
            f.write(preprocessed_code.encode("utf-8"))
        src_file = os.path.join(run_dir, "src_preprocessed.cob")
        with open(src_file, "wb") as f:
            f.write(preprocessed_code.encode("utf-8"))
    else:
        src_file = os.path.join(run_dir, f"{fixture.program_name}.cob")
        with open(src_file, "wb") as f:
            f.write(fixture.cobol_code.encode("utf-8"))

    if PARITY_RUNTIME == "local":
        # Local fallback execution
        compile_cmd = ["cobc", "-x", "-std=default", "-fsign=ASCII", "-o", os.path.join(run_dir, "prog.exe"), src_file]
        rc, out, err, term = run_cmd_bytes(compile_cmd)
        if rc != 0:
            return ExecutionResult(rc, out, err, termination_status="error", error_message=f"GnuCOBOL compilation failed: {err.decode('utf-8', errors='replace')}")
        
        run_cmd = [os.path.join(run_dir, "prog.exe")] + fixture.args
        rc, out, err, term = run_cmd_bytes(run_cmd, stdin_bytes=fixture.stdin_bytes)
        
        # Read output files
        outputs = {}
        hashes = {}
        sizes = {}
        for f_name in fixture.declared_outputs:
            p_path = os.path.join(run_dir, f_name)
            if os.path.exists(p_path):
                with open(p_path, "rb") as f:
                    data = f.read()
                outputs[f_name] = data
                hashes[f_name] = hashlib.sha256(data).hexdigest()
                sizes[f_name] = len(data)
            else:
                outputs[f_name] = b""
                hashes[f_name] = ""
                sizes[f_name] = 0
        return ExecutionResult(rc, out, err, files=outputs, termination_status=term,
                               file_hashes=hashes, file_sizes=sizes)
        
    else:
        # Docker canonical runtime execution
        if not check_docker_available():
            raise RuntimeError("Docker is not running, but PARITY_RUNTIME=docker is canonical.")
        if not check_docker_image_cached(PARITY_GNUCOBOL_IMAGE):
            raise RuntimeError(f"Required Docker image {PARITY_GNUCOBOL_IMAGE} is not cached.")

        # Mount run_dir to /run
        run_dir_abs = os.path.abspath(run_dir).replace("\\", "/")
        net_name = "modernization-platform_default"
        
        # Connectivity Smoke Test if SQL is present
        if has_sql:
            cmd_ping = [
                "docker", "run", "--rm", "--network", net_name,
                "-e", "PGPASSWORD=modernize",
                PARITY_GNUCOBOL_IMAGE,
                "psql", "-h", "db", "-U", "modernize", "-d", "modernization_db", "-c", "SELECT 1;"
            ]
            ping_rc, ping_out, ping_err, ping_term = run_cmd_bytes(cmd_ping)
            if ping_rc != 0:
                raise RuntimeError(
                    f"PostgreSQL connectivity check failed on host=db port=5432. "
                    f"Ensure db container is up and network={net_name}. Error: {ping_err.decode('utf-8', errors='replace')}"
                )

        if has_sql:
            # 1. Run ocesql dry-run precompile step
            precompile_cmd = [
                "docker", "run", "--rm",
                "-v", f"{run_dir_abs}:/run",
                PARITY_GNUCOBOL_IMAGE,
                "ocesql", "/run/src_preprocessed.cob", "/run/src_precompiled.cob"
            ]
            prc, pout, perr, pterm = run_cmd_bytes(precompile_cmd)
            if prc != 0:
                err_msg = perr.decode('utf-8', errors='replace') + "\n" + pout.decode('utf-8', errors='replace')
                return ExecutionResult(
                    prc, pout, perr, termination_status="error",
                    error_message=f"ocesql precompile failed: {err_msg}. Check host variable types, SQLCA, and CONNECT injection."
                )

            # 2. Compile precompiled COBOL inside GnuCOBOL-ocesql container
            inner_compile = (
                "cobc -x -std=default -fsign=ASCII -o /run/prog.exe /run/src_precompiled.cob "
                "-I/usr/share/open-cobol-esql/copy -locesql"
            )
        else:
            # Normal compilation
            inner_compile = f"cobc -x -std=default -fsign=ASCII -o /run/prog.exe /run/{fixture.program_name}.cob"

        compile_cmd = [
            "docker", "run", "--rm",
            "-v", f"{run_dir_abs}:/run",
            "-w", "/run",
            PARITY_GNUCOBOL_IMAGE,
            "sh", "-c", inner_compile
        ]
        rc, out, err, term = run_cmd_bytes(compile_cmd)
        if rc != 0:
            return ExecutionResult(rc, out, err, termination_status="error", error_message=f"Docker GnuCOBOL compilation failed: {err.decode('utf-8', errors='replace')}")

        # Stdin redirect inside docker execution
        with open(os.path.join(run_dir, "stdin.txt"), "wb") as f:
            f.write(fixture.stdin_bytes)

        inner_run = f"/run/prog.exe < /run/stdin.txt"
        
        # Docker run parameters
        run_cmd_params = [
            "docker", "run", "--rm",
            "-v", f"{run_dir_abs}:/run",
            "-w", "/run"
        ]
        
        # If SQL is present, set network and environment variables
        if has_sql:
            run_cmd_params.extend([
                "--network", net_name,
                "-e", "PGHOST=db",
                "-e", "PGPORT=5432",
                "-e", "PGUSER=modernize",
                "-e", "PGPASSWORD=modernize",
                "-e", "PGDATABASE=modernization_db",
                "-e", "COB_PRE_LOAD=/usr/lib/libocesql.so"
            ])
            
        run_cmd_params.extend([
            PARITY_GNUCOBOL_IMAGE,
            "sh", "-c", inner_run
        ])
        
        rc, out, err, term = run_cmd_bytes(run_cmd_params)

        # Read output files
        outputs = {}
        hashes = {}
        sizes = {}
        for f_name in fixture.declared_outputs:
            p_path = os.path.join(run_dir, f_name)
            if os.path.exists(p_path):
                with open(p_path, "rb") as f:
                    data = f.read()
                outputs[f_name] = data
                hashes[f_name] = hashlib.sha256(data).hexdigest()
                sizes[f_name] = len(data)
            else:
                outputs[f_name] = b""
                hashes[f_name] = ""
                sizes[f_name] = 0
        return ExecutionResult(rc, out, err, files=outputs, termination_status=term,
                               file_hashes=hashes, file_sizes=sizes)

def run_java_transpiled(fixture: ParityFixture, run_dir: str) -> ExecutionResult:
    # 1. Transpile COBOL source to Java source
    from modernize.lexer import CobolLexer
    from modernize.parser import CobolParser
    from modernize.native_generator import NativeProgramGenerator

    filename = f"{fixture.program_name}.cob"
    lexer = CobolLexer(filename)
    tokens = lexer.tokenize(fixture.cobol_code)
    parser = CobolParser(tokens, filename)
    ir = parser.parse()

    gen = NativeProgramGenerator(fixture.program_name, list(ir.nodes.values()))
    all_generators = {fixture.program_name.upper(): gen}
    def register_child_generators(g):
        for c_name, c_gen in g.child_generators.items():
            all_generators[c_name.upper()] = c_gen
            register_child_generators(c_gen)
    register_child_generators(gen)
    java_source = gen.generate_class_source(all_generators)

    # 2. Write Java source files and runtime helper dependencies to run_dir
    pkg_dir = os.path.join(run_dir, "com", "systema", "modernized", "native_gen")
    os.makedirs(pkg_dir, exist_ok=True)
    
    # Adjust assignments in generated Java to refer to absolute paths in temporary workspace
    adjusted_java_source = java_source
    if hasattr(gen, "file_assigns") and gen.file_assigns:
        for assign in gen.file_assigns:
            k = assign.get("physical_path") or assign.get("assign_path")
            if k:
                if PARITY_JAVA_RUNTIME == "docker":
                    target_path = f"/run/{k}"
                else:
                    target_path = os.path.abspath(os.path.join(run_dir, k)).replace("\\", "/")
                adjusted_java_source = adjusted_java_source.replace(f'"{k}"', f'"{target_path}"')

    src_file_path = os.path.join(pkg_dir, f"{fixture.program_name.capitalize()}.java")
    with open(src_file_path, "w", encoding="utf-8") as f:
        f.write(adjusted_java_source)

    jcl_context_dir = os.path.join(run_dir, "com", "systema", "modernized")
    os.makedirs(jcl_context_dir, exist_ok=True)

    # Generate mock SQL assets if mock_db.yaml exists in the repository
    repo_name = fixture.program_name
    repo_paths = [
        os.path.join("tests", "repos", repo_name),
        os.path.join("tests", "repos", repo_name.upper())
    ]
    repo_path = None
    for rp in repo_paths:
        if os.path.exists(rp):
            repo_path = rp
            break
    if repo_path:
        mock_db_yaml = os.path.join(repo_path, "mock_db.yaml")
        if os.path.exists(mock_db_yaml):
            import shutil
            from modernize.mock_sql_service import generate_mock_sql_assets
            generate_mock_sql_assets(mock_db_yaml, run_dir, run_dir)
            src_mss = os.path.join(run_dir, "src", "main", "java", "com", "systema", "modernized", "MockSqlService.java")
            if os.path.exists(src_mss):
                shutil.copy2(src_mss, os.path.join(jcl_context_dir, "MockSqlService.java"))

    # Write JclExecutionContext, CobolFormatHelper, CicsProgramRegistry, SpringContextHelper
    with open(os.path.join(jcl_context_dir, "JclExecutionContext.java"), "w", encoding="utf-8") as f:
        f.write("""package com.systema.modernized;
import java.util.HashMap;
import java.util.Map;
public class JclExecutionContext {
    private static final ThreadLocal<Map<String, String>> ddAssignments = ThreadLocal.withInitial(HashMap::new);
    private static final ThreadLocal<Map<String, String>> sysinData = ThreadLocal.withInitial(HashMap::new);
    private static final ThreadLocal<Map<String, Integer>> stepReturnCodes = ThreadLocal.withInitial(HashMap::new);
    public static void setDdAssignment(String ddName, String physicalPath) { ddAssignments.get().put(ddName.toUpperCase(), physicalPath); }
    public static String getDdAssignment(String ddName) { return ddAssignments.get().get(ddName.toUpperCase()); }
    public static void setSysinData(String ddName, String data) { sysinData.get().put(ddName.toUpperCase(), data); }
    public static String getSysinData(String ddName) { return sysinData.get().get(ddName.toUpperCase()); }
    public static void setStepReturnCode(String stepName, int rc) { stepReturnCodes.get().put(stepName.toUpperCase(), rc); }
    public static Integer getStepReturnCode(String stepName) { return stepReturnCodes.get().getOrDefault(stepName.toUpperCase(), 0); }
    public static boolean checkAnyStepCond(int code, String op) { return false; }
    public static boolean compareRc(int code, String op, int rc) { return false; }
    public static void clear() { ddAssignments.get().clear(); sysinData.get().clear(); stepReturnCodes.get().clear(); }
}""")

    with open(os.path.join(jcl_context_dir, "CicsProgramRegistry.java"), "w", encoding="utf-8") as f:
        f.write("""package com.systema.modernized;
public class CicsProgramRegistry {
    public static void register(String name, java.util.function.Supplier<Object> supplier) {}
    public static Object invoke(String name, String commarea) throws Exception { return commarea; }
}""")

    with open(os.path.join(jcl_context_dir, "SpringContextHelper.java"), "w", encoding="utf-8") as f:
        f.write("""package com.systema.modernized;
public class SpringContextHelper {
    public static class MockResultSet {
        public String getString(String c) { return null; }
        public String getString(int idx) { return null; }
        public int getInt(String c) { return 0; }
        public int getInt(int idx) { return 0; }
    }
    @FunctionalInterface
    public interface MockRowMapper<T> { T mapRow(MockResultSet rs, int r) throws Exception; }
    public static class MockJdbcTemplate {
        public void execute(String sql) {}
        public int update(String sql, Object... args) { return 0; }
        public <T> java.util.List<T> query(String sql, MockRowMapper<T> rowMapper, Object... args) { return new java.util.ArrayList<>(); }
        public <T> T queryForObject(String sql, Class<T> requiredType, Object... args) { return null; }
    }
    public static MockJdbcTemplate jdbcTemplate = null;
}""")

    # Copy stable format and numeric runtime helpers
    helpers_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    format_helper_src = open(os.path.join(helpers_dir, "modernize", "java_helpers", "CobolFormatHelper.java"), "r", encoding="utf-8").read()
    with open(os.path.join(jcl_context_dir, "CobolFormatHelper.java"), "w", encoding="utf-8") as f:
        f.write(format_helper_src)

    runtime_dir = os.path.join(jcl_context_dir, "runtime")
    os.makedirs(runtime_dir, exist_ok=True)
    helpers_src_dir = os.path.join(helpers_dir, "modernize", "java_helpers", "src", "main", "java", "com", "systema", "modernized", "runtime")
    for f_name in os.listdir(helpers_src_dir):
        if f_name.endswith(".java"):
            if f_name == "VsamIndexedStore.java":
                continue
            src = open(os.path.join(helpers_src_dir, f_name), "r", encoding="utf-8").read()
            with open(os.path.join(runtime_dir, f_name), "w", encoding="utf-8") as f:
                f.write(src)

    if PARITY_JAVA_RUNTIME == "local":
        # Compile Java sources locally
        java_files = [os.path.join(runtime_dir, f) for f in os.listdir(runtime_dir) if f.endswith(".java")]
        compile_cmd = [
            "javac", "-cp", run_dir,
            os.path.join(jcl_context_dir, "JclExecutionContext.java"),
            os.path.join(jcl_context_dir, "CicsProgramRegistry.java"),
            os.path.join(jcl_context_dir, "SpringContextHelper.java"),
            os.path.join(jcl_context_dir, "CobolFormatHelper.java")
        ] + java_files + [src_file_path]
        rc, out, err, term = run_cmd_bytes(compile_cmd)
        if rc != 0:
            return ExecutionResult(rc, out, err, termination_status="error", error_message=f"Java compilation failed: {err.decode('utf-8', errors='replace')}")

        run_cmd = ["java", "-cp", run_dir, f"com.systema.modernized.native_gen.{fixture.program_name.capitalize()}"]
        rc, out, err, term = run_cmd_bytes(run_cmd, stdin_bytes=fixture.stdin_bytes)

        # Read output files
        outputs = {}
        hashes = {}
        sizes = {}
        for f_name in fixture.declared_outputs:
            p_path = os.path.join(run_dir, f_name)
            if os.path.exists(p_path):
                with open(p_path, "rb") as f:
                    data = f.read()
                outputs[f_name] = data
                hashes[f_name] = hashlib.sha256(data).hexdigest()
                sizes[f_name] = len(data)
            else:
                outputs[f_name] = b""
                hashes[f_name] = ""
                sizes[f_name] = 0
        return ExecutionResult(rc, out, err, files=outputs, termination_status=term,
                               file_hashes=hashes, file_sizes=sizes)

    else:
        # Docker Temurin canonical runtimes execution
        if not check_docker_available():
            raise RuntimeError("Docker is not running, but PARITY_JAVA_RUNTIME=docker is canonical.")
        if not check_docker_image_cached(PARITY_JDK_IMAGE):
            raise RuntimeError(f"Required Docker image {PARITY_JDK_IMAGE} is not cached.")

        run_dir_abs = os.path.abspath(run_dir).replace("\\", "/")

        # Compile inside Docker
        inner_compile = (
            "javac -cp /run "
            "/run/com/systema/modernized/JclExecutionContext.java "
            "/run/com/systema/modernized/CicsProgramRegistry.java "
            "/run/com/systema/modernized/SpringContextHelper.java "
            "/run/com/systema/modernized/CobolFormatHelper.java "
            "/run/com/systema/modernized/runtime/*.java "
            f"/run/com/systema/modernized/native_gen/{fixture.program_name.capitalize()}.java"
        )
        compile_cmd = [
            "docker", "run", "--rm",
            "-v", f"{run_dir_abs}:/run",
            "-w", "/run",
            PARITY_JDK_IMAGE,
            "sh", "-c", inner_compile
        ]
        rc, out, err, term = run_cmd_bytes(compile_cmd)
        if rc != 0:
            return ExecutionResult(rc, out, err, termination_status="error", error_message=f"Docker Java compilation failed: {err.decode('utf-8', errors='replace')}")

        # Stdin redirect inside docker
        with open(os.path.join(run_dir, "stdin.txt"), "wb") as f:
            f.write(fixture.stdin_bytes)

        inner_run = f"java -cp /run com.systema.modernized.native_gen.{fixture.program_name.capitalize()} < /run/stdin.txt"
        run_cmd = [
            "docker", "run", "--rm",
            "-v", f"{run_dir_abs}:/run",
            "-w", "/run",
            PARITY_JDK_IMAGE,
            "sh", "-c", inner_run
        ]
        rc, out, err, term = run_cmd_bytes(run_cmd)

        # Read output files
        outputs = {}
        hashes = {}
        sizes = {}
        for f_name in fixture.declared_outputs:
            p_path = os.path.join(run_dir, f_name)
            if os.path.exists(p_path):
                with open(p_path, "rb") as f:
                    data = f.read()
                outputs[f_name] = data
                hashes[f_name] = hashlib.sha256(data).hexdigest()
                sizes[f_name] = len(data)
            else:
                outputs[f_name] = b""
                hashes[f_name] = ""
                sizes[f_name] = 0
        return ExecutionResult(rc, out, err, files=outputs, termination_status=term,
                               file_hashes=hashes, file_sizes=sizes)

def compare_raw_bytes(target: str, cobol_bytes: bytes, java_bytes: bytes) -> ParityMismatch:
    if cobol_bytes == java_bytes:
        return None

    # Find first different byte offset
    offset = 0
    min_len = min(len(cobol_bytes), len(java_bytes))
    while offset < min_len and cobol_bytes[offset] == java_bytes[offset]:
        offset += 1

    # Hex rendering
    c_slice = cobol_bytes[max(0, offset - 8):min(len(cobol_bytes), offset + 8)]
    j_slice = java_bytes[max(0, offset - 8):min(len(java_bytes), offset + 8)]
    
    cobol_hex = c_slice.hex(" ")
    java_hex = j_slice.hex(" ")
    
    return ParityMismatch(
        target=target,
        offset=offset,
        cobol_val=c_slice,
        java_val=j_slice,
        cobol_hex=cobol_hex,
        java_hex=java_hex,
        explanation=f"Mismatch on target {target} at byte offset {offset}. COBOL length: {len(cobol_bytes)}, Java length: {len(java_bytes)}"
    )

def run_parity(fixture: ParityFixture) -> ParityComparison:
    # 1. Environment pre-validation
    docker_ok = check_docker_available()
    image_cobol_ok = check_docker_image_cached(PARITY_GNUCOBOL_IMAGE) if docker_ok else False
    image_java_ok = check_docker_image_cached(PARITY_JDK_IMAGE) if docker_ok else False

    if PARITY_RUNTIME == "docker" or PARITY_JAVA_RUNTIME == "docker":
        if not docker_ok or not image_cobol_ok or not image_java_ok:
            if PARITY_ALLOW_SKIP:
                return ParityComparison(status="SKIP", skip_reason="Docker or required parity images not available on host.")
            else:
                mismatch = ParityMismatch(
                    target="setup",
                    explanation=f"CI Failure: Docker parity images not found. Docker status: {docker_ok}, COBOL image cached: {image_cobol_ok}, JDK image cached: {image_java_ok}"
                )
                return ParityComparison(status="FAIL", mismatches=[mismatch])

    temp_root = tempfile.mkdtemp(prefix=f"parity_{fixture.name}_")
    cobol_run_dir = os.path.join(temp_root, "cobol-run")
    java_run_dir = os.path.join(temp_root, "java-run")
    
    os.makedirs(cobol_run_dir, exist_ok=True)
    os.makedirs(java_run_dir, exist_ok=True)

    # Copy identical inputs to each isolated directory
    if fixture.input_files:
        for k, v in fixture.input_files.items():
            for d in (cobol_run_dir, java_run_dir):
                p = os.path.join(d, k)
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "wb") as f:
                    f.write(v)

    # 2. Run GnuCOBOL baseline
    cobol_res = run_cobol_baseline(fixture, cobol_run_dir)
    if cobol_res.termination_status == "error":
        shutil.rmtree(temp_root, ignore_errors=True)
        mismatch = ParityMismatch(target="cobol_compilation", explanation=cobol_res.error_message)
        return ParityComparison(status="FAIL", mismatches=[mismatch])

    # 3. Run generated Java class
    java_res = run_java_transpiled(fixture, java_run_dir)
    if java_res.termination_status == "error":
        # Keep compile diagnostics
        if PARITY_KEEP_ARTIFACTS_ON_FAILURE:
            fail_dir = os.path.join(PARITY_ARTIFACT_DIR, fixture.name)
            shutil.rmtree(fail_dir, ignore_errors=True)
            shutil.copytree(temp_root, fail_dir, dirs_exist_ok=True)
        shutil.rmtree(temp_root, ignore_errors=True)
        mismatch = ParityMismatch(target="java_compilation", explanation=java_res.error_message)
        return ParityComparison(status="FAIL", mismatches=[mismatch])

    # 4. Compare exit status, stdout, stderr, and declared outputs
    mismatches = []
    
    # Exit code
    if cobol_res.rc != java_res.rc:
        mismatches.append(ParityMismatch(
            target="exit_code",
            explanation=f"COBOL exit code: {cobol_res.rc}, Java exit code: {java_res.rc}"
        ))

    # Stdout comparison (raw bytes with display normalization)
    m_stdout = compare_raw_bytes(
        "stdout",
        normalize_display(cobol_res.stdout),
        normalize_display(java_res.stdout)
    )
    if m_stdout:
        mismatches.append(m_stdout)
        
    # Stderr comparison — normalize before comparing to strip GnuCOBOL boilerplate
    m_stderr = compare_raw_bytes(
        "stderr",
        normalize_stderr(cobol_res.stderr),
        normalize_stderr(java_res.stderr),
    )
    if m_stderr:
        mismatches.append(m_stderr)

    # Output files comparison
    for f_name in fixture.declared_outputs:
        c_bytes = cobol_res.files.get(f_name, b"")
        j_bytes = java_res.files.get(f_name, b"")
        m_file = compare_raw_bytes(f"file:{f_name}", c_bytes, j_bytes)
        if m_file:
            mismatches.append(m_file)

    # 5. Clean up or retain temporary directories
    if mismatches:
        if PARITY_KEEP_ARTIFACTS_ON_FAILURE:
            fail_dir = os.path.join(PARITY_ARTIFACT_DIR, fixture.name)
            shutil.rmtree(fail_dir, ignore_errors=True)
            shutil.copytree(temp_root, fail_dir, dirs_exist_ok=True)
        shutil.rmtree(temp_root, ignore_errors=True)
        return ParityComparison(status="FAIL", mismatches=mismatches)

    shutil.rmtree(temp_root, ignore_errors=True)
    return ParityComparison(status="PASS")
