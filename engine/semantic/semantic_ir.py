"""
Semantic Intermediate Representation.

A language-agnostic, serializable tree that sits between the COBOL parser
and all downstream generators/verifiers.  Every node carries:
  - a unique id
  - a kind (DATA_ITEM, STATEMENT, PARAGRAPH, ...)
  - arbitrary key/value properties
  - source location (file, line, column, byte offsets)
  - a status (PARSED, GENERATED, VERIFIED, UNSUPPORTED, ...)
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class SourceLocation:
    file: str = ""
    line: int = 0
    column: int = 0
    start_offset: int = 0
    end_offset: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SemanticIRNode:
    node_id: str
    kind: str
    properties: dict[str, Any] = field(default_factory=dict)
    location: SourceLocation = field(default_factory=SourceLocation)
    status: str = "PARSED"

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "kind": self.kind,
            "status": self.status,
            "properties": self.properties,
            "source_location": self.location.to_dict(),
        }


class SemanticIR:
    """Container for the full set of SemanticIRNodes for one program."""

    SCHEMA_VERSION = "2.0"

    def __init__(self) -> None:
        self.schema_version: str = self.SCHEMA_VERSION
        self.nodes: dict[str, SemanticIRNode] = {}
        # Top-level status set by the parser after completing analysis
        self.status: str = "PARSED"
        # Optional human-readable summary of unsupported/partial constructs
        self.diagnostics: list[dict] = []

    # ── Mutation ──────────────────────────────────────────────────────────────

    def add_node(self, node: SemanticIRNode) -> None:
        self.nodes[node.node_id] = node

    def add_diagnostic(self, severity: str, detail: str, *, file: str = "", line: int = 0) -> None:
        self.diagnostics.append({"severity": severity, "detail": detail, "file": file, "line": line})

    # ── Query ─────────────────────────────────────────────────────────────────

    def nodes_of_kind(self, kind: str) -> list[SemanticIRNode]:
        return [n for n in self.nodes.values() if n.kind == kind]

    def node(self, node_id: str) -> SemanticIRNode | None:
        return self.nodes.get(node_id)

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "diagnostics": self.diagnostics,
            "nodes": {nid: n.to_dict() for nid, n in self.nodes.items()},
        }

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2)

    @classmethod
    def load(cls, path: str) -> "SemanticIR":
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        ir = cls()
        ir.schema_version = data.get("schema_version", "1.0")
        ir.status = data.get("status", "PARSED")
        ir.diagnostics = data.get("diagnostics", [])
        for nid, n_dict in data.get("nodes", {}).items():
            loc_d = n_dict.get("source_location", {})
            loc = SourceLocation(
                file=loc_d.get("file", ""),
                line=loc_d.get("line", 0),
                column=loc_d.get("column", 0),
                start_offset=loc_d.get("start_offset", 0),
                end_offset=loc_d.get("end_offset", 0),
            )
            node = SemanticIRNode(
                node_id=nid,
                kind=n_dict.get("kind", ""),
                properties=n_dict.get("properties", {}),
                location=loc,
                status=n_dict.get("status", "PARSED"),
            )
            ir.add_node(node)
        return ir


# ---------------------------------------------------------------------------
# Backward-compatibility shim
#
# The existing custom parser (engine/parser/custom/parser.py) creates
# SemanticIRNode using the OLD keyword argument API:
#   SemanticIRNode(node_id=..., kind=..., properties=...,
#                  source_file=..., source_line=..., source_column=...,
#                  start_offset=..., end_offset=..., status=...)
#
# The new API uses a SourceLocation dataclass. This shim allows the parser
# to work without modification during the incremental refactoring phase.
# Once parser.py is refactored to use SourceLocation, this shim will be removed.
# ---------------------------------------------------------------------------

_SemanticIRNodeBase = SemanticIRNode

def SemanticIRNode(
    node_id: str,
    kind: str,
    properties: dict = None,
    *,
    # Old-API keyword args
    source_file: str = "",
    source_line: int = 0,
    source_column: int = 0,
    start_offset: int = 0,
    end_offset: int = 0,
    # New-API keyword arg
    location: SourceLocation = None,
    status: str = "PARSED",
) -> _SemanticIRNodeBase:
    """Factory that accepts both old-style and new-style keyword arguments."""
    if location is None:
        location = SourceLocation(
            file=source_file,
            line=source_line,
            column=source_column,
            start_offset=start_offset,
            end_offset=end_offset,
        )
    return _SemanticIRNodeBase(
        node_id=node_id,
        kind=kind,
        properties=properties or {},
        location=location,
        status=status,
    )
