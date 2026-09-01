"""
Regression tests for COBOL PICTURE storage/truncation semantics in the native
Java generator.

COBOL (without ROUNDED) truncates every arithmetic result to the receiver
field's PICTURE before storing it. Subsequent arithmetic reads the *stored*
(truncated) value, which is what makes chained COMPUTE correct.

The anchor regression is the payroll01-unseen off-by-one found during frontend
acceptance: PY-TAX = PY-GROSS * 0.20 must be stored as 258.64 (not the full
258.648), so that PY-NET = PY-GROSS - PY-TAX yields 1034.60.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.test_phase8_file_semantics import run_cobol_code


def _numeric_lines(stdout):
    if isinstance(stdout, str):
        stdout = stdout.splitlines()
    out = {}
    for line in stdout:
        if "=" in line:
            key, _, val = line.partition("=")
            out[key.strip()] = val.strip()
    return out


def test_payroll_chained_compute_off_by_one():
    """Exact reproduction of the payroll01-unseen defect (P0)."""
    code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PYRL.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 PY-GROSS PIC 9(6)V99.
       01 PY-TAX   PIC 9(5)V99.
       01 PY-NET   PIC 9(6)V99.
       01 RATE     PIC V99 VALUE 0.20.
       PROCEDURE DIVISION.
           MOVE 01293.24 TO PY-GROSS.
           COMPUTE PY-TAX = PY-GROSS * RATE.
           COMPUTE PY-NET = PY-GROSS - PY-TAX.
           DISPLAY "TAX=" PY-TAX.
           DISPLAY "NET=" PY-NET.
           GOBACK.
    """
    rc, out, err, _, _ = run_cobol_code("PYRL", code)
    assert rc == 0, err
    vals = _numeric_lines(out)
    # Truncated intermediate: 1293.24 * 0.20 = 258.648 -> 258.64 (PIC 9(5)V99)
    assert vals["TAX"] == "00258.64", vals
    # Reads the *stored* truncated TAX: 1293.24 - 258.64 = 1034.60
    assert vals["NET"] == "001034.60", vals


def test_chained_intermediate_storage_read():
    """A chained COMPUTE where the intermediate must be truncated before reuse."""
    code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. CHAIN.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 A PIC 9(4)V99.
       01 B PIC 9(3)V99.
       01 C PIC 9(5)V99.
       PROCEDURE DIVISION.
           MOVE 123.45 TO A.
           COMPUTE B = A / 7.
           COMPUTE C = A - B.
           DISPLAY "B=" B.
           DISPLAY "C=" C.
           GOBACK.
    """
    rc, out, err, _, _ = run_cobol_code("CHAIN", code)
    assert rc == 0, err
    vals = _numeric_lines(out)
    # 123.45 / 7 = 17.635 -> truncated to 9(3)V99 => 17.63
    assert vals["B"] == "017.63", vals
    # C uses the stored/truncated B: 123.45 - 17.63 = 105.82
    assert vals["C"] == "00105.82", vals


def test_decimal_truncation_not_rounding():
    """Non-ROUNDED truncation must drop digits, never round up."""
    code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TRUNC.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 X PIC 9(2)V99.
       01 Y PIC 9(2)V99.
       PROCEDURE DIVISION.
           MOVE 1.999 TO X.
           COMPUTE Y = X * 1.
           DISPLAY "Y=" Y.
           GOBACK.
    """
    rc, out, err, _, _ = run_cobol_code("TRUNC", code)
    assert rc == 0, err
    vals = _numeric_lines(out)
    # 1.999 truncated to 9(2)V99 => 1.99 (NOT 2.00)
    assert vals["Y"] == "01.99", vals


def test_integer_pic_left_truncation():
    """Value exceeding the integer capacity truncates most-significant digits."""
    code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. LEFTT.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 W PIC 9(3).
       PROCEDURE DIVISION.
           COMPUTE W = 1234 + 0.
           DISPLAY "W=" W.
           GOBACK.
     """
    rc, out, err, _, _ = run_cobol_code("LEFTT", code)
    assert rc == 0, err
    vals = _numeric_lines(out)
    # 1234 stored in PIC 9(3) -> 234
    assert vals["W"] == "234", vals


def test_different_pic_precisions():
    """Truncation is generic across PIC precisions / USAGE."""
    # (pic, expression, expected_display)
    cases = [
        ("9(3)V999", "1.23456", "001.234"),   # 1.23456 -> 1.234
        ("9(4)V99",  "12.349",  "0012.34"),   # 12.349  -> 12.34
        ("9(2)V9",   "5.678",   "05.6"),      # 5.678   -> 5.6
    ]
    for pic, expr, expected in cases:
        code = f"""
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PICX.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 FLD PIC {pic}.
       PROCEDURE DIVISION.
           COMPUTE FLD = {expr}.
           DISPLAY "F=" FLD.
           GOBACK."""
        rc, out, err, _, _ = run_cobol_code("PICX", code)
        assert rc == 0, err
        vals = _numeric_lines(out)
        assert vals["F"] == expected, f"PIC {pic}: got {vals.get('F')} expected {expected}"


def test_signed_truncation_via_subtraction():
    """Signed field truncation (negative result) keeps sign and truncates."""
    code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. SNEG.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 FLD PIC S9(2)V99.
       PROCEDURE DIVISION.
           COMPUTE FLD = 0 - 3.149.
           DISPLAY "F=" FLD.
           GOBACK.
    """
    rc, out, err, _, _ = run_cobol_code("SNEG", code)
    assert rc == 0, err
    vals = _numeric_lines(out)
    # 0 - 3.149 = -3.149 -> truncated to S9(2)V99 => -3.14
    assert vals["F"] == "-03.14", vals


def test_multiplication_scale_truncation():
    """Product scale must be truncated to the receiver PIC scale."""
    code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. MULTS.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 P PIC 9(5)V99.
       01 Q PIC 9(3)V99.
       01 R PIC 9(4)V99.
       PROCEDURE DIVISION.
           MOVE 12.34 TO P.
           MOVE 5.67 TO Q.
           COMPUTE R = P * Q.
           DISPLAY "R=" R.
           GOBACK.
    """
    rc, out, err, _, _ = run_cobol_code("MULTS", code)
    assert rc == 0, err
    vals = _numeric_lines(out)
    # 12.34 * 5.67 = 69.9678 -> truncated to 9(4)V99 => 69.96
    assert vals["R"] == "0069.96", vals


def test_add_subtract_truncation():
    """ADD/SUBTRACT results are also truncated to the receiver PIC."""
    code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ADDSUB.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 A PIC 9(3)V99.
       01 B PIC 9(3)V99.
       01 C PIC 9(3)V99.
       PROCEDURE DIVISION.
           MOVE 10.55 TO A.
           MOVE 20.66 TO B.
           ADD A TO B GIVING C.
           DISPLAY "C=" C.
           GOBACK.
    """
    rc, out, err, _, _ = run_cobol_code("ADDSUB", code)
    assert rc == 0, err
    vals = _numeric_lines(out)
    # 20.66 + 10.55 = 31.21 (exact, but path through truncation still correct)
    assert vals["C"] == "031.21", vals
