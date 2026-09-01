"""
test_phase8_dependency_audit.py — Step 3: Zero Legacy Dependency (all artifact types)

Verifies that forbidden legacy dependency strings are absent from:
  .java, .xml, .properties, .yml, .yaml, Dockerfile, shell scripts
in every generated artifact produced by the enterprise generator and the native pipeline.
"""
import os
import tempfile
import shutil
import pytest
from modernize.enterprise_generator import EnterpriseApplicationGenerator
from modernize.native_pipeline import NativePipeline


FORBIDDEN = [
    'jp.osscons',
    'libcobj',
    'CobolResolve',
    'opensourcecobol',
    'opensourcecobol4j',
]
SCAN_EXTS = ('.java', '.xml', '.properties', '.yml', '.yaml', '.sh', '.bat', '.gradle')
SCAN_NAMES = {'Dockerfile', 'Makefile'}


def _scan_for_forbidden(root_dir):
    hits = []
    for root, _, files in os.walk(root_dir):
        for fname in files:
            if fname.endswith(SCAN_EXTS) or fname in SCAN_NAMES:
                path = os.path.join(root, fname)
                try:
                    content = open(path, encoding='utf-8', errors='replace').read()
                except Exception:
                    continue
                for term in FORBIDDEN:
                    if term in content:
                        rel = os.path.relpath(path, root_dir)
                        hits.append(f'{rel}: contains "{term}"')
    return hits


# ── Enterprise generator output ────────────────────────────────────────────

def test_enterprise_java_files_no_forbidden():
    gen = EnterpriseApplicationGenerator('/fake', {
        'parsed_models': {'Item': [{'camel_name': 'itemCode', 'pic': 'PIC X(5)'}]},
    }, 'ItemProg', has_db_evidence=True, has_rest_evidence=True)
    dest = tempfile.mkdtemp(prefix='dep_audit_')
    try:
        gen.generate_project(dest)
        hits = _scan_for_forbidden(dest)
        assert not hits, f'Forbidden legacy deps in enterprise output: {hits}'
    finally:
        shutil.rmtree(dest, ignore_errors=True)


def test_enterprise_dockerfile_no_forbidden():
    gen = EnterpriseApplicationGenerator('/fake', {}, 'SomeProg')
    dest = tempfile.mkdtemp(prefix='dep_docker_')
    try:
        gen.generate_project(dest)
        dockerfile = os.path.join(dest, 'Dockerfile')
        assert os.path.exists(dockerfile), 'Dockerfile not generated'
        content = open(dockerfile, encoding='utf-8').read()
        for term in FORBIDDEN:
            assert term not in content, f'Dockerfile contains forbidden term: {term}'
    finally:
        shutil.rmtree(dest, ignore_errors=True)


def test_enterprise_properties_no_forbidden():
    gen = EnterpriseApplicationGenerator('/fake', {
        'file_assigns': {'PROD': 'prod.dat'},
        'file_ops': {'PROD': 'INPUT'},
    }, 'ProdProg')
    dest = tempfile.mkdtemp(prefix='dep_prop_')
    try:
        gen.generate_project(dest)
        # Find application.properties
        prop_files = []
        for r, _, fs in os.walk(dest):
            for fname in fs:
                if fname == 'application.properties':
                    prop_files.append(os.path.join(r, fname))
        assert prop_files, 'application.properties not generated'
        for pf in prop_files:
            content = open(pf, encoding='utf-8').read()
            for term in FORBIDDEN:
                assert term not in content, f'application.properties contains forbidden: {term}'
    finally:
        shutil.rmtree(dest, ignore_errors=True)


# ── Native pipeline output ────────────────────────────────────────────────

def test_native_pipeline_generated_java_no_forbidden():
    repo = os.path.join(os.path.dirname(__file__), 'repos', 'ACCTPROG')
    if not os.path.exists(repo):
        pytest.skip('ACCTPROG repo not available')
    out = tempfile.mkdtemp(prefix='dep_native_')
    try:
        pipe = NativePipeline(repo, out)
        pipe.stage_discover()
        pipe.stage_parse()
        src = pipe.stage_select_slice()
        if src:
            pipe.stage_generate(src)
        # Scan the generated directory
        native_dir = os.path.join(out, 'native')
        if not os.path.exists(native_dir):
            pytest.skip('No native dir generated')
        hits = _scan_for_forbidden(native_dir)
        assert not hits, f'Forbidden legacy deps in native pipeline output: {hits}'
    finally:
        shutil.rmtree(out, ignore_errors=True)


def test_native_pipeline_pom_no_forbidden():
    repo = os.path.join(os.path.dirname(__file__), 'repos', 'ACCTPROG')
    if not os.path.exists(repo):
        pytest.skip('ACCTPROG repo not available')
    out = tempfile.mkdtemp(prefix='dep_pom_')
    try:
        pipe = NativePipeline(repo, out)
        pipe.stage_discover()
        pipe.stage_parse()
        src = pipe.stage_select_slice()
        if src:
            pipe.stage_generate(src)
        pom = os.path.join(out, 'native', 'pom.xml')
        if not os.path.exists(pom):
            pytest.skip('pom.xml not generated')
        content = open(pom, encoding='utf-8').read()
        for term in FORBIDDEN:
            assert term not in content, f'pom.xml contains forbidden legacy term: {term}'
    finally:
        shutil.rmtree(out, ignore_errors=True)
