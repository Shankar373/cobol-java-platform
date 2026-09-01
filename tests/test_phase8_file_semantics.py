import sys
import os
import subprocess
import tempfile
import shutil
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.utils.cobol_runner import run_cobol_code as _run_cobol_code
from modernize.lexer import CobolLexer
from modernize.parser import CobolParser
from modernize.native_generator import NativeProgramGenerator

def run_cobol_code(program_name: str, code: str, input_files: dict = None) -> tuple:
    return _run_cobol_code(program_name, code, input_files, return_full=True)

def test_file_control_parsing():
    code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. FILETEST.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT MY-FILE ASSIGN TO "input.dat"
               ORGANIZATION IS INDEXED
               ACCESS MODE IS RANDOM
               RECORD KEY IS MY-KEY
               FILE STATUS IS MY-STATUS.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 MY-STATUS PIC X(2).
       01 MY-RECORD.
          05 MY-KEY PIC X(5).
          05 MY-DATA PIC X(10).
       PROCEDURE DIVISION.
           GOBACK.
    """
    lexer = CobolLexer("FILETEST.cob")
    tokens = lexer.tokenize(code)
    print("TOKENS:", [(t.type, t.value) for t in tokens])
    parser = CobolParser(tokens, "FILETEST.cob")
    ir = parser.parse()
    
    fc_nodes = [n for n in ir.nodes.values() if n.kind == "FILE_CONTROL"]
    assert len(fc_nodes) == 1
    props = fc_nodes[0].properties
    print("PROPS:", props)
    assert props["file_name"] == "MY-FILE"
    assert props["assign_name"] == 'input.dat'
    assert props["organization"] == "INDEXED"
    assert props["access_mode"] == "RANDOM"
    assert props["record_key"] == "MY-KEY"
    assert props["status_var"] == "MY-STATUS"

def test_invalid_key_parsing():
    code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. KEYTEST.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT MY-FILE ASSIGN TO "input.dat"
               ORGANIZATION IS INDEXED
               RECORD KEY IS MY-KEY
               FILE STATUS IS MY-STATUS.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 MY-STATUS PIC X(2).
       01 MY-RECORD.
          05 MY-KEY PIC X(5).
          05 MY-DATA PIC X(10).
       PROCEDURE DIVISION.
           READ MY-FILE
               INVALID KEY MOVE "23" TO MY-STATUS
               NOT INVALID KEY MOVE "00" TO MY-STATUS
           END-READ.
           GOBACK.
    """
    lexer = CobolLexer("KEYTEST.cob")
    tokens = lexer.tokenize(code)
    parser = CobolParser(tokens, "KEYTEST.cob")
    ir = parser.parse()
    
    stmt_nodes = [n for n in ir.nodes.values() if n.kind == "STATEMENT" and n.properties.get("statement_type") == "READ"]
    assert len(stmt_nodes) == 1
    props = stmt_nodes[0].properties
    assert len(props["invalid_key_nodes"]) == 1
    assert len(props["not_invalid_key_nodes"]) == 1
    assert props["invalid_key_nodes"][0].properties["statement_type"] == "MOVE"
    assert props["not_invalid_key_nodes"][0].properties["statement_type"] == "MOVE"

