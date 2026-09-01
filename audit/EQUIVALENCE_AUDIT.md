# Phase 13: Behavioral Equivalence Audit (Stage 8)

- **Parity Metric**: Compares stdout, stderr, and output directories.
- **Empty Output Loophole**: If both baseline and execute fail without creating files and return code 0, it reports a false-positive PASS.
- **Logical Indexed Compare**: Physically differing database files are compared logically by querying their SQLite database tables, verifying field-level equivalence.
