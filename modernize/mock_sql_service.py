import os
import yaml

def generate_mock_sql_assets(yaml_path: str, generated_dir: str, build_dir: str):
    """
    Parses mock_db.yaml, generates mock_schema.sql, mock_data.sql, and MockSqlService.java.
    Saves SQL scripts to:
      1. build_dir/mock_schema.sql and build_dir/mock_data.sql (for local classpath resolution in Gate 1)
      2. generated_dir/src/main/resources/mock_schema.sql and mock_data.sql (for Gate 2 Spring Boot packing)
    """
    if not os.path.exists(yaml_path):
        return

    with open(yaml_path, 'r', encoding='utf-8') as fh:
        config = yaml.safe_load(fh)

    tables = config.get('tables', [])
    schema_lines = []
    data_lines = []

    for table in tables:
        name = table.get('name', '').upper()
        columns = table.get('columns', [])
        rows = table.get('rows', [])

        # Schema definition
        schema_lines.append(f"DROP TABLE IF EXISTS {name};")
        col_defs = []
        col_names = []
        for col in columns:
            col_name = col.get('name', '').upper()
            col_type = col.get('type', '').upper()
            col_names.append(col_name)
            
            is_pk = col.get('primary_key', False)
            pk_str = " PRIMARY KEY" if is_pk else ""
            col_defs.append(f"    {col_name} {col_type}{pk_str}")
            
        schema_lines.append(f"CREATE TABLE {name} (\n" + ",\n".join(col_defs) + "\n);")
        schema_lines.append("")

        # Data definition
        for row in rows:
            val_strs = []
            for val in row:
                if val is None:
                    val_strs.append("NULL")
                elif isinstance(val, bool):
                    val_strs.append("TRUE" if val else "FALSE")
                elif isinstance(val, str):
                    escaped = val.replace("'", "''")
                    val_strs.append(f"'{escaped}'")
                else:
                    val_strs.append(str(val))
            cols_str = ", ".join(col_names)
            vals_str = ", ".join(val_strs)
            data_lines.append(f"INSERT INTO {name} ({cols_str}) VALUES ({vals_str});")
        data_lines.append("")

    schema_sql = "\n".join(schema_lines)
    data_sql = "\n".join(data_lines)

    # Write DDL/DML to build_dir (Gate 1 local execution)
    os.makedirs(build_dir, exist_ok=True)
    with open(os.path.join(build_dir, "mock_schema.sql"), "w", encoding="utf-8") as fh:
        fh.write(schema_sql)
    with open(os.path.join(build_dir, "mock_data.sql"), "w", encoding="utf-8") as fh:
        fh.write(data_sql)

    # Write DDL/DML to resources dir (Gate 2 production pack)
    resources_dir = os.path.join(generated_dir, "src", "main", "resources")
    os.makedirs(resources_dir, exist_ok=True)
    with open(os.path.join(resources_dir, "mock_schema.sql"), "w", encoding="utf-8") as fh:
        fh.write(schema_sql)
    with open(os.path.join(resources_dir, "mock_data.sql"), "w", encoding="utf-8") as fh:
        fh.write(data_sql)

    # Generate MockSqlService.java helper
    java_helpers_dir = os.path.join(generated_dir, "src", "main", "java", "com", "systema", "modernized")
    os.makedirs(java_helpers_dir, exist_ok=True)
    
    java_src = """package com.systema.modernized;

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
"""
    with open(os.path.join(java_helpers_dir, "MockSqlService.java"), "w", encoding="utf-8") as fh:
        fh.write(java_src)