def test_sequential_file_operations_success():
    code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. SEQTEST.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT IN-FILE ASSIGN TO "in.dat"
               ORGANIZATION IS LINE SEQUENTIAL
               FILE STATUS IS WS-STATUS.
           SELECT OUT-FILE ASSIGN TO "out.dat"
               ORGANIZATION IS LINE SEQUENTIAL
               FILE STATUS IS WS-STATUS.
       DATA DIVISION.
       FILE SECTION.
       FD IN-FILE.
       01 IN-REC.
          05 IN-VAL PIC X(5).
       FD OUT-FILE.
       01 OUT-REC.
          05 OUT-VAL PIC X(5).
       WORKING-STORAGE SECTION.
       01 WS-STATUS PIC X(2) VALUE "  ".
       PROCEDURE DIVISION.
           OPEN INPUT IN-FILE.
           DISPLAY "OPEN IN STATUS: " WS-STATUS.
           OPEN OUTPUT OUT-FILE.
           DISPLAY "OPEN OUT STATUS: " WS-STATUS.
           READ IN-FILE.
           DISPLAY "READ STATUS: " WS-STATUS " VAL: " IN-VAL.
           MOVE IN-VAL TO OUT-VAL.
           WRITE OUT-REC.
           DISPLAY "WRITE STATUS: " WS-STATUS.
           READ IN-FILE.
           DISPLAY "READ EOF STATUS: " WS-STATUS.
           CLOSE IN-FILE.
           DISPLAY "CLOSE IN STATUS: " WS-STATUS.
           CLOSE OUT-FILE.
           DISPLAY "CLOSE OUT STATUS: " WS-STATUS.
           GOBACK.
    """
    inputs = {"in.dat": "HELLO\n"}
    ret, stdout, stderr, java_src, outputs = run_cobol_code("SEQTEST", code, inputs)
    print("STDOUT:", stdout)
    print("STDERR:", stderr)
    assert ret == 0
    lines = [l.strip() for l in stdout.strip().splitlines()]
    assert "OPEN IN STATUS: 00" in lines
    assert "OPEN OUT STATUS: 00" in lines
    assert "READ STATUS: 00 VAL: HELLO" in lines
    assert "WRITE STATUS: 00" in lines
    assert "READ EOF STATUS: 10" in lines
    assert "CLOSE IN STATUS: 00" in lines
    assert "CLOSE OUT STATUS: 00" in lines
    assert outputs.get("out.dat") == "HELLO\n"

def test_open_input_file_not_found():
    code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. MISSINGTEST.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT IN-FILE ASSIGN TO "missing.dat"
               FILE STATUS IS WS-STATUS.
       DATA DIVISION.
       FILE SECTION.
       FD IN-FILE.
       01 IN-REC PIC X(5).
       WORKING-STORAGE SECTION.
       01 WS-STATUS PIC X(2) VALUE "  ".
       PROCEDURE DIVISION.
           OPEN INPUT IN-FILE.
           DISPLAY "OPEN STATUS: " WS-STATUS.
           GOBACK.
    """
    ret, stdout, stderr, java_src, outputs = run_cobol_code("MISSINGTEST", code)
    assert ret == 0
    lines = [l.strip() for l in stdout.strip().splitlines()]
    assert "OPEN STATUS: 35" in lines

