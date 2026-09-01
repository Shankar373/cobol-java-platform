package com.systema.modernized;

import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
public class KsdSDbService {
    
    public static class KsdsFile {
        private final JdbcTemplate jdbcTemplate;
        private final String tableName;
        private final String keyColumn = "key_col";
        private final String recordColumn = "record_col";
        private List<String> cursorList = null;
        private Iterator<String> cursorIterator = null;

        public KsdsFile(JdbcTemplate jdbcTemplate, String tableName) {
            this.jdbcTemplate = jdbcTemplate;
            this.tableName = tableName.toLowerCase().replace("-", "_") + "_vsam";
        }

        public void init(String keyColDdl, String[] altKeyDdls) {
            if (jdbcTemplate != null) {
                StringBuilder ddl = new StringBuilder("CREATE TABLE IF NOT EXISTS " + tableName + " (" + keyColumn + " " + keyColDdl + " PRIMARY KEY");
                if (altKeyDdls != null) {
                    for (String ak : altKeyDdls) {
                        ddl.append(", ").append(ak);
                    }
                }
                ddl.append(", ").append(recordColumn).append(" VARCHAR(4000))");
                jdbcTemplate.execute(ddl.toString());
            }
        }

        public String readKey(String key, String[] fileStatus) {
            if (jdbcTemplate == null) {
                fileStatus[0] = "30";
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
                fileStatus[0] = "23";
                return null;
            } catch (Exception e) {
                fileStatus[0] = "30";
                return null;
            }
        }

        public boolean start(String key, String op, String[] fileStatus) {
            return start(key, op, keyColumn, fileStatus);
        }

        public boolean start(String key, String op, String keyColName, String[] fileStatus) {
            if (jdbcTemplate == null) {
                fileStatus[0] = "30";
                return false;
            }
            String sqlOp = "=";
            if (">".equals(op)) sqlOp = ">";
            else if (">=".equals(op)) sqlOp = ">=";

            try {
                cursorList = jdbcTemplate.query(
                    "SELECT " + recordColumn + " FROM " + tableName + " WHERE " + keyColName + " " + sqlOp + " ? ORDER BY " + keyColName,
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
                fileStatus[0] = "46";
                return null;
            }
            if (!cursorIterator.hasNext()) {
                fileStatus[0] = "10";
                return null;
            }
            fileStatus[0] = "00";
            return cursorIterator.next();
        }

        public boolean write(String key, String record, String[] fileStatus) {
            return write(key, null, null, record, fileStatus);
        }

        public boolean write(String key, String[] altKeys, String[] altVals, String record, String[] fileStatus) {
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
                    fileStatus[0] = "22";
                    return false;
                }
                StringBuilder cols = new StringBuilder(keyColumn);
                StringBuilder placeholders = new StringBuilder("?");
                List<Object> args = new ArrayList<>();
                args.add(key.trim());
                if (altKeys != null && altVals != null) {
                    for (int i = 0; i < altKeys.length; i++) {
                        cols.append(", ").append(altKeys[i]);
                        placeholders.append(", ?");
                        args.add(altVals[i].trim());
                    }
                }
                cols.append(", ").append(recordColumn);
                placeholders.append(", ?");
                args.add(record);

                jdbcTemplate.update(
                    "INSERT INTO " + tableName + " (" + cols + ") VALUES (" + placeholders + ")",
                    args.toArray()
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
                    fileStatus[0] = "23";
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
                    fileStatus[0] = "23";
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

    public KsdsFile getFile(JdbcTemplate jdbcTemplate, String tableName) {
        return new KsdsFile(jdbcTemplate, tableName);
    }
}
