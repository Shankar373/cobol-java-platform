import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modernize.native_generator import NativeFileIOGenerator

def test_generate_io_methods_input():
    record_fields = [
        ("FIELD-A", "X(5)"),
        ("FIELD-B", "9(3)"),
        ("FIELD-C", "9(4)V99")
    ]
    res = NativeFileIOGenerator.generate_io_methods("FILE-A", "input.dat", True, record_fields)
    
    assert "private java.io.InputStream file_a_stream_in;" in res
    assert "file_a_stream_in = new java.io.BufferedInputStream(new java.io.FileInputStream(resolve_path_file_a()));" in res
    assert "field_a = new String(buf, 0, 5, java.nio.charset.StandardCharsets.ISO_8859_1);" in res
    assert "field_b = (int) new com.systema.modernized.runtime.CobolNumeric(buf, 5, 3, new com.systema.modernized.runtime.CobolNumericSpec(true, 18, 0, com.systema.modernized.runtime.CobolUsage.DISPLAY, com.systema.modernized.runtime.CobolSignPosition.TRAILING, false)).getValue().intValue();" in res
    assert "field_c.assign(new com.systema.modernized.runtime.CobolNumeric(buf, 8, 6, new com.systema.modernized.runtime.CobolNumericSpec(true, 18, 0, com.systema.modernized.runtime.CobolUsage.DISPLAY, com.systema.modernized.runtime.CobolSignPosition.TRAILING, false)).getValue());" in res

def test_generate_io_methods_output():
    record_fields = [
        ("OUT-FIELD-A", "X(10)"),
        ("OUT-FIELD-B", "9(5)")
    ]
    res = NativeFileIOGenerator.generate_io_methods("FILE-B", "output.dat", False, record_fields)
    
    assert "private java.io.OutputStream file_b_stream_out;" in res
    assert "file_b_stream_out = new java.io.BufferedOutputStream(new java.io.FileOutputStream(resolve_path_file_b()));" in res
    assert "write_file_b" in res
    assert "byte[] c_out_field_a = padString(out_field_a, 10).getBytes(java.nio.charset.StandardCharsets.ISO_8859_1);" in res

def test_sequential_preserves_trailing_spaces():
    record_fields = [
        ("OUT-FIELD-A", "X(10)"),
        ("OUT-FIELD-B", "9(5)")
    ]
    # Fixed-length SEQUENTIAL must preserve spaces (no replaceAll)
    res_seq = NativeFileIOGenerator.generate_io_methods("FILE-B", "output.dat", False, record_fields, organization="SEQUENTIAL")
    assert ".replaceAll(" not in res_seq

    # LINE SEQUENTIAL must trim spaces
    res_line_seq = NativeFileIOGenerator.generate_io_methods("FILE-B", "output.dat", False, record_fields, organization="LINE SEQUENTIAL")
    assert ".replaceAll(\"\\\\s+$\", \"\")" in res_line_seq
