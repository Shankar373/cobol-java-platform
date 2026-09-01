import json
import os
from .semantic_ir import SemanticIR, SemanticIRNode
from .control_flow import ControlFlowModel

class DFNode:
    def __init__(
        self,
        node_id: str,
        node_type: str,
        name: str,
        status: str,
        source_file: str,
        source_line: int,
        source_column: int,
        ir_node_id: str,
        properties: dict = None
    ):
        self.node_id = node_id
        self.node_type = node_type
        self.name = name
        self.status = status
        self.source_file = source_file
        self.source_line = source_line
        self.source_column = source_column
        self.ir_node_id = ir_node_id
        self.properties = properties or {}

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "name": self.name,
            "status": self.status,
            "source_location": {
                "file": self.source_file,
                "line": self.source_line,
                "column": self.source_column
            },
            "ir_node_id": self.ir_node_id,
            "properties": self.properties
        }


class DFEdge:
    def __init__(self, from_node: str, to_node: str, classification: str, condition: str = "", metadata: dict = None):
        self.from_node = from_node
        self.to_node = to_node
        self.classification = classification
        self.condition = condition
        self.metadata = metadata or {}

    def to_dict(self) -> dict:
        return {
            "from": self.from_node,
            "to": self.to_node,
            "classification": self.classification,
            "condition": self.condition,
            "metadata": self.metadata
        }


class DataFlowTransition:
    def __init__(self, from_var: str, to_var: str, operation: str = "", expression: str = ""):
        self.from_var = from_var
        self.to_var = to_var
        self.operation = operation
        self.expression = expression

    def to_dict(self) -> dict:
        return {
            "from": self.from_var,
            "to": self.to_var,
            "operation": self.operation,
            "expression": self.expression
        }


