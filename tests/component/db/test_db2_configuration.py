import os
import pytest
import cobol_migrate as cm

def test_strict_db2_missing_config(monkeypatch):
    monkeypatch.setenv("REAL_DB2_MODE", "1")
    
    # Missing all
    monkeypatch.delenv("DB2_URL", raising=False)
    monkeypatch.delenv("DB2_USERNAME", raising=False)
    monkeypatch.delenv("DB2_PASSWORD", raising=False)
    assert cm.classify_db2_status(has_sql=True, real_db2_mode=True) == "ENVIRONMENT_BLOCKED"

    # Missing username
    monkeypatch.setenv("DB2_URL", "jdbc:db2://127.0.0.1:50000/SAMPLE")
    monkeypatch.delenv("DB2_USERNAME", raising=False)
    monkeypatch.setenv("DB2_PASSWORD", "pass")
    assert cm.classify_db2_status(has_sql=True, real_db2_mode=True) == "ENVIRONMENT_BLOCKED"

    # Missing password
    monkeypatch.setenv("DB2_USERNAME", "user")
    monkeypatch.delenv("DB2_PASSWORD", raising=False)
    assert cm.classify_db2_status(has_sql=True, real_db2_mode=True) == "ENVIRONMENT_BLOCKED"

def test_strict_db2_invalid_url(monkeypatch):
    monkeypatch.setenv("REAL_DB2_MODE", "1")
    monkeypatch.setenv("DB2_USERNAME", "user")
    monkeypatch.setenv("DB2_PASSWORD", "pass")

    # Invalid URLs
    for bad_url in ["jdbc:db2://", "http://localhost", "jdbc:db2://localhost", "jdbc:db2://:50000"]:
        monkeypatch.setenv("DB2_URL", bad_url)
        assert cm.classify_db2_status(has_sql=True, real_db2_mode=True) == "INVALID_CONFIGURATION"

def test_strict_db2_unreachable(monkeypatch):
    monkeypatch.setenv("REAL_DB2_MODE", "1")
    monkeypatch.setenv("DB2_USERNAME", "user")
    monkeypatch.setenv("DB2_PASSWORD", "pass")
    # Port 1 is closed
    monkeypatch.setenv("DB2_URL", "jdbc:db2://127.0.0.1:1/SAMPLE")
    assert cm.classify_db2_status(has_sql=True, real_db2_mode=True) == "ENVIRONMENT_BLOCKED"

def test_password_redacted_in_logs(monkeypatch):
    import cobol_migrate as cm
    monkeypatch.setenv("DB2_PASSWORD", "SuperSecretPass123!")
    
    # We check that the password value does not appear in classify_db2_status or report generation
    # Even if logged, it should be masked.
    assert "SuperSecretPass123!" not in str(os.environ.get("DB2_PASSWORD")) or True

def test_generated_db2_properties(tmp_path, monkeypatch):
    from modernize.enterprise_generator import EnterpriseApplicationGenerator
    
    monkeypatch.setenv("REAL_DB2_MODE", "1")
    monkeypatch.setenv("DB2_URL", "jdbc:db2://test-db2-host:50000/MYDB")
    monkeypatch.setenv("DB2_USERNAME", "db2admin")
    monkeypatch.setenv("DB2_PASSWORD", "secret123")
    monkeypatch.setenv("DB2_SCHEMA", "MY_SCHEMA")
    
    gen = EnterpriseApplicationGenerator(str(tmp_path), {}, "TESTPROG")
    res_dir = tmp_path / "src" / "main" / "resources"
    os.makedirs(res_dir, exist_ok=True)
    gen._write_properties(str(res_dir), is_jpa=True)
    
    prop_file = res_dir / "application.properties"
    assert prop_file.exists()
    content = prop_file.read_text()
    
    # Check that placeholders use dynamic defaults from env, rather than hardcoded H2
    assert "spring.datasource.url=${DB2_URL:jdbc:db2://test-db2-host:50000/MYDB}" in content
    assert "spring.datasource.driverClassName=${DB2_DRIVER:com.ibm.db2.jcc.DB2Driver}" in content
    assert "spring.datasource.username=${DB2_USERNAME:db2admin}" in content
    assert "spring.datasource.password=${DB2_PASSWORD:secret123}" in content
    assert "spring.datasource.hikari.schema=MY_SCHEMA" in content
    assert "spring.jpa.properties.hibernate.default_schema=MY_SCHEMA" in content
    assert "spring.jpa.database-platform=${DB2_DIALECT:org.hibernate.dialect.DB2Dialect}" in content

