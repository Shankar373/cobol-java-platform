"""
Unit test: native Java generator for PAYMAIN.cob.

Tests that:
1. The parser produces a SemanticIR for PAYMAIN.cob
2. The generator produces valid Java source
3. The generated Java contains the expected DISPLAY statements
4. The generated Java has no libcobj / jp.osscons imports (Track-B contract)
"""
import os
import sys
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

from engine.lexer.lexer import CobolLexer
from engine.parser.custom.parser import CobolParser
from generators.native_java.program import NativeJavaGenerator

PAYMAIN_COB = os.path.join(ROOT, "tests", "fixtures", "A-PAYONLY", "src", "PAYMAIN.cob")
BASE_PACKAGE = "com.platform.test"


def _parse_paymain():
    with open(PAYMAIN_COB, "r", encoding="utf-8", errors="ignore") as fh:
        text = fh.read()
    lexer = CobolLexer(PAYMAIN_COB)
    lexer.tokenize(text)
    parser = CobolParser(lexer.tokens, PAYMAIN_COB)
    return parser.parse()


def _generate(ir, tmpdir):
    program_nodes = ir.nodes_of_kind("PROGRAM")
    program_name = program_nodes[0].properties.get("name", "PAYMAIN") if program_nodes else "PAYMAIN"
    gen = NativeJavaGenerator(ir, program_name, base_package=BASE_PACKAGE)
    return gen.generate(tmpdir), program_name


class TestGeneratorPaymain:
    @pytest.fixture
    def generated(self, tmp_path):
        ir = _parse_paymain()
        artifacts, prog_name = _generate(ir, str(tmp_path))
        return artifacts, prog_name, tmp_path

    def test_java_file_created(self, generated):
        artifacts, prog_name, tmp_path = generated
        java_files = [k for k in artifacts if k.endswith(".java")]
        assert java_files, f"No .java file generated. Got: {list(artifacts.keys())}"

    def test_pom_xml_created(self, generated):
        artifacts, prog_name, tmp_path = generated
        assert "pom.xml" in artifacts, "pom.xml not generated"
        assert os.path.isfile(artifacts["pom.xml"]), "pom.xml path does not exist"

    def test_no_libcobj_import(self, generated):
        artifacts, prog_name, tmp_path = generated
        for fname, fpath in artifacts.items():
            if not fname.endswith(".java"):
                continue
            content = open(fpath, encoding="utf-8").read()
            assert "libcobj" not in content, f"libcobj found in {fname}"
            assert "jp.osscons" not in content, f"jp.osscons found in {fname}"

    def test_display_batch_started(self, generated):
        artifacts, prog_name, tmp_path = generated
        for fname, fpath in artifacts.items():
            if not fname.endswith(".java"):
                continue
            content = open(fpath, encoding="utf-8").read()
            assert "PAYMENT PROCESSING BATCH STARTED" in content

    def test_display_batch_completed(self, generated):
        artifacts, prog_name, tmp_path = generated
        for fname, fpath in artifacts.items():
            if not fname.endswith(".java"):
                continue
            content = open(fpath, encoding="utf-8").read()
            assert "PAYMENT PROCESSING BATCH COMPLETED" in content

    def test_process_items_method(self, generated):
        artifacts, prog_name, tmp_path = generated
        for fname, fpath in artifacts.items():
            if not fname.endswith(".java"):
                continue
            content = open(fpath, encoding="utf-8").read()
            assert "process_items" in content

    def test_base_package_used(self, generated):
        artifacts, prog_name, tmp_path = generated
        for fname, fpath in artifacts.items():
            if not fname.endswith(".java"):
                continue
            content = open(fpath, encoding="utf-8").read()
            assert f"package {BASE_PACKAGE}" in content

    def test_main_class_structure(self, generated):
        artifacts, prog_name, tmp_path = generated
        for fname, fpath in artifacts.items():
            if not fname.endswith(".java"):
                continue
            content = open(fpath, encoding="utf-8").read()
            assert "public class" in content
            assert "public static void main" in content
