import os
import tempfile
import pytest
from modernize.proleap_adapter.parser_adapter import ProLeapParserAdapter, resolve_copybooks_recursively

def test_resolve_copybooks_success():
    with tempfile.TemporaryDirectory() as tmpdir:
        cob_path = os.path.join(tmpdir, "main.cob")
        with open(cob_path, "w") as f:
            f.write("       IDENTIFICATION DIVISION.\n       PROGRAM-ID. MAIN.\n       PROCEDURE DIVISION.\n           COPY \"SUB\".\n")
        
        sub_path = os.path.join(tmpdir, "SUB.cpy")
        with open(sub_path, "w") as f:
            f.write("           DISPLAY \"HELLO\".\n")
            
        missing = resolve_copybooks_recursively(cob_path, [tmpdir])
        assert not missing

def test_resolve_nested_copybooks():
    with tempfile.TemporaryDirectory() as tmpdir:
        cob_path = os.path.join(tmpdir, "main.cob")
        with open(cob_path, "w") as f:
            f.write("       COPY \"A\".\n")
            
        a_path = os.path.join(tmpdir, "A.cpy")
        with open(a_path, "w") as f:
            f.write("       COPY \"B\".\n")
            
        b_path = os.path.join(tmpdir, "B.cpy")
        with open(b_path, "w") as f:
            f.write("       DISPLAY \"B\".\n")
            
        missing = resolve_copybooks_recursively(cob_path, [tmpdir])
        assert not missing

def test_resolve_missing_copybook():
    with tempfile.TemporaryDirectory() as tmpdir:
        cob_path = os.path.join(tmpdir, "main.cob")
        with open(cob_path, "w") as f:
            f.write("       COPY \"MISSING\".\n")
            
        missing = resolve_copybooks_recursively(cob_path, [tmpdir])
        assert "MISSING" in missing

def test_resolve_duplicate_copybooks_recursion_protection():
    with tempfile.TemporaryDirectory() as tmpdir:
        cob_path = os.path.join(tmpdir, "main.cob")
        with open(cob_path, "w") as f:
            f.write("       COPY \"A\".\n")
            
        a_path = os.path.join(tmpdir, "A.cpy")
        with open(a_path, "w") as f:
            f.write("       COPY \"A\".\n")
            
        missing = resolve_copybooks_recursively(cob_path, [tmpdir])
        assert not missing  # Should not result in stack overflow / infinite loop

def test_resolve_invalid_copybook():
    with tempfile.TemporaryDirectory() as tmpdir:
        cob_path = os.path.join(tmpdir, "main.cob")
        with open(cob_path, "w") as f:
            f.write("       COPY \"BAD\".\n")
            
        # Create BAD directory instead of file to trigger read error
        os.makedirs(os.path.join(tmpdir, "BAD.cpy"), exist_ok=True)
        
        missing = resolve_copybooks_recursively(cob_path, [tmpdir])
        assert "BAD" in missing

def _proleap_jars_available() -> bool:
    """Guard MUST mirror the adapter's exact requirement list.

    REGRESSION: this previously checked only 2 of the 7 required JARs, so a
    half-seeded environment ran the test and failed inside parse() with
    PROLEAP_UNAVAILABLE instead of exercising the missing-copybook path.
    The list now comes from the adapter itself (single source of truth).
    """
    required = ProLeapParserAdapter.required_proleap_jars()
    return all(os.path.exists(p) for p in required)


@pytest.mark.skipif(
    not _proleap_jars_available(),
    reason=(
        "ENVIRONMENT_BLOCKED: ProLeap runtime JARs not in .m2 cache. "
        "Seed deterministically with: mvn -B -f docker/maven-proleap-seed-pom.xml dependency:resolve"
    ),
)
def test_copybook_adapter_missing_fails_cleanly():
    with tempfile.TemporaryDirectory() as tmpdir:
        cob_path = os.path.join(tmpdir, "main.cob")
        with open(cob_path, "w") as f:
            f.write("       COPY \"NOTFOUND\".\n")
            
        adapter = ProLeapParserAdapter(cob_path)
        ir = adapter.parse()
        assert adapter.status == "FAILURE"
        assert ir.status == "FAILURE"
        assert any("PROLEAP_MISSING_COPYBOOK" in d.detail for d in adapter.diagnostics)

