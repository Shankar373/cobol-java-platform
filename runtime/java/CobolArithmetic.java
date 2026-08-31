package com.systema.modernized.runtime;

import java.math.BigDecimal;
import java.math.MathContext;

public class CobolArithmetic {
    private static final MathContext MC = MathContext.DECIMAL128;

    public static void checkPrecision(int totalDigits, int scale) {
        // totalDigits (integer + scale) + guard digits (9) cannot exceed 34
        if (totalDigits + 9 > 34) {
            throw new UnsupportedPrecisionException("Unsupported precision: target total digits + guard digits exceed 34 intermediate precision");
        }
    }

    public static BigDecimal add(BigDecimal a, BigDecimal b) {
        return a.add(b);
    }

    public static BigDecimal add(CobolNumeric a, CobolNumeric b) {
        return a.getValue().add(b.getValue());
    }

    public static BigDecimal add(CobolNumeric a, BigDecimal b) {
        return a.getValue().add(b);
    }

    public static BigDecimal add(BigDecimal a, CobolNumeric b) {
        return a.add(b.getValue());
    }

    public static BigDecimal subtract(BigDecimal a, BigDecimal b) {
        return a.subtract(b);
    }

    public static BigDecimal subtract(CobolNumeric a, CobolNumeric b) {
        return a.getValue().subtract(b.getValue());
    }

    public static BigDecimal subtract(CobolNumeric a, BigDecimal b) {
        return a.getValue().subtract(b);
    }

    public static BigDecimal subtract(BigDecimal a, CobolNumeric b) {
        return a.subtract(b.getValue());
    }

    public static BigDecimal multiply(BigDecimal a, BigDecimal b) {
        return a.multiply(b);
    }

    public static BigDecimal multiply(CobolNumeric a, CobolNumeric b) {
        return a.getValue().multiply(b.getValue());
    }

    public static BigDecimal multiply(CobolNumeric a, BigDecimal b) {
        return a.getValue().multiply(b);
    }

    public static BigDecimal multiply(BigDecimal a, CobolNumeric b) {
        return a.multiply(b.getValue());
    }

    public static BigDecimal divide(BigDecimal a, BigDecimal b) {
        // Divisor zero pre-check is handled in the generated statements to avoid catch-based control flow (C1)
        return a.divide(b, MC);
    }

    public static BigDecimal divide(CobolNumeric a, CobolNumeric b) {
        return a.getValue().divide(b.getValue(), MC);
    }

    public static BigDecimal divide(CobolNumeric a, BigDecimal b) {
        return a.getValue().divide(b, MC);
    }

    public static BigDecimal divide(BigDecimal a, CobolNumeric b) {
        return a.divide(b.getValue(), MC);
    }

    public static BigDecimal remainder(BigDecimal dividend, BigDecimal divisor, BigDecimal quotient) {
        BigDecimal truncatedQuotient = quotient.setScale(0, java.math.RoundingMode.DOWN);
        return dividend.subtract(truncatedQuotient.multiply(divisor));
    }

    public static BigDecimal remainder(CobolNumeric dividend, CobolNumeric divisor, CobolNumeric quotient) {
        return remainder(dividend.getValue(), divisor.getValue(), quotient.getValue());
    }

    public static BigDecimal remainder(BigDecimal dividend, CobolNumeric divisor, BigDecimal quotient) {
        return remainder(dividend, divisor.getValue(), quotient);
    }

    public static BigDecimal remainder(BigDecimal dividend, BigDecimal divisor, CobolNumeric quotient) {
        return remainder(dividend, divisor, quotient.getValue());
    }

    public static BigDecimal power(BigDecimal a, BigDecimal b) {
        try {
            int exponent = b.intValueExact();
            if (exponent < 0) {
                BigDecimal basePow = a.pow(-exponent, MC);
                return BigDecimal.ONE.divide(basePow, MC);
            }
            return a.pow(exponent, MC);
        } catch (ArithmeticException e) {
            throw new ArithmeticException("COBOL_UNSUPPORTED_NUMERIC_FEATURE: Fractional or out-of-range exponentiation (" + a + " ** " + b + ") is unsupported under no-double policy.");
        }
    }

    public static BigDecimal power(CobolNumeric a, CobolNumeric b) {
        return power(a.getValue(), b.getValue());
    }

    public static BigDecimal power(CobolNumeric a, BigDecimal b) {
        return power(a.getValue(), b);
    }

    public static BigDecimal power(BigDecimal a, CobolNumeric b) {
        return power(a, b.getValue());
    }
}
