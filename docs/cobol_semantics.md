# COBOL Language Semantics & Transformation Rules

**Specification**: Phase 8 Semantic Invariants & Java Equivalents  
**Date**: September 2026

---

## 1. Data Division & Storage Semantics

### 1.1 Fixed-Precision Numeric Representation
COBOL fixed-point arithmetic (`PIC S9(d)V9(s) COMP-3 / COMP`) avoids IEEE-754 floating-point approximation.
- **Java Class**: `com.systema.modernized.runtime.CobolNumeric`
- **Backing**: `BigDecimal` scaled exactly to `s` decimal digits with `CobolRoundingMode.TRUNCATION` by default, or `CobolRoundingMode.NEAREST_AWAY_FROM_ZERO` when `ROUNDED` is specified.
- **Size Error Policy**: `ON SIZE ERROR` detects integer truncation and branches to the error handler without altering destination values.

### 1.2 Backing Storage & REDEFINES Overlays
- When variable `B` redefines variable `A`, they share the exact same underlying byte sequence.
- Writes to `B` immediately alter the characters read through `A`.
- **Java Representation**: A single contiguous `char[]` backing array allocated at the size of `max(length(A), length(B))`, accessed via `get_<name>()` / `set_<name>()`.

### 1.3 OCCURS DEPENDING ON (ODO) Dynamic Sizing
- Elements beyond the current value of the dependency variable cannot be read or written.
- Bounds checking logic: `checkBounds(subscript, min_bound, "dep_var", dep_var_val)` throws `IndexOutOfBoundsException` if violated.

---

## 2. Procedure Division Control Flow

### 2.1 EVALUATE Selection Rules
- Evaluates subject against object criteria sequentially.
- Multi-subject `EVALUATE subj1 ALSO subj2` checks pairs `obj1 ALSO obj2` without flattening or loss of precedence.
- Range testing: `WHEN 1 THRU 10` is translated into condition `(subj >= 1 && subj <= 10)`.

### 2.2 PERFORM Rules
- Out-of-line `PERFORM para1 THRU para2` executes all contiguous paragraphs from `para1` to `para2` inclusive.
- `PERFORM VARYING i FROM 1 BY 1 UNTIL i > N` checks the termination condition before loop body execution by default (standard `TEST BEFORE`).

### 2.3 NEXT SENTENCE vs CONTINUE
- `NEXT SENTENCE` transfers control to the statement immediately following the next period (`.`).
- `CONTINUE` is a no-op that transfers control to the next executable statement in the current sentence.
