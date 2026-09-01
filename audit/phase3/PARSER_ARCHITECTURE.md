# Parser Architecture Audit and Recommendations

This document compares different technical approaches for parsing and representing COBOL semantic elements into our `SemanticIR`.

---

## 1. Options Evaluation

### Option A: Existing Parser/AST (Scaffolded regex extractors)
- **Semantic Accuracy**: Low. The current codebase only extracts macro-level attributes (SELECT ASSIGN statements, FD copybooks, static CALLs) and lacks detailed statement-level parsing.
- **Source Traceability**: Medium. Stores file and paragraph occurrences but lacks line/column offsets for nested expressions.
- **Supported Constructs**: SELECT, FD, COPY, CALL.
- **Limitations**: Cannot extract nested IF/ELSE conditions, arithmetic formulas, or loops.
- **Maintenance Cost**: Low.

### Option B: Compiler-Derived Representation (GnuCOBOL C transpilation)
- **Semantic Accuracy**: High for control structures, but low for mapping COBOL source variables back to original representations.
- **Source Traceability**: Low. Intermediate C code lacks clear lines map back to the original `.cob` file.
- **Supported Constructs**: All GnuCOBOL-compatible keywords.
- **Limitations**: Parsing generated C is equivalent to compiling, adding huge complexity.
- **Maintenance Cost**: High.

### Option C: Generated Java Reconstruction (OpenSource COBOL 4J outputs)
- **Semantic Accuracy**: Medium. OpenSource COBOL 4J (`cobj`) transpiles COBOL statements to corresponding Java classes. However, it translates variables into raw wrapper arrays and helper method invocations, losing explicit PICTURE scales, REDEFINES types, and local scopes.
- **Source Traceability**: Low to Medium. Requires mapping Java lines back to COBOL.
- **Supported Constructs**: All constructs transpiled by `cobj`.
- **Limitations**: The generated Java output acts as a secondary representation; translating from Java back to Semantic IR introduces lossy reconstructions.
- **Maintenance Cost**: High.

### Option D: Direct COBOL Parser (Lightweight custom recursive descent / token scanner)
- **Semantic Accuracy**: High. Parses variables (`PIC`, `COMP-3`, `REDEFINES`, `OCCURS`) and control blocks (`IF`, `PERFORM`, `CALL`, `EVALUATE`) directly from source.
- **Source Traceability**: High. Every token is scanned from the original file, capturing exact line, column, and span offsets.
- **Supported Constructs**: Working-Storage variables, level numbers, arithmetic, and basic PROCEDURE statements.
- **Limitations**: Custom implementation required for complex nested expressions.
- **Maintenance Cost**: Medium.

### Option E: Regex Fallback
- **Semantic Accuracy**: Low. Easily breaks on nested loops, multi-line statements, and comments.
- **Source Traceability**: High for matched lines, but low for spans.
- **Supported Constructs**: Simple linear statements.
- **Limitations**: Incapable of parsing structured COBOL control flow (e.g. IF/ELSE nesting, PERFORM THRU blocks).
- **Maintenance Cost**: Very High.

---

## 2. Selection and Architecture Decision

We select **Option D (Direct COBOL Parser)** as the authoritative architecture for populating `SemanticIR`.

To implement this without adding heavy third-party parsing dependencies, we will build a lightweight **Lexical Token Scanner** and **Recursive Parser** inside `modernize/` to directly scan and build AST nodes from COBOL source files. This ensures that:
1. original COBOL source semantics remain the absolute authority.
2. Every generated node maintains accurate line, column, and node ID coordinates.
