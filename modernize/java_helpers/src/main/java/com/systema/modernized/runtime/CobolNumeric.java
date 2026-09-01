package com.systema.modernized.runtime;

import java.math.BigDecimal;
import java.math.BigInteger;
import java.math.RoundingMode;

public class CobolNumeric {
    private BigDecimal value;
    private final CobolNumericSpec spec;
    private byte[] sharedBuffer;
    private int offset;
    private int length;

    public CobolNumeric(CobolNumericSpec spec) {
        this.spec = spec;
        this.value = normalizeValue(BigDecimal.ZERO);
    }

    public CobolNumeric(BigDecimal value, CobolNumericSpec spec) {
        this.spec = spec;
        this.value = normalizeValue(value);
    }

    public CobolNumeric(long value, CobolNumericSpec spec) {
        this.spec = spec;
        this.value = normalizeValue(BigDecimal.valueOf(value));
    }

    public CobolNumeric(String val, CobolNumericSpec spec) {
        this.spec = spec;
        this.value = normalizeValue(new BigDecimal(val.trim()));
    }

    public CobolNumeric(byte[] sharedBuffer, int offset, int length, CobolNumericSpec spec) {
        this.spec = spec;
        this.sharedBuffer = sharedBuffer;
        this.offset = offset;
        this.length = length;
        this.value = normalizeValue(BigDecimal.ZERO);
    }

    public BigDecimal getValue() {
        if (sharedBuffer != null) {
            if (spec.usage == CobolUsage.COMP_3) {
                return unpackComp3(sharedBuffer, offset, length);
            } else {
                return unpackDisplay(sharedBuffer, offset, length);
            }
        }
        return this.value;
    }

    public int intValue() {
        return getValue().intValue();
    }

    public long longValue() {
        return getValue().longValue();
    }

    public CobolNumericSpec getSpec() {
        return this.spec;
    }

    public AssignResult assign(BigDecimal val) {
        return assign(val, CobolRoundingMode.TRUNCATION, SizeErrorPolicy.UNCHECKED);
    }

    public AssignResult assign(BigDecimal val, CobolRoundingMode roundingMode, SizeErrorPolicy policy) {
        if (val == null) {
            val = BigDecimal.ZERO;
        }
        // Take absolute value first for unsigned receivers (Constraint C9)
        BigDecimal inputVal = val;
        if (!spec.signed && inputVal.signum() < 0) {
            inputVal = inputVal.abs();
        }

        BigDecimal roundedVal = roundingMode.round(inputVal, spec.scale);
        boolean sizeErrorOccurred = checkSizeError(roundedVal);

        if (sizeErrorOccurred) {
            if (policy == SizeErrorPolicy.CHECKED) {
                // Target remains unmodified (Blocker 2, C9)
                return new AssignResult(true, getValue());
            } else {
                // UNCHECKED: Perform silent high-order truncation (Constraint C9)
                BigDecimal truncatedVal = truncateToPic(roundedVal);
                this.value = truncatedVal;
                if (sharedBuffer != null) {
                    byte[] bytes = toStorageImage();
                    System.arraycopy(bytes, 0, sharedBuffer, offset, Math.min(bytes.length, length));
                }
                return new AssignResult(true, truncatedVal);
            }
        } else {
            this.value = roundedVal;
            if (sharedBuffer != null) {
                byte[] bytes = toStorageImage();
                System.arraycopy(bytes, 0, sharedBuffer, offset, Math.min(bytes.length, length));
            }
            return new AssignResult(false, roundedVal);
        }
    }

    public AssignResult assign(CobolNumeric other, CobolRoundingMode roundingMode, SizeErrorPolicy policy) {
        return assign(other.getValue(), roundingMode, policy);
    }

    public AssignResult assign(long val, CobolRoundingMode roundingMode, SizeErrorPolicy policy) {
        return assign(BigDecimal.valueOf(val), roundingMode, policy);
    }

    public AssignResult assign(double val, CobolRoundingMode roundingMode, SizeErrorPolicy policy) {
        return assign(BigDecimal.valueOf(val), roundingMode, policy);
    }