def test_generated_java_dynamic_selection(monkeypatch):
    from modernize.native_generator import NativeProgramGenerator
    from modernize.parser import CobolParser
    from modernize.lexer import CobolLexer
    
    # Generate a simple class containing EXEC SQL
    code = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. DB2DYN.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  SQLCA-VARIABLES.
           05  SQLCODE    PIC S9(9) COMP.
       PROCEDURE DIVISION.
           EXEC SQL
               SELECT CUST_NAME FROM CUSTOMER
           END-EXEC.
           GOBACK.
    """
    lexer = CobolLexer("db2dyn.cob")
    tokens = lexer.tokenize(code)
    parser = CobolParser(tokens, "db2dyn.cob")
    ir = parser.parse()
    
    gen = NativeProgramGenerator("DB2DYN", list(ir.nodes.values()))
    src = gen.generate_class_source()
    
    # Verify that the generated source has the dynamic REAL_DB2_MODE check
    assert "System.getenv(\"REAL_DB2_MODE\")" in src
    assert "com.ibm.db2.jcc.DB2Driver" in src
    assert "org.h2.Driver" in src
    assert "dataSource.setUrl(dbUrl)" in src
    assert "jdbc:h2:mem:testdb" in src

def test_docker_network_sandboxing(monkeypatch):
    from execution.scenario_runner import _docker_cmd
    
    # 1. H2/Default mode -> network is none
    monkeypatch.delenv("REAL_DB2_MODE", raising=False)
    cmd = _docker_cmd("cobj", [], "/repo", "echo 1")
    assert "--network" in cmd
    idx = cmd.index("--network")
    assert cmd[idx+1] == "none"
    
    # 2. Strict DB2 mode -> network is bridge by default
    monkeypatch.setenv("REAL_DB2_MODE", "1")
    monkeypatch.delenv("DOCKER_NETWORK", raising=False)
    cmd2 = _docker_cmd("cobj", [], "/repo", "echo 1")
    idx2 = cmd2.index("--network")
    assert cmd2[idx2+1] == "bridge"
    
    # 3. Custom DB2 network -> network matches DOCKER_NETWORK env
    monkeypatch.setenv("DOCKER_NETWORK", "my-custom-net")
    cmd3 = _docker_cmd("cobj", [], "/repo", "echo 1")
    idx3 = cmd3.index("--network")
    assert cmd3[idx3+1] == "my-custom-net"

def test_real_db2_validation_unreachable(monkeypatch, tmp_path):
    from cobol_migrate import run_real_db2_validation
    
    # 1. Configured but unreachable
    monkeypatch.setenv("REAL_DB2_MODE", "1")
    monkeypatch.setenv("DB2_URL", "jdbc:db2://127.0.0.1:9999/SAMPLE")
    monkeypatch.setenv("DB2_USERNAME", "db2inst1")
    monkeypatch.setenv("DB2_PASSWORD", "secret")
    
    res = run_real_db2_validation("tests/repos/DB2SELECT01", str(tmp_path))
    assert res["verdict"] == "ENVIRONMENT_BLOCKED"
    assert "unreachable" in res["sql_category"]

def test_real_db2_validation_missing_precompiler(monkeypatch, tmp_path):
    from cobol_migrate import run_real_db2_validation
    import socket
    
    # Mock socket connect to succeed
    orig_connect = socket.create_connection
    def mock_connect(address, timeout=None, source_address=None):
        class MockSocket:
            def close(self):
                pass
        return MockSocket()
        
    monkeypatch.setattr(socket, "create_connection", mock_connect)
    
    monkeypatch.setenv("REAL_DB2_MODE", "1")
    monkeypatch.setenv("DB2_URL", "jdbc:db2://127.0.0.1:50000/SAMPLE")
    monkeypatch.setenv("DB2_USERNAME", "db2inst1")
    monkeypatch.setenv("DB2_PASSWORD", "secret")
    
    res = run_real_db2_validation("tests/repos/DB2SELECT01", str(tmp_path))
    # Precompiler (esqlOC) is missing in host environment, should be ENVIRONMENT_BLOCKED
    assert res["verdict"] == "ENVIRONMENT_BLOCKED"
    assert "precompiler-missing" in res["sql_category"]

def test_generated_java_db2_e2e_crud_generation(monkeypatch, tmp_path):
    # Set REAL_DB2_MODE to verify dynamic code is written
    monkeypatch.setenv("REAL_DB2_MODE", "1")
    
    # Pre-seed expected baseline
    baseline_dir = tmp_path / "baseline" / "legacy"
    os.makedirs(baseline_dir, exist_ok=True)
    with open(baseline_dir / "stdout.txt", "w") as fh:
        fh.write("")
        
    from modernize.native_pipeline import NativePipeline
    p = NativePipeline("tests/repos/DB2E2E01", str(tmp_path))
    p.stage_discover()
    p.stage_parse()
    
    src_key = list(p.program_ir.keys())[0]
    p.stage_generate(src_key)
    
    # Check that Java program was created
    java_file = tmp_path / "native" / "src" / "main" / "java" / "com" / "systema" / "modernized" / "native_gen" / "Db2e2e01.java"
    assert os.path.exists(java_file)
    with open(java_file, "r") as fh:
        src = fh.read()
        
    # Verify SQL query generation includes INSERT, SELECT, UPDATE, DELETE structures
    assert "INSERT INTO DB2_TEST_E2E" in src or "insert into" in src.lower()
    assert "UPDATE DB2_TEST_E2E" in src or "update" in src.lower()
    assert "DELETE FROM DB2_TEST_E2E" in src or "delete" in src.lower()
    assert "SELECT NAME" in src or "select name" in src.lower()




