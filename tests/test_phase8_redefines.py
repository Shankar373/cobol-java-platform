import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest
from modernize.lexer import CobolLexer
from modernize.parser import CobolParser
from modernize.native_generator import NativeProgramGenerator


def parse_and_gen(cobol_source, prog_name="TEST"):
    padded = "\n".join("       " + line if not line.startswith(" ") else line for line in cobol_source.splitlines())
    tokens = CobolLexer(prog_name + ".cob").tokenize(padded)
    ir = CobolParser(tokens, prog_name + ".cob").parse()
    gen = NativeProgramGenerator(prog_name, list(ir.nodes.values()))
    return gen, gen.generate_class_source()


def parse_ir(cobol_source, prog_name="T"):
    padded = "\n".join("       " + line if not line.startswith(" ") else line for line in cobol_source.splitlines())
    tokens = CobolLexer(prog_name + ".cob").tokenize(padded)
    ir = CobolParser(tokens, prog_name + ".cob").parse()
    return list(ir.nodes.values())


# ---------------------------------------------------------------------------
# 1. Parser — redefines metadata captured
# ---------------------------------------------------------------------------

class TestParserRedefinesMeta:
    def test_redefines_property_captured(self):
        cobol = (
            "IDENTIFICATION DIVISION. PROGRAM-ID. T.\n"
            "DATA DIVISION. WORKING-STORAGE SECTION.\n"
            "01 R. 05 WA PIC X(4). 05 WB REDEFINES WA PIC 9(4).\n"
            "PROCEDURE DIVISION. P. STOP RUN."
        )
        nodes = parse_ir(cobol)
        items = {n.properties["name"]: n for n in nodes if n.kind == "DATA_ITEM"}
        assert items["WB"].properties.get("redefines") == "WA"

    def test_odo_min_max_captured(self):
        cobol = (
            "IDENTIFICATION DIVISION. PROGRAM-ID. T.\n"
            "DATA DIVISION. WORKING-STORAGE SECTION.\n"
            "01 D. 05 C PIC 9(2). 05 I PIC X(3) OCCURS 1 TO 5 DEPENDING ON C.\n"
            "PROCEDURE DIVISION. P. STOP RUN."
        )
        nodes = parse_ir(cobol)
        items = {n.properties["name"]: n for n in nodes if n.kind == "DATA_ITEM"}
        assert items["I"].properties.get("occurs_min") == 1
        assert items["I"].properties.get("occurs_max") == 5
        assert items["I"].properties.get("depending_on") == "C"


# ---------------------------------------------------------------------------
# 2. Layout offsets
# ---------------------------------------------------------------------------

class TestLayoutOffsets:
    def test_same_offset_for_redefines(self):
        cobol = (
            "IDENTIFICATION DIVISION. PROGRAM-ID. T.\n"
            "DATA DIVISION. WORKING-STORAGE SECTION.\n"
            "01 R. 05 WA PIC X(4). 05 WB REDEFINES WA PIC 9(4).\n"
            "PROCEDURE DIVISION. P. STOP RUN."
        )
        gen, _ = parse_and_gen(cobol, "T")
        la = gen.redefines_layout.get("WA")
        lb = gen.redefines_layout.get("WB")
        assert la is not None, "WA not in redefines_layout"
        assert lb is not None, "WB not in redefines_layout"
        assert la["offset"] == 0 and lb["offset"] == 0
        assert la["length"] == 4 and lb["length"] == 4

    def test_second_field_correct_offset(self):
        cobol = (
            "IDENTIFICATION DIVISION. PROGRAM-ID. T.\n"
            "DATA DIVISION. WORKING-STORAGE SECTION.\n"
            "01 R. 05 F1 PIC X(3). 05 F2 PIC 9(5). 05 F3 REDEFINES F2 PIC X(5).\n"
            "PROCEDURE DIVISION. P. STOP RUN."
        )
        gen, _ = parse_and_gen(cobol, "T")
        assert gen.redefines_layout["F2"]["offset"] == 3
        assert gen.redefines_layout["F3"]["offset"] == 3

    def test_backing_store_correct_size(self):
        cobol = (
            "IDENTIFICATION DIVISION. PROGRAM-ID. T.\n"
            "DATA DIVISION. WORKING-STORAGE SECTION.\n"
            "01 R. 05 A PIC X(3). 05 B PIC 9(5). 05 C REDEFINES A PIC X(3).\n"
            "PROCEDURE DIVISION. P. STOP RUN."
        )
        gen, _ = parse_and_gen(cobol, "T")
        assert gen.redefined_records_backing.get("R") == 8


# ---------------------------------------------------------------------------
# 3. Backing storage in generated Java
# ---------------------------------------------------------------------------

