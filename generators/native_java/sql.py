"""
generators/native_java/sql.py

Generates Java JDBC / Spring JDBC code for parsed EXEC SQL statements.

Supports:
  - SELECT ... INTO :var1 FROM table WHERE col = :var2
  - INSERT / UPDATE / DELETE
  - DECLARE / OPEN / FETCH / CLOSE CURSOR
  - SQLCODE and SQLSTATE updates (0 = OK, 100 = NOT FOUND, -1 = ERROR)
"""
from __future__ import annotations

from transformation.sql.extractor import parse_sql_block, ParsedSqlStatement
from generators.native_java.types import to_java_var


def translate_sql_block(sql_text: str, ctx: "GeneratorContext") -> list[str]:
    """
    Translate an EXEC SQL block into Java code lines.

    Parameters
    ----------
    sql_text: Content of EXEC SQL block.
    ctx: GeneratorContext.

    Returns
    -------
    List of Java source lines.
    """
    parsed = parse_sql_block(sql_text)
    lines = []

    lines.append(f"// EXEC SQL: {parsed.statement_type}")

    if parsed.statement_type == "SELECT_INTO":
        lines.extend(_translate_select_into(parsed, ctx))
    elif parsed.statement_type in ("INSERT", "UPDATE", "DELETE"):
        lines.extend(_translate_dml(parsed, ctx))
    elif parsed.statement_type == "DECLARE_CURSOR":
        lines.extend(_translate_declare_cursor(parsed, ctx))
    elif parsed.statement_type == "OPEN_CURSOR":
        lines.extend(_translate_open_cursor(parsed, ctx))
    elif parsed.statement_type == "FETCH":
        lines.extend(_translate_fetch(parsed, ctx))
    elif parsed.statement_type == "CLOSE_CURSOR":
        lines.extend(_translate_close_cursor(parsed, ctx))
    else:
        lines.append(f"// UNHANDLED SQL STATEMENT: {parsed.clean_sql}")

    return lines


def _translate_select_into(parsed: ParsedSqlStatement, ctx: "GeneratorContext") -> list[str]:
    lines = []
    lines.append("try {")
    lines.append(f'    String _sql = "{parsed.clean_sql}";')

    # Prepare parameters
    param_vars = [to_java_var(v) for v in parsed.input_vars]
    into_vars = [to_java_var(v) for v in parsed.into_vars]

    # Connection lookup (standard JDBC for standalone execution)
    lines.append("    try (java.sql.Connection _conn = getDbConnection();")
    lines.append("         java.sql.PreparedStatement _stmt = _conn.prepareStatement(_sql)) {")

    for idx, pvar in enumerate(param_vars, start=1):
        lines.append(f"        _stmt.setObject({idx}, {pvar});")

    lines.append("        try (java.sql.ResultSet _rs = _stmt.executeQuery()) {")
    lines.append("            if (_rs.next()) {")

    for idx, ivar in enumerate(into_vars, start=1):
        ti = ctx.field_type(ivar)
        if ti and ti.is_numeric:
            if ti.java_type == "int":
                lines.append(f"                {ivar} = _rs.getInt({idx});")
            elif ti.java_type == "long":
                lines.append(f"                {ivar} = _rs.getLong({idx});")
            else:
                lines.append(f"                {ivar} = _rs.getBigDecimal({idx});")
        else:
            lines.append(f"                {ivar} = _rs.getString({idx});")
            lines.append(f"                if ({ivar} == null) {ivar} = \"\";")

    lines.append("                sqlcode = 0;")
    lines.append('                sqlstate = "00000";')
    lines.append("            } else {")
    lines.append("                sqlcode = 100; // COBOL NOT FOUND")
    lines.append('                sqlstate = "02000";')
    lines.append("            }")
    lines.append("        }")
    lines.append("    }")
    lines.append("} catch (Exception _e) {")
    lines.append("    sqlcode = -1;")
    lines.append('    sqlstate = "58004";')
    lines.append('    System.err.println("SQL Error: " + _e.getMessage());')
    lines.append("}")

    return lines


