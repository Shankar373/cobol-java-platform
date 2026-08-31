"""Unit tests for the EXEC SQL extractor."""
import pytest
from transformation.sql.extractor import parse_sql_block


class TestSqlExtractor:
    def test_parse_select_into(self):
        sql = """
            EXEC SQL
                SELECT CUST_NAME
                INTO :WS-CUST-NAME
                FROM CUSTOMER
                WHERE CUST_ID = :WS-CUST-ID
            END-EXEC.
        """
        parsed = parse_sql_block(sql)
        assert parsed.statement_type == "SELECT_INTO"
        assert parsed.into_vars == ["WS-CUST-NAME"]
        assert parsed.input_vars == ["WS-CUST-ID"]
        assert "?" in parsed.clean_sql
        assert ":WS-CUST-NAME" not in parsed.clean_sql

    def test_parse_insert(self):
        sql = "EXEC SQL INSERT INTO CUSTOMER (CUST_ID, CUST_NAME) VALUES (:ID, :NAME) END-EXEC"
        parsed = parse_sql_block(sql)
        assert parsed.statement_type == "INSERT"
        assert parsed.input_vars == ["ID", "NAME"]
        assert "?" in parsed.clean_sql

    def test_parse_declare_cursor(self):
        sql = "EXEC SQL DECLARE C1 CURSOR FOR SELECT CUST_NAME FROM CUSTOMER WHERE DEPT = :DEPT END-EXEC"
        parsed = parse_sql_block(sql)
        assert parsed.statement_type == "DECLARE_CURSOR"
        assert parsed.cursor_name == "C1"
        assert parsed.input_vars == ["DEPT"]
