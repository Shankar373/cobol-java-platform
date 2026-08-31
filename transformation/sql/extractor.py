"""
transformation/sql/extractor.py

Parses EXEC SQL blocks extracted from COBOL source.

Translates DB2 SQL constructs to PostgreSQL-compatible SQL queries and
extracts COBOL host variables.

Supported DB2 constructs:
  - SELECT ... INTO :var1, :var2 FROM table WHERE ...
  - INSERT INTO table (...) VALUES (:var1, ...)
  - UPDATE table SET col1 = :var1 WHERE ...
  - DELETE FROM table WHERE ...
  - DECLARE cursor CURSOR FOR SELECT ...
  - OPEN cursor / FETCH cursor INTO ... / CLOSE cursor
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SqlHostVar:
    cobol_name: str
    is_indicator: bool = False


@dataclass
class ParsedSqlStatement:
    statement_type: str
    """'SELECT_INTO', 'INSERT', 'UPDATE', 'DELETE', 'DECLARE_CURSOR', 'OPEN_CURSOR', 'FETCH', 'CLOSE_CURSOR'"""

    raw_sql: str
    """Original EXEC SQL block string."""

    clean_sql: str
    """PostgreSQL-compatible SQL string with positional placeholders ($1, $2, ... or ?)."""

    into_vars: list[str] = field(default_factory=list)
    """COBOL host variables receiving query output (INTO clause)."""

    input_vars: list[str] = field(default_factory=list)
    """COBOL host variables supplying input parameters."""

    cursor_name: Optional[str] = None
    """Cursor name if DECLARE/OPEN/FETCH/CLOSE."""


def parse_sql_block(sql_text: str) -> ParsedSqlStatement:
    """
    Parse an EXEC SQL text string into a ParsedSqlStatement.

    Parameters
    ----------
    sql_text:
        Content between EXEC SQL and END-EXEC.

    Returns
    -------
    ParsedSqlStatement
    """
    clean_text = _clean_sql_text(sql_text)
    upper_text = clean_text.upper()

    if upper_text.startswith("SELECT"):
        return _parse_select_into(clean_text)
    elif upper_text.startswith("INSERT"):
        return _parse_insert(clean_text)
    elif upper_text.startswith("UPDATE"):
        return _parse_update(clean_text)
    elif upper_text.startswith("DELETE"):
        return _parse_delete(clean_text)
    elif "DECLARE" in upper_text and "CURSOR" in upper_text:
        return _parse_declare_cursor(clean_text)
    elif upper_text.startswith("OPEN"):
        return _parse_cursor_op("OPEN_CURSOR", clean_text)
    elif upper_text.startswith("FETCH"):
        return _parse_fetch(clean_text)
    elif upper_text.startswith("CLOSE"):
        return _parse_cursor_op("CLOSE_CURSOR", clean_text)

    # Fallback
    return ParsedSqlStatement(
        statement_type="UNKNOWN",
        raw_sql=sql_text,
        clean_sql=clean_text,
    )


def _clean_sql_text(text: str) -> str:
    """Strip EXEC SQL / END-EXEC headers and comments."""
    text = re.sub(r'^\s*EXEC\s+SQL\s+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s+END-EXEC\.?\s*$', '', text, flags=re.IGNORECASE)
    # Replace multiple spaces/newlines with single space
    return " ".join(text.split())


def _parse_select_into(sql: str) -> ParsedSqlStatement:
    """
    Parse SELECT ... INTO :var1, :var2 FROM ... WHERE ...
    """
    # Separate INTO clause from the rest of the query
    into_match = re.search(r'\bINTO\s+((?::[A-Za-z0-9\-_]+(?:\s*:\s*[A-Za-z0-9\-_]+)?\s*,?\s*)+)', sql, re.IGNORECASE)

    into_vars = []
    if into_match:
        raw_into = into_match.group(1)
        # Extract host variables :VAR_NAME
        into_vars = [v.strip().lstrip(":") for v in re.findall(r':([A-Za-z0-9\-_]+)', raw_into)]
        # Remove INTO clause from SQL statement to make standard SQL
        sql_no_into = sql[:into_match.start()] + sql[into_match.end():]
    else:
        sql_no_into = sql

    # Find remaining input host variables in WHERE/etc clause
    input_vars = [v.strip().lstrip(":") for v in re.findall(r':([A-Za-z0-9\-_]+)', sql_no_into)]

    # Replace :HOST_VAR with ?
    pg_sql = re.sub(r':([A-Za-z0-9\-_]+)', '?', sql_no_into)

    return ParsedSqlStatement(
        statement_type="SELECT_INTO",
        raw_sql=sql,
        clean_sql=pg_sql.strip(),
        into_vars=into_vars,
        input_vars=input_vars,
    )


def _parse_insert(sql: str) -> ParsedSqlStatement:
    input_vars = [v.strip().lstrip(":") for v in re.findall(r':([A-Za-z0-9\-_]+)', sql)]
    pg_sql = re.sub(r':([A-Za-z0-9\-_]+)', '?', sql)
    return ParsedSqlStatement(
        statement_type="INSERT",
        raw_sql=sql,
        clean_sql=pg_sql.strip(),
        input_vars=input_vars,
    )


def _parse_update(sql: str) -> ParsedSqlStatement:
    input_vars = [v.strip().lstrip(":") for v in re.findall(r':([A-Za-z0-9\-_]+)', sql)]
    pg_sql = re.sub(r':([A-Za-z0-9\-_]+)', '?', sql)
    return ParsedSqlStatement(
        statement_type="UPDATE",
        raw_sql=sql,
        clean_sql=pg_sql.strip(),
        input_vars=input_vars,
    )


def _parse_delete(sql: str) -> ParsedSqlStatement:
    input_vars = [v.strip().lstrip(":") for v in re.findall(r':([A-Za-z0-9\-_]+)', sql)]
    pg_sql = re.sub(r':([A-Za-z0-9\-_]+)', '?', sql)
    return ParsedSqlStatement(
        statement_type="DELETE",
        raw_sql=sql,
        clean_sql=pg_sql.strip(),
        input_vars=input_vars,
    )


def _parse_declare_cursor(sql: str) -> ParsedSqlStatement:
    m = re.search(r'\bDECLARE\s+([A-Za-z0-9\-_]+)\s+CURSOR\s+FOR\s+(.*)', sql, re.IGNORECASE | re.DOTALL)
    cursor_name = m.group(1) if m else "C1"
    sub_select = m.group(2) if m else sql
    input_vars = [v.strip().lstrip(":") for v in re.findall(r':([A-Za-z0-9\-_]+)', sub_select)]
    pg_sql = re.sub(r':([A-Za-z0-9\-_]+)', '?', sub_select)
    return ParsedSqlStatement(
        statement_type="DECLARE_CURSOR",
        raw_sql=sql,
        clean_sql=pg_sql.strip(),
        cursor_name=cursor_name,
        input_vars=input_vars,
    )


def _parse_fetch(sql: str) -> ParsedSqlStatement:
    m = re.search(r'\bFETCH\s+([A-Za-z0-9\-_]+)\s+INTO\s+(.*)', sql, re.IGNORECASE)
    cursor_name = m.group(1) if m else "C1"
    raw_into = m.group(2) if m else ""
    into_vars = [v.strip().lstrip(":") for v in re.findall(r':([A-Za-z0-9\-_]+)', raw_into)]
    return ParsedSqlStatement(
        statement_type="FETCH",
        raw_sql=sql,
        clean_sql=sql,
        cursor_name=cursor_name,
        into_vars=into_vars,
    )


def _parse_cursor_op(op_type: str, sql: str) -> ParsedSqlStatement:
    words = sql.split()
    cursor_name = words[1] if len(words) > 1 else "C1"
    return ParsedSqlStatement(
        statement_type=op_type,
        raw_sql=sql,
        clean_sql=sql,
        cursor_name=cursor_name,
    )
