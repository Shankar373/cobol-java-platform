import json
import os

class TraceabilityRecord:
    def __init__(
        self,
        rule_id: str,
        cobol_source: dict,
        ir_node_id: str,
        java_target: dict = None,
        test_cases: list = None,
        verification_status: str = "ANALYZED"
    ):
        self.rule_id = rule_id
        self.cobol_source = cobol_source or {}
        self.ir_node_id = ir_node_id
        self.java_target = java_target or {
            "class": "",
            "method": "",
            "statement": "NOT_GENERATED"
        }
        self.test_cases = test_cases or []
        self.verification_status = verification_status

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "cobol_source": self.cobol_source,
            "intermediate_representation": {
                "node_id": self.ir_node_id
            },
            "java_target": self.java_target,
            "test_cases": self.test_cases,
            "verification": {
                "status": self.verification_status
            }
        }

class TraceabilityModel:
    def __init__(self, schema_version: str = "1.0"):
        self.schema_version = schema_version
        self.records = []

    def add_record(self, record: TraceabilityRecord):
        self.records.append(record)

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "records": [r.to_dict() for r in self.records]
        }

    def save(self, path: str):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2)
