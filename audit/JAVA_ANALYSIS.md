# Phase 11: Java Translation and Mapping Analysis

The Java code is transpiled by OpenSourceCOBOL4J (`cobj`):

## Key Characteristics:
- **Emulated Runtime Coupling**: The generated code is highly coupled to `libcobj.jar` wrappers. Alphanumeric/Numeric fields are represented as `CobolDataStorage` objects.
- **COMP-3 Conversions**: Managed via BCD conversions inside `cobj` library methods.
- **Size Mismatch Vulnerabilities**: Caller variables passing smaller sizes than linkage variables expect cause `ArrayIndexOutOfBoundsException` crashes.
