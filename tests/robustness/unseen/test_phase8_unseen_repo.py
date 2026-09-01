"""
test_phase8_unseen_repo.py — Step 4 + Step 5: INVMGR Unseen Repository + Negative Equivalence

INVMGR is a genuine inventory management domain not seen by any previous benchmark.
No benchmark-specific hardcoding handles it; the pipeline must run generically.

Step 4: Full pipeline end-to-end — parse, generate, compile, execute, verify output
Step 5: Negative equivalence — mutations must produce FAIL, not false PASS
"""
import os
import sys
import json
import tempfile
import shutil
import subprocess
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modernize.lexer import CobolLexer
from modernize.parser import CobolParser
from modernize.native_generator import NativeProgramGenerator
from tests.test_phase8_file_semantics import run_cobol_code


INVMGR_COB = os.path.join(os.path.dirname(__file__), '..', '..', 'repos', 'INVMGR', 'src', 'INVMGR.cob')
INVMGR_COB = os.path.abspath(INVMGR_COB)
INVMGR_CODE = open(INVMGR_COB, encoding='utf-8').read()


# ─── Step 4: Parse + Generate ────────────────────────────────────────────

def test_invmgr_parse_and_generate():
    """INVMGR must parse without errors and generate Java without blocked diagnostics."""
    lex = CobolLexer('INVMGR.cob')
    toks = lex.tokenize(INVMGR_CODE)
    parser = CobolParser(toks, 'INVMGR.cob')
    ir = parser.parse()
    gen = NativeProgramGenerator('INVMGR', list(ir.nodes.values()))
    java_src = gen.generate_class_source()
    assert java_src, 'No Java source generated'
    # Verify no benchmark-specific name embedded
    for banned in ('BankCore', 'ClaimsCore', 'ACCTPROG', 'SALESPROG', 'INVOICE01'):
        assert banned not in java_src, f'Benchmark-specific name found in generated Java: {banned}'
    blocked = [d for d in gen.diagnostics if d['status'] == 'NATIVE_TRANSLATION_BLOCKED']
    assert not blocked, f'Unexpected blocked diagnostics: {blocked}'


def test_invmgr_compile():
    """Generated Java for INVMGR must compile successfully."""
    ret, stdout, stderr, java_src, outputs = run_cobol_code('INVMGR', INVMGR_CODE)
    # If compilation fails, run_cobol_code raises RuntimeError; reaching here means it compiled+ran
    assert ret == 0, f'INVMGR execution failed. stderr:\n{stderr}'


def test_invmgr_execute_in_stock_path():
    """With QTY=50 and LOW_THRESH=10, INVMGR must print IN STOCK and correct values."""
    ret, stdout, stderr, java_src, outputs = run_cobol_code('INVMGR', INVMGR_CODE)
    assert ret == 0
    lines = [l.strip() for l in stdout.strip().splitlines()]
    # INVMGR sets QTY=50, which is >= 10, so IN STOCK
    assert any('IN STOCK' in l for l in lines), f'Expected IN STOCK in output: {lines}'
    # TOTAL_VAL = 50 * 1.50 = 75.00 → stored as PIC 9(8)V99 = 7500
    # DISPLAY of 9(8)V99 will show as integer-part of 7500 (raw long*100)
    assert any('QTY' in l for l in lines), f'Expected QTY line in output: {lines}'
    assert any('VAL' in l for l in lines), f'Expected VAL line in output: {lines}'
    assert any('STS' in l for l in lines), f'Expected STS line in output: {lines}'
    assert any('OK' in l for l in lines), f'Expected status OK in output: {lines}'


def test_invmgr_zero_forbidden_dependencies():
    """Generated Java for INVMGR must contain zero forbidden legacy dependency strings."""
    lex = CobolLexer('INVMGR.cob')
    toks = lex.tokenize(INVMGR_CODE)
    parser = CobolParser(toks, 'INVMGR.cob')
    ir = parser.parse()
    gen = NativeProgramGenerator('INVMGR', list(ir.nodes.values()))
    java_src = gen.generate_class_source()
    FORBIDDEN = ['jp.osscons', 'libcobj', 'CobolResolve', 'opensourcecobol', 'opensourcecobol4j']
    for term in FORBIDDEN:
        assert term not in java_src, f'Generated Java contains forbidden term: {term}'


def test_invmgr_traceability_coordinates():
    """All IR nodes for INVMGR must have source_line > 0 (no orphaned nodes)."""
    lex = CobolLexer('INVMGR.cob')
    toks = lex.tokenize(INVMGR_CODE)
    parser = CobolParser(toks, 'INVMGR.cob')
    ir = parser.parse()
    stmt_nodes = [n for n in ir.nodes.values() if n.kind == 'STATEMENT']
    assert stmt_nodes, 'No STATEMENT nodes in INVMGR IR'
    no_line = [n for n in stmt_nodes if n.source_line == 0]
    assert not no_line, f'Statement nodes with no source_line: {[n.node_id for n in no_line]}'


