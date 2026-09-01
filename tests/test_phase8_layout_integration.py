import sys
import os
import subprocess
import tempfile
import shutil
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modernize.lexer import CobolLexer
from modernize.parser import CobolParser
from modernize.native_generator import NativeProgramGenerator

def test_layout01_compilation_and_execution():
    cob_path = "tests/repos/LAYOUT01/LAYOUT01.cob"
    assert os.path.exists(cob_path)
    
    with open(cob_path, "r", encoding="utf-8") as fh:
        code = fh.read()
        
    lexer = CobolLexer(cob_path)
    tokens = lexer.tokenize(code)
    parser = CobolParser(tokens, cob_path)
    ir = parser.parse()
    
    gen = NativeProgramGenerator("LAYOUT01", list(ir.nodes.values()))
    java_source = gen.generate_class_source()
    
    temp_dir = tempfile.mkdtemp()
    try:
        pkg_dir = os.path.join(temp_dir, "com", "systema", "modernized", "native_gen")
        os.makedirs(pkg_dir, exist_ok=True)
        
        # Write CicsProgramRegistry
        registry_dir = os.path.join(temp_dir, "com", "systema", "modernized")
        os.makedirs(registry_dir, exist_ok=True)
        registry_src = """package com.systema.modernized;
import java.util.HashMap;
import java.util.Map;
import java.util.function.Supplier;
public class CicsProgramRegistry {
    private static final Map<String, Supplier<Object>> registry = new HashMap<>();
    public static void register(String name, Supplier<Object> supplier) {
        registry.put(name.toUpperCase(), supplier);
    }
}
"""
        with open(os.path.join(registry_dir, "CicsProgramRegistry.java"), "w", encoding="utf-8") as fh:
            fh.write(registry_src)
            
        subprocess.run(["javac", os.path.join(registry_dir, "CicsProgramRegistry.java")], capture_output=True)

        # Write and compile CobolNumeric helpers
        runtime_dir = os.path.join(temp_dir, "com", "systema", "modernized", "runtime")
        os.makedirs(runtime_dir, exist_ok=True)
        helpers_src_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "modernize", "java_helpers", "src", "main", "java", "com", "systema", "modernized", "runtime")
        
        for f_name in os.listdir(helpers_src_dir):
            if f_name.endswith(".java"):
                path = os.path.join(helpers_src_dir, f_name)
                with open(path, "r", encoding="utf-8") as f:
                    src = f.read()
                with open(os.path.join(runtime_dir, f_name), "w", encoding="utf-8") as f:
                    f.write(src)
        
        # Compile all java files in runtime directory
        java_files = [os.path.join(runtime_dir, f) for f in os.listdir(runtime_dir) if f.endswith(".java")]
        subprocess.run(
            ["javac", "-cp", temp_dir] + java_files,
            capture_output=True,
            text=True
        )

        src_file = os.path.join(pkg_dir, "Layout01.java")
        with open(src_file, "w", encoding="utf-8") as f:
            f.write(java_source)
            
        compile_res = subprocess.run(
            ["javac", "-cp", temp_dir, src_file],
            capture_output=True,
            text=True
        )
        if compile_res.returncode != 0:
            raise Exception(f"Java compilation failed:\n{compile_res.stderr}\nSource:\n{java_source}")
            
        run_res = subprocess.run(
            ["java", "-cp", temp_dir, "com.systema.modernized.native_gen.Layout01"],
            capture_output=True,
            text=True
        )
        assert run_res.returncode == 0, f"Run failed:\n{run_res.stderr}"
        lines = [l.strip() for l in run_res.stdout.strip().splitlines()]
        
        # Verify printed outputs
        assert "INITIAL TEXT: AAAA" in lines
        assert "AFTER NUM MOVE TEXT: 1234" in lines
        assert "AFTER NUM MOVE NUM: 1234" in lines
        assert "ITEM 1: XYZ" in lines
        assert "ITEM 2: ABC" in lines
        assert "ITEM 3: DEF" in lines
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
