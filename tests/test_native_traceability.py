import sys
import os
import json
import pytest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modernize.traceability import TraceabilityRecord, TraceabilityModel
from modernize.native_pipeline import NativePipeline
from modernize.semantic_ir import SemanticIR, SemanticIRNode

def test_traceability_record_to_dict():
    rec = TraceabilityRecord(
        rule_id="RULE-01",
        cobol_source={"file": "MAIN.cob", "line": 42},
        ir_node_id="stmt_10",
        java_target={"class": "MainProg", "method": "execute", "statement": "a = b;"},
        test_cases=["test_main"],
        verification_status="PASS"
    )
    d = rec.to_dict()
    assert d["rule_id"] == "RULE-01"
    assert d["cobol_source"]["file"] == "MAIN.cob"
    assert d["intermediate_representation"]["node_id"] == "stmt_10"
    assert d["java_target"]["class"] == "MainProg"
    assert d["verification"]["status"] == "PASS"

def test_native_pipeline_stage_traceability(tmpdir):
    # Mock NativePipeline to test stage_traceability
    out_dir = str(tmpdir.mkdir("out"))
    p = NativePipeline("tests/repos/MULTIFILE01", out_dir)
    
    # Mock program_ir
    ir = SemanticIR()
    ir.nodes["node_1"] = SemanticIRNode(
        node_id="node_1",
        kind="STATEMENT",
        source_line=5,
        properties={
            "statement_type": "MOVE",
            "source": "1",
            "target": "X"
        }
    )
    p.program_ir["tests/repos/MULTIFILE01/MULTIFILE01.cob"] = ir
    
    p.stage_traceability("tests/repos/MULTIFILE01/MULTIFILE01.cob")

    # Artifacts are run-scoped: written under this pipeline's out directory.
    trace_file = os.path.join(out_dir, "generated", "native_traceability.json")
    assert os.path.exists(trace_file)
    with open(trace_file, "r") as fh:
        data = json.load(fh)
        assert data["schema_version"] == "1.0"
        assert len(data["mappings"]) == 1
        mapping = data["mappings"][0]
        assert mapping["source_coordinate"] == "MULTIFILE01.cob:5"
        assert mapping["lexer_token"] == "MOVE"
        assert mapping["semantic_ir_node"] == "node_1"
        assert mapping["java_class"] == "com.systema.modernized.native_gen.Multifile01"