def _translate_dml(parsed: ParsedSqlStatement, ctx: "GeneratorContext") -> list[str]:
    lines = []
    lines.append("try {")
    lines.append(f'    String _sql = "{parsed.clean_sql}";')
    lines.append("    try (java.sql.Connection _conn = getDbConnection();")
    lines.append("         java.sql.PreparedStatement _stmt = _conn.prepareStatement(_sql)) {")

    for idx, pvar in enumerate(parsed.input_vars, start=1):
        lines.append(f"        _stmt.setObject({idx}, {to_java_var(pvar)});")

    lines.append("        int _count = _stmt.executeUpdate();")
    lines.append("        if (_count > 0) {")
    lines.append("            sqlcode = 0;")
    lines.append('            sqlstate = "00000";')
    lines.append("        } else {")
    lines.append("            sqlcode = 100;")
    lines.append('            sqlstate = "02000";')
    lines.append("        }")
    lines.append("    }")
    lines.append("} catch (Exception _e) {")
    lines.append("    sqlcode = -1;")
    lines.append('    sqlstate = "58004";')
    lines.append("}")

    return lines


def _translate_declare_cursor(parsed: ParsedSqlStatement, ctx: "GeneratorContext") -> list[str]:
    cname = to_java_var(parsed.cursor_name or "C1")
    return [
        f'// DECLARE CURSOR {parsed.cursor_name}',
        f'private String {cname}_sql = "{parsed.clean_sql}";',
        f'private java.sql.ResultSet {cname}_rs = null;',
        f'private java.sql.PreparedStatement {cname}_stmt = null;',
    ]


def _translate_open_cursor(parsed: ParsedSqlStatement, ctx: "GeneratorContext") -> list[str]:
    cname = to_java_var(parsed.cursor_name or "C1")
    return [
        "try {",
        f"    java.sql.Connection _conn = getDbConnection();",
        f"    {cname}_stmt = _conn.prepareStatement({cname}_sql);",
        f"    {cname}_rs = {cname}_stmt.executeQuery();",
        "    sqlcode = 0;",
        '    sqlstate = "00000";',
        "} catch (Exception _e) {",
        "    sqlcode = -1;",
        '    sqlstate = "58004";',
        "}",
    ]


def _translate_fetch(parsed: ParsedSqlStatement, ctx: "GeneratorContext") -> list[str]:
    cname = to_java_var(parsed.cursor_name or "C1")
    into_vars = [to_java_var(v) for v in parsed.into_vars]

    lines = []
    lines.append("try {")
    lines.append(f"    if ({cname}_rs != null && {cname}_rs.next()) {{")
    for idx, ivar in enumerate(into_vars, start=1):
        ti = ctx.field_type(ivar)
        if ti and ti.is_numeric:
            if ti.java_type == "int":
                lines.append(f"        {ivar} = {cname}_rs.getInt({idx});")
            elif ti.java_type == "long":
                lines.append(f"        {ivar} = {cname}_rs.getLong({idx});")
            else:
                lines.append(f"        {ivar} = {cname}_rs.getBigDecimal({idx});")
        else:
            lines.append(f"        {ivar} = {cname}_rs.getString({idx});")
            lines.append(f"        if ({ivar} == null) {ivar} = \"\";")
    lines.append("        sqlcode = 0;")
    lines.append('        sqlstate = "00000";')
    lines.append("    } else {")
    lines.append("        sqlcode = 100; // END OF CURSOR")
    lines.append('        sqlstate = "02000";')
    lines.append("    }")
    lines.append("} catch (Exception _e) {")
    lines.append("    sqlcode = -1;")
    lines.append('    sqlstate = "58004";')
    lines.append("}")
    return lines


def _translate_close_cursor(parsed: ParsedSqlStatement, ctx: "GeneratorContext") -> list[str]:
    cname = to_java_var(parsed.cursor_name or "C1")
    return [
        "try {",
        f"    if ({cname}_rs != null) {cname}_rs.close();",
        f"    if ({cname}_stmt != null) {cname}_stmt.close();",
        "    sqlcode = 0;",
        '    sqlstate = "00000";',
        "} catch (Exception _e) {",
        "    sqlcode = -1;",
        '    sqlstate = "58004";',
        "}",
    ]
