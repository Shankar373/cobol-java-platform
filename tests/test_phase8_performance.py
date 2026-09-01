import os
import time
import json
import tempfile
import shutil
import subprocess
import pytest
from modernize.lexer import CobolLexer
from modernize.parser import CobolParser
from modernize.native_generator import NativeProgramGenerator
from tests.test_phase8_file_semantics import run_cobol_code

def test_pipeline_performance_metrics(tmp_path):
    # Load INVMGR code
    cob_path = os.path.join("tests", "repos", "INVMGR", "src", "INVMGR.cob")
    assert os.path.exists(cob_path), f"INVMGR source not found at {cob_path}"
    with open(cob_path, "r", encoding="utf-8") as fh:
        code = fh.read()

    metrics = {}

    # 1. Lexer Performance
    t_start = time.perf_counter()
    lexer = CobolLexer("INVMGR.cob")
    tokens = list(lexer.tokenize(code))
    t_lex = time.perf_counter() - t_start
    metrics["lexer_seconds"] = t_lex
    assert len(tokens) > 0

    # 2. Parser & IR Performance
    t_start = time.perf_counter()
    parser = CobolParser(tokens, "INVMGR.cob")
    ir = parser.parse()
    t_parse = time.perf_counter() - t_start
    metrics["parser_and_ir_seconds"] = t_parse
    assert ir is not None

    # 3. Native Java Generation Performance
    t_start = time.perf_counter()
    gen = NativeProgramGenerator("INVMGR", list(ir.nodes.values()))
    java_source = gen.generate_class_source()
    t_gen = time.perf_counter() - t_start
    metrics["generation_seconds"] = t_gen
    assert java_source

    # 4. Compilation & Execution Performance
    # We will run compilation and execution via run_cobol_code
    t_start = time.perf_counter()
    ret, stdout, stderr, java_src, outputs = run_cobol_code("INVMGR", code)
    t_run = time.perf_counter() - t_start
    metrics["compilation_and_execution_seconds"] = t_run

    assert ret == 0, f"Execution failed: {stderr}"
    assert "QTY" in stdout and "0050" in stdout

    # Write performance results to the run-scoped temp directory.
    # AGENTS.md §13: test artifacts must never dirty tracked repository files
    # (this previously overwrote audit/phase8/performance_results.json).
    results_path = tmp_path / "performance_results.json"
    with open(results_path, "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2)

    # Performance Threshold Assertions (with generous margins for CI environments)
    assert t_lex < 5.0, f"Lexer was too slow: {t_lex:.3f}s"
    assert t_parse < 5.0, f"Parser was too slow: {t_parse:.3f}s"
    assert t_gen < 5.0, f"Generator was too slow: {t_gen:.3f}s"
    assert t_run < 120.0, f"Compilation and execution was too slow: {t_run:.3f}s"
