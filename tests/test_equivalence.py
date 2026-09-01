import os
import json
import pytest
from execution import ExecutionObservation, ExecutionContract, ComparisonResult, EquivalenceEngine, NormalizationRules

def test_equivalence_cases_all():
    # 1. Matching outputs case (State D / Case B)
    obs_cobol = ExecutionObservation(
        scenario_id="SC-MATCH",
        exit_code=0,
        stdout="success run",
        files={"out.txt": "PRESENT_NONEMPTY"},
        file_contents={"out.txt": "data-val"}
    )
    obs_java = ExecutionObservation(
        scenario_id="SC-MATCH",
        exit_code=0,
        stdout="success run",
        files={"out.txt": "PRESENT_NONEMPTY"},
        file_contents={"out.txt": "data-val"}
    )
    contract = ExecutionContract(
        expected_output_modes=["EXPECTED_FILES", "EXPECTED_STDOUT", "EXPECTED_EXIT_STATUS"],
        required_files=["out.txt"]
    )
    res = EquivalenceEngine.compare(obs_cobol, obs_java, contract)
    assert res.status == "PASS"
    assert res.checks["file_contents"] == "PASS"
    assert res.checks["exit_code"] == "PASS"
    assert res.checks["stdout"] == "PASS"

    # 2. Mismatched scenario ID (Case Scenario Mismatch)
    obs_java.scenario_id = "SC-DIFF"
    res = EquivalenceEngine.compare(obs_cobol, obs_java, contract)
    assert res.status == "UNVERIFIED"
    assert "scenario_id_mismatch" in [d["type"] for d in res.differences]

    # Restore scenario ID
    obs_java.scenario_id = "SC-MATCH"

    # 3. Different exit code (Case K)
    obs_java.exit_code = 1
    res = EquivalenceEngine.compare(obs_cobol, obs_java, contract)
    assert res.status == "FAIL"
    assert res.checks["exit_code"] == "FAIL"
    
    # 4. Exit code parity exception
    contract.exit_code_parities = {"0": [0, 1]}
    res = EquivalenceEngine.compare(obs_cobol, obs_java, contract)
    assert res.status == "PASS"
    assert res.checks["exit_code"] == "PASS"
    obs_java.exit_code = 0  # Restore

    # 5. Expected no output + actual no output (Case A)
    obs_cobol_no = ExecutionObservation(scenario_id="SC-NO", exit_code=0, files={})
    obs_java_no = ExecutionObservation(scenario_id="SC-NO", exit_code=0, files={})
    contract_no = ExecutionContract(
        expected_output_modes=["EXPECTED_NO_OUTPUT", "EXPECTED_EXIT_STATUS"]
    )
    res = EquivalenceEngine.compare(obs_cobol_no, obs_java_no, contract_no)
    assert res.status == "PASS"
    assert res.checks["file_set"] == "PASS"

    # 6. Expected no output + actual output (Case E)
    obs_java_no.files = {"unexpected.txt": "PRESENT_NONEMPTY"}
    res = EquivalenceEngine.compare(obs_cobol_no, obs_java_no, contract_no)
    assert res.status == "FAIL"
    assert "unexpected_output_files" in [d["type"] for d in res.differences]

    # 7. Expected output + actual no output (Case D/J)
    obs_cobol_no.scenario_id = "SC-MATCH"
    res = EquivalenceEngine.compare(obs_cobol, obs_cobol_no, contract)
    assert res.status == "FAIL"
    assert "missing_required_files" in [d["type"] for d in res.differences]

    # 8. Content difference (Case C)
    obs_java.file_contents["out.txt"] = "diff-val"
    res = EquivalenceEngine.compare(obs_cobol, obs_java, contract)
    assert res.status == "FAIL"
    assert res.checks["file_contents"] == "FAIL"

    # 9. Normalization check
    contract.normalization_rules = [
        {"pattern": r"diff-val|data-val", "artifact": "out.txt", "replacement": "norm-val"}
    ]
    res = EquivalenceEngine.compare(obs_cobol, obs_java, contract)
    assert res.status == "PASS"
    assert res.checks["file_contents"] == "PASS"

    # 10. Expected empty file parity (Case G)
    obs_cobol.files["out.txt"] = "PRESENT_EMPTY"
    obs_java.files["out.txt"] = "PRESENT_EMPTY"
    contract.expected_empty_files = ["out.txt"]
    res = EquivalenceEngine.compare(obs_cobol, obs_java, contract)
    assert res.status == "PASS"

    # 11. Expected non-empty file + actual empty file (Case H)
    obs_cobol.files["out.txt"] = "PRESENT_NONEMPTY"
    obs_java.files["out.txt"] = "PRESENT_EMPTY"
    res = EquivalenceEngine.compare(obs_cobol, obs_java, contract)
    assert res.status == "FAIL"

    # 12. Database observations comparison
    obs_cobol.database_state = {
        "db_type": "sqlite",
        "context_id": "db1",
        "affected_tables": ["claims"],
        "row_counts": {"claims": 10}
    }
    obs_java.database_state = {
        "db_type": "sqlite",
        "context_id": "db1",
        "affected_tables": ["claims"],
        "row_counts": {"claims": 10}
    }
    contract.expected_output_modes.append("EXPECTED_DATABASE_STATE")
    res = EquivalenceEngine.compare(obs_cobol, obs_java, contract)
    assert res.checks["database_state"] == "PASS"

    # 13. Database mismatch
    obs_java.database_state["db_type"] = "postgres"
    res = EquivalenceEngine.compare(obs_cobol, obs_java, contract)
    assert res.status == "FAIL"
    assert res.checks["database_state"] == "FAIL"

    # 14. Serialization and Deserialization check
    dict_repr = obs_cobol.to_dict()
    obs_deser = ExecutionObservation.from_dict(dict_repr)
    assert obs_deser.scenario_id == obs_cobol.scenario_id
    assert obs_deser.exit_code == obs_cobol.exit_code
