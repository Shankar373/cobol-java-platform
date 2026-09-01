package com.systema.modernized;

import java.math.BigDecimal;
import java.math.BigInteger;
import java.math.RoundingMode;

public class CobolFormatHelper {
    public static String format(Object value, String pattern) {
        if (value == null) {
            value = "";
        }
        pattern = pattern.toUpperCase();
        
        // Convert value to BigDecimal for formatting if possible
        BigDecimal num = null;
        try {
            if (value instanceof BigDecimal) {
                num = (BigDecimal) value;
            } else {
                String strVal = value.toString().trim();
                if (strVal.isEmpty()) {
                    num = BigDecimal.ZERO;
                } else {
                    strVal = strVal.replace("$", "").replace(",", "");
                    if (strVal.endsWith("CR") || strVal.endsWith("DB")) {
                        strVal = "-" + strVal.substring(0, strVal.length() - 2).trim();
                    } else if (strVal.endsWith("-")) {
                        strVal = "-" + strVal.substring(0, strVal.length() - 1).trim();
                    } else if (strVal.endsWith("+")) {
                        strVal = strVal.substring(0, strVal.length() - 1).trim();
                    }
                    num = new BigDecimal(strVal);
                }
            }
        } catch (Exception e) {
            return padString(value.toString(), pattern.length());
        }

        boolean isNegative = num.compareTo(BigDecimal.ZERO) < 0;
        BigDecimal absNum = num.abs();

        // Check layout options
        boolean hasFixedCurrency = pattern.startsWith("$") && pattern.indexOf("$", 1) == -1;
        boolean hasFixedPlus = pattern.startsWith("+") && pattern.indexOf("+", 1) == -1;
        boolean hasFixedMinus = pattern.startsWith("-") && pattern.indexOf("-", 1) == -1;
        
        boolean hasFloatingCurrency = pattern.contains("$") && !hasFixedCurrency;
        boolean hasFloatingPlus = pattern.contains("+") && !hasFixedPlus;
        boolean hasFloatingMinus = pattern.contains("-") && !hasFixedMinus;
        
        boolean hasCr = pattern.contains("CR");
        boolean hasDb = pattern.contains("DB");
        boolean asteriskFill = pattern.contains("*");

        // Determine decimal positions in pattern
        int decIdx = pattern.indexOf(".");
        int patternScale = 0;
        if (decIdx != -1) {
            for (int i = decIdx + 1; i < pattern.length(); i++) {
                char c = pattern.charAt(i);
                if (c == '9' || c == 'Z' || c == '*') {
                    patternScale++;
                }
            }
        }

        // Round absolute number to pattern scale
        absNum = absNum.setScale(patternScale, RoundingMode.HALF_UP);
        String absStr = absNum.toPlainString();
        int absDecIdx = absStr.indexOf(".");
        String intPart = absDecIdx != -1 ? absStr.substring(0, absDecIdx) : absStr;
        String decPart = absDecIdx != -1 ? absStr.substring(absDecIdx + 1) : "";

        // Isolate integer pattern part
        String intPattern = decIdx != -1 ? pattern.substring(0, decIdx) : pattern;
        
        // Count digit placeholders in integer part of pattern
        int intPlaceholdersCount = 0;
        for (int i = 0; i < intPattern.length(); i++) {
            char c = intPattern.charAt(i);
            if (c == '9' || c == 'Z' || c == '*' || c == '$' || c == '+' || c == '-') {
                intPlaceholdersCount++;
            }
        }

        // Truncate leftmost integer digits if value exceeds integer placeholders
        if (intPart.length() > intPlaceholdersCount) {
            intPart = intPart.substring(intPart.length() - intPlaceholdersCount);
        }

        // Traverse integer pattern right-to-left to place digits
        StringBuilder intResult = new StringBuilder();
        int intPtr = intPart.length() - 1;
        for (int i = intPattern.length() - 1; i >= 0; i--) {
            char pChar = intPattern.charAt(i);
            if (pChar == '9' || pChar == 'Z' || pChar == '*' || pChar == '$' || pChar == '+' || pChar == '-') {
                if (intPtr >= 0) {
                    intResult.append(intPart.charAt(intPtr--));
                } else {
                    // Suppression or padding
                    if (pChar == '9') {
                        intResult.append('0');
                    } else if (pChar == '*') {
                        intResult.append('*');
                    } else {
                        intResult.append(' '); // Space for Z, $, +, -
                    }
                }
            } else if (pChar == ',') {
                if (intPtr >= 0 || (intResult.length() > 0 && intResult.charAt(intResult.length() - 1) != ' ' && intResult.charAt(intResult.length() - 1) != '*')) {
                    intResult.append(',');
                } else {
                    intResult.append(asteriskFill ? '*' : ' ');
                }
            } else {
                intResult.append(pChar);
            }
        }
        intResult.reverse();
        String formattedInt = intResult.toString();

        // Post-processing for floating currency / sign
        char[] chars = formattedInt.toCharArray();
        if (hasFloatingCurrency || hasFloatingPlus || hasFloatingMinus) {
            // Find the index of the first digit (or comma) from left to right
            int firstDigitIdx = chars.length;
            for (int i = 0; i < chars.length; i++) {
                if (chars[i] != ' ' && chars[i] != '*') {
                    firstDigitIdx = i;
                    break;
                }
            }
            // The float symbol goes to the rightmost space before that index
            int targetIdx = firstDigitIdx - 1;
            if (targetIdx >= 0 && chars[targetIdx] == ' ') {
                if (hasFloatingCurrency) {
                    chars[targetIdx] = '$';
                } else if (hasFloatingPlus) {
                    chars[targetIdx] = isNegative ? '-' : '+';
                } else if (hasFloatingMinus) {
                    chars[targetIdx] = isNegative ? '-' : ' ';
                }
            } else if (targetIdx == -1) {
                // If it filled completely, wait, this should have been handled by overflow or fits exactly.
            }
        }

        // Format decimal part
        String formattedDec = "";
        if (decIdx != -1) {
            String decPattern = pattern.substring(decIdx + 1);
            String cleanDecPattern = decPattern.replace("+", "").replace("-", "").replace("CR", "").replace("DB", "").replace("$", "");
            StringBuilder decResult = new StringBuilder();
            int decPtr = 0;
            for (int i = 0; i < cleanDecPattern.length(); i++) {
                char pChar = cleanDecPattern.charAt(i);
                if (pChar == '9' || pChar == 'Z' || pChar == '*') {
                    if (decPtr < decPart.length()) {
                        decResult.append(decPart.charAt(decPtr++));
                    } else {
                        decResult.append('0');
                    }
                } else {
                    decResult.append(pChar);
                }
            }
            formattedDec = "." + decResult.toString();
        }

        // Combine integer and decimal
        String combined = new String(chars) + formattedDec;

        // Apply fixed currency and sign if applicable
        String prefix = "";
        String suffix = "";
        if (hasFixedCurrency) {
            prefix = "$";
        }
        if (hasFixedPlus) {
            prefix = isNegative ? "-" : "+";
        }
        if (hasFixedMinus) {
            prefix = isNegative ? "-" : " ";
        }
        
        // CR / DB suffixes
        if (hasCr) {
            suffix = isNegative ? "CR" : "  ";
        }
        if (hasDb) {
            suffix = isNegative ? "DB" : "  ";
        }

        String finalResult = prefix + combined + suffix;

        // Adjust string to fit pattern length exactly
        if (finalResult.length() < pattern.length()) {
            finalResult = padString(finalResult, pattern.length());
        }

        return finalResult;
    }

