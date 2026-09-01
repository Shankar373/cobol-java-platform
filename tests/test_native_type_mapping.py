import sys
import os

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modernize.native_generator import NativeTypeMapper

def test_type_mapper_pic_x():
    java_type = NativeTypeMapper.get_java_type("X(10)")
    assert java_type == "String"
    
    java_type_xx = NativeTypeMapper.get_java_type("XX")
    assert java_type_xx == "String"

def test_type_mapper_pic_9():
    java_type_9 = NativeTypeMapper.get_java_type("9(5)")
    assert java_type_9 == "Integer"
    
    java_type_9_large = NativeTypeMapper.get_java_type("9(12)")
    assert java_type_9_large == "Long"

def test_type_mapper_pic_decimal():
    java_type_v = NativeTypeMapper.get_java_type("9(8)V99")
    assert java_type_v == "BigDecimal"
    
    java_type_sv = NativeTypeMapper.get_java_type("S9(7)V9(3)")
    assert java_type_sv == "BigDecimal"

def test_type_mapper_comp3():
    java_type_comp3 = NativeTypeMapper.get_java_type("9(7)V99", "COMP-3")
    assert java_type_comp3 == "BigDecimal"
