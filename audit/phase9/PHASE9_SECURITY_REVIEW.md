# Phase 9 — Security and Hardening Review

This audit document verifies the safety, robustness, and production readiness of the modernized engine and its generated applications from a security perspective.

## 1. Safe Process Execution Practices

To prevent command injection and unauthorized privilege escalation, the following security constraints are enforced across the engine codebase:

- **Avoidance of `shell=True`**: All invocations of external processes (including compiler runs, GnuCOBOL tests, Maven compilation, and Spring Boot app execution) pass arguments as parsed, structured lists (`list`) instead of raw strings. This prevents command injection vulnerabilities associated with command interpreters.
- **Strict Parameter Sanitization**: The entry args, file paths, and environment variables are strictly sanitized. For example, `run_id` is sanitized via regex (`re.sub(r'[^a-zA-Z0-9_-]', '', ...)`) to eliminate path traversal attacks or shell control characters.
- **Absolute Path Resolution**: Input files and work directories are resolved to their absolute canonical paths, preventing symbolic link exploits or directory traversal (`../`).

## 2. Resource and File Descriptor Leaks Mitigation

In Java runtime execution and testing environments, long-running processes must clean up system resources under all failure modes.
- **Harnessed `subprocess.Popen` Cleanup**: The launch of the Spring Boot verification container at line 4182 in `cobol_migrate.py` is fully protected by a `try-finally` block starting immediately upon opening the log file descriptor.
- **Assured Close of Log File Handlers**: In all execution paths (success, normal failure, or unexpected exception), the process `proc` is explicitly terminated (and killed if necessary), and the output file handler is safely closed.
- **No Residual Processes**: Verification runs check for active child processes and perform active cleanup, leaving no stray background threads or leaked network ports.

## 3. Runtime Independence (Zero Legacy/Container Dependencies)

The modernized Native Spring Boot architecture achieves complete runtime separation from the legacy COBOL environment:
- **No Classpath Coupling**: The refactored enterprise Java application (`modernized/` project) has **zero** dependency on `libcobj.jar` or any legacy COBOL support libraries.
- **No Legacy Binary Dependencies**: Java classes generated under the native refactoring path compile directly to standard Java 17 / Jakarta EE bytecode and run on vanilla JVMs without any Docker/container requirements.
- **Standard Enterprise Libraries**: The application relies exclusively on standard Spring Boot Starter dependencies (Batch, Web, JPA, H2/PostgreSQL) and standard Java standard library utilities.
