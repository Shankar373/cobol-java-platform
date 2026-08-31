"""
End-to-end differential test: PAYMAIN.cob vertical slice.

This is the FIRST and most important test in the platform.
It validates the entire pipeline:
  real COBOL -> GnuCOBOL baseline -> parse/IR -> native Java
  -> Maven compile -> Java execute -> equivalence comparison -> EQUIVALENT verdict

Verdict contract (cannot be relaxed):
  - BASELINE_VERIFIED requires Docker + GnuCOBOL image available
  - NATIVE_JAVA_VERIFIED requires Maven + JDK 17 available
  - EQUIVALENT requires both executions to produce matching stdout
  - If Docker unavailable: test is marked BLOCKED (not FAILED, not PASS)
  - If Maven unavailable: Java stages are BLOCKED (not FAILED, not PASS)
  - Empty COBOL output + non-empty Java output = FAIL (not PASS)

Markers:
  @pytest.mark.differential  - requires full toolchain
  @pytest.mark.docker        - requires Docker daemon
"""
import os
import sys
import json
import tempfile
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from cjp_platform.pipeline.pipeline import Pipeline
from verification.evidence.verdict import Verdict
from verification.baseline.baseline import docker_available, image_available
from verification.java_build.java_build import maven_available, java_available

PAYMAIN_FIXTURE = os.path.join(ROOT, "tests", "fixtures", "A-PAYONLY")
GNUCOBOL_IMAGE = os.environ.get("GNUCOBOL_IMAGE", "gnucobol-ocesql:latest")


@pytest.mark.differential
@pytest.mark.docker
def test_paymain_end_to_end(tmp_path):
    """
    Full end-to-end pipeline for PAYMAIN.cob.

    Expected:
      - COBOL compiles and prints the three DISPLAY lines
      - Java generates, compiles, executes, and prints identical output
      - Equivalence: EQUIVALENT

    If Docker or Maven is unavailable, the test records BLOCKED status
    in the evidence and is skipped (not failed — infrastructure gap, not
    a code defect).
    """
    assert os.path.isdir(PAYMAIN_FIXTURE), (
        f"Fixture not found: {PAYMAIN_FIXTURE}. "
        "Run from repository root."
    )

    out_dir = str(tmp_path / "pipeline_out")
    pipeline = Pipeline(
        repo_path=PAYMAIN_FIXTURE,
        out_dir=out_dir,
        gnucobol_image=GNUCOBOL_IMAGE,
    )
    verdict = pipeline.run()

    # Print full summary for CI evidence
    print("\n" + "=" * 60)
    print(verdict.summary())
    print("=" * 60)

    # Inspect stage verdicts
    baseline_v = verdict.baseline_verdict
    java_v = verdict.java_execute_verdict
    equiv_v = verdict.equivalence_verdict

    print(f"\nBaseline:    {baseline_v.value}")
    print(f"Java:        {java_v.value}")
    print(f"Equivalence: {equiv_v.value}")

    # If Docker not available, this is BLOCKED infrastructure — skip, not fail
    if baseline_v == Verdict.BLOCKED:
        if not docker_available():
            pytest.skip("BLOCKED: Docker not available — GnuCOBOL baseline cannot run")
        if not image_available(GNUCOBOL_IMAGE):
            pytest.skip(f"BLOCKED: Docker image not found: {GNUCOBOL_IMAGE}. "
                        f"Build it first: docker build -f docker/Dockerfile.gnucobol-ocesql .")
        pytest.fail(f"BLOCKED for unknown reason: {verdict.stages}")

    # If baseline ran but Java infra is missing, skip Java stages
    if java_v in (Verdict.BLOCKED, Verdict.UNVERIFIED):
        if not maven_available():
            pytest.skip("BLOCKED: Maven not available — Java build cannot run")
        if not java_available():
            pytest.skip("BLOCKED: JDK not available — Java execution cannot run")

    # If we get here, both baseline and Java ran — check equivalence
    assert baseline_v == Verdict.EXECUTED, (
        f"Expected COBOL baseline to EXECUTE, got {baseline_v.value}. "
        f"Check baseline stage evidence in {out_dir}"
    )
    assert java_v == Verdict.EXECUTED, (
        f"Expected Java to EXECUTE, got {java_v.value}. "
        f"Check java_build stage evidence in {out_dir}"
    )
    assert equiv_v == Verdict.EQUIVALENT, (
        f"COBOL and Java outputs differ. Equivalence: {equiv_v.value}. "
        f"Check equivalence evidence in {out_dir}/evidence/equivalence/"
    )


