"""Real end-to-end Java source mutation integration test.

This test proves that the equivalence engine correctly detects and REJECTS
mutated versions of the opensourcecobol4j-generated Java application.

Real flow for each mutation:
  COBOL fixture
  → GnuCOBOL baseline (Track A)
  → opensourcecobol4j transpile → Java source (Track B intermediate)
  → javac compile → class files
  → execute via JVM inside Docker
  → compare against baseline → PASS (initial)
  → physically mutate generated Java source
  → recompile with javac inside Docker
  → re-execute
  → compare against baseline → MUST FAIL

Three mutation classes are tested:
  1. Arithmetic: wrong multiplier constant (d1.set(99) instead of d1.set(2))
  2. Operation substitution: add instead of multiply (d0.add instead of d0.mul)
  3. Business-logic / write suppression: suppress output record write

If Docker is not available, this test is skipped — it is NEVER silently converted to PASS.
"""
import json
import os
import shutil
import tempfile

import pytest

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cobol_migrate import Pipeline, docker_available, docker_run, DEFAULT_COBJ_IMAGE

# --------------------------------------------------------------------------- #
# COBOL fixture: simple fixed-format batch program performing COMPUTE * 2     #
# --------------------------------------------------------------------------- #

_COBOL_SOURCE = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. MUTPROG.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT IN-FILE ASSIGN TO "data/in/input.dat"
               ORGANIZATION IS LINE SEQUENTIAL.
           SELECT OUT-FILE ASSIGN TO "data/out/output.dat"
               ORGANIZATION IS LINE SEQUENTIAL.
       DATA DIVISION.
       FILE SECTION.
       FD  IN-FILE.
       01  IN-REC.
           05  IN-VAL         PIC 9(4).
       FD  OUT-FILE.
       01  OUT-REC.
           05  OUT-VAL        PIC 9(4).
       WORKING-STORAGE SECTION.
       01  WS-EOF             PIC X VALUE "N".
       PROCEDURE DIVISION.
       MAIN-PARA.
           OPEN INPUT IN-FILE
                OUTPUT OUT-FILE.
           PERFORM UNTIL WS-EOF = "Y"
               READ IN-FILE
                   AT END
                       MOVE "Y" TO WS-EOF
                   NOT AT END
                       COMPUTE OUT-VAL = IN-VAL * 2
                       WRITE OUT-REC
               END-READ
           END-PERFORM.
           CLOSE IN-FILE OUT-FILE.
           STOP RUN.