class TestBackingStorage:
    def test_char_array_emitted(self):
        cobol = (
            "IDENTIFICATION DIVISION. PROGRAM-ID. T.\n"
            "DATA DIVISION. WORKING-STORAGE SECTION.\n"
            "01 R. 05 WA PIC X(8). 05 WB REDEFINES WA PIC 9(8).\n"
            "PROCEDURE DIVISION. P. STOP RUN."
        )
        _, java = parse_and_gen(cobol)
        assert "byte[]" in java and "_backing" in java

    def test_no_independent_field_for_redefines(self):
        cobol = (
            "IDENTIFICATION DIVISION. PROGRAM-ID. T.\n"
            "DATA DIVISION. WORKING-STORAGE SECTION.\n"
            "01 R. 05 WA PIC X(8). 05 WB REDEFINES WA PIC 9(8).\n"
            "PROCEDURE DIVISION. P. STOP RUN."
        )
        _, java = parse_and_gen(cobol)
        assert "public String wa " not in java
        assert "public String wb " not in java

    def test_backing_initialized_to_spaces(self):
        cobol = (
            "IDENTIFICATION DIVISION. PROGRAM-ID. T.\n"
            "DATA DIVISION. WORKING-STORAGE SECTION.\n"
            "01 R. 05 WA PIC X(4). 05 WB REDEFINES WA PIC 9(4).\n"
            "PROCEDURE DIVISION. P. STOP RUN."
        )
        _, java = parse_and_gen(cobol)
        assert "Arrays.fill(" in java

    def test_correct_backing_length(self):
        cobol = (
            "IDENTIFICATION DIVISION. PROGRAM-ID. T.\n"
            "DATA DIVISION. WORKING-STORAGE SECTION.\n"
            "01 R. 05 A PIC X(3). 05 B PIC 9(5). 05 C REDEFINES A PIC X(3).\n"
            "PROCEDURE DIVISION. P. STOP RUN."
        )
        _, java = parse_and_gen(cobol)
        assert "new byte[8]" in java


# ---------------------------------------------------------------------------
# 4. Accessor generation
# ---------------------------------------------------------------------------

class TestAccessors:
    def test_getters_and_setters_generated(self):
        cobol = (
            "IDENTIFICATION DIVISION. PROGRAM-ID. T.\n"
            "DATA DIVISION. WORKING-STORAGE SECTION.\n"
            "01 R. 05 WA PIC X(5). 05 WB REDEFINES WA PIC X(5).\n"
            "PROCEDURE DIVISION. P. STOP RUN."
        )
        _, java = parse_and_gen(cobol)
        assert "get_wa()" in java
        assert "set_wa(String val)" in java
        assert "get_wb()" in java
        assert "set_wb(String val)" in java

    def test_setter_writes_into_backing(self):
        cobol = (
            "IDENTIFICATION DIVISION. PROGRAM-ID. T.\n"
            "DATA DIVISION. WORKING-STORAGE SECTION.\n"
            "01 R. 05 WA PIC X(4). 05 WB REDEFINES WA PIC X(4).\n"
            "PROCEDURE DIVISION. P. STOP RUN."
        )
        _, java = parse_and_gen(cobol)
        assert "System.arraycopy(" in java
        assert "getBytes(" in java

    def test_getter_reads_from_backing(self):
        cobol = (
            "IDENTIFICATION DIVISION. PROGRAM-ID. T.\n"
            "DATA DIVISION. WORKING-STORAGE SECTION.\n"
            "01 R. 05 WA PIC X(4). 05 WB REDEFINES WA PIC X(4).\n"
            "PROCEDURE DIVISION. P. STOP RUN."
        )
        _, java = parse_and_gen(cobol)
        assert "new String(" in java
        assert "_backing" in java


# ---------------------------------------------------------------------------
# 5. Statement integration
# ---------------------------------------------------------------------------

class TestStatements:
    def test_move_to_redefined_uses_setter(self):
        cobol = (
            "IDENTIFICATION DIVISION. PROGRAM-ID. T.\n"
            "DATA DIVISION. WORKING-STORAGE SECTION.\n"
            "01 R. 05 WA PIC X(4). 05 WB REDEFINES WA PIC X(4).\n"
            "PROCEDURE DIVISION. P. MOVE SPACES TO WA. STOP RUN."
        )
        _, java = parse_and_gen(cobol)
        assert "set_wa(" in java

    def test_move_from_redefine_uses_getter(self):
        cobol = (
            "IDENTIFICATION DIVISION. PROGRAM-ID. T.\n"
            "DATA DIVISION. WORKING-STORAGE SECTION.\n"
            "01 R. 05 WA PIC X(4). 05 WB REDEFINES WA PIC X(4).\n"
            "01 O PIC X(4).\n"
            "PROCEDURE DIVISION. P. MOVE WB TO O. STOP RUN."
        )
        _, java = parse_and_gen(cobol)
        assert "get_wb()" in java


# ---------------------------------------------------------------------------
# 6. ODO — checkBounds emission
# ---------------------------------------------------------------------------

class TestCheckBounds:
    def test_checkbounds_emitted_for_odo(self):
        cobol = (
            "IDENTIFICATION DIVISION. PROGRAM-ID. T.\n"
            "DATA DIVISION. WORKING-STORAGE SECTION.\n"
            "01 D. 05 C PIC 9(2). 05 I PIC X(3) OCCURS 1 TO 5 DEPENDING ON C.\n"
            "PROCEDURE DIVISION. P. STOP RUN."
        )
        _, java = parse_and_gen(cobol)
        assert "checkBounds" in java
        assert "IndexOutOfBoundsException" in java


# ---------------------------------------------------------------------------
# 7. Layout completeness
# ---------------------------------------------------------------------------

class TestLayoutCompleteness:
    def test_both_sides_in_layout(self):
        cobol = (
            "IDENTIFICATION DIVISION. PROGRAM-ID. T.\n"
            "DATA DIVISION. WORKING-STORAGE SECTION.\n"
            "01 R. 05 WA PIC X(4). 05 WB REDEFINES WA PIC 9(4).\n"
            "PROCEDURE DIVISION. P. STOP RUN."
        )
        gen, _ = parse_and_gen(cobol, "T")
        assert "WA" in gen.redefines_layout
        assert "WB" in gen.redefines_layout
