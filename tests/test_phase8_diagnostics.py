import os
import json
import tempfile
import shutil
import pytest

from modernize.lexer import CobolLexer
from modernize.parser import CobolParser
from modernize.native_generator import NativeProgramGenerator, NativeStatementTranslator
from modernize.semantic_ir import SemanticIR, SemanticIRNode


def _build_and_generate(program_name, code):
    filename = f'{program_name}.cob'
    lexer = CobolLexer(filename)
    tokens = lexer.tokenize(code)
    parser = CobolParser(tokens, filename)
    ir = parser.parse()
    gen = NativeProgramGenerator(program_name, list(ir.nodes.values()))
    java_src = gen.generate_class_source()
    return gen, java_src


def _inject_unknown_statement_node(gen, node_id='FAKE_STMT_1', stype='HYPOTHETICAL_STMT',
                                    src_line=42, src_file='TEST.cob'):
    fake_node = SemanticIRNode(
        node_id=node_id,
        kind='STATEMENT',
        properties={'statement_type': stype},
        source_file=src_file,
        source_line=src_line,
    )
    translator = NativeStatementTranslator(gen.var_types, current_generator=gen)
    result = translator.translate_statement(fake_node)
    return result, fake_node


def _collect_all_diagnostics(all_generators, parsers, program_ir):
    diagnostics = []
    for s, parser in parsers.items():
        for diag in parser.diagnostics:
            diagnostics.append({
                'construct': 'SYNTAX_ERROR',
                'source_coordinate': f'{os.path.basename(s)}:{diag.line}',
                'semantic_ir_node': None,
                'severity': 'ERROR',
                'status': 'NATIVE_TRANSLATION_BLOCKED',
                'reason': diag.message
            })
    for s, ir in program_ir.items():
        for node in ir.nodes.values():
            if node.status == 'UNSUPPORTED':
                diagnostics.append({
                    'construct': node.properties.get('statement_type', 'UNKNOWN'),
                    'source_coordinate': f'{os.path.basename(s)}:{node.source_line}',
                    'semantic_ir_node': node.node_id,
                    'severity': 'ERROR',
                    'status': 'NATIVE_TRANSLATION_BLOCKED',
                    'reason': f"Unsupported statement type {node.properties.get('statement_type')}"
                })
    for p_id, gen in all_generators.items():
        for diag in gen.diagnostics:
            diagnostics.append({
                'construct': diag.get('construct', 'UNKNOWN'),
                'source_coordinate': diag.get('source_coordinate') or diag.get('source') or 'UNKNOWN',
                'semantic_ir_node': diag.get('semantic_ir_node'),
                'severity': diag.get('severity', 'ERROR'),
                'status': diag.get('status', 'NATIVE_TRANSLATION_BLOCKED'),
                'reason': diag.get('reason') or diag.get('detail') or 'UNKNOWN'
            })
    return diagnostics


def test_diagnostics_json_structure():
    from modernize.native_pipeline import NativePipeline
    repo = os.path.join(os.path.dirname(__file__), 'repos', 'ACCTPROG')
    if not os.path.exists(repo):
        pytest.skip('ACCTPROG repo not available')
    out = tempfile.mkdtemp(prefix='diag_test_')
    try:
        pipe = NativePipeline(repo, out)
        pipe.stage_discover()
        pipe.stage_parse()
        src = pipe.stage_select_slice()
        if src:
            pipe.stage_generate(src)
        # Run-scoped artifact: lives inside this pipeline's out directory.
        diag_path = pipe._artifact_file('native_translation_diagnostics.json')
        assert os.path.exists(diag_path), 'native_translation_diagnostics.json was not written'
        with open(diag_path, encoding='utf-8') as fh:
            data = json.load(fh)
        assert isinstance(data, list), 'diagnostics must be a JSON array'
        REQUIRED_FIELDS = {'construct', 'source_coordinate', 'semantic_ir_node', 'severity', 'status', 'reason'}
        for entry in data:
            missing = REQUIRED_FIELDS - set(entry.keys())
            assert not missing, f'Diagnostic entry missing fields {missing}: {entry}'
            assert entry['severity'] in ('INFO', 'WARNING', 'ERROR')
            assert entry['status'] in ('SUPPORTED', 'PARTIAL', 'NATIVE_TRANSLATION_BLOCKED')
    finally:
        shutil.rmtree(out, ignore_errors=True)


def test_unknown_construct_emits_blocked_diagnostic():
    code = '''
       IDENTIFICATION DIVISION.
       PROGRAM-ID. DIAGTEST.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-X PIC 9(3) VALUE 5.
       PROCEDURE DIVISION.
           DISPLAY WS-X.
           GOBACK.
    '''
    gen, java_src = _build_and_generate('DIAGTEST', code)
    result, _ = _inject_unknown_statement_node(gen, stype='HYPOTHETICAL_STMT', src_line=9, src_file='DIAGTEST.cob')
    assert 'UNSUPPORTED' in result, f'Expected // UNSUPPORTED:... in result, got: {result!r}'
    assert 'HYPOTHETICAL_STMT' in result
    assert len(gen.diagnostics) > 0, 'No diagnostics were recorded'
    blocked = [d for d in gen.diagnostics if d['status'] == 'NATIVE_TRANSLATION_BLOCKED']
    assert len(blocked) > 0, 'No NATIVE_TRANSLATION_BLOCKED diagnostic recorded'
    diag = blocked[0]
    assert diag['construct'] == 'HYPOTHETICAL_STMT'
    assert diag['severity'] == 'ERROR'
    assert 'HYPOTHETICAL_STMT' in diag['reason']


