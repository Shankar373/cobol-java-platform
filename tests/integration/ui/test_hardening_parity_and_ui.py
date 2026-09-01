"""P2 hardening: cross-module drift guards and UI XSS regression.

- Copybook resolver parity: parser_adapter.resolve_copybooks_recursively and
  cobol_migrate.resolve_copybook are two implementations of copybook lookup.
  They must agree on which files they accept, or preprocessing (cobj path)
  and ProLeap parsing silently diverge on the same repository.

- UI XSS regression: escapeJs() historically emitted backslash-escaped text
  into HTML attribute contexts, letting uploaded filenames break out of the
  attribute (AGENTS.md §12). The fix routes through encodeURIComponent; this
  test pins the contract so it cannot silently regress.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modernize.proleap_adapter.parser_adapter import resolve_copybooks_recursively
import cobol_migrate as cm
import pytest


def _make_repo(tmp_path, cobol_body="       COPY \"SUB\".\n"):
    cob = tmp_path / "main.cob"
    cob.write_text("       IDENTIFICATION DIVISION.\n"
                   "       PROGRAM-ID. P.\n"
                   "       PROCEDURE DIVISION.\n" + cobol_body, encoding="utf-8")
    return str(cob)


def test_resolvers_agree_on_resolution(tmp_path):
    """A copybook found by one resolver must be found by the other, and a
    missing one must be reported by both."""
    (tmp_path / "SUB.cpy").write_text("       DISPLAY \"HI\".\n", encoding="utf-8")
    cob = _make_repo(tmp_path)

    # adapter resolver: returns list of MISSING names
    missing_adapter = resolve_copybooks_recursively(cob, [str(tmp_path)])
    assert "SUB" not in missing_adapter

    # engine resolver: single-level lookup via resolve_copybook
    found = cm.resolve_copybook("SUB", str(tmp_path), [str(tmp_path)])
    assert found is not None, "engine resolver could not find SUB"

    # both must agree on absence
    missing2 = resolve_copybooks_recursively(
        _make_repo(tmp_path / "_x" if False else tmp_path,
                   '       COPY "ABSENT".\n'), [str(tmp_path)])
    assert "ABSENT" in missing2
    assert cm.resolve_copybook("ABSENT", str(tmp_path), [str(tmp_path)]) is None


@pytest.mark.parametrize("fname", ["SUB.cpy", "SUB.CPY", "sub.copy"])
def test_resolvers_agree_on_extension_handling(tmp_path, fname):
    (tmp_path / fname).write_text("       DISPLAY \"X\".\n", encoding="utf-8")
    cob = _make_repo(tmp_path)
    missing_adapter = resolve_copybooks_recursively(cob, [str(tmp_path)])
    engine_found = cm.resolve_copybook("SUB", str(tmp_path), [str(tmp_path)])
    # Both resolvers must reach the same verdict for every case variant.
    assert ("SUB" not in missing_adapter) == (engine_found is not None), (
        f"resolver drift for {fname}: adapter_missing={missing_adapter} "
        f"engine_found={engine_found}")


# ---------------------------------------------------------------------------
# UI XSS regression (static contract on ui.html)
# ---------------------------------------------------------------------------

UI_HTML = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "ui.html"))


def _ui_src():
    with open(UI_HTML, encoding="utf-8") as fh:
        return fh.read()


def test_escapejs_is_attribute_context_safe():
    """escapeJs must percent-encode structural characters.

    Backslash-escaping ('\\'' -> "\\'") does NOT terminate an HTML attribute:
    the raw byte still closes the attribute, enabling stored XSS from uploaded
    filenames. encodeURIComponent emits no quotes/angle-brackets at all.
    """
    src = _ui_src()
    assert "function escapeJs(s)" in src
    body_start = src.index("function escapeJs(s)")
    body = src[body_start:src.index("}", body_start)]
    assert "encodeURIComponent" in body, (
        "escapeJs must use encodeURIComponent (attribute-context safe)")
    assert "replace(/'/" not in body and 'replace(/"/' not in body, (
        "escapeJs must not rely on backslash escaping")


def test_onclick_paths_roundtrip_through_decode():
    """Every dynamic onclick that passes user-controlled text must decode the
    value inside the handler (escapeJs encodes; handler decodes)."""
    src = _ui_src()
    assert "onclick=\"selectRun('${escapeJs(r.run_id)}')\"" in src.replace("'", '"') or \
           "selectRun('${escapeJs(r.run_id)}')" in src
    assert "path = decodeJs(path)" in src, (
        "viewArtifactContent must decode escaped paths")
    assert "runId = decodeJs(runId)" in src, (
        "selectRun must decode escaped run ids")


def test_verdict_interpolation_escaped():
    """Verdict strings rendered in the sidebar must pass through escapeHtml."""
    src = _ui_src()
    assert "escapeHtml(r.verdict || 'UNVERIFIED')" in src
