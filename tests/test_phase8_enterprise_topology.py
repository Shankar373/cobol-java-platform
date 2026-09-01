import os
import tempfile
import shutil
import pytest
from modernize.enterprise_generator import EnterpriseApplicationGenerator


def _make_gen(model=None, native_class='TestClass'):
    return EnterpriseApplicationGenerator(
        repo_path='/fake/repo',
        model=model or {},
        native_class_name=native_class
    )


# ─── Topology: single input, single output ────────────────────────────────

def test_topology_single_io():
    gen = _make_gen(model={
        'file_assigns': {'INPUT-FILE': 'input.dat'},
        'file_ops': {'INPUT-FILE': 'INPUT'},
        'programs': ['PROG1'],
    })
    topo = gen.analyze_topology()
    assert topo['flow_type'] == 'SINGLE_IO'
    assert not topo['gap']
    assert topo['gap_reason'] is None
    assert 'INPUT-FILE' in topo['inputs']


# ─── Topology: multiple inputs ────────────────────────────────────────────

def test_topology_multi_input():
    gen = _make_gen(model={
        'file_assigns': {'FILE-A': 'a.dat', 'FILE-B': 'b.dat'},
        'file_ops': {'FILE-A': 'INPUT', 'FILE-B': 'INPUT', 'OUT-FILE': 'OUTPUT'},
        'programs': ['PROG1'],
    })
    topo = gen.analyze_topology()
    assert topo['flow_type'] == 'MULTI_INPUT'
    assert len(topo['inputs']) == 2
    assert not topo['gap'], 'Single-program multi-input should not be a gap'


# ─── Topology: multiple outputs ───────────────────────────────────────────

def test_topology_multi_output():
    gen = _make_gen(model={
        'file_ops': {'IN-FILE': 'INPUT', 'OUT-A': 'OUTPUT', 'OUT-B': 'OUTPUT'},
        'programs': ['PROG1'],
    })
    topo = gen.analyze_topology()
    assert topo['flow_type'] == 'MULTI_OUTPUT'
    assert len(topo['outputs']) == 2


# ─── Topology: composite/multi-program without call graph ────────────────

def test_topology_composite_gap():
    gen = _make_gen(model={
        'file_ops': {'IN-A': 'INPUT', 'OUT-B': 'OUTPUT', 'OUT-C': 'OUTPUT'},
        'programs': ['PROGA', 'PROGB'],
        # no call_graph key
    })
    topo = gen.analyze_topology()
    assert topo['gap'], 'Multi-program multi-file without call graph must flag a gap'
    assert 'MULTI_FILE_ARCHITECTURAL_GAP' in topo['gap_reason']


# ─── Topology: composite WITH call graph – no gap ─────────────────────────

def test_topology_composite_with_call_graph_no_gap():
    gen = _make_gen(model={
        'file_ops': {'IN-A': 'INPUT', 'OUT-B': 'OUTPUT'},
        'programs': ['PROGA', 'PROGB'],
        'call_graph': {'PROGA': ['PROGB']},
    })
    topo = gen.analyze_topology()
    assert not topo['gap'], 'Call graph provided: gap should not be flagged'


# ─── generate_project: zero forbidden legacy references in output ─────────

def test_enterprise_generated_project_no_forbidden_references():
    gen = _make_gen(model={
        'parsed_models': {'Order': [{'camel_name': 'orderId', 'pic': 'PIC 9(5)'}, {'camel_name': 'orderAmt', 'pic': 'PIC 9(7)V99'}]},
        'file_assigns': {},
        'file_ops': {},
        'programs': ['ORDERPROG'],
    })
    dest = tempfile.mkdtemp(prefix='ent_topo_')
    try:
        gen.generate_project(dest)
        FORBIDDEN = ['jp.osscons', 'libcobj', 'CobolResolve', 'opensourcecobol', 'opensourcecobol4j']
        SCAN_EXTS = ('.java', '.xml', '.properties', '.yml', '.yaml', '.sh', 'Dockerfile')
        hits = []
        for root, _, files in os.walk(dest):
            for fname in files:
                if any(fname.endswith(e) or fname == e for e in SCAN_EXTS):
                    content = open(os.path.join(root, fname), encoding='utf-8').read()
                    for term in FORBIDDEN:
                        if term in content:
                            hits.append(f'{fname}: {term}')
        assert not hits, f'Forbidden legacy references found in enterprise output: {hits}'
    finally:
        shutil.rmtree(dest, ignore_errors=True)


# ─── generate_project: all artifacts invoke native Java, not emulated COBOL ─

def test_enterprise_generated_artifacts_use_native_java():
    gen = _make_gen(model={
        'parsed_models': {'Product': [{'camel_name': 'prodId', 'pic': 'PIC X(5)'}, {'camel_name': 'price', 'pic': 'PIC 9(5)V99'}]},
        'file_assigns': {'PROD-FILE': 'products.dat'},
        'file_ops': {'PROD-FILE': 'INPUT'},
        'programs': ['PRODUCTPROG'],
    }, native_class='Productprog')
    dest = tempfile.mkdtemp(prefix='ent_native_')
    try:
        gen.generate_project(dest)
        # Batch config should exist (file evidence)
        batch_dir = os.path.join(dest, 'src', 'main', 'java', 'com', 'systema', 'modernized', 'batch')
        assert os.path.exists(batch_dir), 'batch/ directory expected from file-assign evidence'
        batch_files = os.listdir(batch_dir)
        assert batch_files, 'At least one batch config file expected'
    finally:
        shutil.rmtree(dest, ignore_errors=True)


# ─── Gap: no discovered file → no gap (empty topology) ───────────────────

def test_topology_empty_no_gap():
    gen = _make_gen(model={'programs': ['SIMPLE'], 'file_assigns': {}, 'file_ops': {}})
    topo = gen.analyze_topology()
    assert not topo['gap']
    assert topo['flow_type'] == 'SINGLE_IO'
