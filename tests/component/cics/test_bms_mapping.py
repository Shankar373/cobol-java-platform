import pytest
from modernize.bms_parser import BmsParser

def test_bms_parser_simple():
    bms_src = """
MSET1    DFHMSD TYPE=&SYSPARM,MODE=INOUT,LANG=COBOL,STORAGE=AUTO,      *
               CTRL=FREEKB,TERM=3270
MAP1     DFHMDI SIZE=(24,80)
FIELD1   DFHMDF POS=(05,10),LENGTH=15,INITIAL='CUSTOMER NAME',         *
               ATTRB=(ASKIP,BRT)
         DFHMDF POS=(05,26),LENGTH=1,ATTRB=ASKIP
NAME     DFHMDF POS=(06,10),LENGTH=30,ATTRB=(UNPROT,IC)
    """
    parser = BmsParser(bms_src)
    mapset = parser.parse()
    
    assert mapset.name == "MSET1"
    assert len(mapset.maps) == 1
    
    map1 = mapset.maps[0]
    assert map1.name == "MAP1"
    assert map1.size == (24, 80)
    assert len(map1.fields) == 3
    
    f1 = map1.fields[0]
    assert f1.name == "FIELD1"
    assert f1.pos == (5, 10)
    assert f1.length == 15
    assert f1.initial == "CUSTOMER NAME"
    assert "ASKIP" in f1.attrb
    assert "BRT" in f1.attrb

    f2 = map1.fields[1]
    assert f2.name == "" # Unnamed
    assert f2.pos == (5, 26)
    assert f2.length == 1
    assert f2.attrb == ["ASKIP"]

    f3 = map1.fields[2]
    assert f3.name == "NAME"
    assert f3.pos == (6, 10)
    assert f3.length == 30
    assert "UNPROT" in f3.attrb
    assert "IC" in f3.attrb


def test_bms_pipeline_generation():
    import tempfile
    import os
    import shutil
    from modernize.native_pipeline import NativePipeline

    temp_repo = tempfile.mkdtemp()
    temp_out = tempfile.mkdtemp()
    
    try:
        # Create sources folder and bms map file
        os.makedirs(os.path.join(temp_repo, "sources"), exist_ok=True)
        bms_src = """
MSET1    DFHMSD TYPE=&SYSPARM,MODE=INOUT,LANG=COBOL,STORAGE=AUTO,      *
               CTRL=FREEKB,TERM=3270
MAP1     DFHMDI SIZE=(24,80)
FIELD1   DFHMDF POS=(05,10),LENGTH=15,INITIAL='CUSTOMER NAME',         *
               ATTRB=(ASKIP,BRT)
        """
        with open(os.path.join(temp_repo, "sources", "cics_screen.map"), "w", encoding="utf-8") as fh:
            fh.write(bms_src)

        # Write dummy main program configuration
        import json
        config = {
            "main_program": "dummy.cob",
            "file_assignments": {}
        }
        with open(os.path.join(temp_repo, "migration_config.json"), "w", encoding="utf-8") as fh:
            json.dump(config, fh)

        # Dummy cobol source
        with open(os.path.join(temp_repo, "sources", "dummy.cob"), "w", encoding="utf-8") as fh:
            fh.write("       IDENTIFICATION DIVISION.\n       PROGRAM-ID. DUMMY.\n       PROCEDURE DIVISION.\n           GOBACK.\n")

        p = NativePipeline(temp_repo, temp_out)
        p.stage_discover()
        p.stage_parse()
        p.stage_generate(list(p.program_ir.keys())[0])

        # Verify output files exist
        bms_out_dir = os.path.join(temp_out, "results", "native", "bms_maps")
        assert os.path.isdir(bms_out_dir)
        
        json_path = os.path.join(bms_out_dir, "mset1.json")
        assert os.path.isfile(json_path)
        with open(json_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            assert data["name"] == "MSET1"

        html_path = os.path.join(bms_out_dir, "mset1_map1.html")
        assert os.path.isfile(html_path)
        with open(html_path, "r", encoding="utf-8") as fh:
            html = fh.read()
            assert "CUSTOMER NAME" in html
            assert "MSET1" not in html # Page title should be mapped correctly

    finally:
        shutil.rmtree(temp_repo, ignore_errors=True)
        shutil.rmtree(temp_out, ignore_errors=True)

