import os
import json

class ExecutionObservation:
    def __init__(
        self,
        scenario_id: str = "",
        exit_code: int = -1,
        stdout: str = "",
        stderr: str = "",
        files: dict = None,
        file_contents: dict = None,
        file_sizes: dict = None,
        record_counts: dict = None,
        database_state: dict = None,
        structured_output: dict = None,
        execution_status: str = "unknown",
        duration: float = 0.0,
        normalization_metadata: dict = None,
        schema_version: str = "1.0",
    ):
        self.schema_version = schema_version
        self.scenario_id = scenario_id
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.files = files or {}
        self.file_contents = file_contents or {}
        self.file_sizes = file_sizes or {}
        self.record_counts = record_counts or {}
        self.database_state = database_state or {
            "db_type": "unknown",
            "context_id": "",
            "affected_tables": [],
            "row_counts": {},
            "relevant_keys": {},
            "before_after_state": {},
            "transaction_status": "unknown",
            "normalization_metadata": {},
            "evidence_references": []
        }
        self.structured_output = structured_output or {}
        self.execution_status = execution_status
        self.duration = duration
        self.normalization_metadata = normalization_metadata or {}

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "scenario_id": self.scenario_id,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "files": self.files,
            "file_contents": self.file_contents,
            "file_sizes": self.file_sizes,
            "record_counts": self.record_counts,
            "database_state": self.database_state,
            "structured_output": self.structured_output,
            "execution_status": self.execution_status,
            "duration": self.duration,
            "normalization_metadata": self.normalization_metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ExecutionObservation":
        return cls(
            schema_version=data.get("schema_version", "1.0"),
            scenario_id=data.get("scenario_id", ""),
            exit_code=data.get("exit_code", -1),
            stdout=data.get("stdout", ""),
            stderr=data.get("stderr", ""),
            files=data.get("files", {}),
            file_contents=data.get("file_contents", {}),
            file_sizes=data.get("file_sizes", {}),
            record_counts=data.get("record_counts", {}),
            database_state=data.get("database_state", {}),
            structured_output=data.get("structured_output", {}),
            execution_status=data.get("execution_status", "unknown"),
            duration=data.get("duration", 0.0),
            normalization_metadata=data.get("normalization_metadata", {}),
        )

    def save(self, path: str):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2)

    @classmethod
    def load(cls, path: str) -> "ExecutionObservation":
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return cls.from_dict(data)
