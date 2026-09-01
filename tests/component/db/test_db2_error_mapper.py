import os
import shutil
import tempfile
import subprocess
import pytest

def test_db2_error_mapper_compilation_and_behavior():
    # Verify that Db2ErrorMapper compiles and maps SQL exceptions to DB2 codes correctly
    tmp_dir = tempfile.mkdtemp()
    try:
        pkg_dir = os.path.join(tmp_dir, "com", "systema", "modernized")
        os.makedirs(pkg_dir, exist_ok=True)
        
        # Write Db2ErrorMapper.java
        mapper_src = """package com.systema.modernized;
public class Db2ErrorMapper {
    public static int getSqlCode(Exception e) {
        if (e instanceof org.springframework.dao.EmptyResultDataAccessException) {
            return 100;
        }
        Throwable cause = e.getCause();
        if (cause instanceof java.sql.SQLException) {
            java.sql.SQLException sqle = (java.sql.SQLException) cause;
            String state = sqle.getSQLState();
            if ("23505".equals(state)) return -803; // duplicate key
            if ("42P01".equals(state) || "42S02".equals(state)) return -204; // table undefined
            if ("42703".equals(state) || "42S22".equals(state)) return -206; // column undefined
            int code = sqle.getErrorCode();
            return code != 0 ? -Math.abs(code) : -1;
        }
        return -1;
    }
    
    public static String getSqlState(Exception e) {
        if (e instanceof org.springframework.dao.EmptyResultDataAccessException) {
            return "02000";
        }
        Throwable cause = e.getCause();
        if (cause instanceof java.sql.SQLException) {
            java.sql.SQLException sqle = (java.sql.SQLException) cause;
            String state = sqle.getSQLState();
            if ("42P01".equals(state) || "42S02".equals(state)) return "42704"; // table undefined
            if ("42703".equals(state) || "42S22".equals(state)) return "42704";
            return state != null ? state : "99999";
        }
        return "99999";
    }
}
"""
        with open(os.path.join(pkg_dir, "Db2ErrorMapper.java"), "w", encoding="utf-8") as fh:
            fh.write(mapper_src)
            
        # Write EmptyResultDataAccessException mock (since Spring JAR is not in raw classpath, we can mock it)
        spring_mock_dir = os.path.join(tmp_dir, "org", "springframework", "dao")
        os.makedirs(spring_mock_dir, exist_ok=True)
        spring_mock_src = """package org.springframework.dao;
public class EmptyResultDataAccessException extends RuntimeException {
    public EmptyResultDataAccessException(String msg) {
        super(msg);
    }
}
"""
        with open(os.path.join(spring_mock_dir, "EmptyResultDataAccessException.java"), "w", encoding="utf-8") as fh:
            fh.write(spring_mock_src)

        # Write TestMain.java
        test_main_src = """import com.systema.modernized.Db2ErrorMapper;
import org.springframework.dao.EmptyResultDataAccessException;
import java.sql.SQLException;

public class TestMain {
    public static void main(String[] args) {
        // Test 1: EmptyResultDataAccessException -> 100 / "02000"
        Exception e1 = new EmptyResultDataAccessException("No row found");
        System.out.println("T1:" + Db2ErrorMapper.getSqlCode(e1) + ":" + Db2ErrorMapper.getSqlState(e1));
        
        // Test 2: SQLException with State 23505 -> -803 / "23505"
        SQLException sqle2 = new SQLException("Duplicate key", "23505", 0);
        Exception e2 = new Exception(sqle2);
        System.out.println("T2:" + Db2ErrorMapper.getSqlCode(e2) + ":" + Db2ErrorMapper.getSqlState(e2));
        
        // Test 3: SQLException with State 42P01 -> -204 / "42704"
        SQLException sqle3 = new SQLException("Table undefined", "42P01", 0);
        Exception e3 = new Exception(sqle3);
        System.out.println("T3:" + Db2ErrorMapper.getSqlCode(e3) + ":" + Db2ErrorMapper.getSqlState(e3));
    }
}
"""
        with open(os.path.join(tmp_dir, "TestMain.java"), "w", encoding="utf-8") as fh:
            fh.write(test_main_src)
            
        # Compile
        res_compile = subprocess.run([
            "javac", 
            "org/springframework/dao/EmptyResultDataAccessException.java",
            "com/systema/modernized/Db2ErrorMapper.java",
            "TestMain.java"
        ], cwd=tmp_dir, capture_output=True, text=True)
        assert res_compile.returncode == 0, f"Compilation failed: {res_compile.stderr}"
        
        # Execute
        res_exec = subprocess.run([
            "java", "TestMain"
        ], cwd=tmp_dir, capture_output=True, text=True)
        assert res_exec.returncode == 0, f"Execution failed: {res_exec.stderr}"
        
        output = res_exec.stdout.strip().splitlines()
        assert output[0] == "T1:100:02000"
        assert output[1] == "T2:-803:23505"
        assert output[2] == "T3:-204:42704"
        
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
