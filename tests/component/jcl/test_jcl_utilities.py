import os
import json
import shutil
import tempfile
import pytest
from modernize.native_pipeline import NativePipeline

def test_iebgener_emulation_e2e():
    temp_out = tempfile.mkdtemp(prefix="jcl_ut1_out_")
    repo_dir = tempfile.mkdtemp(prefix="jcl_ut1_repo_")
    os.makedirs(os.path.join(repo_dir, "src"), exist_ok=True)
    
    jcl_content = """//JCLUT1 JOB (ACCT),'UTILITY_TEST'
//STEP1   EXEC PGM=IEBGENER
//SYSUT1  DD DSN='MY.INPUT.DATA',DISP=SHR
//SYSUT2  DD DSN='MY.OUTPUT.DATA',DISP=(NEW,CATLG)
//SYSIN   DD DUMMY
"""
    with open(os.path.join(repo_dir, "src", "JCLUT1.jcl"), "w", encoding="utf-8") as fh:
        fh.write(jcl_content)
        
    config = {
        "main_program": "JCLUT1.jcl",
        "file_assignments": {
            "SYSUT1": "MY.INPUT.DATA",
            "SYSUT2": "MY.OUTPUT.DATA"
        }
    }
    with open(os.path.join(repo_dir, "migration_config.json"), "w", encoding="utf-8") as fh:
        json.dump(config, fh)
        
    with open(os.path.join(repo_dir, "MY.INPUT.DATA"), "w", encoding="utf-8") as fh:
        fh.write("LINE 1\nLINE 2\n")
        
    try:
        p = NativePipeline(repo_dir, temp_out)
        verdict = p.run()
        
        assert verdict == "NATIVE_JAVA_VERIFIED", f"IEBGENER utility pipeline failed: {verdict}"
        
        # Verify copied output
        copied_file = os.path.join(temp_out, "results", "native", "MY.OUTPUT.DATA")
        assert os.path.exists(copied_file)
        with open(copied_file, "r") as fh:
            content = fh.read()
        assert content == "LINE 1\nLINE 2\n"
        
    finally:
        shutil.rmtree(temp_out, ignore_errors=True)
        shutil.rmtree(repo_dir, ignore_errors=True)

def test_idcams_emulation_e2e():
    temp_out = tempfile.mkdtemp(prefix="jcl_ut2_out_")
    repo_dir = tempfile.mkdtemp(prefix="jcl_ut2_repo_")
    os.makedirs(os.path.join(repo_dir, "src"), exist_ok=True)
    
    jcl_content = """//JCLUT2 JOB (ACCT),'IDCAMS_TEST'
//STEP1   EXEC PGM=IDCAMS
//SYSIN   DD *
  DELETE MY.DEL.DATA
  DEFINE CLUSTER NAME(MY.NEW.CLUSTER)
/*
"""
    with open(os.path.join(repo_dir, "src", "JCLUT2.jcl"), "w", encoding="utf-8") as fh:
        fh.write(jcl_content)
        
    config = {
        "main_program": "JCLUT2.jcl",
        "file_assignments": {}
    }
    with open(os.path.join(repo_dir, "migration_config.json"), "w", encoding="utf-8") as fh:
        json.dump(config, fh)
        
    del_file = os.path.join(repo_dir, "MY.DEL.DATA")
    with open(del_file, "w") as fh:
        fh.write("to delete")
        
    try:
        p = NativePipeline(repo_dir, temp_out)
        verdict = p.run()
        
        assert verdict == "NATIVE_JAVA_VERIFIED", f"IDCAMS utility pipeline failed: {verdict}"
        
        # Verify cluster created, del file deleted in results/native
        assert not os.path.exists(os.path.join(temp_out, "results", "native", "MY.DEL.DATA"))
        assert os.path.exists(os.path.join(temp_out, "results", "native", "MY.NEW.CLUSTER"))
        
    finally:
        shutil.rmtree(temp_out, ignore_errors=True)
        shutil.rmtree(repo_dir, ignore_errors=True)

def test_sort_emulation_e2e():
    temp_out = tempfile.mkdtemp(prefix="jcl_ut3_out_")
    repo_dir = tempfile.mkdtemp(prefix="jcl_ut3_repo_")
    os.makedirs(os.path.join(repo_dir, "src"), exist_ok=True)
    
    jcl_content = """//JCLUT3 JOB (ACCT),'SORT_TEST'
//STEP1   EXEC PGM=SORT
//SORTIN  DD DSN='MY.UNSORTED.DATA',DISP=SHR
//SORTOUT DD DSN='MY.SORTED.DATA',DISP=(NEW,CATLG)
//SYSIN   DD *
  SORT FIELDS=(1,4,CH,A)
/*
"""
    with open(os.path.join(repo_dir, "src", "JCLUT3.jcl"), "w", encoding="utf-8") as fh:
        fh.write(jcl_content)
        
    config = {
        "main_program": "JCLUT3.jcl",
        "file_assignments": {
            "SORTIN": "MY.UNSORTED.DATA",
            "SORTOUT": "MY.SORTED.DATA"
        }
    }
    with open(os.path.join(repo_dir, "migration_config.json"), "w", encoding="utf-8") as fh:
        json.dump(config, fh)
        
    with open(os.path.join(repo_dir, "MY.UNSORTED.DATA"), "w", encoding="utf-8") as fh:
        fh.write("ZZZZ\nBBBB\nAAAA\nCCCC\n")
        
    try:
        p = NativePipeline(repo_dir, temp_out)
        verdict = p.run()
        
        assert verdict == "NATIVE_JAVA_VERIFIED", f"SORT utility pipeline failed: {verdict}"
        
        # Verify sorted output
        sorted_file = os.path.join(temp_out, "results", "native", "MY.SORTED.DATA")
        assert os.path.exists(sorted_file)
        with open(sorted_file, "r") as fh:
            content = fh.read()
        assert content == "AAAA\nBBBB\nCCCC\nZZZZ\n"
        
    finally:
        shutil.rmtree(temp_out, ignore_errors=True)
        shutil.rmtree(repo_dir, ignore_errors=True)

