import os
import shutil
import tempfile
import json
import pytest

from skills import (
    validate_skill_directory,
    parse_skill_file,
    SkillValidationError,
    SkillRegistry,
    discover_repository,
    analyze_cobol_program,
    resolve_copybooks_for_file,
    validate_semantic_ir,
    execute_native_java_generation,
    verify_pipeline_equivalence
)
from modernize.semantic_ir import SemanticIR, SemanticIRNode
from modernize.native_pipeline import NativePipeline

SKILLS_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "skills")

def test_all_skills_pass_validation():
    """Validates that every registered skill in skills/ complies with Google-style specification."""
    reg = SkillRegistry(SKILLS_ROOT)
    assert len(reg.skills) == 6, f"Expected 6 pilot skills, got {len(reg.skills)}: {list(reg.skills.keys())}"

    for name, skill in reg.skills.items():
        is_valid, errors, warnings = validate_skill_directory(skill.skill_dir)
        assert is_valid, f"Skill '{name}' in {skill.skill_dir} failed validation: {errors}"
        assert len(errors) == 0

        # Check references and scripts physically exist
        for script in skill.scripts:
            full_s = os.path.join(skill.skill_dir, script)
            assert os.path.isfile(full_s), f"Script {script} missing for skill {name}"

        for ref in skill.references:
            full_r = os.path.join(skill.skill_dir, ref)
            assert os.path.isfile(full_r), f"Reference {ref} missing for skill {name}"

def test_skill_validator_negative_cases():
    """Verifies that the validator correctly detects malformed frontmatter or missing scripts."""
    temp_d = tempfile.mkdtemp()
    try:
        # Case 1: Missing SKILL.md
        is_valid, errors, _ = validate_skill_directory(temp_d)
        assert not is_valid
        assert any("Missing SKILL.md" in e for e in errors)

        # Case 2: Malformed frontmatter (missing required keys)
        bad_md = """---
name: bad-skill
---
# Overview
Some overview.
"""
        with open(os.path.join(temp_d, "SKILL.md"), "w", encoding="utf-8") as fh:
            fh.write(bad_md)
        is_valid2, errors2, _ = validate_skill_directory(temp_d)
        assert not is_valid2
        assert any("Missing required frontmatter key" in e for e in errors2)

    finally:
        shutil.rmtree(temp_d, ignore_errors=True)

def test_repository_discovery_multi_fixtures():
    """Tests discovery skill across standard COBOL, DB2, JCL, and CICS fixtures."""
    # 1. COBOL standard
    prof_cobol = discover_repository("tests/repos/A-PAYONLY")
    assert "COBOL" in prof_cobol["technologies"]
    assert any("PAYMAIN.cob" in src for src in prof_cobol["artifacts"]["cobol_sources"])

    # 2. DB2 / SQL
    prof_sql = discover_repository("tests/repos/DB2E2E01")
    assert "COBOL" in prof_sql["technologies"]
    assert "SQL" in prof_sql["technologies"]
    assert "DB2" in prof_sql["technologies"]

    # 3. JCL batch
    prof_jcl = discover_repository("tests/repos/JCLBATCH01")
    assert "JCL" in prof_jcl["technologies"]
    assert len(prof_jcl["artifacts"]["jcl_files"]) > 0

    # 4. CICS online
    prof_cics = discover_repository("tests/repos/CICSREST01")
    assert "CICS" in prof_cics["technologies"]

def test_skill_registry_deterministic_matching():
    """Tests skill registry dynamic matching and decision tracing."""
    reg = SkillRegistry(SKILLS_ROOT)

    prof = discover_repository("tests/repos/A-PAYONLY")
    matched, trace = reg.match_skills(prof)

    matched_names = [s.name for s in matched]
    assert "repository-discovery" in matched_names
    assert "cobol-program-analysis" in matched_names
    assert "ir-validation" in matched_names
    assert "native-java-generation" in matched_names
    assert "behavioral-equivalence" in matched_names

    # Verify decision trace has entries for all skills
    assert len(trace) >= len(reg.skills)
    for t in trace:
        assert "skill" in t
        assert "stage" in t
        assert "selected" in t
        assert "reason" in t
        assert len(t["reason"]) > 0

def test_cobol_program_analysis_skill():
    """Tests deterministic program analysis script on A-PAYONLY."""
    res = analyze_cobol_program("tests/repos/A-PAYONLY/src/PAYMAIN.cob")
    assert res["program_id"] == "PAYMAIN"
    assert res["metrics"]["variables_count"] > 0
    assert res["metrics"]["statements_count"] > 0
    assert res["diagnostics_count"] == 0

def test_copybook_analysis_skill():
    """Tests copybook resolution script on B-PAYCOPY and G-PAYMISSCP."""
    # Resolved case
    res_b = resolve_copybooks_for_file("tests/repos/B-PAYCOPY/src/PAYMAIN.cob", ["tests/repos/B-PAYCOPY/copybooks"])
    assert res_b["copy_references_count"] > 0
    assert res_b["all_resolved"] is True
    assert any("PAY-RECORD" in k for k in res_b["resolved_copybooks"])

    # Missing copybook case
    res_g = resolve_copybooks_for_file("tests/repos/G-PAYMISSCP/src/PAYMAIN.cob", ["tests/repos/G-PAYMISSCP/copybooks"])
    assert len(res_g["missing_copybooks"]) > 0
    assert res_g["all_resolved"] is False

