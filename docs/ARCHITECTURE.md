# Platform Architecture

This document describes the compiler and generator design of the COBOL-to-Java Modernization Platform.

---

## 1. Multi-Track Architecture

To support both verification and modernization paths, the platform compiles target repositories into two distinct folders in the final ZIP archive:

```
target/
├── transpiled/ (Track A - Emulated)
│   ├── src/main/java/ (Uses jp.osscons wrappers)
│   └── lib/libcobj.jar
└── modernized/ (Track B - Native Java Spring Boot)
    ├── src/main/java/ (Direct native Java types)
    └── pom.xml (Zero libcobj runtime dependencies)
```

### Track A: Emulated Path
*   **Purpose**: Legacy verification gate.
*   **Translation**: Maps COBOL byte data structure layouts onto `CobolRef` wrappers matching the GNU-like memory representations.
*   **Execution**: Validates logic parity against the baseline.

### Track B: Native Java Path
*   **Purpose**: Target decoupled enterprise code.
*   **Translation**: Translates variables directly to Java primitives (`int`, `long`, `String`) and `BigDecimal`.
*   **Decoupled Frameworks**: Generates REST Controllers, Spring Batch tasklets/steps, and standard Spring Data JPA interfaces.

---

## 2. Compiler Subsystem Components

```
COBOL Source
   │
   ▼
[Lexer] ──(Token Stream)──► [Parser] ──(Semantic AST)──► [Control Resolver]
                                                            │
                                                            ▼
                                                     [Semantic IR]
                                                            │
                                                            ▼
                                                   [Native Generator]
                                                            │
                                                            ▼
                                                   Spring Boot Project
```

1.  **Lexer (`modernize/lexer.py`)**: Supports copybook resolution, continuation line normalization, comment stripping, and free/fixed margin detection.
2.  **Parser (`modernize/parser.py`)**: Maps token sequences to custom AST statement blocks.
3.  **Semantic IR (`modernize/semantic_ir.py`)**: Normalizes scopes, paragraphs, and data structures.
4.  **Control Flow (`modernize/control_flow.py`)**: Resolves implicit loops, break conditions, and GO TO paragraph sequences.
5.  **Native Generator (`modernize/native_generator.py`)**: Emits type-safe native Java classes.
