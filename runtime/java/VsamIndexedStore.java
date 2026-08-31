package com.systema.modernized.runtime;

import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;

public class VsamIndexedStore {
    private final JdbcTemplate jdbcTemplate;
    private final String tableName;
    private final String keyColumn = "key_col";
    private final String recordColumn = "record_col";
    private List<String> cursorList = null;
    private Iterator<String> cursorIterator = null;

    public VsamIndexedStore(JdbcTemplate jdbcTemplate, String tableName) {
        this.jdbcTemplate = jdbcTemplate;
        this.tableName = tableName.toLowerCase().replace("-", "_") + "_vsam";
        initializeTable();
    }

    private void initializeTable() {
        if (jdbcTemplate != null) {
            jdbcTemplate.execute("CREATE TABLE IF NOT EXISTS " + tableName + " (" + keyColumn + " VARCHAR(255) PRIMARY KEY, " + recordColumn + " VARCHAR(4000))");
        }
    }

    public String readKey(String key, String[] fileStatus) {
        if (jdbcTemplate == null) {
            fileStatus[0] = "30"; // Permanent error
            return null;
        }
        try {
            String record = jdbcTemplate.queryForObject(
                "SELECT " + recordColumn + " FROM " + tableName + " WHERE " + keyColumn + " = ?",
                String.class, key.trim()
            );
            fileStatus[0] = "00";
            return record;
        } catch (org.springframework.dao.EmptyResultDataAccessException e) {
            fileStatus[0] = "23"; // Key not found
            return null;
        } catch (Exception e) {
            fileStatus[0] = "30";
            return null;
        }
    }

    public boolean start(String key, String op, String[] fileStatus) {
        if (jdbcTemplate == null) {
            fileStatus[0] = "30";
            return false;
        }
        String sqlOp = "=";
        if (">".equals(op)) sqlOp = ">";
        else if (">=".equals(op)) sqlOp = ">=";

        try {
            cursorList = jdbcTemplate.query(
                "SELECT " + recordColumn + " FROM " + tableName + " WHERE " + keyColumn + " " + sqlOp + " ? ORDER BY " + keyColumn,
                (rs, rowNum) -> rs.getString(recordColumn), key.trim()
            );
            if (cursorList.isEmpty()) {
                fileStatus[0] = "23";
                cursorIterator = null;
                return false;
            }
            cursorIterator = cursorList.iterator();
            fileStatus[0] = "00";
            return true;
        } catch (Exception e) {
            fileStatus[0] = "30";
            return false;
        }
    }

    public String readNext(String[] fileStatus) {
        if (cursorIterator == null) {
            fileStatus[0] = "46"; // Read next without start
            return null;
        }
        if (!cursorIterator.hasNext()) {
            fileStatus[0] = "10"; // EOF
            return null;
        }
        fileStatus[0] = "00";
        return cursorIterator.next();
    }

    public boolean write(String key, String record, String[] fileStatus) {
        if (jdbcTemplate == null) {
            fileStatus[0] = "30";
            return false;
        }
        try {
            int existing = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM " + tableName + " WHERE " + keyColumn + " = ?",
                Integer.class, key.trim()
            );
            if (existing > 0) {
                fileStatus[0] = "22"; // Duplicate key
                return false;
            }
            jdbcTemplate.update(
                "INSERT INTO " + tableName + " (" + keyColumn + ", " + recordColumn + ") VALUES (?, ?)",
                key.trim(), record
            );
            fileStatus[0] = "00";
            return true;
        } catch (Exception e) {
            fileStatus[0] = "30";
            return false;
        }
    }

    public boolean rewrite(String key, String record, String[] fileStatus) {
        if (jdbcTemplate == null) {
            fileStatus[0] = "30";
            return false;
        }
        try {
            int rows = jdbcTemplate.update(
                "UPDATE " + tableName + " SET " + recordColumn + " = ? WHERE " + keyColumn + " = ?",
                record, key.trim()
            );
            if (rows == 0) {
                fileStatus[0] = "23"; // Key not found
                return false;
            }
            fileStatus[0] = "00";
            return true;
        } catch (Exception e) {
            fileStatus[0] = "30";
            return false;
        }
    }

    public boolean delete(String key, String[] fileStatus) {
        if (jdbcTemplate == null) {
            fileStatus[0] = "30";
            return false;
        }
        try {
            int rows = jdbcTemplate.update(
                "DELETE FROM " + tableName + " WHERE " + keyColumn + " = ?",
                key.trim()
            );
            if (rows == 0) {
                fileStatus[0] = "23"; // Key not found
                return false;
            }
            fileStatus[0] = "00";
            return true;
        } catch (Exception e) {
            fileStatus[0] = "30";
            return false;
        }
    }
}
