import json

def compare_ir(file_path, ir_custom, ir_proleap, proleap_status, duration_custom, duration_proleap):
    custom_vars = [n.properties.get("name", "") for n in ir_custom.nodes.values() if n.kind == "DATA_ITEM"]
    custom_paras = [n.properties.get("name", "") for n in ir_custom.nodes.values() if n.kind == "PARAGRAPH"]
    custom_stmts = [n.properties.get("statement_type", "") for n in ir_custom.nodes.values() if n.kind == "STATEMENT"]
    custom_sql = [s for s in custom_stmts if s == "EXEC_SQL"]
    custom_cics = [s for s in custom_stmts if s == "EXEC_CICS"]
    custom_nested = sum(1 for n in ir_custom.nodes.values() if n.kind == "PROGRAM") - 1
    
    custom_info = {
        "status": "SUCCESS",
        "variables_count": len(custom_vars),
        "paragraphs_count": len(custom_paras),
        "statements_count": len(custom_stmts),
        "sql_count": len(custom_sql),
        "cics_count": len(custom_cics),
        "nested_programs_count": max(0, custom_nested),
        "duration_ms": duration_custom
    }
    
    differences = []
    
    if proleap_status == "FAILURE" or not ir_proleap:
        proleap_info = {
            "status": "FAILURE",
            "variables_count": 0,
            "paragraphs_count": 0,
            "statements_count": 0,
            "sql_count": 0,
            "cics_count": 0,
            "nested_programs_count": 0,
            "duration_ms": duration_proleap
        }
        comparison = {
            "status": "FAILURE",
            "differences": ["ProLeap parser failed or copybook resolution failed"]
        }
    else:
        pro_vars = [n.properties.get("name", "") for n in ir_proleap.nodes.values() if n.kind == "DATA_ITEM"]
        pro_paras = [n.properties.get("name", "") for n in ir_proleap.nodes.values() if n.kind == "PARAGRAPH"]
        pro_stmts = [n.properties.get("statement_type", "") for n in ir_proleap.nodes.values() if n.kind == "STATEMENT"]
        pro_sql = [s for s in pro_stmts if s == "EXEC_SQL"]
        pro_cics = [s for s in pro_stmts if s == "EXEC_CICS"]
        pro_nested = sum(1 for n in ir_proleap.nodes.values() if n.kind == "PROGRAM") - 1
        
        proleap_info = {
            "status": "SUCCESS",
            "variables_count": len(pro_vars),
            "paragraphs_count": len(pro_paras),
            "statements_count": len(pro_stmts),
            "sql_count": len(pro_sql),
            "cics_count": len(pro_cics),
            "nested_programs_count": max(0, pro_nested),
            "duration_ms": duration_proleap
        }
        
        # Check Node Count differences
        if len(custom_vars) != len(pro_vars):
            differences.append(f"Variables count mismatch: Custom={len(custom_vars)}, ProLeap={len(pro_vars)}")
        if len(custom_paras) != len(pro_paras):
            differences.append(f"Paragraphs count mismatch: Custom={len(custom_paras)}, ProLeap={len(pro_paras)}")
        if len(custom_stmts) != len(pro_stmts):
            differences.append(f"Statements count mismatch: Custom={len(custom_stmts)}, ProLeap={len(pro_stmts)}")
        if len(custom_sql) != len(pro_sql):
            differences.append(f"SQL statements count mismatch: Custom={len(custom_sql)}, ProLeap={len(pro_sql)}")
        if len(custom_cics) != len(pro_cics):
            differences.append(f"CICS statements count mismatch: Custom={len(custom_cics)}, ProLeap={len(pro_cics)}")
            
        # Check content match details
        missing_vars = set(custom_vars) - set(pro_vars)
        if missing_vars:
            differences.append(f"Variables present only in Custom: {list(missing_vars)[:5]}")
            
        missing_paras = set(custom_paras) - set(pro_paras)
        if missing_paras:
            differences.append(f"Paragraphs present only in Custom: {list(missing_paras)[:5]}")
            
        status = "MATCH" if not differences else "DIFFERENCE"
        comparison = {
            "status": status,
            "differences": differences
        }
        
    return {
        "file": file_path,
        "custom": custom_info,
        "proleap": proleap_info,
        "comparison": comparison
    }
