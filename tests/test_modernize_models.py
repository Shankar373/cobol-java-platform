import os
import json
import pytest
from modernize import (
    SemanticIR, SemanticIRNode,
    ControlFlowModel, ControlFlowEdge,
    DataFlowModel, DataFlowTransition,
    DependencyMigrationStatus, CallDependencyRecord,
    TraceabilityModel, TraceabilityRecord,
    BusinessRuleCoverage
)

def test_modernize_models_serialization():
    # 1. SemanticIR
    ir = SemanticIR()
    node = SemanticIRNode("node1", "Variable", {"PIC": "X(10)", "USAGE": "DISPLAY"}, "main.cob", 10, 5)
    ir.add_node(node)
    
    d = ir.to_dict()
    assert d["schema_version"] == "1.0"
    assert "node1" in d["nodes"]
    assert d["nodes"]["node1"]["properties"]["PIC"] == "X(10)"
    assert d["nodes"]["node1"]["source_location"]["line"] == 10

    # 2. ControlFlowModel
    cfg = ControlFlowModel()
    cfg.add_paragraph("PARA-1", ["STMT-1", "STMT-2"])
    cfg.add_edge(ControlFlowEdge("STMT-1", "STMT-2"))
    
    d = cfg.to_dict()
    assert "PARA-1" in d["paragraphs"]
    assert len(d["edges"]) == 1

    # 3. DataFlowModel
    df = DataFlowModel()
    df.add_input("in1", "stdin")
    df.add_output("out1", "stdout")
    df.add_transition(DataFlowTransition("in1", "out1", "MOVE"))
    
    d = df.to_dict()
    assert d["inputs"][0]["name"] == "in1"
    assert d["transitions"][0]["operation"] == "MOVE"

    # 4. DependencyMigrationStatus
    dep = DependencyMigrationStatus()
    dep.add_call(CallDependencyRecord("MAIN", "SUB", "RESOLVED_STATIC", "YES", "YES", "SubClass", "MIGRATED"))
    
    d = dep.to_dict()
    assert d["calls"][0]["caller"] == "MAIN"
    assert d["calls"][0]["migration_status"] == "MIGRATED"

    # 5. TraceabilityModel
    tr = TraceabilityModel()
    tr.add_record(TraceabilityRecord("rule1", {"file": "main.cob", "line": 15}, "node1", {"class": "MainClass", "method": "run", "statement": "run();"}, ["test1"], "VERIFIED"))
    
    d = tr.to_dict()
    assert d["records"][0]["rule_id"] == "rule1"
    assert d["records"][0]["verification"]["status"] == "VERIFIED"

    # 6. BusinessRuleCoverage
    cov = BusinessRuleCoverage()
    cov.add_evidence("audit_log.txt")
    cov.add_unsupported("CICS commands")
    
    d = cov.to_dict()
    assert d["categories"]["program_discovery"] == "VERIFIED"
    assert "audit_log.txt" in d["evidence_references"]
    assert "CICS commands" in d["unsupported_features"]