def test_indexed_operations():
    code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. INDEXTEST.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT IDX-FILE ASSIGN TO "idx.dat"
               ORGANIZATION IS INDEXED
               ACCESS MODE IS RANDOM
               RECORD KEY IS IDX-KEY
               FILE STATUS IS WS-STATUS.
       DATA DIVISION.
       FILE SECTION.
       FD IDX-FILE.
       01 IDX-REC.
          05 IDX-KEY PIC X(5).
          05 IDX-VAL PIC X(5).
       WORKING-STORAGE SECTION.
       01 WS-STATUS PIC X(2) VALUE "  ".
       PROCEDURE DIVISION.
           OPEN OUTPUT IDX-FILE.
           MOVE "K1234" TO IDX-KEY.
           MOVE "VAL01" TO IDX-VAL.
           WRITE IDX-REC
               INVALID KEY DISPLAY "WRITE K1234 INVALID"
               NOT INVALID KEY DISPLAY "WRITE K1234 SUCCESS".
           DISPLAY "WRITE STATUS: " WS-STATUS.
           
           *> Test duplicate write
           WRITE IDX-REC
               INVALID KEY DISPLAY "WRITE DUP INVALID"
               NOT INVALID KEY DISPLAY "WRITE DUP SUCCESS".
           DISPLAY "DUP WRITE STATUS: " WS-STATUS.
           
           CLOSE IDX-FILE.
           
           OPEN INPUT IDX-FILE.
           MOVE "K1234" TO IDX-KEY.
           READ IDX-FILE
               INVALID KEY DISPLAY "READ K1234 INVALID"
               NOT INVALID KEY DISPLAY "READ K1234 SUCCESS: " IDX-VAL.
           DISPLAY "READ STATUS: " WS-STATUS.
           
           *> Test missing key
           MOVE "K9999" TO IDX-KEY.
           READ IDX-FILE
               INVALID KEY DISPLAY "READ K9999 INVALID"
               NOT INVALID KEY DISPLAY "READ K9999 SUCCESS".
           DISPLAY "MISSING READ STATUS: " WS-STATUS.
           
           CLOSE IDX-FILE.
           
           OPEN I-O IDX-FILE.
           MOVE "K1234" TO IDX-KEY.
           MOVE "VAL02" TO IDX-VAL.
           REWRITE IDX-REC
               INVALID KEY DISPLAY "REWRITE INVALID"
               NOT INVALID KEY DISPLAY "REWRITE SUCCESS".
           DISPLAY "REWRITE STATUS: " WS-STATUS.
           
           *> Test missing rewrite
           MOVE "K9999" TO IDX-KEY.
           REWRITE IDX-REC
               INVALID KEY DISPLAY "REWRITE MISSING INVALID"
               NOT INVALID KEY DISPLAY "REWRITE MISSING SUCCESS".
           DISPLAY "REWRITE MISSING STATUS: " WS-STATUS.
           
           CLOSE IDX-FILE.
           GOBACK.
    """
    ret, stdout, stderr, java_src, outputs = run_cobol_code("INDEXTEST", code)
    assert ret == 0
    lines = [l.strip() for l in stdout.strip().splitlines()]
    assert "WRITE K1234 SUCCESS" in lines
    assert "WRITE STATUS: 00" in lines
    assert "WRITE DUP INVALID" in lines
    assert "DUP WRITE STATUS: 22" in lines
    assert "READ K1234 SUCCESS: VAL01" in lines
    assert "READ STATUS: 00" in lines
    assert "READ K9999 INVALID" in lines
    assert "MISSING READ STATUS: 23" in lines
    assert "REWRITE SUCCESS" in lines
    assert "REWRITE STATUS: 00" in lines
    assert "REWRITE MISSING INVALID" in lines
    assert "REWRITE MISSING STATUS: 23" in lines
    
    # Zero dependencies check
    forbidden = ["jp.osscons", "libcobj", "CobolResolve", "opensourcecobol"]
    for word in forbidden:
        assert word not in java_src

def test_vsam_delete_and_start():
    code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. VSAMTEST.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT IDX-FILE ASSIGN TO "vsam.dat"
               ORGANIZATION IS INDEXED
               ACCESS MODE IS DYNAMIC
               RECORD KEY IS IDX-KEY
               FILE STATUS IS WS-STATUS.
       DATA DIVISION.
       FILE SECTION.
       FD IDX-FILE.
       01 IDX-REC.
          05 IDX-KEY PIC X(5).
          05 IDX-VAL PIC X(5).
       WORKING-STORAGE SECTION.
       01 WS-STATUS PIC X(2).
       PROCEDURE DIVISION.
           OPEN OUTPUT IDX-FILE.
           MOVE "K1234" TO IDX-KEY.
           MOVE "VAL01" TO IDX-VAL.
           WRITE IDX-REC.
           MOVE "K5678" TO IDX-KEY.
           MOVE "VAL02" TO IDX-VAL.
           WRITE IDX-REC.
           MOVE "K9012" TO IDX-KEY.
           MOVE "VAL03" TO IDX-VAL.
           WRITE IDX-REC.
           CLOSE IDX-FILE.

           OPEN I-O IDX-FILE.
           
           *> Test START EQUAL
           MOVE "K5678" TO IDX-KEY.
           START IDX-FILE KEY IS EQUAL TO IDX-KEY
               INVALID KEY DISPLAY "START EQUAL FAILED"
               NOT INVALID KEY DISPLAY "START EQUAL SUCCESS".
               
           READ IDX-FILE NEXT
               AT END DISPLAY "READ NEXT END"
               NOT AT END DISPLAY "READ EQUAL VAL: " IDX-VAL.

           *> Test START GREATER
           MOVE "K1234" TO IDX-KEY.
           START IDX-FILE KEY GREATER THAN IDX-KEY
               INVALID KEY DISPLAY "START GREATER FAILED"
               NOT INVALID KEY DISPLAY "START GREATER SUCCESS".
               
           READ IDX-FILE NEXT
               AT END DISPLAY "READ NEXT END"
               NOT AT END DISPLAY "READ GREATER VAL: " IDX-VAL.

           *> Test DELETE
           MOVE "K5678" TO IDX-KEY.
           DELETE IDX-FILE RECORD
               INVALID KEY DISPLAY "DELETE FAILED"
               NOT INVALID KEY DISPLAY "DELETE SUCCESS".

           *> Verify deleted record is missing
           MOVE "K5678" TO IDX-KEY.
           READ IDX-FILE
               INVALID KEY DISPLAY "READ DELETED RECORD INVALID"
               NOT INVALID KEY DISPLAY "READ DELETED RECORD SUCCESS".

           CLOSE IDX-FILE.
           GOBACK.
    """
    ret, stdout, stderr, java_src, outputs = run_cobol_code("VSAMTEST", code)
    assert ret == 0
    lines = [l.strip() for l in stdout.strip().splitlines()]
    assert "START EQUAL SUCCESS" in lines
    assert "READ EQUAL VAL: VAL02" in lines
    assert "START GREATER SUCCESS" in lines
    assert "READ GREATER VAL: VAL02" in lines
    assert "DELETE SUCCESS" in lines
    assert "READ DELETED RECORD INVALID" in lines

