package com.systema.modernized.runtime;

import java.math.BigDecimal;
import java.math.RoundingMode;

public enum CobolRoundingMode {
    NEAREST_AWAY_FROM_ZERO, // default ROUNDED (HALF_UP)
    TRUNCATION,             // default non-ROUNDED (DOWN / towards zero)
    NEAREST_EVEN,           // HALF_EVEN
    NEAREST_TOWARD_ZERO,    // HALF_DOWN (unconditionally rounds ties toward zero)
    TOWARD_GREATER,         // CEILING
    TOWARD_LESSER,          // FLOOR
    AWAY_FROM_ZERO,         // UP
    PROHIBITED;             // UNNECESSARY

    public BigDecimal round(BigDecimal value, int scale) {
        if (value.scale() <= scale) {
            return value.setScale(scale);
        }
        switch (this) {
            case NEAREST_AWAY_FROM_ZERO:
                return value.setScale(scale, RoundingMode.HALF_UP);
            case TRUNCATION:
                return value.setScale(scale, RoundingMode.DOWN);
            case NEAREST_EVEN:
                return value.setScale(scale, RoundingMode.HALF_EVEN);
            case NEAREST_TOWARD_ZERO:
                return value.setScale(scale, RoundingMode.HALF_DOWN);
            case TOWARD_GREATER:
                return value.setScale(scale, RoundingMode.CEILING);
            case TOWARD_LESSER:
                return value.setScale(scale, RoundingMode.FLOOR);
            case AWAY_FROM_ZERO:
                return value.setScale(scale, RoundingMode.UP);
            case PROHIBITED:
                // Pre-check for scale truncation to avoid catch-based control flow (Constraint C1)
                BigDecimal scaledValue = value.setScale(scale, RoundingMode.DOWN);
                if (value.compareTo(scaledValue) != 0) {
                    throw new ProhibitedRoundingException("Rounding prohibited but required under PROHIBITED mode");
                }
                return scaledValue;
            default:
                return value.setScale(scale, RoundingMode.DOWN);
        }
    }
}
