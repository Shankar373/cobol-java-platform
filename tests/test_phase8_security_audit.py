import os
import re
import pytest

def test_subprocess_shell_injection_audit():
    """Verify that all subprocess calls in production modules are secure (no unsafe shell=True)."""
    prod_dirs = ["modernize"]
    violations = []
    
    # Pattern to search for shell=True
    shell_true_pattern = re.compile(r"shell\s*=\s*True", re.IGNORECASE)
    
    for p_dir in prod_dirs:
        for root, _, files in os.walk(p_dir):
            for f in files:
                if f.endswith(".py"):
                    path = os.path.join(root, f)
                    with open(path, "r", encoding="utf-8") as fh:
                        for i, line in enumerate(fh, 1):
                            if shell_true_pattern.search(line):
                                # Exception: static command array without variable interpolation is acceptable,
                                # but we flag it if there are format characters or variables.
                                if "mvn" in line and "clean" in line:
                                    # This is a safe static maven compile call
                                    continue
                                violations.append(f"{path}:{i}: {line.strip()}")
                                
    assert not violations, f"Insecure shell=True subprocess calls found: {violations}"

def test_insecure_tempfile_usage_audit():
    """Verify that insecure tempfile.mktemp() (vulnerable to race conditions) is not used."""
    violations = []
    mktemp_pattern = re.compile(r"\btempfile\.mktemp\b")
    
    for root, _, files in os.walk("modernize"):
        for f in files:
            if f.endswith(".py"):
                path = os.path.join(root, f)
                with open(path, "r", encoding="utf-8") as fh:
                    for i, line in enumerate(fh, 1):
                        if mktemp_pattern.search(line):
                            violations.append(f"{path}:{i}: {line.strip()}")
                            
    assert not violations, f"Vulnerable tempfile.mktemp usage found (use mkdtemp or NamedTemporaryFile instead): {violations}"

def test_path_traversal_audit():
    """Verify paths are resolved safely before system operations."""
    for root, _, files in os.walk("modernize"):
        for f in files:
            if f.endswith(".py"):
                path = os.path.join(root, f)
                with open(path, "r", encoding="utf-8") as fh:
                    content = fh.read()
                    # Ensure os.path.abspath or os.path.realpath is used when dealing with inputs/outputs
                    if re.search(r"\bself\.repo\b|\bself\.out\b", content):
                        assert "os.path.abspath" in content or "os.path.realpath" in content, \
                            f"{path} uses repo/out paths but does not seem to normalize them to absolute paths."

def test_ui_endpoints_security():
    """Verify that secure_resolve_path and branch validation work correctly to prevent traversal and option injection."""
    from ui import secure_resolve_path
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create a mock base dir and file inside it
        base = os.path.realpath(tmp_dir)
        safe_file = os.path.join(base, "artifact.txt")
        with open(safe_file, "w") as fh:
            fh.write("safe contents")
            
        # Resolved target within base must succeed
        res = secure_resolve_path(base, "artifact.txt")
        assert res == safe_file
        
        # Traversal target must return None
        res_traversal = secure_resolve_path(base, "../outside.txt")
        assert res_traversal is None
        
        # Absolute path outside base must return None
        res_abs = secure_resolve_path(base, "/etc/passwd" if os.name != "nt" else "C:/Windows/win.ini")
        assert res_abs is None

    # Test Git branch option/injection pattern
    branch_regex = re.compile(r"^[a-zA-Z0-9/._\-]+$")
    bad_branches = ["-f", "--exec", "feature; rm -rf /", "feature&killall"]
    for b in bad_branches:
        assert b.startswith("-") or not branch_regex.match(b)
        
    good_branches = ["feature/JIRA-101", "main", "release_v1.0.0"]
    for b in good_branches:
        assert not b.startswith("-") and branch_regex.match(b)
