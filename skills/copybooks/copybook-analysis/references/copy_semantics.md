# COBOL COPY Statement Semantics & Resolution Reference

## Syntax and Forms
- Standard: `COPY COPYBOOK-NAME.`
- Qualified: `COPY COPYBOOK-NAME IN/OF LIBRARY-NAME.`
- Replacing: `COPY COPYBOOK-NAME REPLACING ==old== BY ==new==.`

## Library Resolution Order
1. Relative to the directory containing the referring COBOL source file.
2. Directories specified in `copybook_dirs` configuration.
3. Standard subdirectories: `copybooks/`, `cpy/`, `copylib/`, `include/`.
4. Case-sensitivity handling: Exact match -> lower-case fallback -> upper-case fallback -> `.cpy`, `.cpb`, `.cbl`, `.cob` extension fallback.

## Circular Dependency Prevention
- Circular copybook references (e.g. A includes B includes A) must be detected and aborted with an explicit recursion diagnostic.