    private BigDecimal normalizeValue(BigDecimal val) {
        if (!spec.signed && val.signum() < 0) {
            val = val.abs();
        }
        return val.setScale(spec.scale, RoundingMode.DOWN);
    }

    private boolean checkSizeError(BigDecimal val) {
        BigDecimal absVal = val.abs();
        BigDecimal limit = BigDecimal.TEN.pow(spec.digits - spec.scale);
        return absVal.compareTo(limit) >= 0;
    }

    private BigDecimal truncateToPic(BigDecimal v) {
        BigDecimal t = v;
        if (t.scale() > spec.scale) {
            t = t.setScale(spec.scale, RoundingMode.DOWN);
        }
        int intDigits = spec.digits - spec.scale;
        if (intDigits < 0) intDigits = 0;
        if (intDigits > 0) {
            BigInteger intPart = t.unscaledValue().divide(BigInteger.TEN.pow(t.scale()));
            BigInteger maxInt = BigInteger.TEN.pow(intDigits);
            if (intPart.abs().compareTo(maxInt) >= 0) {
                BigInteger trunc = intPart.abs().remainder(maxInt);
                intPart = intPart.signum() < 0 ? trunc.negate() : trunc;
                t = new BigDecimal(intPart).setScale(spec.scale, RoundingMode.DOWN);
            }
        }
        if (t.scale() != spec.scale) {
            t = t.setScale(spec.scale, RoundingMode.DOWN);
        }
        return t;
    }

    public byte[] toStorageImage() {
        BigDecimal currentVal = this.value;
        if (spec.usage == CobolUsage.COMP_3) {
            // Packed Decimal BCD
            int totalDigits = spec.digits;
            if (totalDigits % 2 == 0) {
                totalDigits++;
            }
            byte[] bytes = new byte[totalDigits / 2 + 1];
            String digitsStr = getUnscaledAbsoluteString(totalDigits);
            int strIdx = 0;
            for (int i = 0; i < bytes.length - 1; i++) {
                int high = digitsStr.charAt(strIdx++) - '0';
                int low = digitsStr.charAt(strIdx++) - '0';
                bytes[i] = (byte) ((high << 4) | low);
            }
            int lastDigit = digitsStr.charAt(strIdx) - '0';
            int signNibble = 0x0F;
            if (spec.signed) {
                signNibble = currentVal.signum() >= 0 ? 0x0C : 0x0D;
            }
            bytes[bytes.length - 1] = (byte) ((lastDigit << 4) | signNibble);
            return bytes;
        } else {
            // USAGE DISPLAY Zoned / Separate Sign
            String digitsStr = getUnscaledAbsoluteString(spec.digits);
            if (spec.signSeparate) {
                byte[] bytes = new byte[spec.digits + 1];
                byte signByte = (byte) (currentVal.signum() >= 0 ? '+' : '-');
                if (spec.signPosition == CobolSignPosition.LEADING) {
                    bytes[0] = signByte;
                    for (int i = 0; i < spec.digits; i++) {
                        bytes[i + 1] = (byte) digitsStr.charAt(i);
                    }
                } else {
                    for (int i = 0; i < spec.digits; i++) {
                        bytes[i] = (byte) digitsStr.charAt(i);
                    }
                    bytes[spec.digits] = signByte;
                }
                return bytes;
            } else {
                byte[] bytes = new byte[spec.digits];
                for (int i = 0; i < spec.digits; i++) {
                    bytes[i] = (byte) digitsStr.charAt(i);
                }
                if (spec.signed && currentVal.signum() < 0) {
                    // Default ASCII overpunch trailing zoned decimal
                    int targetIdx = (spec.signPosition == CobolSignPosition.LEADING) ? 0 : (spec.digits - 1);
                    bytes[targetIdx] += 0x40; // Convert '0'-'9' (0x30-0x39) to 'p'-'y' (0x70-0x79)
                }
                return bytes;
            }
        }
    }

