package com.systema.modernized.runtime;

import java.math.BigDecimal;

public class AssignResult {
    public final boolean sizeError;
    public final BigDecimal storedValue;

    public AssignResult(boolean sizeError, BigDecimal storedValue) {
        this.sizeError = sizeError;
        this.storedValue = storedValue;
    }
}
