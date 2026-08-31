"""Unit tests for the native Java type mapper."""
import pytest
from generators.native_java.types import parse_pic, map_data_item, to_java_var, to_java_class


class TestParsePic:
    def test_pic_x10(self):
        signed, digits, scale, edited = parse_pic("X(10)")
        assert not signed
        assert digits == 0
        assert scale == 0

    def test_pic_9_5(self):
        signed, digits, scale, edited = parse_pic("9(5)")
        assert not signed
        assert digits == 5
        assert scale == 0

    def test_pic_s9_9_comp(self):
        signed, digits, scale, edited = parse_pic("S9(9)")
        assert signed
        assert digits == 9

    def test_pic_decimal(self):
        signed, digits, scale, edited = parse_pic("9(7)V99")
        assert digits == 9
        assert scale == 2

    def test_pic_comp3(self):
        signed, digits, scale, edited = parse_pic("S9(5)V9(2)")
        assert signed
        assert scale == 2


class TestMapDataItem:
    def test_alpha_field(self):
        ti = map_data_item("X(10)", "DISPLAY")
        assert ti.java_type == "String"
        assert ti.is_alpha
        assert not ti.is_numeric

    def test_display_numeric(self):
        ti = map_data_item("9(5)", "DISPLAY")
        assert ti.java_type == "int"
        assert ti.is_numeric

    def test_comp3_field(self):
        ti = map_data_item("S9(7)V99", "COMP-3")
        assert "BigDecimal" in ti.java_type
        assert ti.is_comp3

    def test_comp_field(self):
        ti = map_data_item("S9(9)", "COMP")
        assert ti.java_type in ("int", "long")
        assert ti.is_numeric


class TestJavaNameConversions:
    def test_cobol_to_var(self):
        assert to_java_var("WS-COUNTER") == "ws_counter"
        assert to_java_var("WS-STATUS") == "ws_status"

    def test_reserved_word_escaping(self):
        # 'class' is a Java reserved word
        result = to_java_var("CLASS")
        assert result == "class_"

    def test_to_java_class(self):
        assert to_java_class("PAYMAIN") == "Paymain"
        assert to_java_class("DB2-SELECT") == "Db2Select"

    def test_subscript(self):
        result = to_java_var("ITEM-AMOUNT(3)")
        assert "[2]" in result  # COBOL 1-indexed -> Java 0-indexed

    def test_ref_mod(self):
        result = to_java_var("WS-STATUS(1:4)")
        assert "substring(0, 4)" in result

