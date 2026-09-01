import sys
import os
import json
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modernize.native_pipeline import NativePipeline

def test_dependency_gate_clean(tmpdir):
    out_dir = str(tmpdir.mkdir("out"))
    p = NativePipeline("tests/repos/MULTIFILE01", out_dir)
    
    # Create clean directory structure in generated_dir
    os.makedirs(p.src_dir, exist_ok=True)
    with open(os.path.join(p.src_dir, "CleanClass.java"), "w") as fh:
        fh.write("package com.systema.modernized.native_gen;\npublic class CleanClass {}")
        
    try:
        passed = p.stage_dependency_gate()
        assert passed is True
        
        audit_file = os.path.join(out_dir, "generated", "native_java_dependency_audit.json")
        assert os.path.exists(audit_file)
        with open(audit_file, "r") as fh:
            audit = json.load(fh)
            assert audit["native_java_dependency_status"] == "PASS"
            assert audit["native_java"] is True
            assert len(audit["forbidden_dependencies"]) == 0
    finally:
        pass

def test_dependency_gate_forbidden(tmpdir):
    out_dir = str(tmpdir.mkdir("out"))
    p = NativePipeline("tests/repos/MULTIFILE01", out_dir)
    
    # Create dirty directory structure in generated_dir
    os.makedirs(p.src_dir, exist_ok=True)
    with open(os.path.join(p.src_dir, "DirtyClass.java"), "w") as fh:
        fh.write("import jp.osscons.CobolField;\npublic class DirtyClass {}")
        
    try:
        passed = p.stage_dependency_gate()
        assert passed is False
        
        audit_file = os.path.join(out_dir, "generated", "native_java_dependency_audit.json")
        assert os.path.exists(audit_file)
        with open(audit_file, "r") as fh:
            audit = json.load(fh)
            assert audit["native_java_dependency_status"] == "NATIVE_JAVA_BLOCKED"
            assert audit["native_java"] is False
            assert len(audit["forbidden_dependencies"]) > 0
            assert "DirtyClass.java: matches term 'jp.osscons'" in audit["forbidden_dependencies"][0]
    finally:
        pass
