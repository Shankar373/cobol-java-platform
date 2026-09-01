# Phase 14: Business Logic Preservation

The compiler transpiles statement blocks literally, preserving original business logic:
- **EVALUATE Statements**: Mapped to standard switch-case blocks.
- **Numeric Computations**: Managed via custom `CobolDecimal` math packages to prevent precision loss.
- **Control Flows**: Paragraph paragraphs are mapped to helper method calls.
