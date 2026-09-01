# Development Guide

This document describes how to modify and extend the COBOL-to-Java translation engine.

---

## 1. Project Organization

*   `cobol_migrate.py`: Entry point and pipeline stage orchestrator.
*   `ui.py` & `ui.html`: Web dashboard server and client UI.
*   `modernize/`:
    *   `lexer.py`: Lexical tokenization and COPYBOOK expansion.
    *   `parser.py`: Syntax translation to AST.
    *   `control_flow.py`: Paragraph block resolution.
    *   `native_generator.py`: Track-B native Java source emitter.
    *   `jcl_parser.py`: JCL workflow parser.

---

## 2. Extending AST Grammar

To add support for a new COBOL statement (e.g. `ACCEPT`):

1.  **Lexer**: Verify that the statement keyword is tokenized in `modernize/lexer.py`.
2.  **Parser**: Add a statement parsing method in `modernize/parser.py` (e.g. `self.parse_accept_stmt()`) and map it inside the main parser dispatch table. Return a custom node representation.
3.  **Generator**: Update the statement translator inside `modernize/native_generator.py` to recognize the AST node and emit the corresponding Java class syntax.
