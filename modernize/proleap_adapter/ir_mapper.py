from modernize.semantic_ir import SemanticIR, SemanticIRNode
from modernize.proleap_adapter.diagnostics import ProLeapDiagnostic

class ProLeapIRMapper:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.node_counter = 0
        self.diagnostics = []

    def next_node_id(self) -> str:
        nid = f"node_{self.node_counter}"
        self.node_counter += 1
        return nid

    def map_to_ir(self, ast_json: dict) -> SemanticIR:
        ir = SemanticIR()
        
        comp_units = ast_json.get("compilation_units", [])
        for unit in comp_units:
            unit_name = unit.get("program_name") or unit.get("name") or "UNKNOWN"
            
            # 1. Map Program Node
            prog_node = SemanticIRNode(
                node_id=self.next_node_id(),
                kind="PROGRAM",
                properties={"name": unit_name},
                source_file=self.file_path,
                source_line=1,
                source_column=1
            )
            ir.add_node(prog_node)
            
            # 2. Map Variables (DATA_ITEM nodes)
            for var in unit.get("variables", []):
                var_name = var.get("name")
                level = var.get("level")
                
                # Check for REDEFINES or OCCURS if mapped
                props = {
                    "name": var_name,
                    "level": level,
                    "program": unit_name
                }
                
                var_node = SemanticIRNode(
                    node_id=self.next_node_id(),
                    kind="DATA_ITEM",
                    properties=props,
                    source_file=self.file_path,
                    source_line=1,
                    source_column=1
                )
                ir.add_node(var_node)
                
            # 3. Map Paragraphs & Statements
            for para in unit.get("paragraphs", []):
                para_name = para.get("name")
                
                para_node = SemanticIRNode(
                    node_id=self.next_node_id(),
                    kind="PARAGRAPH",
                    properties={
                        "name": para_name,
                        "program": unit_name
                    },
                    source_file=self.file_path,
                    source_line=1,
                    source_column=1
                )
                ir.add_node(para_node)
                
                for stmt_obj in para.get("statements", []):
                    stmt_type = stmt_obj.get("type", "UNKNOWN")
                    stype = stmt_type.upper().replace("_", " ")
                    line = stmt_obj.get("line", 1)
                    col = stmt_obj.get("column", 1)
                    start_offset = stmt_obj.get("start_offset", 0)
                    end_offset = stmt_obj.get("end_offset", 0)
                    
                    # Validate against known supported statement types
                    supported_types = {
                        "DISPLAY", "GOBACK", "EXIT", "EXIT PROGRAM", "INITIALIZE",
                        "MOVE", "ADD", "SUBTRACT", "MULTIPLY", "DIVIDE",
                        "PERFORM", "GO TO", "IF", "EVALUATE", "CALL",
                        "OPEN", "CLOSE", "READ", "WRITE", "REWRITE", "DELETE",
                        "EXEC SQL", "EXEC CICS", "EXEC SQLIMS", "SORT", "MERGE"
                    }
                    
                    if stype not in supported_types:
                        self.diagnostics.append(
                            ProLeapDiagnostic(
                                severity="WARNING",
                                detail=f"PROLEAP_IR_MAPPING_UNSUPPORTED: '{stype}' is not mapped to Semantic IR",
                                line=line,
                                col=col
                            )
                        )
                    
                    props = {
                        "statement_type": stype,
                        "program": unit_name
                    }
                    
                    # 4. Map SQL Statement
                    if stype in ("EXEC SQL", "EXEC SQLIMS"):
                        original_text = stmt_obj.get("original_text", "")
                        from modernize.parser import tokenize_sql, parse_sql_tokens, extract_host_variables
                        try:
                            sql_tokens = tokenize_sql(original_text)
                            sql_props = parse_sql_tokens(sql_tokens)
                            host_vars = extract_host_variables(sql_props)
                            props = {
                                "statement_type": "EXEC_SQL",
                                "sql_props": sql_props,
                                "host_variables": host_vars,
                                "original_sql": original_text,
                                "program": unit_name
                            }
                        except Exception as e:
                            self.diagnostics.append(
                                ProLeapDiagnostic(
                                    severity="WARNING",
                                    detail=f"PROLEAP_SQL_PARSING_FAILED: Failed to parse SQL properties: {e}",
                                    line=line,
                                    col=col
                                )
                            )
                            
                    # 5. Map CICS Statement
                    elif stype == "EXEC CICS":
                        original_text = stmt_obj.get("original_text", "")
                        from modernize.parser import tokenize_cics, parse_cics_tokens
                        try:
                            cics_tokens = tokenize_cics(original_text)
                            cics_props = parse_cics_tokens(cics_tokens)
                            props = {
                                "statement_type": "EXEC_CICS",
                                "cics_props": cics_props,
                                "original_cics": original_text,
                                "program": unit_name
                            }
                        except Exception as e:
                            self.diagnostics.append(
                                ProLeapDiagnostic(
                                    severity="WARNING",
                                    detail=f"PROLEAP_CICS_PARSING_FAILED: Failed to parse CICS properties: {e}",
                                    line=line,
                                    col=col
                                )
                            )
                    
                    stmt_node = SemanticIRNode(
                        node_id=self.next_node_id(),
                        kind="STATEMENT",
                        properties=props,
                        source_file=self.file_path,
                        source_line=line,
                        source_column=col,
                        start_offset=start_offset,
                        end_offset=end_offset
                    )
                    ir.add_node(stmt_node)
                    
        return ir
