import json
import os

class BusinessRuleCoverage:
    def __init__(self, schema_version: str = "1.0"):
        self.schema_version = schema_version
        self.categories = {
            "program_discovery": "VERIFIED",
            "program_analysis": "VERIFIED",
            "statement_analysis": "PARTIAL",
            "control_flow_analysis": "PARTIAL",
            "data_flow_analysis": "PARTIAL",
            "call_coverage": "PARTIAL",
            "business_rule_coverage": "UNVERIFIED",
            "transformation_coverage": "DEFERRED",
            "execution_coverage": "PARTIAL",
            "equivalence_coverage": "PARTIAL"
        }
        self.evidence_references = []
        self.unsupported_features = []

    def add_evidence(self, ref: str):
        self.evidence_references.append(ref)

    def add_unsupported(self, feature: str):
        self.unsupported_features.append(feature)

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "categories": self.categories,
            "evidence_references": self.evidence_references,
            "unsupported_features": self.unsupported_features
        }

    def save(self, path: str):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2)
