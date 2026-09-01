import os
import sys
import pytest
from modernize.native_generator import NativeExpressionTranslator
from cobol_migrate import resolve_copybook, preprocess_cobol_for_cobj, build_call_graph
from modernize.native_pipeline import NativePipeline

# 1 & 2: String literals quoting and escaping tests
def test_string_literal_translation():
    trans = NativeExpressionTranslator({"WS-STATUS": "String"}, is_child=False)
    
    # Simple single quote literals
    assert trans.translate("'READY'") == '"READY"'
    assert trans.translate("'ABC'") == '"ABC"'
    assert trans.translate("'Y'") == '"Y"'
    assert trans.translate("'0'") == '"0"'
    assert trans.translate("' '") == '" "'
    
    # Escaping double quotes inside single quotes
    assert trans.translate("'A\"B'") == '"A\\"B"'
    
    # Escaping backslashes
    assert trans.translate("'A\\\\B'") == '"A\\\\\\\\B"'
    assert trans.translate("'A\\B'") == '"A\\\\B"'
    
    # Keep numeric literals unchanged
    assert trans.translate("123.45") == 'new BigDecimal("123.45")'
    
    # Keep identifiers unchanged
    assert trans.translate("WS-STATUS") == "ws_status"

# 3, 4, 5 & 6: Copybook resolution tests
def test_copybook_resolution(tmpdir):
    repo_dir = str(tmpdir)
    cb_dir = tmpdir.mkdir("copybooks")
    
    # Create copybook files
    # Case A: Exact match
    cb_exact = cb_dir.join("exact.cpy")
    cb_exact.write("01 EXACT PIC X.")
    
    # Case B: Case-insensitive match (lowercase file, uppercase query)
    cb_case = cb_dir.join("lgcmarea.cpy")
    cb_case.write("01 LGCMAREA PIC X.")
    
    # Test Exact Match
    p_exact = resolve_copybook("exact.cpy", repo_dir, ["copybooks"])
    assert p_exact == "copybooks/exact.cpy"
    
    # Test Case-insensitive Match
    p_case = resolve_copybook("LGCMAREA", repo_dir, ["copybooks"])
    assert p_case is not None
    assert p_case.lower() == "copybooks/lgcmarea.cpy"
    
    # Test Missing Copybook
    p_missing = resolve_copybook("MISSING", repo_dir, ["copybooks"])
    assert p_missing is None

def test_copybook_ambiguity_mocked(monkeypatch):
    # Mock os.listdir and os.path.isfile to simulate case-insensitive ambiguity
    def mock_listdir(path):
        if "copybooks" in path:
            return ["AMBIG.cpy", "ambig.cpy"]
        return []
    
    def mock_exists(path):
        # Prevent exact match from succeeding
        return False
        
    def mock_isfile(path):
        if "AMBIG.cpy" in path or "ambig.cpy" in path:
            return True
        return False
        
    monkeypatch.setattr(os, "listdir", mock_listdir)
    monkeypatch.setattr(os.path, "exists", mock_exists)
    monkeypatch.setattr(os.path, "isfile", mock_isfile)
    
    # Check that resolve_copybook returns None (due to ambiguity) and writes warning
    p_ambig = resolve_copybook("ambig.cpy", "/dummy_repo", ["copybooks"])
    assert p_ambig is None

def test_native_pipeline_copybook_resolution(tmpdir):
    repo_dir = str(tmpdir)
    cb_dir = tmpdir.mkdir("copybooks")
    cb_case = cb_dir.join("lgcmarea.cpy")
    cb_case.write("01 LGCMAREA PIC X.")
    
    pipeline = NativePipeline(repo_dir, str(tmpdir.join("out")))
    content = "       COPY LGCMAREA."
    result = pipeline._preprocess_cobol(content, repo_dir)
    assert "01 LGCMAREA PIC X." in result

# 7 & 8: Fixed-format comment preservation and false CALL detection prevention
def test_fixed_format_comment_preservation(tmpdir):
    # Free-format file containing comments that starts with IDENTIFICATION
    cobol_src = (
        "IDENTIFICATION DIVISION.\n"
        "PROGRAM-ID. COMMENTTEST.\n"
        "      * This is a comment at col 7\n"
        "       * Another comment at col 8\n"
        "      / Slash comment at col 7\n"
        "       DISPLAY 'HELLO'.\n"
    )
    
    # Run preprocessor shifting
    src_dir = tmpdir.mkdir("src")
    dest_dir = tmpdir.mkdir("dest")
    src_file = src_dir.join("COMMENTTEST.cob")
    src_file.write(cobol_src)
    
    # Run the preprocessor
    from cobol_migrate import preprocess_cobol_for_cobj
    norm_sources, norm_cb_dirs, norm_dir, pp_stats = preprocess_cobol_for_cobj(
        str(tmpdir), ["src/COMMENTTEST.cob"], [], fmt="fixed"
    )
    
    # Read preprocessed source file
    pp_file = os.path.join(norm_dir, "src/COMMENTTEST.cob")
    with open(pp_file, "r") as fh:
        pp_content = fh.read()
        
    lines = pp_content.splitlines()
    # Check that comment lines have comment character at exactly column 7 (index 6)
    assert lines[2][6] == "*"
    assert lines[3][6] == "*"
    assert lines[4][6] == "/"
    
    # Check that it doesn't create false dynamic CALL targets
    # (Comments are ignored, so no dynamic CALL should be detected)
    program_ids = {"src/COMMENTTEST.cob": "COMMENTTEST"}
    call_graph = build_call_graph(["src/COMMENTTEST.cob"], {"src/COMMENTTEST.cob": pp_content}, program_ids)
    assert len(call_graph["dynamic_callers"]) == 0

# 9: Legitimate dynamic CALL detection
def test_legitimate_dynamic_call():
    cobol_src = (
        "IDENTIFICATION DIVISION.\n"
        "PROGRAM-ID. DYNTEST.\n"
        "PROCEDURE DIVISION.\n"
        "    CALL SOME-VAR.\n"
    )
    program_ids = {"src/DYNTEST.cob": "DYNTEST"}
    call_graph = build_call_graph(["src/DYNTEST.cob"], {"src/DYNTEST.cob": cobol_src}, program_ids)
    assert "DYNTEST" in call_graph["dynamic_callers"]
