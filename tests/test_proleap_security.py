import os
import pytest
import subprocess
from modernize.proleap_adapter.parser_adapter import ProLeapParserAdapter

def test_no_shell_true_in_adapter():
    adapter_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "modernize", "proleap_adapter", "parser_adapter.py"
    )
    with open(adapter_file, "r", encoding="utf-8") as f:
        content = f.read()
    
    assert "shell=True" not in content
    assert "shell = True" not in content

def test_copybook_traversal_protection():
    # Pass a path that contains traversal segments to mimic a malicious copybook inclusion
    adapter = ProLeapParserAdapter("tests/repos/../../etc/passwd")
    # Verify that it fails safely or resolves to missing copybook without throwing RuntimeError
    ir = adapter.parse()
    assert adapter.status == "FAILURE"
    assert ir.status == "FAILURE"