"""

_INPUT_DATA = "0010\n0020\n0030\n"


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

def _scaffold_repo(repo_dir: str, out_dir: str) -> dict:
    """Create the minimal directory + file layout for the COBOL fixture."""
    os.makedirs(os.path.join(repo_dir, "sources"), exist_ok=True)
    os.makedirs(os.path.join(repo_dir, "data", "in"), exist_ok=True)
    os.makedirs(os.path.join(repo_dir, "data", "out"), exist_ok=True)

    with open(os.path.join(repo_dir, "data", "in", "input.dat"), "w", encoding="utf-8") as f:
        f.write(_INPUT_DATA)

    with open(os.path.join(repo_dir, "sources", "mutprog.cob"), "w", encoding="utf-8") as f:
        f.write(_COBOL_SOURCE)

    cfg = {
        "main_program": "sources/mutprog.cob",
        "entry": "MUTPROG",
        "file_assignments": {
            "IN-FILE": "data/in/input.dat",
            "OUT-FILE": "data/out/output.dat",
        },
    }
    with open(os.path.join(repo_dir, "migration_config.json"), "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

    return cfg


def _recompile(out_dir: str) -> bool:
    """Recompile all .java files in out/generated using javac inside Docker.

    Mirrors exactly what stage_collect does so the test does not rely on any
    hidden build infrastructure.
    """
    r = docker_run(
        DEFAULT_COBJ_IMAGE,
        [(out_dir, "/target")],
        "/target",
        "javac -cp /usr/lib/opensourcecobol4j/libcobj.jar "
        "-d /target/generated /target/generated/*.java",
    )
    return r.returncode == 0, r.stderr


def _reset_stage(p: "Pipeline", *stages: str) -> None:
    """Clear stage-done markers and data keys so the stage is re-executed."""
    for name in stages:
        p.state["stages"].pop(name, None)
        p.state["data"].pop(name, None)


# --------------------------------------------------------------------------- #
# Main test                                                                    #
# --------------------------------------------------------------------------- #

def test_java_source_mutation_e2e():
    """Physical Java source mutations are detected and rejected by the equivalence engine."""
    if not docker_available():
        pytest.skip("Docker is not available — Java source mutation E2E test skipped")

    repo_dir = tempfile.mkdtemp(prefix="mut_repo_")
    out_dir = tempfile.mkdtemp(prefix="mut_out_")

    try:
        # ------------------------------------------------------------------ #
        # Step 1: scaffold fixture + run pipeline through compare             #
        # ------------------------------------------------------------------ #
        cfg = _scaffold_repo(repo_dir, out_dir)
        p = Pipeline(repo_dir, out_dir, cfg=cfg)
        p.pull = False

        for stage_name in [
            "ingest", "discover", "analyze",
            "baseline", "transpile", "collect",
            "generate", "execute",
        ]:
            fn = getattr(p, "stage_" + stage_name)
            ok, detail, _ = fn()
            assert ok, f"Stage '{stage_name}' failed during initial pipeline run: {detail}"

        ok_cmp, detail_cmp, _ = p.stage_compare()
        assert ok_cmp, f"Initial comparison must pass before mutation: {detail_cmp}"

        initial_status = p.data("compare").get("status")
        assert initial_status == "PASS", (
            f"Expected initial comparison status PASS, got: {initial_status}"
        )

        # ------------------------------------------------------------------ #
        # Step 2: load original generated Java source (read-only snapshot)   #
        # ------------------------------------------------------------------ #
        java_path = os.path.join(out_dir, "generated", "MUTPROG.java")
        assert os.path.isfile(java_path), (
            f"Generated Java source not found at: {java_path}\n"
            f"Generated dir contents: {os.listdir(os.path.join(out_dir, 'generated'))}"
        )
        original_src = open(java_path, encoding="utf-8").read()

        # ------------------------------------------------------------------ #
        # Step 3: define mutations (deterministic, verifiable)               #
        # ------------------------------------------------------------------ #
        mutations = [
            (
                "arithmetic_multiplier",
                # COMPUTE OUT-VAL = IN-VAL * 2 generates d1.set(2)
                # Changing to d1.set(99) makes every output value 99x the input
                "d1.set (2);",
                "d1.set (99);",
            ),
            (
                "operation_substitution",
                # d0.mul(d1) performs multiplication; replacing with add changes semantics
                "d0.mul (d1);",
                "d0.add (d1);",
            ),
            (
                "write_suppression",
                # Commenting out the write makes the output file empty
                "h_OUT_FILE.write (f_OUT_REC, 2162689, null);",
                "/* MUTATED: write suppressed */ if (false) { h_OUT_FILE.write (f_OUT_REC, 2162689, null); }",
            ),
        ]

        # ------------------------------------------------------------------ #
        # Step 4: apply each mutation, rebuild, re-execute, verify rejection  #
        # ------------------------------------------------------------------ #
        for mutation_name, old_pattern, new_pattern in mutations:
            mutated_src = original_src.replace(old_pattern, new_pattern)
            assert mutated_src != original_src, (
                f"[{mutation_name}] Mutation pattern not found in generated Java.\n"
                f"Pattern: {old_pattern!r}"
            )

            # Write mutated Java source
            with open(java_path, "w", encoding="utf-8") as f:
                f.write(mutated_src)

            # Recompile mutated source inside Docker
            compile_ok, compile_err = _recompile(out_dir)
            assert compile_ok, (
                f"[{mutation_name}] Maven/javac compilation of mutated Java failed:\n{compile_err}"
            )

            # Re-execute and re-compare
            _reset_stage(p, "execute", "compare")
            ok_exec, detail_exec, _ = p.stage_execute()
            assert ok_exec, (
                f"[{mutation_name}] Mutated Java execution failed unexpectedly: {detail_exec}"
            )

            p.stage_compare()

            mut_status = p.data("compare").get("status", "UNKNOWN")
            assert mut_status == "FAIL", (
                f"[{mutation_name}] Mutation was NOT detected by the equivalence engine!\n"
                f"Expected status=FAIL, got status={mut_status}.\n"
                f"The production equivalence gate must reject incorrectly translated Java."
            )

            # Restore original source for next mutation
            with open(java_path, "w", encoding="utf-8") as f:
                f.write(original_src)

            restore_ok, restore_err = _recompile(out_dir)
            assert restore_ok, (
                f"[{mutation_name}] Failed to recompile after restoring original source:\n{restore_err}"
            )

    finally:
        shutil.rmtree(repo_dir, ignore_errors=True)
        shutil.rmtree(out_dir, ignore_errors=True)
