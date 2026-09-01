# Track B Native Java / Spring Boot Architecture Standards

## Target Architecture
- **Framework**: Spring Boot 3.2.5 + Plain Java 17.
- **Dependency Discipline**: Zero proprietary COBOL runtime jars (`libcobj.jar`, `jp.osscons`, `COBOL4J`).
- **Data Types**:
  - `BigDecimal` for exact financial fixed-point arithmetic (`CobolNumeric` rounding/truncation).
  - Standard `String` for alphanumeric fields.
  - Standard `int` / `long` for binary counters.
- **Control Flow**: Clean Java methods, loops, switch statements, and dynamic service injection.
- **Database Access**: Standard Spring `JdbcTemplate` with parameterized queries.
- **Online Transactions**: Clean REST Controllers with typed DTOs and thread-isolated transaction context.
