import os
import pytest
import cobol_migrate as cm

def test_local_docker_validation(monkeypatch):
    # Unset DOCKER_HOST should validate successfully to allow local socket usage
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    ok, msg = cm.validate_docker_configuration()
    assert ok is True
    assert msg == "OK"

def test_remote_insecure_docker_tcp_fails(monkeypatch):
    # Remote unauthenticated Docker TCP (e.g. tcp://host:2375) must be blocked
    monkeypatch.setenv("DOCKER_HOST", "tcp://1.2.3.4:2375")
    monkeypatch.delenv("DOCKER_TLS_VERIFY", raising=False)
    ok, msg = cm.validate_docker_configuration()
    assert ok is False
    assert "Insecure remote Docker" in msg

def test_remote_tls_missing_cert_path(monkeypatch):
    # If TLS verify is set or port is 2376, but DOCKER_CERT_PATH is unset
    monkeypatch.setenv("DOCKER_HOST", "tcp://1.2.3.4:2376")
    monkeypatch.delenv("DOCKER_CERT_PATH", raising=False)
    ok, msg = cm.validate_docker_configuration()
    assert ok is False
    assert "DOCKER_CERT_PATH environment variable is not set" in msg

def test_remote_tls_invalid_cert_path(monkeypatch):
    # If DOCKER_CERT_PATH is set but points to a non-existent directory
    monkeypatch.setenv("DOCKER_HOST", "tcp://1.2.3.4:2376")
    monkeypatch.setenv("DOCKER_CERT_PATH", "this-is-not-a-directory-123456")
    ok, msg = cm.validate_docker_configuration()
    assert ok is False
    assert "is not a valid directory" in msg

def test_remote_tls_missing_certs_files(monkeypatch, tmp_path):
    # If DOCKER_CERT_PATH exists but is missing ca.pem, cert.pem, or key.pem
    monkeypatch.setenv("DOCKER_HOST", "tcp://1.2.3.4:2376")
    monkeypatch.setenv("DOCKER_CERT_PATH", str(tmp_path))
    
    # Missing all
    ok, msg = cm.validate_docker_configuration()
    assert ok is False
    assert "ca.pem" in msg
    
    # Write ca.pem, missing cert.pem
    (tmp_path / "ca.pem").write_text("ca-content")
    ok, msg = cm.validate_docker_configuration()
    assert ok is False
    assert "cert.pem" in msg
    
    # Write cert.pem, missing key.pem
    (tmp_path / "cert.pem").write_text("cert-content")
    ok, msg = cm.validate_docker_configuration()
    assert ok is False
    assert "key.pem" in msg

def test_remote_tls_success(monkeypatch, tmp_path):
    # If DOCKER_HOST uses port 2376 and TLS certs are correct
    monkeypatch.setenv("DOCKER_HOST", "tcp://1.2.3.4:2376")
    monkeypatch.setenv("DOCKER_CERT_PATH", str(tmp_path))
    (tmp_path / "ca.pem").write_text("ca")
    (tmp_path / "cert.pem").write_text("cert")
    (tmp_path / "key.pem").write_text("key")
    
    ok, msg = cm.validate_docker_configuration()
    assert ok is True
    assert msg == "OK"

def test_docker_available_fail_fast(monkeypatch):
    # If validate_docker_configuration fails, docker_available() must return False
    monkeypatch.setenv("DOCKER_HOST", "tcp://1.2.3.4:2375")
    assert cm.docker_available() is False
