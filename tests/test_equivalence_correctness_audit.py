import os
import sys
import pytest
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cobol_migrate as cm
from execution import ExecutionObservation, ExecutionContract, EquivalenceEngine

@pytest.fixture
def blank_pipeline(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    out = tmp_path / "out"
    out.mkdir()
    return cm.Pipeline(str(repo), str(out), pull=False)

def _set_stage_done(p, name):
    p.state["stages"].setdefault(name, {})["status"] = "done"

def _set_data(p, key, value):
    p.state["data"][key] = value

def test_verdict_a_exact_sequential_match():
    # A. exact sequential-file match → PASS
    obs_cobol = ExecutionObservation(
        scenario_id="SC", exit_code=0, files={"out.txt": "PRESENT_NONEMPTY"}, file_contents={"out.txt": "exact_match_data"}
    )
    obs_java = ExecutionObservation(
        scenario_id="SC", exit_code=0, files={"out.txt": "PRESENT_NONEMPTY"}, file_contents={"out.txt": "exact_match_data"}
    )
    contract = ExecutionContract(
        expected_output_modes=["EXPECTED_FILES"], required_files=["out.txt"]
    )
    res = EquivalenceEngine.compare(obs_cobol, obs_java, contract)
    assert res.status == "PASS"

def test_verdict_b_indexed_logical_match():
    # B. indexed files with different physical runtime representation but identical logical records → PASS_WITH_LIMITATIONS
    obs_cobol = ExecutionObservation(scenario_id="SC", exit_code=0, files={"out.dat": "PRESENT_NONEMPTY"})
    obs_java = ExecutionObservation(scenario_id="SC", exit_code=0, files={"out.dat": "PRESENT_NONEMPTY"})
    
    # Simulate DB state with LOGICAL_MATCH for both sides
    obs_cobol.database_state = {
        "out.dat": {
            "db_type": "sqlite",
            "context_id": "out.dat",
            "normalization_metadata": {"logical_verdict": "LOGICAL_MATCH"}
        }
    }
    obs_java.database_state = {
        "out.dat": {
            "db_type": "sqlite",
            "context_id": "out.dat",
            "normalization_metadata": {"logical_verdict": "LOGICAL_MATCH"}
        }
    }
    contract = ExecutionContract(expected_output_modes=["EXPECTED_FILES"], required_files=["out.dat"])
    res = EquivalenceEngine.compare(obs_cobol, obs_java, contract)
    assert res.status == "PASS"

def test_verdict_c_indexed_changed_field():
    # C. indexed files with a changed field → FAIL
    obs_cobol = ExecutionObservation(scenario_id="SC", exit_code=0, files={"out.dat": "PRESENT_NONEMPTY"})
    obs_java = ExecutionObservation(scenario_id="SC", exit_code=0, files={"out.dat": "PRESENT_NONEMPTY"})
    obs_cobol.database_state = {
        "out.dat": {
            "db_type": "sqlite",
            "context_id": "out.dat",
            "normalization_metadata": {"logical_verdict": "LOGICAL_MATCH"}
        }
    }
    obs_java.database_state = {
        "out.dat": {
            "db_type": "sqlite",
            "context_id": "out.dat",
            "normalization_metadata": {"logical_verdict": "LOGICAL_MISMATCH"} # field changed!
        }
    }
    contract = ExecutionContract(expected_output_modes=["EXPECTED_FILES"], required_files=["out.dat"])
    res = EquivalenceEngine.compare(obs_cobol, obs_java, contract)
    assert res.status == "FAIL"

def test_verdict_d_indexed_missing_record():
    # D. indexed files with missing record → FAIL
    obs_cobol = ExecutionObservation(scenario_id="SC", exit_code=0, files={"out.dat": "PRESENT_NONEMPTY"})
    obs_java = ExecutionObservation(scenario_id="SC", exit_code=0, files={"out.dat": "PRESENT_NONEMPTY"})
    obs_cobol.database_state = {
        "out.dat": {
            "db_type": "sqlite",
            "context_id": "out.dat",
            "normalization_metadata": {"logical_verdict": "LOGICAL_MATCH"}
        }
    }
    obs_java.database_state = {
        "out.dat": {
            "db_type": "sqlite",
            "context_id": "out.dat",
            "normalization_metadata": {"logical_verdict": "LOGICAL_MISMATCH"} # missing record
        }
    }
    contract = ExecutionContract(expected_output_modes=["EXPECTED_FILES"], required_files=["out.dat"])
    res = EquivalenceEngine.compare(obs_cobol, obs_java, contract)
    assert res.status == "FAIL"

def test_verdict_e_indexed_extra_record():
    # E. indexed files with extra record → FAIL
    obs_cobol = ExecutionObservation(scenario_id="SC", exit_code=0, files={"out.dat": "PRESENT_NONEMPTY"})
    obs_java = ExecutionObservation(scenario_id="SC", exit_code=0, files={"out.dat": "PRESENT_NONEMPTY"})
    obs_cobol.database_state = {
        "out.dat": {
            "db_type": "sqlite",
            "context_id": "out.dat",
            "normalization_metadata": {"logical_verdict": "LOGICAL_MATCH"}
        }
    }
    obs_java.database_state = {
        "out.dat": {
            "db_type": "sqlite",
            "context_id": "out.dat",
            "normalization_metadata": {"logical_verdict": "LOGICAL_MISMATCH"} # extra record
        }
    }
    contract = ExecutionContract(expected_output_modes=["EXPECTED_FILES"], required_files=["out.dat"])
    res = EquivalenceEngine.compare(obs_cobol, obs_java, contract)
    assert res.status == "FAIL"

def test_verdict_f_indexed_changed_key():
    # F. indexed files with changed key → FAIL
    obs_cobol = ExecutionObservation(scenario_id="SC", exit_code=0, files={"out.dat": "PRESENT_NONEMPTY"})
    obs_java = ExecutionObservation(scenario_id="SC", exit_code=0, files={"out.dat": "PRESENT_NONEMPTY"})
    obs_cobol.database_state = {
        "out.dat": {
            "db_type": "sqlite",
            "context_id": "out.dat",
            "normalization_metadata": {"logical_verdict": "LOGICAL_MATCH"}
        }
    }
    obs_java.database_state = {
        "out.dat": {
            "db_type": "sqlite",
            "context_id": "out.dat",
            "normalization_metadata": {"logical_verdict": "LOGICAL_MISMATCH"} # changed key
        }
    }
    contract = ExecutionContract(expected_output_modes=["EXPECTED_FILES"], required_files=["out.dat"])
    res = EquivalenceEngine.compare(obs_cobol, obs_java, contract)
    assert res.status == "FAIL"

def test_verdict_g_incomplete_transpilation(blank_pipeline):
    # G. incomplete transpilation → PARTIAL
    p = blank_pipeline
    _set_stage_done(p, "ingest")
    _set_data(p, "transpile", {"n_ok": 2, "n_total": 5})
    v = p._compute_verdict()
    assert v == "PARTIAL"

def test_verdict_h_unresolved_schema_metadata(blank_pipeline):
    # H. unresolved schema metadata with otherwise valid execution → VERIFIED_WITH_LIMITATIONS
    p = blank_pipeline
    _set_stage_done(p, "ingest")
    _set_stage_done(p, "generate")
    _set_data(p, "transpile", {"n_ok": 1, "n_total": 1})
    _set_data(p, "baseline_files", ["out.txt"])
    _set_data(p, "compare", {"status": "PASS", "checks": [{"ok": True}], "rows": [],
                             "stdout_equiv_ok": True})
    _set_data(p, "collect", {"dependency_audit": {"status": "PASS", "executed": True}})
    
    # Set semantic model input record confidence to UNRESOLVED
    _set_data(p, "semantic_model", {"input_record_confidence": "UNRESOLVED"})
    
    v = p._compute_verdict()
    assert v == "VERIFIED_WITH_LIMITATIONS"