def test_semantic_ir_validation_skill():
    """Tests Semantic IR validation on valid and invalid IR graphs."""
    # 1. Valid IR
    ir = SemanticIR()
    prog_node = SemanticIRNode(node_id="prog_1", kind="PROGRAM", properties={"program_id": "TESTPROG"})
    var_node = SemanticIRNode(node_id="var_1", kind="VARIABLE", properties={"name": "WS-VAL", "level": 1, "picture": "X(10)"})
    stmt_node = SemanticIRNode(node_id="stmt_1", kind="STATEMENT", properties={"statement_type": "MOVE"})
    ir.add_node(prog_node)
    ir.add_node(var_node)
    ir.add_node(stmt_node)

    val_valid = validate_semantic_ir(ir)
    assert val_valid["valid"] is True
    assert val_valid["errors_count"] == 0

    # 2. Invalid IR (missing name on variable and missing statement_type on statement)
    bad_ir = SemanticIR()
    bad_var = SemanticIRNode(node_id="bvar_1", kind="VARIABLE", properties={"level": 1})
    bad_stmt = SemanticIRNode(node_id="bstmt_1", kind="STATEMENT", properties={})
    bad_ir.add_node(bad_var)
    bad_ir.add_node(bad_stmt)

    val_bad = validate_semantic_ir(bad_ir)
    assert val_bad["valid"] is False
    assert val_bad["errors_count"] >= 2

def test_native_java_generation_and_equivalence_skills():
    """Tests native Java generation and equivalence verification skills end-to-end on A-PAYONLY."""
    temp_out = tempfile.mkdtemp()
    try:
        repo = "tests/repos/A-PAYONLY"
        
        # Prepare baseline output
        baseline_dir = os.path.join(temp_out, "baseline", "legacy")
        os.makedirs(baseline_dir, exist_ok=True)
        with open(os.path.join(baseline_dir, "stdout.txt"), "w", encoding="utf-8") as fh:
            fh.write("PAYMENT PROCESSING BATCH STARTED\nITEMS PROCESSED: 00001\nPAYMENT PROCESSING BATCH COMPLETED\n")

        gen_res = execute_native_java_generation(repo, temp_out)
        assert gen_res["dependency_gate_passed"] is True
        assert gen_res["generated_classes_count"] > 0

        eq_res = verify_pipeline_equivalence(repo, temp_out)
        assert eq_res["build_gate"] == "PASS"
        assert eq_res["execute_gate"] == "PASS"
        assert eq_res["equivalence_verdict"] == "PASS"
        assert eq_res["overall_status"] == "VERIFIED"
    finally:
        shutil.rmtree(temp_out, ignore_errors=True)

def test_pipeline_parity_with_and_without_skill_routing():
    """
    Proves requirement 3:
    existing pipeline result == skill-routed pipeline result
    for the exact same input repository.
    """
    repo = "tests/repos/A-PAYONLY"
    out_default = tempfile.mkdtemp()
    out_skilled = tempfile.mkdtemp()

    try:
        expected_stdout = "PAYMENT PROCESSING BATCH STARTED\nITEMS PROCESSED: 00001\nPAYMENT PROCESSING BATCH COMPLETED\n"

        # 1. Run with SKILL_ROUTING_ENABLED=false (default)
        os.environ["SKILL_ROUTING_ENABLED"] = "false"
        base_def = os.path.join(out_default, "baseline", "legacy")
        os.makedirs(base_def, exist_ok=True)
        with open(os.path.join(base_def, "stdout.txt"), "w", encoding="utf-8") as fh:
            fh.write(expected_stdout)

        p_def = NativePipeline(repo, out_default)
        p_def.stage_discover()
        p_def.stage_parse()
        main_src = p_def.stage_select_slice()
        p_def.stage_generate(main_src)
        assert p_def.stage_build_gate()
        assert p_def.stage_execute_gate(main_src)
        p_def.baseline_verified = True
        assert p_def.stage_equivalence_gate(main_src) == "PASS"

        # 2. Run with SKILL_ROUTING_ENABLED=true
        os.environ["SKILL_ROUTING_ENABLED"] = "true"
        base_skill = os.path.join(out_skilled, "baseline", "legacy")
        os.makedirs(base_skill, exist_ok=True)
        with open(os.path.join(base_skill, "stdout.txt"), "w", encoding="utf-8") as fh:
            fh.write(expected_stdout)

        p_skill = NativePipeline(repo, out_skilled)
        p_skill.stage_discover()
        p_skill.stage_parse()
        main_src_skill = p_skill.stage_select_slice()
        p_skill.stage_generate(main_src_skill)
        assert p_skill.stage_build_gate()
        assert p_skill.stage_execute_gate(main_src_skill)
        p_skill.baseline_verified = True
        assert p_skill.stage_equivalence_gate(main_src_skill) == "PASS"

        # Verify matched skills in skilled mode
        assert len(p_skill.matched_skills) > 0
        assert os.path.isfile(os.path.join(p_skill.artifacts_dir, "repository_profile.json"))

        # Verify identical generated Java output
        java_def = open(os.path.join(p_def.src_dir, "Paymain.java"), "r", encoding="utf-8").read()
        java_skill = open(os.path.join(p_skill.src_dir, "Paymain.java"), "r", encoding="utf-8").read()
        assert java_def == java_skill, "Generated Java code differed between default and skill-routed mode!"

        # Verify identical execution output
        stdout_def = open(os.path.join(out_default, "results", "native", "stdout.txt"), "r", encoding="utf-8").read()
        stdout_skill = open(os.path.join(out_skilled, "results", "native", "stdout.txt"), "r", encoding="utf-8").read()
        assert stdout_def == stdout_skill, "Execution stdout differed between default and skill-routed mode!"

    finally:
        os.environ["SKILL_ROUTING_ENABLED"] = "false"
        shutil.rmtree(out_default, ignore_errors=True)
        shutil.rmtree(out_skilled, ignore_errors=True)
