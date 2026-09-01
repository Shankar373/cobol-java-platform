import sys
import pytest
from unittest.mock import MagicMock, patch
import cobol_migrate

def test_cli_native_java_flag_accepted():
    with patch("sys.argv", ["cobol_migrate.py", "--native-java", "--repo", "tests/repos/MULTIFILE01", "--out", "target/test_native_cli"]):
        with patch("modernize.native_pipeline.NativePipeline") as mock_pipeline:
            mock_inst = MagicMock()
            mock_inst.run.return_value = "NATIVE_JAVA_VERIFIED"
            mock_pipeline.return_value = mock_inst
            
            with pytest.raises(SystemExit) as excinfo:
                cobol_migrate.main()
            
            assert excinfo.value.code == 0
            mock_pipeline.assert_called_once_with(
                cobol_migrate.os.path.abspath("tests/repos/MULTIFILE01"),
                cobol_migrate.os.path.abspath("target/test_native_cli")
            )
            mock_inst.run.assert_called_once()

def test_cli_native_java_flag_failure_propagates():
    with patch("sys.argv", ["cobol_migrate.py", "--native-java", "--repo", "tests/repos/MULTIFILE01", "--out", "target/test_native_cli"]):
        with patch("modernize.native_pipeline.NativePipeline") as mock_pipeline:
            mock_inst = MagicMock()
            mock_inst.run.return_value = "NATIVE_JAVA_NOT_VERIFIED"
            mock_pipeline.return_value = mock_inst
            
            with pytest.raises(SystemExit) as excinfo:
                cobol_migrate.main()
            
            assert excinfo.value.code == 2
            mock_inst.run.assert_called_once()

def test_cli_default_mode_does_not_invoke_native():
    with patch("sys.argv", ["cobol_migrate.py", "--repo", "tests/repos/MULTIFILE01", "--out", "target/test_native_cli"]):
        with patch("cobol_migrate.Pipeline") as mock_pipeline:
            mock_inst = MagicMock()
            mock_pipeline.return_value = mock_inst
            mock_inst.data.return_value = {"checks": [], "verdict_counts": {}}
            mock_inst._compute_verdict.return_value = "PASS"
            
            with patch("modernize.native_pipeline.NativePipeline") as mock_native_pipeline:
                with pytest.raises(SystemExit) as excinfo:
                    cobol_migrate.main()
                
                assert excinfo.value.code == 0
                mock_native_pipeline.assert_not_called()
                mock_pipeline.assert_called_once()
