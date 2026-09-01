import json
import os

class SemanticIRNode:
    def __init__(
        self,
        node_id: str,
        kind: str,
        properties: dict = None,
        source_file: str = "",
        source_line: int = 0,
        source_column: int = 0,
        start_offset: int = 0,
        end_offset: int = 0,
        status: str = "PARSED"
    ):
        self.node_id = node_id
        self.kind = kind
        self.properties = properties or {}
        self.source_file = source_file
        self.source_line = source_line
        self.source_column = source_column
        self.start_offset = start_offset
        self.end_offset = end_offset
        self.status = status

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "kind": self.kind,
            "status": self.status,
            "properties": self.properties,
            "source_location": {
                "file": self.source_file,
                "line": self.source_line,
                "column": self.source_column,
                "start_offset": self.start_offset,
                "end_offset": self.end_offset
            }
        }

class SemanticIR:
    def __init__(self, schema_version: str = "1.0"):
        self.schema_version = schema_version
        self.nodes = {}

    def add_node(self, node: SemanticIRNode):
        self.nodes[node.node_id] = node

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "nodes": {nid: node.to_dict() for nid, node in self.nodes.items()}
        }

    def save(self, path: str):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2)

    @classmethod
    def load(cls, path: str) -> "SemanticIR":
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        ir = cls(schema_version=data.get("schema_version", "1.0"))
        for nid, n_dict in data.get("nodes", {}).items():
            loc = n_dict.get("source_location", {})
            node = SemanticIRNode(
                node_id=nid,
                kind=n_dict.get("kind", ""),
                properties=n_dict.get("properties", {}),
                source_file=loc.get("file", ""),
                source_line=loc.get("line", 0),
                source_column=loc.get("column", 0),
                start_offset=loc.get("start_offset", 0),
                end_offset=loc.get("end_offset", 0),
                status=n_dict.get("status", "PARSED")
            )
            ir.add_node(node)
        return ir
