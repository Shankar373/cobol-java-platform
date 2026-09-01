package com.systema.modernized.runtime;

public class CobolNumericSpec {
    public final boolean signed;
    public final int digits;
    public final int scale;
    public final CobolUsage usage;
    public final CobolSignPosition signPosition;
    public final boolean signSeparate;

    public CobolNumericSpec(boolean signed, int digits, int scale, CobolUsage usage) {
        this(signed, digits, scale, usage, CobolSignPosition.TRAILING, false);
    }

    public CobolNumericSpec(boolean signed, int digits, int scale, CobolUsage usage, CobolSignPosition signPosition, boolean signSeparate) {
        this.signed = signed;
        this.digits = digits;
        this.scale = scale;
        this.usage = usage != null ? usage : CobolUsage.DISPLAY;
        this.signPosition = signPosition != null ? signPosition : CobolSignPosition.TRAILING;
        this.signSeparate = signSeparate;
    }
}
