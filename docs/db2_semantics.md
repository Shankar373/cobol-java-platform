# DB2 & Enterprise SQL Semantics Specification
## Modernization Architecture & Translation Reference

---

## 1. Relational Boundary Specification

When modernizing mainframe Enterprise COBOL programs containing embedded SQL (`EXEC SQL ... END-EXEC`), the platform translates embedded queries into Spring Boot Data / Spring JDBC calls targeting PostgreSQL.

### Execution Target Principles
1. **Target Dialect**: PostgreSQL 15+ via Spring JDBC (`JdbcTemplate`).
2. **Type Mapping**:
   - `PIC S9(4) COMP` / `SMALLINT` ➔ `short` / `Integer`
   - `PIC S9(9) COMP` / `INTEGER` ➔ `int` / `Integer`
   - `PIC S9(18) COMP` / `BIGINT` ➔ `long` / `Long`
   - `PIC S9(p)V9(s) COMP-3` / `DECIMAL(p,s)` ➔ `BigDecimal`
   - `PIC X(n)` / `CHAR(n)`, `VARCHAR(n)` ➔ `String` (with whitespace handling and fixed-width padding)
   - `PIC X(10)` / `DATE` ➔ `String` (`YYYY-MM-DD`) / `LocalDate`
   - `PIC X(26)` / `TIMESTAMP` ➔ `String` (`YYYY-MM-DD HH:MM:SS.ffffff`) / `LocalDateTime`
3. **Nullability Indicator Mapping**:
   - COBOL: `:HOST-VAR :IND-VAR` where `IND-VAR` is `PIC S9(4) COMP`.
   - Java: On read, `rs.wasNull()` sets `indVar = -1`; on write, `indVar == -1` passes `null` parameter.

---

## 2. Dialect Translation Rules

### 2.1 Single-Row and Dummy Queries
- DB2: `SELECT CURRENT TIMESTAMP INTO :WS-TIME FROM SYSIBM.SYSDUMMY1`
- Modernized: `SELECT CURRENT_TIMESTAMP`

### 2.2 Row Limiting
- DB2: `SELECT * FROM CUSTOMER FETCH FIRST 10 ROWS ONLY`
- Modernized: `SELECT * FROM CUSTOMER LIMIT 10`

### 2.3 Isolation Hints
- DB2: `SELECT * FROM ORDERS WITH UR`
- Modernized: `SELECT * FROM ORDERS` (read uncommitted hint stripped; isolation managed via Spring transaction definition)

### 2.4 Error Handling
- All SQL operations are wrapped in `try-catch` blocks.
- Caught exceptions are mapped using `Db2ErrorMapper`:
  - `EmptyResultDataAccessException` ➔ `sqlcode = 100`, `sqlstate = "02000"`
  - `Duplicate Key (23505)` ➔ `sqlcode = -803`, `sqlstate = "23000"`
  - `Table Not Found (42P01)` ➔ `sqlcode = -204`, `sqlstate = "42704"`
  - `Column Not Found (42703)` ➔ `sqlcode = -206`, `sqlstate = "42704"`
  - `Deadlock (40001)` ➔ `sqlcode = -911`, `sqlstate = "40001"`

---

## 3. Transaction Management

- Transaction boundary operations `EXEC SQL COMMIT END-EXEC` and `EXEC SQL ROLLBACK END-EXEC` map to `PlatformTransactionManager.commit()` and `PlatformTransactionManager.rollback()` within `SpringContextHelper`.
- Real database state is isolated per execution session:
  - Database schema and initial data are seeded prior to execution.
  - Transactions are isolated and verified against baseline expectations.
