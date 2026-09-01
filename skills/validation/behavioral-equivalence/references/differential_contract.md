# Differential Behavioral Equivalence Contract

## Equivalence Principles
1. **Initial State Invariant**: Both legacy COBOL and modern Java must execute against identical initial state (input files, environment, test databases).
2. **Deterministic Output Comparison**:
   - Standard output (`stdout.txt`) byte-by-byte or line-by-line comparison with strict normalization only for platform-specific line endings.
   - Record-oriented and sequential file comparison (`out.dat`, reports).
   - Relational database state diff (`SELECT * FROM table ORDER BY pk`).
   - Transaction state and COMMAREA return buffers.
3. **No False Equivalences**: Passing compilation or mock tests must never be substituted for differential equivalence evidence.
