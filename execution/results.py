import os
import json

class ComparisonResult:
    def __init__(
        self,
        status: str = "UNVERIFIED",
        checks: dict = None,
        differences: list = None,
        evidence: dict = None,
        normalizations: list = None,
        schema_version: str = "1.0",
    ):
        self.schema_version = schema_version
        self.status = status
        self.checks = checks or {
            "output_presence": "UNVERIFIED",
            "file_set": "UNVERIFIED",
            "file_contents": "UNVERIFIED",
            "record_counts": "UNVERIFIED",
            "stdout": "UNVERIFIED",
            "stderr": "UNVERIFIED",
            "exit_code": "UNVERIFIED",
            "database_state": "UNVERIFIED",
        }
        self.differences = differences or []
        self.evidence = evidence or {}
        self.normalizations = normalizations or []

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "checks": self.checks,
            "differences": self.differences,
            "evidence": self.evidence,
            "normalizations": self.normalizations,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ComparisonResult":
        return cls(
            schema_version=data.get("schema_version", "1.0"),
            status=data.get("status", "UNVERIFIED"),
            checks=data.get("checks"),
            differences=data.get("differences"),
            evidence=data.get("evidence"),
            normalizations=data.get("normalizations"),
        )

    def save(self, path: str):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2)

    @classmethod
    def load(cls, path: str) -> "ComparisonResult":
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return cls.from_dict(data)