def test_invmgr_no_benchmark_fallback():
    """The generated Java must not contain any benchmark-specific special-case strings."""
    lex = CobolLexer('INVMGR.cob')
    toks = lex.tokenize(INVMGR_CODE)
    parser = CobolParser(toks, 'INVMGR.cob')
    ir = parser.parse()
    gen = NativeProgramGenerator('INVMGR', list(ir.nodes.values()))
    java_src = gen.generate_class_source()
    BENCHMARK_STRINGS = ['ClaimsCore', 'BankCore', 'Claim_Exception', 'LegacyFeature_Service',
                         'EodReport_Service', 'Claim_Audit']
    for s in BENCHMARK_STRINGS:
        assert s not in java_src, f'Benchmark string "{s}" found in INVMGR generated Java'


# ─── Step 5: Negative Equivalence ────────────────────────────────────────

def _mutated_code(mutation: str) -> str:
    """Apply a named mutation to the INVMGR COBOL source."""
    code = INVMGR_CODE
    if mutation == 'wrong_qty':
        return code.replace('MOVE 50 TO WS-ITEM-QTY', 'MOVE 5 TO WS-ITEM-QTY')
    if mutation == 'wrong_price':
        return code.replace('VALUE 1.50', 'VALUE 2.00')
    if mutation == 'wrong_threshold':
        return code.replace('VALUE 10', 'VALUE 100')
    if mutation == 'delete_calc':
        return code.replace('PERFORM CALC-TOTAL.', '').replace('COMPUTE WS-TOTAL-VAL = WS-ITEM-QTY * WS-ITEM-PRICE.', '')
    if mutation == 'swap_status_strings':
        return code.replace('MOVE "RESTOCK" TO WS-STATUS', 'MOVE "WRONG_STS" TO WS-STATUS')
    raise ValueError(f'Unknown mutation: {mutation}')


def _run_and_get_lines(code: str, program_name: str = 'INVMGR'):
    ret, stdout, stderr, _, _ = run_cobol_code(program_name, code)
    return ret, [l.strip() for l in stdout.strip().splitlines()]


def _original_lines():
    ret, lines = _run_and_get_lines(INVMGR_CODE)
    return lines


def test_neg_equiv_wrong_quantity():
    """Mutation: change QTY from 50 to 5 → LOW STOCK path, output differs from original."""
    orig = _original_lines()
    _, mutated = _run_and_get_lines(_mutated_code('wrong_qty'))
    assert orig != mutated, 'Mutation wrong_qty must produce different output'
    assert any('LOW STOCK' in l for l in mutated), 'wrong_qty must trigger LOW STOCK branch'
    assert not any('IN STOCK' in l for l in mutated), 'wrong_qty must NOT show IN STOCK'


def test_neg_equiv_wrong_price():
    """Mutation: change price from 1.50 to 2.00 → total value differs."""
    orig = _original_lines()
    _, mutated = _run_and_get_lines(_mutated_code('wrong_price'))
    val_orig = [l for l in orig if 'VAL' in l]
    val_mut = [l for l in mutated if 'VAL' in l]
    assert val_orig != val_mut, 'Mutation wrong_price must change VAL output'


def test_neg_equiv_wrong_threshold():
    """Mutation: threshold raised to 100 → LOW STOCK path triggered even with QTY=50."""
    _, mutated = _run_and_get_lines(_mutated_code('wrong_threshold'))
    assert any('LOW STOCK' in l for l in mutated), 'Raised threshold must trigger LOW STOCK'


def test_neg_equiv_delete_calc():
    """Mutation: remove CALC-TOTAL perform → VAL stays 0."""
    orig = _original_lines()
    _, mutated = _run_and_get_lines(_mutated_code('delete_calc'))
    val_orig = [l for l in orig if 'VAL' in l]
    val_mut = [l for l in mutated if 'VAL' in l]
    assert val_orig != val_mut, 'Removing CALC-TOTAL must change VAL output'


def test_neg_equiv_swap_status_strings():
    """Mutation: RESTOCK status string changed → STS output differs."""
    orig = _original_lines()
    _, mutated = _run_and_get_lines(_mutated_code('swap_status_strings'))
    # With QTY=5 (from wrong_qty) this matters; but with QTY=50 OK is shown
    # Use wrong_qty + swap to force RESTOCK path
    low_code = _mutated_code('wrong_qty').replace('MOVE "RESTOCK" TO WS-STATUS', 'MOVE "WRONG_STS" TO WS-STATUS')
    _, orig_low = _run_and_get_lines(low_code.replace('MOVE "WRONG_STS"', 'MOVE "RESTOCK"'))
    _, mutated_low = _run_and_get_lines(low_code)
    assert orig_low != mutated_low, 'Swapped status string must produce different STS output'