@pytest.mark.differential
def test_paymain_parse_generates_java(tmp_path):
    """
    Parse PAYMAIN.cob and verify Java generation — does NOT require Docker.
    Fails only if parse/generate stages fail (infrastructure-independent).
    """
    assert os.path.isdir(PAYMAIN_FIXTURE), f"Fixture not found: {PAYMAIN_FIXTURE}"

    out_dir = str(tmp_path / "gen_only")
    from engine.lexer.lexer import CobolLexer
    from engine.parser.custom.parser import CobolParser
    from generators.native_java.program import NativeJavaGenerator

    src = os.path.join(PAYMAIN_FIXTURE, "src", "PAYMAIN.cob")
    assert os.path.isfile(src), f"Source not found: {src}"

    with open(src, 'r', encoding='utf-8', errors='ignore') as fh:
        cobol_text = fh.read()
    lexer = CobolLexer(src)
    lexer.tokenize(cobol_text)
    assert lexer.tokens, "Lexer produced no tokens"

    parser = CobolParser(lexer.tokens, src)
    ir = parser.parse()
    assert ir is not None, "Parser returned None"
    assert len(ir.nodes) > 0, "IR is empty — parser produced no nodes"

    program_nodes = ir.nodes_of_kind("PROGRAM")
    assert program_nodes, "No PROGRAM node in IR"
    program_name = program_nodes[0].properties.get("name", "PAYMAIN")

    gen = NativeJavaGenerator(ir, program_name, base_package="com.platform.test")
    artifacts = gen.generate(out_dir)

    assert artifacts, "Generator produced no artifacts"
    java_files = [k for k in artifacts if k.endswith(".java")]
    assert java_files, "Generator produced no .java file"

    java_path = artifacts[java_files[0]]
    assert os.path.isfile(java_path), f"Java file not on disk: {java_path}"

    java_src = open(java_path, encoding="utf-8").read()

    # Check key expected outputs
    assert "PAYMENT PROCESSING BATCH STARTED" in java_src, (
        "Missing PAYMENT PROCESSING BATCH STARTED in generated Java"
    )
    assert "PAYMENT PROCESSING BATCH COMPLETED" in java_src, (
        "Missing PAYMENT PROCESSING BATCH COMPLETED in generated Java"
    )

    # Track-B contract
    assert "libcobj" not in java_src, "Track-B violation: libcobj in generated code"
    assert "jp.osscons" not in java_src, "Track-B violation: jp.osscons in generated code"

    print(f"\nGenerated Java ({os.path.basename(java_path)}):")
    print("-" * 50)
    print(java_src)
    print("-" * 50)


@pytest.mark.differential
def test_equivalence_comparator_rules():
    """
    Unit-level check that the equivalence comparator enforces hard rules.
    Does NOT require Docker or Maven.
    """
    from verification.equivalence.comparator import compare
    from verification.evidence.verdict import Verdict

    # Rule: empty COBOL + non-empty Java = FAIL (not PASS)
    result = compare("", "some output\n")
    assert result.verdict == Verdict.FAILED, (
        "Empty COBOL vs non-empty Java must be FAIL, not PASS"
    )

    # Rule: non-empty COBOL + empty Java = FAIL
    result = compare("some output\n", "")
    assert result.verdict == Verdict.FAILED, (
        "Non-empty COBOL vs empty Java must be FAIL, not PASS"
    )

    # Rule: identical outputs = EQUIVALENT
    result = compare("HELLO\n", "HELLO\n")
    assert result.verdict == Verdict.EQUIVALENT

    # Rule: different outputs = FAILED
    result = compare("HELLO\n", "WORLD\n")
    assert result.verdict == Verdict.FAILED

    # Rule: normalisation of line endings is OK
    result = compare("HELLO\r\n", "HELLO\n")
    assert result.verdict == Verdict.EQUIVALENT, (
        "\\r\\n vs \\n normalisation should not cause FAIL"
    )

    # Rule: trailing whitespace normalisation is OK
    result = compare("HELLO   \n", "HELLO\n")
    assert result.verdict == Verdict.EQUIVALENT, (
        "Trailing whitespace normalisation should not cause FAIL"
    )


