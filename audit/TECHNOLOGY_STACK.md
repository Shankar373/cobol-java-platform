# Phase 4: Technology Stack Validation

The actual technologies verified in the codebase:

## Backend Stack
- **Python 3.14**: Orchestration driver (`cobol_migrate.py`), audit validator (`audit_engine.py`), and API web server (`ui.py`).
- **HTTP Server**: Handcrafted `ThreadingHTTPServer` from standard `http.server` module. No external framework (Flask/FastAPI) is used.
- **Docker**: Containerized runtime wrappers.

## Frontend Stack
- **HTML5 / CSS**: Single page layout serving responsive columns.
- **JavaScript (Vanilla)**: Uses standard DOM manipulation, `fetch` API, and SSE `EventSource`. No framework (React/Angular/Vue) is used.

## Legacy COBOL Stack
- **GnuCOBOL 3.1**: Compiles COBOL source files into executable binaries inside `hurriedreformist/gnucobol:3.1-builder` container.

## Target Java Stack
- **OpenSourceCOBOL4J 2.0.0**: Transpiler compiler (`cobj`) generating intermediate `.java` source code.
- **libcobj.jar**: Standard runtime emulation library containing `AbstractCobolField`, `CobolDecimal`, and `CobolRunnable` wrappers.
