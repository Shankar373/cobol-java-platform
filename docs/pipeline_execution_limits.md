# Pipeline Execution Limits & Success Criteria

### Executive Summary: Up to what limit does our project pipeline execute successfully?

* **Stages 0–8 (Ingest to Gate 1 Compare) [Works E2E for Plain/File Apps]**: Standard batch COBOL programs utilizing sequential, line-sequential, and index-based relative or VSAM file structures compile, transpile, run, and pass Gate 1 exact output comparisons.
* **Stage 3 (Baseline) [Blocked for Middleware]**: Programs containing `EXEC CICS`, `EXEC SQL`, or `EXEC DLI` are blocked from legacy execution due to the lack of precompiler preprocessors (DB2/IMS/CICS) in the container baseline.
* **Stage 9 (Refactor) [Enterprise Scaffolding Succeeded with Warnings]**: Scaffolds Spring Boot applications, Spring Batch jobs, REST endpoints, and JPA model classes from parsed copybooks/inline definitions. May produce compile warnings if database driver classes, Hibernate schema definitions, or complex JPQL types are misaligned.
* **Stage 10 (Validate) [Gate 2 Mismatch / Maven Compilation Failure]**: Fails compilation during validation if there are JPA property mismatches, missing DB schemas, or batch loader discrepancies. Generates Gate 2 mismatches if modern REST data mutations (deductibles, caps) do not align byte-for-byte with decoded Comp-3 files.
* **Modernization Boundary**:
  - **E2E Success**: Standard file-based batch programs with plain logic (Stages 0–12 succeed).
  - **Refactor Succeeded with Warnings**: Multi-module batch/online systems containing CICS/SQL (Stages 0–9 succeed, 10 produces warnings, 11 fails).
  - **Validation Failed**: Complex enterprise systems with active JPA DB2 integrations requiring external persistence context (Stage 11 validation fails).

---

## 1. Pipeline Success Criteria by Stage

The modernization pipeline (defined in `cobol_migrate.py` and `modernize/native_pipeline.py`) classifies the status of each execution stage using deterministic criteria:

| Stage Index | Stage Name | SUCCESS Conditions | PARTIAL / WARNINGS Conditions | FAILED / BLOCKED Conditions |
| :--- | :--- | :--- | :--- | :--- |
| **Stage 0** | **Ingest** | Repository ingested successfully; file verification hashes saved. | Minor file character encoding repairs. | Repository path missing, invalid zip archive, or empty folder. |
| **Stage 1** | **Discover** | Identifies entry points, copybooks, format dialects, and assigns file paths. | Unresolved copybook directory links or missing optional headers. | No programs or entry point files discovered. |
| **Stage 2** | **Analyze** | Builds complete AST and Semantic IR maps for all sources. | Parsing deviations or dialect warnings in non-critical blocks. | Parser crash; unparseable source files. |
| **Stage 3** | **Baseline** | Legacy COBOL compiles and runs cleanly in GnuCOBOL Docker builder container. | GnuCOBOL fails to build due to missing SDK headers (e.g. MQ Series) but has no EXEC blockers. | Blocked if source contains `EXEC SQL`, `EXEC CICS`, or `EXEC DLI` blocks. |
| **Stage 4** | **Transpile** | Generates Java code representing COBOL AST cleanly. | Translation diagnostics in generated source files. | Transpilation generator crash. |
| **Stage 5** | **Collect** | Accumulates dependency files and classpaths for execution. | Warnings on unresolved transient dependency jar matches. | Core execution libraries (like runtime helper classes) missing. |
| **Stage 6** | **Generate** | Emits helper classes, configuration files, and DB properties. | Stub warnings for unmapped features. | Failed directory write permission or generator crash. |
| **Stage 7** | **Execute** | Runs transpiled Java class successfully under local test harness. | Stderr outputs detected or non-zero return codes inside bounds. | Java runtime crash or uncaught thread exception. |
| **Stage 8** | **Compare (Gate 1)** | Legacy baseline output matches transpiled Java output byte-for-byte. | Tolerable whitespace variations or SQLite vs binary database representation offsets. | Direct mismatch in text/binary outputs or missing output files. |
| **Stage 9** | **Refactor** | Scaffolds native Spring Boot project structure successfully. | Maven compilation warnings ("Generated with compile warnings") due to model mismatches. | Generator crash or failed directories setup. |
| **Stage 10** | **Validate (Gate 2)** | Maven build builds, launches Spring Boot batch, and database matches baseline. | Mutation testing warning flags. | Maven compilation fails, compiled jar missing, or REST/report data mismatch vs baseline. |
| **Stage 11** | **Report** | Generates markdown summary report and state outputs. | Missing non-critical metadata. | Failed file write for report. |
| **Stage 12** | **Package** | Compresses final package zip archive. | Large target jars skipped. | Packager IO exception. |

