# Security Hardening & Vulnerability Mitigation
## Zero-Trust Repository Processing, Parameterization & Cryptographic Integrity

---

## 1. Zero-Trust Untrusted Repository Processing

1. **Path Traversal Protection**:
   - All filesystem operations validate that paths resolve strictly within the project workspace using canonical path checks (`os.path.realpath`).
   - Copybook inclusion paths (`COPY "..."`) cannot escape to system root or parent directories.
2. **Subprocess & Command Safety**:
   - Subprocesses are spawned using list-based argument arrays (`subprocess.run(["cmd", "arg1"])`) without `shell=True`.
3. **Archive Security**:
   - Repository ZIP extractions enforce entry count limits, uncompressed size caps, and directory boundary enforcement to prevent zip-bomb vulnerabilities.

---

## 2. SQL Injection Prevention

- All SQL host variables in `EXEC SQL` blocks are transpiled to positional `?` parameter markers in Spring `JdbcTemplate` queries and updates.
- Dynamic string interpolation or unescaped concatenation into SQL strings is strictly prohibited.

---

## 3. Secret & Credential Redaction

- Passwords, database URLs, and API tokens are read exclusively from environment variables (`PGPASSWORD`, `DB_PASSWORD`).
- All pipeline logging utilities automatically redact sensitive environment variables and credentials before writing to disk.
