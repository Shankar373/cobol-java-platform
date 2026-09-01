"""
Differential and Semantics Tests for COBOL Exponentiation (COMPUTE **)
========================================================================
Validates CobolArithmetic.power() runtime implementation and native code generator:
- Positive integer exponents (e.g. 2 ** 3 = 8, 10 ** 4 = 10000)
- Zero exponent (e.g. 5 ** 0 = 1, 0 ** 0 = 1)
- Negative integer exponents (e.g. 2 ** -2 = 0.25, 10 ** -3 = 0.001)
- Signed base exponentiation (e.g. (-3) ** 3 = -27, (-2) ** 2 = 4)
- Fractional exponent fail-fast behavior (COBOL_UNSUPPORTED_NUMERIC_FEATURE)
- Integration with COMPUTE code generation in NativeProgramGenerator
"""
import os
import shutil
import subprocess
import tempfile
import pytest

from modernize.lexer import CobolLexer
from modernize.parser import CobolParser
from modernize.native_generator import NativeProgramGenerator


def test_power_ast_and_java_code_generation():
    """Verify that COMPUTE expressions with ** are parsed into power() calls."""
    cobol_src = """000100 IDENTIFICATION DIVISION.
000200 PROGRAM-ID. POWTEST.
000300 DATA DIVISION.
000400 WORKING-STORAGE SECTION.
000500 01 WS-A PIC 9(4) VALUE 2.
000600 01 WS-B PIC S9(2) VALUE 3.
000700 01 WS-RES PIC 9(6)V99.
000800 PROCEDURE DIVISION.
000900     COMPUTE WS-RES = WS-A ** WS-B.
001000     GOBACK.
"""
    lexer = CobolLexer("POWTEST.cob", format_mode="fixed")
    tokens = lexer.tokenize(cobol_src)
    parser = CobolParser(tokens, "POWTEST.cob")
    parser.parse()

    gen = NativeProgramGenerator("POWTEST", list(parser.ir.nodes.values()), [])
    java_code = gen.generate_class_source({"POWTEST": gen})

    assert "CobolArithmetic.power" in java_code, "Native generator must emit CobolArithmetic.power for **"
    assert "ws_res.assign" in java_code