---

## 2. What the Pipeline Can Do End-to-End Today

Our migration pipeline can successfully process the following COBOL application patterns end-to-end (Stages 0–12 pass, Gate 1 & Gate 2 both verify exact parity):

* **Plain Batch Calculators**: Math intensive applications using `COMPUTE`, `ROUNDED`, `ON SIZE ERROR`, and `COMP-3` variables.
* **Standard Control Flow**: Programs structured around out-of-line `PERFORM paragraph VARYING`, `PERFORM THRU`, nested routines, and paragraph slices.
* **Structured File Processing**:
  - Sequential files read/write.
  - Line-sequential reporting.
  - Indexed VSAM emulation using local byte arrays and SQLite storage databases.
* **Linkage Parameter Passing**: Static and dynamic program calls passing arguments `BY REFERENCE` and `BY CONTENT` with caller isolation.

---

## 3. Where the Pipeline Currently Stops Working

The following technical patterns introduce compiler, generator, or verification mismatches:

### A. Baseline Blockers (Stage 3)
* **Embedded SQL / CICS / IMS**: Embedded `EXEC SQL`, `EXEC CICS`, or `EXEC DLI` blocks are blocked to prevent baseline compilation crashes in standard GnuCOBOL environments lacking DB2/CICS runtimes.

### B. Gate 1 Mismatches (Stage 8)
* **Variable-Length (RDW) Records**: Recording formats utilizing variable RDW structures cause length mismatch issues.
* **EBCDIC File Encodings**: Files expecting IBM EBCDIC representations fail when compared to GnuCOBOL ASCII outputs.

### C. Refactor Compile Warnings (Stage 9)
* **Model Class Alignment**: Copybook records with irregular nested structures sometimes fail to map to clean Java types, producing compile warnings during Spring scaffolding.
* **DB2 Profiling**: Injecting real DB2 persistence contexts requires active database connectivity configurations.

### D. Validate Failures (Stage 10)
* **Maven Compilation Mismatch**: Generated Spring Boot JPA entities fail compilation if column name aliases or type formats (like large COMP-3 packed decimals) conflict with standard SQL datatypes.
* **Traceability Gate 2 Parity Mismatches**: Batch job verification fails if computed JPA database states or generated EOD text reports do not align byte-for-byte with legacy flat-file reference outputs.

---

## 4. Examples from Our Runs

### A. ClaimsCore (`ClaimsCore-COBOL-Enterprise-GitRepo.zip`)
* **What Succeeded (Stages 0–9)**: Discovered, parsed, transpiled, and ran the program successfully. Captured legacy baseline and passed Gate 1 output comparison.
* **What Failed (Stages 10–11)**:
  - **Refactor Compile Warnings**: Scaffolding Spring Boot generated minor warnings due to DB2 schema mapping properties.
  - **Validation Compilation Failure**: Maven compile failed during Stage 11 validation because the generated Spring Batch JPA entity properties conflicted with H2 dialect rules.
  - **Gate 2 Traceability Mismatch**: Mismatches occurred in claims record calculations and exceptions reports because the deductible logic inside the generated JPA layer drifted from the legacy flat-file COMP-3 structures.

### B. Simple Baseline (`SIMPLEBASELINE01`)
* **E2E SUCCESS**: Standard file-based payroll reporter. Executes legacy GnuCOBOL baseline, transpiles to Java, runs, matches Gate 1, builds Spring Boot batch, and passes Gate 2 validations cleanly.

---

## 5. How to Extend Pipeline Coverage

To scale the pipeline and resolve current limitations:

1. **Improve Spring/JPA Scaffolding**: Refine `EnterpriseApplicationGenerator` to align generated Hibernate mappings with COBOL numeric constraints, preventing Maven compilation crashes.
2. **Optional Refactoring Path**: Modify `cobol_migrate.py` to allow execution of "Refactor & Validate" as an optional sub-pipeline. If enterprise Spring Boot generation is not required, the pipeline can verify parity at Stage 8 (Gate 1) and package the code successfully.
3. **Decouple H2 Database Configurations**: Create separate database profile configurations (e.g. H2 for dev vs DB2/Oracle for staging) to avoid dialect compiler mismatch failures.
