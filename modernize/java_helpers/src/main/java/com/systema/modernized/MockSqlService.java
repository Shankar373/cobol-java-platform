package com.systema.modernized;

import java.io.InputStream;
import java.sql.Connection;
import java.sql.Statement;
import java.util.Scanner;

public class MockSqlService {
    private static boolean initialized = false;

    public static synchronized void initialize() {
        if (initialized) return;
        if (System.getenv("PGHOST") != null || "1".equals(System.getenv("REAL_DB2_MODE"))) {
            initialized = true;
            return;
        }

        // If no embedded mock resources were packaged, there is nothing to
        // initialize. This is the normal path for real-database generated
        // applications and must not be treated as an application failure.
        boolean hasSchema = MockSqlService.class.getResource("/mock_schema.sql") != null;
        boolean hasData = MockSqlService.class.getResource("/mock_data.sql") != null;
        if (!hasSchema && !hasData) {
            initialized = true;
            return;
        }

        try {
            // Instantiate H2 memory DB connection if jdbcTemplate is null
            if (SpringContextHelper.jdbcTemplate == null) {
                org.springframework.jdbc.datasource.SimpleDriverDataSource ds = new org.springframework.jdbc.datasource.SimpleDriverDataSource();
                ds.setDriverClass(org.h2.Driver.class);
                ds.setUrl("jdbc:h2:mem:db2mem;DB_CLOSE_DELAY=-1");
                ds.setUsername("sa");
                ds.setPassword("");
                SpringContextHelper.jdbcTemplate = new org.springframework.jdbc.core.JdbcTemplate(ds);
                SpringContextHelper.transactionManager = new org.springframework.jdbc.datasource.DataSourceTransactionManager(ds);
            }

            Connection conn = SpringContextHelper.jdbcTemplate.getDataSource().getConnection();
            
            // Execute schema script
            InputStream schemaStream = MockSqlService.class.getResourceAsStream("/mock_schema.sql");
            if (schemaStream != null) {
                executeSqlScript(conn, schemaStream);
            }
            
            // Execute data script
            InputStream dataStream = MockSqlService.class.getResourceAsStream("/mock_data.sql");
            if (dataStream != null) {
                executeSqlScript(conn, dataStream);
            }
            
            conn.close();
            initialized = true;
        } catch (Exception e) {
            System.err.println("Failed to initialize MockSqlService database: " + e.getMessage());
            e.printStackTrace();
        }
    }

    private static void executeSqlScript(Connection conn, InputStream is) throws Exception {
        try (Scanner s = new Scanner(is, "UTF-8").useDelimiter("\\\\A")) {
            String content = s.hasNext() ? s.next() : "";
            try (Statement stmt = conn.createStatement()) {
                for (String sql : content.split(";")) {
                    String trimmed = sql.trim();
                    if (!trimmed.isEmpty()) {
                        stmt.execute(trimmed);
                    }
                }
            }
        }
    }
}