def test_cobol_arithmetic_power_java_execution():
    """Directly compile and execute CobolArithmetic.power with Java runtime assertions."""
    temp_dir = tempfile.mkdtemp(prefix="power_test_")
    try:
        # Copy only pure arithmetic runtime helper classes (independent of Spring JDBC)
        src_dir = os.path.join(temp_dir, "com", "systema", "modernized", "runtime")
        os.makedirs(src_dir, exist_ok=True)
        helpers_dir = os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "modernize", "java_helpers",
            "src", "main", "java", "com", "systema", "modernized", "runtime"
        )
        helpers_dir = os.path.abspath(helpers_dir)
        pure_arithmetic_files = [
            "CobolArithmetic.java",
            "CobolNumeric.java",
            "CobolNumericSpec.java",
            "CobolUsage.java",
            "CobolRoundingMode.java",
            "CobolSignPosition.java",
            "AssignResult.java",
            "SizeErrorPolicy.java",
            "ProhibitedRoundingException.java",
            "UnsupportedPrecisionException.java",
        ]
        for f in pure_arithmetic_files:
            src_f = os.path.join(helpers_dir, f)
            if os.path.exists(src_f):
                shutil.copy2(src_f, os.path.join(src_dir, f))

        test_runner_java = """package com.systema.modernized.runtime;
import java.math.BigDecimal;

public class PowerTestRunner {
    public static void main(String[] args) {
        // 1. Positive integer exponent
        BigDecimal p1 = CobolArithmetic.power(new BigDecimal("2"), new BigDecimal("3"));
        if (p1.compareTo(new BigDecimal("8")) != 0) {
            throw new AssertionError("Expected 2^3=8, got: " + p1);
        }

        BigDecimal p1b = CobolArithmetic.power(new BigDecimal("10"), new BigDecimal("4"));
        if (p1b.compareTo(new BigDecimal("10000")) != 0) {
            throw new AssertionError("Expected 10^4=10000, got: " + p1b);
        }

        // 2. Zero exponent
        BigDecimal p2 = CobolArithmetic.power(new BigDecimal("5"), new BigDecimal("0"));
        if (p2.compareTo(BigDecimal.ONE) != 0) {
            throw new AssertionError("Expected 5^0=1, got: " + p2);
        }

        BigDecimal p2b = CobolArithmetic.power(BigDecimal.ZERO, new BigDecimal("0"));
        if (p2b.compareTo(BigDecimal.ONE) != 0) {
            throw new AssertionError("Expected 0^0=1, got: " + p2b);
        }

        // 3. Negative integer exponent
        BigDecimal p3 = CobolArithmetic.power(new BigDecimal("2"), new BigDecimal("-2"));
        if (p3.compareTo(new BigDecimal("0.25")) != 0) {
            throw new AssertionError("Expected 2^-2=0.25, got: " + p3);
        }

        BigDecimal p3b = CobolArithmetic.power(new BigDecimal("10"), new BigDecimal("-3"));
        if (p3b.compareTo(new BigDecimal("0.001")) != 0) {
            throw new AssertionError("Expected 10^-3=0.001, got: " + p3b);
        }

        // 4. Negative base with odd and even integer exponents
        BigDecimal p4 = CobolArithmetic.power(new BigDecimal("-3"), new BigDecimal("3"));
        if (p4.compareTo(new BigDecimal("-27")) != 0) {
            throw new AssertionError("Expected (-3)^3=-27, got: " + p4);
        }

        BigDecimal p4b = CobolArithmetic.power(new BigDecimal("-2"), new BigDecimal("2"));
        if (p4b.compareTo(new BigDecimal("4")) != 0) {
            throw new AssertionError("Expected (-2)^2=4, got: " + p4b);
        }

        // 5. Fractional exponent must fail-fast with COBOL_UNSUPPORTED_NUMERIC_FEATURE
        boolean caughtFractional = false;
        try {
            CobolArithmetic.power(new BigDecimal("2"), new BigDecimal("0.5"));
        } catch (ArithmeticException e) {
            if (e.getMessage() != null && e.getMessage().contains("COBOL_UNSUPPORTED_NUMERIC_FEATURE")) {
                caughtFractional = true;
            }
        }
        if (!caughtFractional) {
            throw new AssertionError("Fractional exponent did not fail fast with COBOL_UNSUPPORTED_NUMERIC_FEATURE");
        }

        // 6. Fractional negative exponent must also fail-fast
        boolean caughtNegFractional = false;
        try {
            CobolArithmetic.power(new BigDecimal("4"), new BigDecimal("-1.5"));
        } catch (ArithmeticException e) {
            if (e.getMessage() != null && e.getMessage().contains("COBOL_UNSUPPORTED_NUMERIC_FEATURE")) {
                caughtNegFractional = true;
            }
        }
        if (!caughtNegFractional) {
            throw new AssertionError("Negative fractional exponent did not fail fast with COBOL_UNSUPPORTED_NUMERIC_FEATURE");
        }

        System.out.println("JAVA_POWER_ALL_PASSED");
    }
}
"""
        with open(os.path.join(src_dir, "PowerTestRunner.java"), "w", encoding="utf-8") as fh:
            fh.write(test_runner_java)

        java_files = [os.path.join(src_dir, f) for f in os.listdir(src_dir) if f.endswith(".java")]
        compile_res = subprocess.run(
            ["javac", "-d", temp_dir] + java_files,
            capture_output=True, text=True, timeout=30
        )
        assert compile_res.returncode == 0, f"Javac compilation failed:\n{compile_res.stderr}"

        run_res = subprocess.run(
            ["java", "-cp", temp_dir, "com.systema.modernized.runtime.PowerTestRunner"],
            capture_output=True, text=True, timeout=15
        )
        assert run_res.returncode == 0, f"Java execution failed:\n{run_res.stderr}"
        assert "JAVA_POWER_ALL_PASSED" in run_res.stdout

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