    public static BigDecimal numval(String val) {
        if (val == null) return BigDecimal.ZERO;
        String clean = val.trim().replace("$", "").replace(",", "").trim();
        if (clean.isEmpty()) return BigDecimal.ZERO;
        try {
            boolean isNegative = false;
            if (clean.endsWith("-") || clean.startsWith("-")) {
                isNegative = true;
                clean = clean.replace("-", "").trim();
            } else if (clean.endsWith("CR") || clean.endsWith("DB")) {
                isNegative = true;
                clean = clean.substring(0, clean.length() - 2).trim();
            }
            BigDecimal d = new BigDecimal(clean);
            return isNegative ? d.negate() : d;
        } catch (Exception e) {
            return BigDecimal.ZERO;
        }
    }

    public static int mod(int a, int b) {
        return a % b;
    }

    public static BigDecimal mod(BigDecimal a, BigDecimal b) {
        return a.remainder(b);
    }


    /**
     * Apply COBOL PICTURE storage/truncation semantics to an arithmetic result.
     *
     * COBOL (without ROUNDED) truncates the value to the receiver field's PICTURE
     * before storing it: extra decimal places are dropped (truncation toward
     * zero) and, when the integer magnitude exceeds the available integer digits,
     * the most-significant integer digits are truncated. The stored (truncated)
     * value is what any subsequent arithmetic reads, which is the root of correct
     * chained-COMPUTE semantics (e.g. PY-TAX = PY-GROSS * RATE must be stored
     * truncated so that PY-NET = PY-GROSS - PY-TAX reads the truncated amount).
     */
    public static BigDecimal truncateToPic(BigDecimal v, int digits, int scale, boolean signed) {
        if (v == null) return BigDecimal.ZERO;
        BigDecimal t = v;
        // Truncate fractional part beyond the PICTURE scale (COBOL non-ROUNDED).
        if (t.scale() > scale) {
            t = t.setScale(scale, RoundingMode.DOWN);
        }
        // Truncate excess most-significant integer digits (COBOL cuts them).
        int intDigits = digits - scale;
        if (intDigits < 0) intDigits = 0;
        if (intDigits > 0) {
            BigInteger intPart = t.unscaledValue().divide(BigInteger.TEN.pow(t.scale()));
            BigInteger maxInt = BigInteger.TEN.pow(intDigits);
            if (intPart.abs().compareTo(maxInt) >= 0) {
                BigInteger trunc = intPart.abs().remainder(maxInt);
                intPart = intPart.signum() < 0 ? trunc.negate() : trunc;
                t = new BigDecimal(intPart).setScale(scale, RoundingMode.DOWN);
            }
        }
        // Guarantee exact scale even for zero / integer results.
        if (t.scale() != scale) {
            t = t.setScale(scale, RoundingMode.DOWN);
        }
        return t;
    }

    private static String padString(String val, int length) {
        if (val == null) val = "";
        String padded = String.format("%-" + length + "s", val);
        if (padded.length() > length) return padded.substring(0, length);
        return padded;
    }

    public static int parseIntSafe(Object src) {
        if (src == null) return 0;
        String s = src.toString().trim();
        if (s.isEmpty()) return 0;
        try {
            return Integer.parseInt(s);
        } catch (NumberFormatException e) {
            return 0;
        }
    }

    public static long parseLongSafe(Object src) {
        if (src == null) return 0L;
        String s = src.toString().trim();
        if (s.isEmpty()) return 0L;
        try {
            return Long.parseLong(s);
        } catch (NumberFormatException e) {
            return 0L;
        }
    }
    public static String delimitedString(String val, String delimiter) {
        if (val == null) return "";
        if (delimiter == null || delimiter.isEmpty()) return val;
        int idx = val.indexOf(delimiter);
        if (idx == -1) return val;
        return val.substring(0, idx);
    }
}