def test_unknown_construct_preserves_source_coordinate():
    code = '''
       IDENTIFICATION DIVISION.
       PROGRAM-ID. DIAGCOORD.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-X PIC X(10).
       PROCEDURE DIVISION.
           GOBACK.
    '''
    gen, _ = _build_and_generate('DIAGCOORD', code)
    _inject_unknown_statement_node(gen, stype='MYSTERY_OP', src_line=7, src_file='DIAGCOORD.cob')
    blocked = [d for d in gen.diagnostics if d['status'] == 'NATIVE_TRANSLATION_BLOCKED']
    assert blocked, 'Expected at least one NATIVE_TRANSLATION_BLOCKED diagnostic'
    coord = blocked[0]['source_coordinate']
    assert coord != 'UNKNOWN', f'Coordinate defaulted to UNKNOWN: {coord}'
    assert '7' in coord or 'DIAGCOORD' in coord, f'Unexpected coordinate: {coord}'


def test_blocked_construct_cannot_produce_false_pass():
    code = '''
       IDENTIFICATION DIVISION.
       PROGRAM-ID. FALSPOS.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-X PIC 9(3) VALUE 5.
       PROCEDURE DIVISION.
           DISPLAY WS-X.
           GOBACK.
    '''
    gen, _ = _build_and_generate('FALSPOS', code)
    _inject_unknown_statement_node(gen, stype='BLOCKED_OP', src_line=8, src_file='FALSPOS.cob')
    parsers = {'FALSPOS.cob': type('P', (), {'diagnostics': []})()}
    all_generators = {'FALSPOS': gen}
    diags = _collect_all_diagnostics(all_generators, parsers, {})
    blocked = [d for d in diags if d['status'] == 'NATIVE_TRANSLATION_BLOCKED']
    assert blocked, 'Pipeline should detect NATIVE_TRANSLATION_BLOCKED'
    translator = NativeStatementTranslator(gen.var_types, current_generator=gen)
    node = SemanticIRNode('BLK', 'STATEMENT', {'statement_type': 'BLOCKED_OP'}, 'FALSPOS.cob', 8)
    translation = translator.translate_statement(node)
    assert '// UNSUPPORTED:' in translation, 'Unsupported construct must produce // UNSUPPORTED: comment'
    assert 'BLOCKED_OP' in translation


def test_diagnostics_are_deterministic():
    code = '''
       IDENTIFICATION DIVISION.
       PROGRAM-ID. DETERMIN.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-X PIC 9(3) VALUE 5.
       PROCEDURE DIVISION.
           DISPLAY WS-X.
           GOBACK.
    '''
    gen1, _ = _build_and_generate('DETERMIN', code)
    _inject_unknown_statement_node(gen1, stype='REPRO_OP', src_line=8, src_file='DETERMIN.cob')
    gen2, _ = _build_and_generate('DETERMIN', code)
    _inject_unknown_statement_node(gen2, stype='REPRO_OP', src_line=8, src_file='DETERMIN.cob')
    d1 = [(d['construct'], d['status'], d['reason']) for d in gen1.diagnostics]
    d2 = [(d['construct'], d['status'], d['reason']) for d in gen2.diagnostics]
    assert d1 == d2, f'Diagnostics not deterministic:\nRun1: {d1}\nRun2: {d2}'


def test_supported_constructs_produce_no_blocked_diagnostics():
    code = '''
       IDENTIFICATION DIVISION.
       PROGRAM-ID. SUPPTEST.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-A PIC 9(3) VALUE 10.
       01 WS-B PIC 9(3) VALUE 5.
       PROCEDURE DIVISION.
           ADD WS-B TO WS-A.
           IF WS-A > 10
               DISPLAY "BIG"
           END-IF.
           MOVE 0 TO WS-A.
           GOBACK.
    '''
    gen, _ = _build_and_generate('SUPPTEST', code)
    blocked = [d for d in gen.diagnostics if d['status'] == 'NATIVE_TRANSLATION_BLOCKED']
    assert not blocked, f'Supported constructs triggered NATIVE_TRANSLATION_BLOCKED: {blocked}'

def test_ims_mq_unsupported_diagnostics():
    code = '''
       IDENTIFICATION DIVISION.
       PROGRAM-ID. IMSMQTEST.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-PCB PIC X(4).
       PROCEDURE DIVISION.
           CALL "CBLTDLI" USING WS-PCB.
           GOBACK.
    '''
    gen, _ = _build_and_generate('IMSMQTEST', code)
    blocked = [d for d in gen.diagnostics if d['status'] == 'NATIVE_TRANSLATION_BLOCKED']
    assert len(blocked) > 0, 'No diagnostics were recorded for CBLTDLI call'
    assert any('CBLTDLI' in d['reason'] for d in blocked)
    assert any(d['construct'] == 'IMS_MQ' for d in blocked)
