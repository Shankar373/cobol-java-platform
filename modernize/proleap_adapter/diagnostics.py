class ProLeapDiagnostic:
    def __init__(self, severity: str, detail: str, line: int = 0, col: int = 0):
        self.severity = severity
        self.detail = detail
        self.line = line
        self.col = col

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "detail": self.detail,
            "line": self.line,
            "column": self.col
        }
