# Phase 6 Native Java Coverage Report

This report documents the architectural design, parser updates, statement translator changes, and type mappings implemented to support the six new native Java target constructs in the modernization pipeline.

---

## 1. Architectural Changes

The direct transpile engine now operates on a generic mapping structure where constructs are parsed into a robust SemanticIR representation, then translated cleanly into instance method blocks within standard standard-library Java classes.

### Decoupled Runtime Principle
Our system adheres strictly to standard libraries without injecting third-party dependencies (`opensourcecobol4j`, `libcobj.jar`, or custom runtime annotations).

---

## 2. Technical Coverage & Statement Translation Details

### 1. DISPLAY Statement
- **Parser Update**: The DISPLAY statement parser was updated to be subscript-aware via `consume_subscripted_identifier()`. It consumes all arguments until a period (`.`) or a statement start verb (e.g., `END-PERFORM`) is reached.
- **Generator Translation**: Non-literal operands are resolved dynamically:
  - If the variable base matches a string type, it is referenced directly.
  - Non-string variables (e.g., `Integer`, `BigDecimal`) are wrapped in `String.valueOf()`.
  - Operands are concatenated using standard string joining: `+ " " +`.

### 2. EVALUATE Statement with Subject
- **Parser Update**: Extracts the subject expression following the `EVALUATE` keyword.
- **Generator Translation**: 
  - Tracks the evaluation subject across subsequent `WHEN` statements.
  - Translates `WHEN` checks using type-safe comparison operations:
    - String comparison: `Objects.equals(subject, value)`
    - BigDecimal comparison: `subject.compareTo(value) == 0`
    - Primitives: `subject == value`
  - Generates clear, structured nested `if-else` blocks terminated by a `WHEN OTHER` branch block.

### 3. Level-88 Conditions
- **Parser Update**: Parses level-88 entries in the data division as dependent condition-name mappings with child condition values.
- **Data Model Generator**: 
  - Collects condition definitions in a localized `level88_map` mapping condition names to their parent variable.
  - Generates boolean helper methods:
    `public boolean isStatusOpen() { return Objects.equals(ws_status, "O"); }`
- **Condition Translation**: The condition translator detects level-88 references inside conditions (`IF`, `PERFORM UNTIL`, `PERFORM VARYING`) and rewrites them into simple method calls: `isStatusOpen()`.

### 4. MOVE to Multiple Targets
- **Parser Update**: Modifies the `MOVE` syntax parser to parse multiple identifier destinations into a target list: `MOVE source TO target1 target2 ...`.
- **Generator Translation**: Emits separate, consecutive assignment lines for each target variable, respecting each target's individual type coercion and format formatting requirements.

### 5. PERFORM VARYING
- **Parser Update**: Extracts loop variables, starting value expressions, increment sizes, and completion conditions.
- **Generator Translation**: Builds standard Java `for` loops:
  - For standard primitive types (`int`, `long`):
    `for (ws_i = 1; !(ws_i > ws_limit); ws_i += 1) {`
  - For `BigDecimal` indices (handling fractional loop ranges):
    `for (ws_idx = new BigDecimal("1.5"); !(ws_idx.compareTo(ws_limit) > 0); ws_idx = ws_idx.add(new BigDecimal("0.5"))) {`

### 6. OCCURS Table Arrays & Subscripts
- **Parser Update**: Captures occurrences count (`occurs: N`) from data division entries and handles subscripted variable references `VAR-NAME(INDEX)` inside statements and condition expressions.
- **Generator Translation**:
  - Declares array fields: `public BigDecimal[] item_val = new BigDecimal[5];`
  - Emits localized initializers to fill arrays to prevent NullPointerExceptions: `java.util.Arrays.fill(item_val, BigDecimal.ZERO);`
  - Translates subscript expressions to zero-based indexing offset: `item_val[ws_i - 1]`. Supports both numeric literals and active variable indices.

---

## 3. Dependency Gate Audit

Every construct adheres to the decoupled architecture:
- No dependencies are added to `pom.xml`.
- No proprietary library imports or class references are generated.
- Standard libraries (`java.math.BigDecimal`, `java.util.Objects`, `java.util.Arrays`) are referenced natively.
