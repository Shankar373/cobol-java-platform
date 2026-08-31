"""
platform/pipeline/pipeline.py

The modernization pipeline runner.

Executes stages in order, stops on BLOCKED/FAILED unless configured to
continue, collects StageEvidence from each stage, and returns a
PipelineVerdict.

Stage order (fixed):
  0. ingest     - fingerprint + config load
  1. discover   - source/copybook/JCL discovery
  2. parse      - COBOL -> SemanticIR
  3. generate   - SemanticIR -> Java source + pom.xml
  4. baseline   - GnuCOBOL compile + execute (BLOCKED if Docker absent)
  5. java_build - mvn compile + java execute
  6. equivalence - compare outputs

Each stage emits a StageEvidence. The pipeline does NOT short-circuit
BLOCKED stages silently — every BLOCKED is recorded in the PipelineVerdict.
"""
from __future__ import annotations

import os
import tempfile
import uuid
from datetime import datetime, timezone
from typing import Optional

from engine.semantic.semantic_ir import SemanticIR
from cjp_platform.configuration.config import load_config, MigrationConfig
from engine.discovery.discovery import discover, DiscoveryResult
from verification.evidence.verdict import (
    PipelineVerdict, StageEvidence, Verdict,
    blocked, failed, executed, compiled,
)


