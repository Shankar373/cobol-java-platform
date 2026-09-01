import os
import json

class ExecutionContract:
    def __init__(
        self,
        expected_output_modes: list = None,
        required_files: list = None,
        optional_files: list = None,
        expected_empty_files: list = None,
        exit_code_parities: dict = None,
        nondeterministic_fields: dict = None,
        normalization_rules: list = None,
        ordering_rules: dict = None,
        numeric_comparison_rules: dict = None,
        schema_version: str = "1.0",
    ):
        self.schema_version = schema_version
        self.expected_output_modes = expected_output_modes or ["EXPECTED_FILES", "EXPECTED_STDOUT", "EXPECTED_EXIT_STATUS"]
        self.required_files = required_files or []
        self.optional_files = optional_files or []
        self.expected_empty_files = expected_empty_files or []
        self.exit_code_parities = exit_code_parities or {}  # e.g., {"0": [0, 1]} or boolean strictness
        self.nondeterministic_fields = nondeterministic_fields or {}
        self.normalization_rules = normalization_rules or []
        self.ordering_rules = ordering_rules or {}
        self.numeric_comparison_rules = numeric_comparison_rules or {}

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "expected_output_modes": self.expected_output_modes,
            "required_files": self.required_files,
            "optional_files": self.optional_files,
            "expected_empty_files": self.expected_empty_files,
            "exit_code_parities": self.exit_code_parities,
            "nondeterministic_fields": self.nondeterministic_fields,
            "normalization_rules": self.normalization_rules,
            "ordering_rules": self.ordering_rules,
            "numeric_comparison_rules": self.numeric_comparison_rules,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ExecutionContract":
        return cls(
            schema_version=data.get("schema_version", "1.0"),
            expected_output_modes=data.get("expected_output_modes"),
            required_files=data.get("required_files"),
            optional_files=data.get("optional_files"),
            expected_empty_files=data.get("expected_empty_files"),
            exit_code_parities=data.get("exit_code_parities"),
            nondeterministic_fields=data.get("nondeterministic_fields"),
            normalization_rules=data.get("normalization_rules"),
            ordering_rules=data.get("ordering_rules"),
            numeric_comparison_rules=data.get("numeric_comparison_rules"),
        )

    def save(self, path: str):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2)

    @classmethod
    def load(cls, path: str) -> "ExecutionContract":
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return cls.from_dict(data)
