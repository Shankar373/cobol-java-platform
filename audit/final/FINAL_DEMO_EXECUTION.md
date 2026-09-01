# SystemaOps Enterprise Application Modernization Platform
## FINAL DEMO EXECUTION & TALK TRACKS
**Author**: Antigravity  
**Status**: APPROVED FOR PRESENTATION  
**Date**: 2026-08-22  

---

### 1. Primary Demo Repository Selection

We recommend **`smoke-repo.zip`** as the primary demonstration repository.
* **Composition**: Contains a clean COBOL program (`SMOKE.cob`) incorporating `PROCEDURE DIVISION`, `DISPLAY` statements, and standard termination logic.
* **Justification**: It executes the entire 13-stage modernization lifecycle in ~15 seconds, making it ideal for live client presentations. It compiles successfully, generates clean Spring Boot structures, and completes the exit code and stdout equivalence checks with full precision, yielding a `PRODUCTION_READY` final verdict.

---

### 2. 10-Minute Executive Demo Click-by-Click Guide

| Timing | Phase / Step | Actions to Perform | Talk Track / Script |
|---|---|---|---|
| **00:00 - 01:00** | Introduction | Open `http://localhost:8787` in browser. Show empty workspace landing page. | *"Welcome to the SystemaOps Modernization Platform. Today, we are demonstrating a 100% automated transcompilation of legacy COBOL to enterprise-ready Spring Boot applications with zero manual injection or faked results."* |
| **01:00 - 02:00** | Upload Repository | Click "Choose File", select `smoke-repo.zip`, and click **Ingest**. | *"By ingesting this repository zip, the backend registers a new sandboxed workspace on disk, creating isolated tracking parameters for execution."* |
| **02:00 - 03:00** | Discovery Summary | Point to the **Repository Summary Card**. Show that format and program parameters are ready. | *"Immediately, the system performs stage 1 and 2: ingestion and discovery. It highlights detected source formats and identifies entry points dynamically."* |
| **03:00 - 05:00** | Run Pipeline | Click **Run pipeline**. Select the **Console Log** tab. Lock/unlock scroll. | *"We are triggering the real modernization engine. As you see on the dynamic stage stepper, it progresses through AST analysis, compilation, and transpilation in real-time."* |
| **05:00 - 07:00** | Generated Code | Click **Unified Explorer** tab. Load `SMOKE.java` or `pom.xml`. | *"Here is the output: clean, modern, and readable Spring Boot code. Variables and database bindings are transpiled to native types."* |
| **07:00 - 08:00** | Equivalence Check | Select **Equivalence** card. Show output matches and exit codes. | *"We don't just translate code; we prove semantic equivalence. The engine executes both the legacy baseline and the Java code, asserting stdout matches."* |
| **08:00 - 09:00** | Evidence Panel | Point to the **7 Evidence Cards** grid. | *"All compilation, execution, and security checks must pass backend gate rules. If any check fails, the verdict decreases automatically."* |
| **09:00 - 10:00** | Export Package | Click **Download Modernized Package** button. | *"With one click, we package a production-ready Maven project containing Spring Batch steps and documentation. The legacy COBOL is fully retired."* |

---

### 3. Technical Demo (20-Minute Deep Dive)
* **Architecture Walkthrough (Min 0-5)**: Dive into compiler parsing steps. Show how `parser.py` maps files into AST records, and how `native_generator.py` translates them.
* **Equivalence Verification (Min 5-10)**: Discuss output streams comparison (`CONSOLE_OUTPUT`, `FILE_OUTPUT`), mutations injection, and how GnuCOBOL is used to compile baselines.
* **Security Validation (Min 10-15)**: Demonstrate that inputting traversal values like `../../ui.py` is safely rejected with HTTP 400. Show SSE connection isolation.
* **Spring Integration (Min 15-20)**: Show how batch jobs are organized in Maven XML schemas, detailing H2 SQL databases mappings and provenance logs.

---

### 4. Client Talk Track Q&A

#### "How do you prevent silent translation failures?"
> *“We enforce double-sided equivalence gates. Both the legacy COBOL compile and the transpiled Java executable must run and output exactly identical buffers. If even one character is mismatched, the equivalence card flags a `FAIL` and halts packaging.”*

#### "Can this work on another COBOL repository?"
> *“Yes. The parsing engine is built on standard COBOL ANSI-85 rules. Ingesting any new repository registers it in isolation, initializing fresh workspace states and independent logs.”*

#### "What happens when migration fails?"
> *“If a stage throws an error (e.g. compile error or syntax failure), the stepper halts immediately. Downstream phases are locked as pending, the verdict panel registers a high-contrast red `FAILED` state, and detailed diagnostics are streamed to the console log window.”*