class Pipeline:
    """
    Run the full modernization pipeline for a COBOL repository.

    Parameters
    ----------
    repo_path:
        Absolute path to the COBOL repository root.
    out_dir:
        Directory to write generated artifacts and evidence.
        If None, a temporary directory is created.
    parser_choice:
        "custom" (default) or "proleap".
    gnucobol_image:
        Docker image tag for the GnuCOBOL+OCESQL compiler.
    pg_network:
        Docker network for PostgreSQL access (SQL programs only).
    """

    def __init__(
        self,
        repo_path: str,
        out_dir: Optional[str] = None,
        *,
        parser_choice: str = "custom",
        gnucobol_image: str = "gnucobol-ocesql:latest",
        pg_network: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> None:
        self.repo_path = os.path.abspath(repo_path)
        self.out_dir = os.path.abspath(out_dir) if out_dir else tempfile.mkdtemp(prefix="cjp_")
        self.parser_choice = parser_choice
        self.gnucobol_image = gnucobol_image
        self.pg_network = pg_network
        self.run_id = run_id or f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"

        self._cfg: Optional[MigrationConfig] = None
        self._discovery: Optional[DiscoveryResult] = None
        self._ir: Optional[SemanticIR] = None
        self._generated_dir: Optional[str] = None
        self._baseline_stdout: str = ""
        self._java_stdout: str = ""

    # ── Public API ────────────────────────────────────────────────────────────

    def run(self) -> PipelineVerdict:
        """Execute all stages and return a PipelineVerdict."""
        verdict = PipelineVerdict(
            program_name="(unknown)",
            repo_path=self.repo_path,
            run_id=self.run_id,
        )

        stages = [
            ("ingest",      self._stage_ingest),
            ("discover",    self._stage_discover),
            ("parse",       self._stage_parse),
            ("generate",    self._stage_generate),
            ("baseline",    self._stage_baseline),
            ("java_build",  self._stage_java_build),
            ("equivalence", self._stage_equivalence),
        ]

        for stage_name, stage_fn in stages:
            print(f"[pipeline] Stage: {stage_name}")
            try:
                evidence = stage_fn()
            except Exception as exc:
                evidence = failed(stage_name,
                                  notes=f"Unhandled exception: {type(exc).__name__}: {exc}")

            verdict.add_stage(evidence)
            print(f"[pipeline]   -> {evidence.verdict.value}  {evidence.notes[:80]}")

            # Stop pipeline on hard failures / blocks for generation-dependent stages
            if evidence.verdict in (Verdict.BLOCKED, Verdict.FAILED):
                if stage_name in ("ingest", "discover", "parse", "generate"):
                    _remaining = [s for s, _ in stages[stages.index((stage_name, stage_fn)) + 1:]]
                    for rem in _remaining:
                        verdict.add_stage(blocked(rem, f"Blocked by failed stage: {stage_name}"))
                    break

        # Persist verdict
        verdict_path = verdict.save(self.out_dir)
        print(f"[pipeline] Verdict: {verdict.overall_verdict.value}")
        print(f"[pipeline] Evidence: {verdict_path}")
        return verdict

    # ── Stage implementations ─────────────────────────────────────────────────

    def _stage_ingest(self) -> StageEvidence:
        from verification.evidence.verdict import executed as ev_executed
        self._cfg = load_config(self.repo_path)
        if self._cfg.repo_name:
            return ev_executed("ingest", stdout=f"repo_name={self._cfg.repo_name}",
                               notes="Config loaded")
        return ev_executed("ingest", notes="No migration_config.json — using discovery defaults")

    def _stage_discover(self) -> StageEvidence:
        from verification.evidence.verdict import executed as ev_executed
        self._discovery = discover(self._cfg)
        if not self._discovery.sources:
            return failed("discover", notes="No COBOL source files found in repository")
        prog = os.path.basename(self._discovery.entrypoint or self._discovery.sources[0])
        return ev_executed("discover",
                           stdout=f"sources={len(self._discovery.sources)} "
                                  f"copybooks={len(self._discovery.copybooks)} "
                                  f"techs={self._discovery.technologies}",
                           notes=f"Entry: {prog}")

    def _stage_parse(self) -> StageEvidence:
        from verification.evidence.verdict import executed as ev_executed
        from engine.lexer.lexer import CobolLexer
        from engine.parser.custom.parser import CobolParser

        entrypoint = self._discovery.entrypoint or self._discovery.sources[0]
        fmt = self._cfg.format if self._cfg else "fixed"

        try:
            with open(entrypoint, 'r', encoding='utf-8', errors='ignore') as _fh:
                cobol_text = _fh.read()
            lexer = CobolLexer(entrypoint, format_mode=fmt)
            lexer.tokenize(cobol_text)
            tokens = lexer.tokens
        except Exception as exc:
            return failed("parse", notes=f"Lexer error: {exc}")

        try:
            parser = CobolParser(tokens, entrypoint)
            self._ir = parser.parse()
        except Exception as exc:
            return failed("parse", notes=f"Parser error: {exc}")

        node_count = len(self._ir.nodes)
        program_nodes = self._ir.nodes_of_kind("PROGRAM")
        program_name = "PROGRAM"
        if program_nodes:
            program_name = program_nodes[0].properties.get("name", "PROGRAM")

        return ev_executed("parse",
                           stdout=f"nodes={node_count} program={program_name}",
                           notes=f"Parsed {os.path.basename(entrypoint)}: {node_count} IR nodes")

    def _stage_generate(self) -> StageEvidence:
        from verification.evidence.verdict import executed as ev_executed
        from generators.native_java.program import NativeJavaGenerator

        program_nodes = self._ir.nodes_of_kind("PROGRAM")
        program_name = program_nodes[0].properties.get("name", "PROGRAM") if program_nodes else "PROGRAM"

        base_pkg = self._cfg.base_package if self._cfg else "com.platform.modernized"
        self._generated_dir = os.path.join(self.out_dir, "generated", "native")

        try:
            gen = NativeJavaGenerator(self._ir, program_name, base_package=base_pkg)
            artifacts = gen.generate(self._generated_dir)
        except Exception as exc:
            return failed("generate", notes=f"Generator error: {exc}")

        return ev_executed("generate",
                           stdout=str(list(artifacts.keys())),
                           artifacts=artifacts,
                           notes=f"Generated {len(artifacts)} files for {program_name}")

    def _stage_baseline(self) -> StageEvidence:
        from verification.baseline.baseline import run_baseline, docker_available

        if not docker_available():
            return blocked("baseline",
                           "Docker not available — COBOL baseline cannot run. "
                           "Set GNUCOBOL_IMAGE env var and start Docker.")

        entrypoint = self._discovery.entrypoint or self._discovery.sources[0]
        baseline_out = os.path.join(self.out_dir, "evidence", "baseline")

        ev = run_baseline(
            source_path=entrypoint,
            repo_root=self.repo_path,
            copybook_dirs=self._discovery.copybook_search_dirs,
            has_sql=self._discovery.has_sql,
            pg_network=self.pg_network,
            image=self.gnucobol_image,
            out_dir=baseline_out,
        )
        if ev.verdict == Verdict.EXECUTED:
            self._baseline_stdout = ev.stdout
        return ev

    def _stage_java_build(self) -> StageEvidence:
        from verification.java_build.java_build import compile_java, execute_java

        if not self._generated_dir or not os.path.isdir(self._generated_dir):
            return blocked("java_execute", "Generated project directory not found")

        java_out = os.path.join(self.out_dir, "evidence", "java")
        os.makedirs(java_out, exist_ok=True)

        # Compile
        compile_ev = compile_java(self._generated_dir, out_dir=java_out)
        if compile_ev.verdict != Verdict.COMPILED:
            return StageEvidence(
                stage="java_execute",
                verdict=compile_ev.verdict,
                notes=compile_ev.notes,
                stdout=compile_ev.stdout,
                stderr=compile_ev.stderr,
            )

        # Determine main class
        program_nodes = self._ir.nodes_of_kind("PROGRAM")
        program_name = program_nodes[0].properties.get("name", "PROGRAM") if program_nodes else "PROGRAM"
        base_pkg = self._cfg.base_package if self._cfg else "com.platform.modernized"
        from generators.native_java.types import to_java_class
        class_name = to_java_class(program_name)
        main_class = f"{base_pkg}.{class_name}"

        # Execute
        exec_ev = execute_java(
            self._generated_dir,
            main_class,
            out_dir=java_out,
        )
        if exec_ev.verdict == Verdict.EXECUTED:
            self._java_stdout = exec_ev.stdout
        exec_ev.stage = "java_build"
        return exec_ev

    def _stage_equivalence(self) -> StageEvidence:
        from verification.equivalence.comparator import compare

        if not self._baseline_stdout and not self._java_stdout:
            return blocked("equivalence",
                           "Both baseline and Java stdout are empty — cannot compare. "
                           "Check that both baseline and java_build stages EXECUTED.")

        equiv_out = os.path.join(self.out_dir, "evidence", "equivalence")
        result = compare(
            self._baseline_stdout,
            self._java_stdout,
            out_dir=equiv_out,
        )
        return result.to_stage_evidence()