    private String getUnscaledAbsoluteString(int len) {
        BigDecimal currentVal = this.value;
        BigDecimal unscaledDecimal = currentVal.movePointRight(spec.scale);
        String plain = unscaledDecimal.abs().setScale(0, RoundingMode.DOWN).toPlainString();
        if (plain.length() < len) {
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < len - plain.length(); i++) {
                sb.append('0');
            }
            sb.append(plain);
            return sb.toString();
        } else if (plain.length() > len) {
            return plain.substring(plain.length() - len);
        }
        return plain;
    }

    public String toDisplayString() {
        BigDecimal currentVal = this.value;
        StringBuilder body = new StringBuilder();
        
        String plain = currentVal.abs().toPlainString();
        int decIdx = plain.indexOf('.');
        String intPart = decIdx != -1 ? plain.substring(0, decIdx) : plain;
        String decPart = decIdx != -1 ? plain.substring(decIdx + 1) : "";
        int intLenRequired = spec.digits - spec.scale;
        if (spec.usage == CobolUsage.COMP_5 && spec.digits == 9 && spec.scale == 0) {
            intLenRequired = 10;
        }
        if (intPart.length() < intLenRequired) {
            for (int i = 0; i < intLenRequired - intPart.length(); i++) {
                body.append('0');
            }
        }
        body.append(intPart);
        if (spec.scale > 0) {
            body.append('.');
            body.append(decPart);
            if (decPart.length() < spec.scale) {
                for (int i = 0; i < spec.scale - decPart.length(); i++) {
                    body.append('0');
                }
            }
        }
        
        String digitsStr = body.toString();
        
        if (spec.signed) {
            if (spec.signSeparate) {
                // SIGN IS SEPARATE: always emit explicit +/-
                String sign = currentVal.signum() >= 0 ? "+" : "-";
                if (spec.signPosition == CobolSignPosition.LEADING) {
                    return sign + digitsStr;
                } else {
                    return digitsStr + sign;
                }
            } else {
                // In GnuCOBOL (-fsign=ASCII behaviour), all signed numeric display output
                // renders with an explicit sign (+ for positive/zero, - for negative).
                String sign = currentVal.signum() < 0 ? "-" : "+";
                return sign + digitsStr;
            }
        } else {
            return digitsStr;
        }
    }

    private BigDecimal unpackComp3(byte[] buffer, int offset, int length) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < length - 1; i++) {
            int b = buffer[offset + i] & 0xFF;
            sb.append(b >> 4);
            sb.append(b & 0x0F);
        }
        int lastByte = buffer[offset + length - 1] & 0xFF;
        sb.append(lastByte >> 4);
        int signNibble = lastByte & 0x0F;
        BigDecimal val = new BigDecimal(sb.toString()).movePointLeft(spec.scale);
        if (signNibble == 0x0D || signNibble == 0x0B) {
            val = val.negate();
        }
        return val;
    }

    private BigDecimal unpackDisplay(byte[] buffer, int offset, int length) {
        byte[] raw = new byte[length];
        System.arraycopy(buffer, offset, raw, 0, length);
        
        boolean isNegative = false;
        StringBuilder sb = new StringBuilder();
        if (spec.signSeparate) {
            if (spec.signPosition == CobolSignPosition.LEADING) {
                if (raw[0] == '-') isNegative = true;
                for (int i = 1; i < length; i++) {
                    sb.append((char) raw[i]);
                }
            } else {
                if (raw[length - 1] == '-') isNegative = true;
                for (int i = 0; i < length - 1; i++) {
                    sb.append((char) raw[i]);
                }
            }
        } else {
            int targetIdx = (spec.signPosition == CobolSignPosition.LEADING) ? 0 : (length - 1);
            for (int i = 0; i < length; i++) {
                byte b = raw[i];
                if (i == targetIdx && spec.signed) {
                    if (b >= 0x70 && b <= 0x79) {
                        isNegative = true;
                        b -= 0x40;
                    }
                }
                sb.append((char) b);
            }
        }
        String s = sb.toString().trim();
        if (s.isEmpty()) return BigDecimal.ZERO;
        BigDecimal val;
        try {
            val = new BigDecimal(s).movePointLeft(spec.scale);
        } catch (NumberFormatException e) {
            val = BigDecimal.ZERO;
        }
        if (isNegative) val = val.negate();
        return val;
    }

    @Override
    public String toString() {
        return toDisplayString();
    }
}
