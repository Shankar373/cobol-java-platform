import os
import shutil
import tempfile
import pytest
from modernize import CobolLexer, CobolParser, DataFlowModel, DependencyAnalysisEngine

def test_dependency_analysis_engine_generic_and_negative_checks():
    # SYNTHETIC GENERICITY TEST
    # Create temporary folder simulating a repository layout
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Program A source code: calls B statically, calls C dynamically, calls external DB2 program, includes copybook
        prog_a_src = (
            "000100 IDENTIFICATION DIVISION.\n"
            "000200 PROGRAM-ID. PROG-A.\n"
            "000300 DATA DIVISION.\n"
            "000400 WORKING-STORAGE SECTION.\n"
            "000500 01  WS-DYNAMIC-PROG PIC X(8) VALUE \"PROG-C\".\n"
            "000600 01  WS-UNRESOLVED-VAR PIC X(8).\n"
            "000700 PROCEDURE DIVISION.\n"
            "000800     COPY MYCOPYBOOK.\n"
            "000900     COPY MISSINGCOPY.\n"
            "001000     CALL \"PROG-B\" USING A B.\n"
            "001100     CALL \"MISSING-PROG\".\n"
            "001200     CALL WS-DYNAMIC-PROG USING X.\n"
            "001300     CALL WS-UNRESOLVED-VAR.\n"
            "001400     CALL \"DB2UTIL\".\n"
            "001500     STOP RUN.\n"
        )
        
        # Program B source code: calls nothing
        prog_b_src = (
            "000100 IDENTIFICATION DIVISION.\n"
            "000200 PROGRAM-ID. PROG-B.\n"
            "000300 PROCEDURE DIVISION.\n"
            "000400     STOP RUN.\n"
        )
        
        # Program C source code: calls nothing, but unreachable initially unless dynamic target matches
        prog_c_src = (
            "000100 IDENTIFICATION DIVISION.\n"
            "000200 PROGRAM-ID. PROG-C.\n"
            "000300 PROCEDURE DIVISION.\n"
            "000400     STOP RUN.\n"
        )

        # Write discovered program source assets
        with open(os.path.join(temp_dir, "PROG-A.cob"), "w", encoding="utf-8") as f:
            f.write(prog_a_src)
        with open(os.path.join(temp_dir, "PROG-B.cob"), "w", encoding="utf-8") as f:
            f.write(prog_b_src)
        with open(os.path.join(temp_dir, "PROG-C.cob"), "w", encoding="utf-8") as f:
            f.write(prog_c_src)
            
        # Write copybook file
        with open(os.path.join(temp_dir, "MYCOPYBOOK.cpy"), "w", encoding="utf-8") as f:
            f.write("01  COPYBOOK-VAR PIC X.\n")

        # Parse all models
        ir_models = {}
        data_flows = {}
        
        for name, src in [("PROG-A", prog_a_src), ("PROG-B", prog_b_src), ("PROG-C", prog_c_src)]:
            tokens = CobolLexer(f"{name}.cob", format_mode="fixed").tokenize(src)
            ir = CobolParser(tokens, f"{name}.cob").parse()
            ir_models[name] = ir
            data_flows[name] = DataFlowModel.build_from_ir(ir)

        # Execute dependency analysis
        status = DependencyAnalysisEngine.analyze(temp_dir, "PROG-A", ir_models, data_flows)
        
        # Group calls by target
        calls_by_target = {}
        for call in status.calls:
            calls_by_target.setdefault(call.target, []).append(call)

        # 1. Valid static CALL check (PROG-B exists)
        assert "PROG-B" in calls_by_target
        assert calls_by_target["PROG-B"][0].resolution == "RESOLVED_STATIC"
        assert calls_by_target["PROG-B"][0].reachable == "YES"
        assert calls_by_target["PROG-B"][0].arguments == ["A", "B"]
        assert calls_by_target["PROG-B"][0].argument_count == 2
        
        # 2. Missing static CALL target check (MISSING-PROG)
        assert "MISSING-PROG" in calls_by_target
        assert calls_by_target["MISSING-PROG"][0].resolution == "MISSING_SOURCE"

        # 3. Dynamic CALL (WS-DYNAMIC-PROG resolved from DataFlow constants)
        assert "WS-DYNAMIC-PROG" in calls_by_target
        assert calls_by_target["WS-DYNAMIC-PROG"][0].resolution == "RESOLVED_DYNAMIC"

        # 4. Unresolved dynamic CALL (WS-UNRESOLVED-VAR has no constants value)
        assert "WS-UNRESOLVED-VAR" in calls_by_target
        assert calls_by_target["WS-UNRESOLVED-VAR"][0].resolution == "UNRESOLVED_DYNAMIC"

        # 5. External CALL (DB2UTIL starting with DB2)
        assert "DB2UTIL" in calls_by_target
        assert calls_by_target["DB2UTIL"][0].resolution == "EXTERNAL_SYSTEM"

        # 6. COPY dependency (found)
        assert "MYCOPYBOOK" in calls_by_target
        assert calls_by_target["MYCOPYBOOK"][0].resolution == "COPY_FOUND"

        # 7. COPY dependency (missing)
        assert "MISSINGCOPY" in calls_by_target
        assert calls_by_target["MISSINGCOPY"][0].resolution == "COPY_MISSING"

    finally:
        shutil.rmtree(temp_dir)
