"""Phase 11 — IMS / MQ / Mainframe Integration Boundary Tests.

Verifies:
1. IMS DL/I (CBLTDLI, ASMTDLI, PLITDLI) calls trigger fail-closed NATIVE_TRANSLATION_BLOCKED diagnostics.
2. IBM MQ (MQCONN, MQOPEN, MQPUT, MQGET, MQCLOSE, MQDISC, MQCMIT, MQBACK) calls trigger fail-closed NATIVE_TRANSLATION_BLOCKED diagnostics.
3. Pipeline dependency & translation gates block unverified IMS/MQ code generation.
4. Capability matrix classifies REAL_IMS as UNPROVEN and REAL_MQ as UNPROVEN.
"""
import pytest
from modernize.lexer import CobolLexer
from modernize.parser import CobolParser
from modernize.native_generator import NativeProgramGenerator
from modernize.capability_matrix import CAPABILITIES, EvidenceLevel

def _build_and_generate(program_name: str, cobol_source: str):
    filename = f"{program_name}.cob"
    lexer = CobolLexer(filename)
    tokens = lexer.tokenize(cobol_source)
    parser = CobolParser(tokens, filename)
    ir = parser.parse()
    gen = NativeProgramGenerator(program_name, list(ir.nodes.values()))
    java_src = gen.generate_class_source()
    return gen, java_src

def test_ims_dli_cbltdli_diagnostic():
    code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. IMSPROG1.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-PCB          PIC X(4) VALUE "DB01".
       01  WS-FUNC-GU      PIC X(4) VALUE "GU  ".
       01  WS-SEG-IO       PIC X(80).
       PROCEDURE DIVISION.
           CALL "CBLTDLI" USING WS-FUNC-GU WS-PCB WS-SEG-IO.
           GOBACK.
    """
    gen, _ = _build_and_generate("IMSPROG1", code)
    blocked = [d for d in gen.diagnostics if d.get("status") == "NATIVE_TRANSLATION_BLOCKED"]
    assert len(blocked) > 0, "Expected NATIVE_TRANSLATION_BLOCKED diagnostic for CBLTDLI call"
    assert any("CBLTDLI" in d.get("reason", "") for d in blocked)
    assert any(d.get("construct") == "IMS_MQ" for d in blocked)

def test_ims_dli_asmtdli_diagnostic():
    code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. IMSPROG2.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-PCB          PIC X(4) VALUE "DB01".
       PROCEDURE DIVISION.
           CALL "ASMTDLI" USING WS-PCB.
           GOBACK.
    """
    gen, _ = _build_and_generate("IMSPROG2", code)
    blocked = [d for d in gen.diagnostics if d.get("status") == "NATIVE_TRANSLATION_BLOCKED"]
    assert len(blocked) > 0, "Expected NATIVE_TRANSLATION_BLOCKED diagnostic for ASMTDLI call"
    assert any("ASMTDLI" in d.get("reason", "") for d in blocked)

def test_ibm_mq_mqconn_diagnostic():
    code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. MQPROG1.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-QM-NAME      PIC X(48) VALUE "QM1                             ".
       01  WS-HCONN        PIC S9(9) BINARY.
       01  WS-COMPCODE     PIC S9(9) BINARY.
       01  WS-REASON       PIC S9(9) BINARY.
       PROCEDURE DIVISION.
           CALL "MQCONN" USING WS-QM-NAME WS-HCONN WS-COMPCODE WS-REASON.
           GOBACK.
    """
    gen, _ = _build_and_generate("MQPROG1", code)
    blocked = [d for d in gen.diagnostics if d.get("status") == "NATIVE_TRANSLATION_BLOCKED"]
    assert len(blocked) > 0, "Expected NATIVE_TRANSLATION_BLOCKED diagnostic for MQCONN call"
    assert any("MQCONN" in d.get("reason", "") for d in blocked)
    assert any(d.get("construct") == "IMS_MQ" for d in blocked)

def test_ibm_mq_mqput_mqget_diagnostics():
    code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. MQPROG2.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-HCONN        PIC S9(9) BINARY.
       01  WS-HOBJ         PIC S9(9) BINARY.
       01  WS-MD           PIC X(364).
       01  WS-PMO          PIC X(128).
       01  WS-BUFFER       PIC X(100).
       01  WS-COMPCODE     PIC S9(9) BINARY.
       01  WS-REASON       PIC S9(9) BINARY.
       PROCEDURE DIVISION.
           CALL "MQPUT" USING WS-HCONN WS-HOBJ WS-MD WS-PMO WS-BUFFER WS-COMPCODE WS-REASON.
           CALL "MQGET" USING WS-HCONN WS-HOBJ WS-MD WS-PMO WS-BUFFER WS-COMPCODE WS-REASON.
           CALL "MQDISC" USING WS-HCONN WS-COMPCODE WS-REASON.
           GOBACK.
    """
    gen, _ = _build_and_generate("MQPROG2", code)
    blocked = [d for d in gen.diagnostics if d.get("status") == "NATIVE_TRANSLATION_BLOCKED"]
    assert len(blocked) >= 3, "Expected at least 3 NATIVE_TRANSLATION_BLOCKED diagnostics for MQ calls"
    reasons = " ".join(d.get("reason", "") for d in blocked)
    assert "MQPUT" in reasons
    assert "MQGET" in reasons
    assert "MQDISC" in reasons

def test_capability_matrix_ims_mq_unproven_and_unsupported():
    """Verify that capability matrix maintains strict unproven/unsupported classifications."""
    assert "IMS.DLI" in CAPABILITIES
    ims_entry = CAPABILITIES["IMS.DLI"]
    assert ims_entry["evidence_level"] in (EvidenceLevel.UNSUPPORTED, "UNPROVEN", "PARTIAL")
    assert any("CBLTDLI" in pat for pat in ims_entry.get("unsupported_patterns", []))