class DataFlowModel:
    def __init__(self, schema_version: str = "1.0"):
        self.schema_version = schema_version
        self.inputs = []
        self.outputs = []
        self.transitions = []
        self.nodes = []
        self.edges = []
        self.nodes_map = {}

    def add_input(self, name: str, source: str):
        self.inputs.append({"name": name, "source": source})

    def add_output(self, name: str, target: str):
        self.outputs.append({"name": name, "target": target})

    def add_transition(self, trans: DataFlowTransition):
        self.transitions.append(trans)

    def add_node(self, node: DFNode):
        self.nodes.append(node)
        self.nodes_map[node.node_id] = node

    def add_edge(self, edge: DFEdge):
        self.edges.append(edge)

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "transitions": [t.to_dict() for t in self.transitions],
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges]
        }

    def save(self, path: str):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2)

    @classmethod
    def build_from_ir(cls, ir: SemanticIR, cfg: ControlFlowModel = None) -> "DataFlowModel":
        model = cls()
        
        # 1. Map all variable declarations from DATA_ITEM nodes
        variables = {}
        last_non_88_name = None
        
        for node in ir.nodes.values():
            if node.kind == "DATA_ITEM":
                name = node.properties.get("name")
                level = node.properties.get("level", 1)
                
                node_type = "VARIABLE" if level == 1 else "FIELD"
                if level == 88:
                    node_type = "STATE"

                df_id = f"df_var_{name}"
                df_node = DFNode(
                    node_id=df_id,
                    node_type=node_type,
                    name=name,
                    status=node.status,
                    source_file=node.source_file,
                    source_line=node.source_line,
                    source_column=node.source_column,
                    ir_node_id=node.node_id,
                    properties=node.properties.copy()
                )
                model.add_node(df_node)
                variables[name] = df_node

                # Redefines handling
                redefines = node.properties.get("redefines")
                if redefines:
                    model.add_edge(DFEdge(
                        from_node=f"df_var_{redefines}",
                        to_node=df_id,
                        classification="SHARED_STORAGE",
                        metadata={"type": "REDEFINES"}
                    ))
                
                # 88-level active reference mapping
                if level == 88:
                    if last_non_88_name:
                        model.add_edge(DFEdge(
                            from_node=df_id,
                            to_node=f"df_var_{last_non_88_name}",
                            classification="USES",
                            metadata={"type": "88_LEVEL_CONDITION"}
                        ))
                else:
                    last_non_88_name = name

        # Helper to get or create constant node
        def get_constant_node(val, stmt_node):
            df_id = f"df_const_{val}"
            if df_id not in model.nodes_map:
                const_node = DFNode(
                    node_id=df_id,
                    node_type="CONSTANT",
                    name=val,
                    status="PARSED",
                    source_file=stmt_node.source_file,
                    source_line=stmt_node.source_line,
                    source_column=stmt_node.source_column,
                    ir_node_id=stmt_node.node_id,
                    properties={"value": val}
                )
                model.add_node(const_node)
            return df_id

        # 2. Trace execution statements for data transitions
        active_conditions = []
        
        # Sort procedure nodes in order
        proc_nodes = sorted(
            [n for n in ir.nodes.values() if n.kind == "STATEMENT"],
            key=lambda n: n.node_id
        )

        for stmt in proc_nodes:
            stmt_type = stmt.properties.get("statement_type", "")
            
            # IF statement conditional data flow tracking
            if stmt_type == "IF":
                cond_val = stmt.properties.get("condition", "")
                cond_id = f"df_cond_{stmt.node_id}"
                
                # Create CONDITION node
                cond_node = DFNode(
                    node_id=cond_id,
                    node_type="CONDITION",
                    name=cond_val,
                    status=stmt.status,
                    source_file=stmt.source_file,
                    source_line=stmt.source_line,
                    source_column=stmt.source_column,
                    ir_node_id=stmt.node_id,
                    properties={"expression": cond_val}
                )
                model.add_node(cond_node)
                active_conditions.append(cond_id)
                
                # Connect variables referenced in condition to the condition node
                for var_name in variables:
                    if var_name in cond_val:
                        model.add_edge(DFEdge(
                            from_node=f"df_var_{var_name}",
                            to_node=cond_id,
                            classification="USES"
                        ))
            
            elif stmt_type == "END-IF":
                if active_conditions:
                    active_conditions.pop()

            # MOVE operation data transition
            elif stmt_type == "MOVE":
                src = stmt.properties.get("source")
                # Support both new 'targets' list and legacy 'target' string
                raw_tgt = stmt.properties.get("targets") or stmt.properties.get("target")
                tgt_list = raw_tgt if isinstance(raw_tgt, list) else ([raw_tgt] if raw_tgt else [])
                
                src_node_id = f"df_var_{src}" if src in variables else get_constant_node(src, stmt)
                
                for tgt in tgt_list:
                    tgt_node_id = f"df_var_{tgt}"
                    
                    model.add_edge(DFEdge(
                        from_node=src_node_id,
                        to_node=tgt_node_id,
                        classification="ASSIGNS"
                    ))
                    
                    # Backward compatibility transition
                    model.add_transition(DataFlowTransition(src, tgt, "MOVE"))

                    # Conditional data flow control mapping
                    for cond_id in active_conditions:
                        model.add_edge(DFEdge(
                            from_node=cond_id,
                            to_node=tgt_node_id,
                            classification="CONDITIONAL_ON"
                        ))

            # COMPUTE operation data transition
            elif stmt_type == "COMPUTE":
                tgt = stmt.properties.get("target")
                expr = stmt.properties.get("expression", "")
                tgt_node_id = f"df_var_{tgt}"
                
                # Add calculation node
                calc_id = f"df_calc_{stmt.node_id}"
                calc_node = DFNode(
                    node_id=calc_id,
                    node_type="CALCULATION",
                    name=expr,
                    status=stmt.status,
                    source_file=stmt.source_file,
                    source_line=stmt.source_line,
                    source_column=stmt.source_column,
                    ir_node_id=stmt.node_id,
                    properties={"expression": expr}
                )
                model.add_node(calc_node)
                
                model.add_edge(DFEdge(
                    from_node=calc_id,
                    to_node=tgt_node_id,
                    classification="ASSIGNS"
                ))

                # Identify operands in expression
                for var_name in variables:
                    if var_name in expr:
                        model.add_edge(DFEdge(
                            from_node=f"df_var_{var_name}",
                            to_node=calc_id,
                            classification="DERIVES_FROM"
                        ))
                        # Backward compatibility transition
                        model.add_transition(DataFlowTransition(var_name, tgt, "COMPUTE", expr))

                # Conditional flow control
                for cond_id in active_conditions:
                    model.add_edge(DFEdge(
                        from_node=cond_id,
                        to_node=tgt_node_id,
                        classification="CONDITIONAL_ON"
                    ))

            # ADD / SUBTRACT / MULTIPLY / DIVIDE data transitions
            elif stmt_type in ("ADD", "SUBTRACT", "MULTIPLY", "DIVIDE"):
                val = stmt.properties.get("value")
                tgt = stmt.properties.get("target")
                tgt_node_id = f"df_var_{tgt}"
                
                val_node_id = f"df_var_{val}" if val in variables else get_constant_node(val, stmt)
                
                model.add_edge(DFEdge(
                    from_node=val_node_id,
                    to_node=tgt_node_id,
                    classification="DERIVES_FROM",
                    metadata={"operation": stmt_type}
                ))
                
                # Backward compatibility transition
                model.add_transition(DataFlowTransition(val, tgt, stmt_type))

                for cond_id in active_conditions:
                    model.add_edge(DFEdge(
                        from_node=cond_id,
                        to_node=tgt_node_id,
                        classification="CONDITIONAL_ON"
                    ))

            # CALL USING arguments mappings
            elif stmt_type == "CALL":
                target_sub = stmt.properties.get("target", "")
                args = stmt.properties.get("arguments", [])
                
                call_node_id = f"df_call_{stmt.node_id}"
                call_node = DFNode(
                    node_id=call_node_id,
                    node_type="CALL_RESULT",
                    name=target_sub,
                    status="UNRESOLVED", # Default to unresolved unless verified
                    source_file=stmt.source_file,
                    source_line=stmt.source_line,
                    source_column=stmt.source_column,
                    ir_node_id=stmt.node_id,
                    properties={"target": target_sub}
                )
                model.add_node(call_node)
                
                for arg in args:
                    arg_node_id = f"df_var_{arg}" if arg in variables else get_constant_node(arg, stmt)
                    model.add_edge(DFEdge(
                        from_node=arg_node_id,
                        to_node=call_node_id,
                        classification="CALLS_WITH"
                    ))

            # File I/O READ / WRITE data flows
            elif stmt_type in ("READ", "WRITE", "REWRITE"):
                tgt = stmt.properties.get("target", "")
                file_io_id = f"df_io_{stmt.node_id}"
                
                node_type = "FILE_READ" if stmt_type == "READ" else "FILE_WRITE"
                io_node = DFNode(
                    node_id=file_io_id,
                    node_type=node_type,
                    name=tgt,
                    status=stmt.status,
                    source_file=stmt.source_file,
                    source_line=stmt.source_line,
                    source_column=stmt.source_column,
                    ir_node_id=stmt.node_id,
                    properties={"target": tgt}
                )
                model.add_node(io_node)
                
                tgt_node_id = f"df_var_{tgt}"
                if stmt_type == "READ":
                    model.add_edge(DFEdge(
                        from_node=file_io_id,
                        to_node=tgt_node_id,
                        classification="CONSUMES"
                    ))
                else:
                    model.add_edge(DFEdge(
                        from_node=tgt_node_id,
                        to_node=file_io_id,
                        classification="PRODUCES"
                    ))

            # Propagation of generic UNSUPPORTED node state status
            elif stmt.status == "UNSUPPORTED":
                unsupported_id = f"df_unsupported_{stmt.node_id}"
                unsupported_node = DFNode(
                    node_id=unsupported_id,
                    node_type="STATE",
                    name="UNSUPPORTED_EXPRESSION",
                    status="UNSUPPORTED",
                    source_file=stmt.source_file,
                    source_line=stmt.source_line,
                    source_column=stmt.source_column,
                    ir_node_id=stmt.node_id,
                    properties=stmt.properties.copy()
                )
                model.add_node(unsupported_node)

        return model
