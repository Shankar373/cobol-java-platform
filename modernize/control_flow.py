import json
import os
from .semantic_ir import SemanticIR, SemanticIRNode

class CFGNode:
    def __init__(
        self,
        node_id: str,
        node_type: str,
        ir_node_id: str,
        source_file: str,
        source_line: int,
        source_column: int,
        start_offset: int,
        end_offset: int,
        status: str = "PARSED",
        properties: dict = None
    ):
        self.node_id = node_id
        self.node_type = node_type
        self.ir_node_id = ir_node_id
        self.source_file = source_file
        self.source_line = source_line
        self.source_column = source_column
        self.start_offset = start_offset
        self.end_offset = end_offset
        self.status = status
        self.properties = properties or {}

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "ir_node_id": self.ir_node_id,
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


class CFGEdge:
    def __init__(self, from_node: str, to_node: str, classification: str = "SEQUENTIAL", condition: str = ""):
        self.from_node = from_node
        self.to_node = to_node
        self.classification = classification
        self.condition = condition

    def to_dict(self) -> dict:
        return {
            "from": self.from_node,
            "to": self.to_node,
            "classification": self.classification,
            "condition": self.condition
        }


class ControlFlowModel:
    def __init__(self, schema_version: str = "1.0"):
        self.schema_version = schema_version
        self.nodes = []
        self.edges = []
        self.paragraphs = {} # Backward compatibility reference

    def add_node(self, node: CFGNode):
        self.nodes.append(node)

    def add_paragraph(self, name: str, statements: list):
        self.paragraphs[name] = statements

    def add_edge(self, edge: CFGEdge):
        self.edges.append(edge)

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "paragraphs": self.paragraphs
        }

    def save(self, path: str):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2)

    @classmethod
    def build_from_ir(cls, ir: SemanticIR) -> "ControlFlowModel":
        model = cls()
        
        # 1. Gather all Procedure Division elements in source order
        ir_ordered = sorted(ir.nodes.values(), key=lambda n: n.node_id)
        proc_nodes = []
        in_procedure = False
        
        for node in ir_ordered:
            if node.kind == "DIVISION" and node.properties.get("name") == "PROCEDURE":
                in_procedure = True
            if in_procedure:
                if node.kind in ("DIVISION", "SECTION", "PARAGRAPH", "STATEMENT"):
                    proc_nodes.append(node)

        if not proc_nodes:
            return model

        # Create CFG Nodes mapping
        cfg_nodes_map = {}
        node_id_to_cfg_id = {}
        
        # Add program exit node
        exit_node = CFGNode(
            node_id="cfg_exit",
            node_type="EXIT",
            ir_node_id="none",
            source_file=proc_nodes[0].source_file,
            source_line=0,
            source_column=0,
            start_offset=0,
            end_offset=0,
            status="PARSED"
        )
        model.add_node(exit_node)

        for idx, ir_node in enumerate(proc_nodes):
            cfg_id = f"cfg_{ir_node.node_id}"
            
            # Map IR node kind to CFG node type
            node_type = "STATEMENT"
            if ir_node.kind == "DIVISION":
                node_type = "PROGRAM"
            elif ir_node.kind == "SECTION":
                node_type = "SECTION"
            elif ir_node.kind == "PARAGRAPH":
                node_type = "PARAGRAPH"
            else:
                stmt_type = ir_node.properties.get("statement_type", "UNKNOWN")
                if stmt_type == "IF":
                    node_type = "CONDITION"
                elif stmt_type == "ELSE":
                    node_type = "BRANCH"
                elif stmt_type in ("STOP RUN", "GOBACK", "EXIT", "EXIT PERFORM", "EXIT PARAGRAPH", "EXIT SECTION"):
                    node_type = "EXIT"
                elif stmt_type == "GO TO":
                    node_type = "GOTO"
                elif stmt_type == "CALL":
                    node_type = "CALL"

            cfg_node = CFGNode(
                node_id=cfg_id,
                node_type=node_type,
                ir_node_id=ir_node.node_id,
                source_file=ir_node.source_file,
                source_line=ir_node.source_line,
                source_column=ir_node.source_column,
                start_offset=ir_node.start_offset,
                end_offset=ir_node.end_offset,
                status=ir_node.status,
                properties=ir_node.properties.copy()
            )
            model.add_node(cfg_node)
            cfg_nodes_map[ir_node.node_id] = cfg_node
            node_id_to_cfg_id[ir_node.node_id] = cfg_id

        # 2. Build edges using sequential flow & nesting stack
        stack = []
        
        # Helper to find next non-control statement/paragraph index
        def get_next_normal_idx(start_idx):
            curr = start_idx
            while curr < len(proc_nodes):
                n = proc_nodes[curr]
                if n.kind == "STATEMENT" and n.properties.get("statement_type") in ("ELSE", "END-IF"):
                    curr += 1
                else:
                    return curr
            return None

        for idx, ir_node in enumerate(proc_nodes):
            cfg_id = node_id_to_cfg_id[ir_node.node_id]
            stmt_type = ir_node.properties.get("statement_type", "") if ir_node.kind == "STATEMENT" else ""
            
            # Look ahead
            next_idx = idx + 1
            has_next = (next_idx < len(proc_nodes))
            next_node = proc_nodes[next_idx] if has_next else None
            next_cfg_id = node_id_to_cfg_id[next_node.node_id] if next_node else None

            # A. Paragraph / Section transitions
            if ir_node.kind in ("SECTION", "PARAGRAPH") and has_next:
                model.add_edge(CFGEdge(cfg_id, next_cfg_id, "FALLTHROUGH"))
                continue

            # B. IF branch handling
            if stmt_type == "IF":
                # Push IF block details
                stack.append(("IF", ir_node.node_id))
                
                # TRUE_BRANCH goes to next statement inside IF
                if has_next:
                    model.add_edge(CFGEdge(cfg_id, next_cfg_id, "TRUE_BRANCH", condition=ir_node.properties.get("condition", "")))
                
                # Find matching ELSE or END-IF to connect FALSE_BRANCH
                nested_lvl = 0
                false_target = None
                for future_idx in range(idx + 1, len(proc_nodes)):
                    future_node = proc_nodes[future_idx]
                    f_stmt_type = future_node.properties.get("statement_type", "") if future_node.kind == "STATEMENT" else ""
                    
                    if f_stmt_type == "IF":
                        nested_lvl += 1
                    elif f_stmt_type == "END-IF":
                        if nested_lvl > 0:
                            nested_lvl -= 1
                        else:
                            false_target = future_node
                            break
                    elif f_stmt_type == "ELSE":
                        if nested_lvl == 0:
                            false_target = future_node
                            break
                
                if false_target:
                    # Connect FALSE_BRANCH to ELSE or END-IF
                    false_cfg_id = node_id_to_cfg_id[false_target.node_id]
                    model.add_edge(CFGEdge(cfg_id, false_cfg_id, "FALSE_BRANCH"))
                continue

            # C. ELSE branch handling
            elif stmt_type == "ELSE":
                # Connect last statement of IF block to corresponding END-IF (if stack matches)
                if stack and stack[-1][0] == "IF":
                    if_kind, if_ir_id = stack.pop()
                    
                    # Find last node before ELSE
                    prev_node = proc_nodes[idx - 1]
                    prev_cfg_id = node_id_to_cfg_id[prev_node.node_id]
                    
                    # Find corresponding END-IF
                    end_if_node = None
                    nested_lvl = 0
                    for future_idx in range(idx + 1, len(proc_nodes)):
                        future_node = proc_nodes[future_idx]
                        f_stmt_type = future_node.properties.get("statement_type", "") if future_node.kind == "STATEMENT" else ""
                        if f_stmt_type == "IF":
                            nested_lvl += 1
                        elif f_stmt_type == "END-IF":
                            if nested_lvl > 0:
                                nested_lvl -= 1
                            else:
                                end_if_node = future_node
                                break
                    
                    if end_if_node:
                        end_if_cfg_id = node_id_to_cfg_id[end_if_node.node_id]
                        model.add_edge(CFGEdge(prev_cfg_id, end_if_cfg_id, "SEQUENTIAL"))
                    
                    stack.append(("ELSE", ir_node.node_id, if_ir_id))
                
                # ELSE branch falls through to next statement inside ELSE block
                if has_next:
                    model.add_edge(CFGEdge(cfg_id, next_cfg_id, "FALSE_BRANCH"))
                continue

            # D. END-IF terminator handling
            elif stmt_type == "END-IF":
                if stack:
                    top = stack.pop()
                    # If top is IF, it means there was no ELSE, connect FALSE_BRANCH directly to END-IF
                    # (This is already handled during IF creation, but we pop the stack here)
                
                # END-IF falls through to next statement
                if has_next:
                    model.add_edge(CFGEdge(cfg_id, next_cfg_id, "SEQUENTIAL"))
                continue

            # E. PERFORM branch execution
            elif stmt_type == "PERFORM":
                target_para = ir_node.properties.get("target", "")
                thru_para = ir_node.properties.get("thru")
                
                # Find target paragraph node ID
                target_node_id = None
                thru_node_id = None
                for n in proc_nodes:
                    if n.kind == "PARAGRAPH" and n.properties.get("name") == target_para:
                        target_node_id = n.node_id
                    if thru_para and n.kind == "PARAGRAPH" and n.properties.get("name") == thru_para:
                        thru_node_id = n.node_id

                if target_node_id:
                    target_cfg = node_id_to_cfg_id[target_node_id]
                    classification = "PERFORM_THRU" if thru_node_id else "PERFORM"
                    model.add_edge(CFGEdge(cfg_id, target_cfg, classification))
                    
                    # Return path edge
                    return_target_node = thru_node_id if thru_node_id else target_node_id
                    return_target_cfg = node_id_to_cfg_id[return_target_node]
                    if has_next:
                        model.add_edge(CFGEdge(return_target_cfg, next_cfg_id, "RETURN"))
                else:
                    # Unresolved perform
                    model.add_edge(CFGEdge(cfg_id, cfg_id, "UNRESOLVED"))

                if has_next:
                    # Non-blocking call fallthrough
                    model.add_edge(CFGEdge(cfg_id, next_cfg_id, "SEQUENTIAL"))
                continue

            # F. CALL branch execution
            elif stmt_type == "CALL":
                target_sub = ir_node.properties.get("target", "")
                model.add_edge(CFGEdge(cfg_id, cfg_id, "CALL", condition=target_sub))
                if has_next:
                    model.add_edge(CFGEdge(cfg_id, next_cfg_id, "RETURN"))
                    model.add_edge(CFGEdge(cfg_id, next_cfg_id, "SEQUENTIAL"))
                continue

            # G. Program exit execution
            elif stmt_type in ("STOP RUN", "GOBACK", "EXIT", "EXIT PERFORM", "EXIT PARAGRAPH", "EXIT SECTION"):
                model.add_edge(CFGEdge(cfg_id, "cfg_exit", "EXIT"))
                continue

            elif stmt_type == "GO TO":
                target_para = ir_node.properties.get("target", "")
                target_node_id = None
                for n in proc_nodes:
                    if n.kind in ("PARAGRAPH", "SECTION") and n.properties.get("name") == target_para:
                        target_node_id = n.node_id
                        break
                if target_node_id:
                    target_cfg = node_id_to_cfg_id[target_node_id]
                    model.add_edge(CFGEdge(cfg_id, target_cfg, "GOTO"))
                else:
                    model.add_edge(CFGEdge(cfg_id, cfg_id, "UNRESOLVED"))
                continue

            # H. Standard sequential execution fallback
            if has_next:
                # Do not transition sequentially into ELSE or END-IF directly from inside active branch
                if next_node.kind == "STATEMENT" and next_node.properties.get("statement_type") in ("ELSE", "END-IF"):
                    # Stack resolution handles these transitions
                    pass
                else:
                    model.add_edge(CFGEdge(cfg_id, next_cfg_id, "SEQUENTIAL"))

        return model

# Backward compatibility alias
ControlFlowEdge = CFGEdge

