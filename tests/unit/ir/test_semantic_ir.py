import os
import pytest
from modernize import SemanticIR, SemanticIRNode

def test_semantic_ir_serialization_and_persistence(tmp_path):
    ir = SemanticIR()
    node = SemanticIRNode(
        node_id="node_00001",
        kind="DATA_ITEM",
        properties={
            "name": "WS-TEST",
            "level": 1,
            "picture": "X(10)",
            "signed": False,
            "digits": 0,
            "scale": 0
        },
        source_file="test.cob",
        source_line=10,
        source_column=8,
        start_offset=100,
        end_offset=120,
        status="PARSED"
    )
    ir.add_node(node)
    
    # Save to temp path
    out_path = os.path.join(tmp_path, "ir_model.json")
    ir.save(out_path)
    
    assert os.path.isfile(out_path)
    
    # Reload and verify
    reloaded = SemanticIR.load(out_path)
    assert reloaded.schema_version == "1.0"
    assert "node_00001" in reloaded.nodes
    
    r_node = reloaded.nodes["node_00001"]
    assert r_node.kind == "DATA_ITEM"
    assert r_node.properties["name"] == "WS-TEST"
    assert r_node.source_line == 10
    assert r_node.source_column == 8
    assert r_node.start_offset == 100
    assert r_node.end_offset == 120
    assert r_node.status == "PARSED"
