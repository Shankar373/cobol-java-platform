import sys
import os

def test_native_no_benchmark_coupling():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    prod_files = [
        os.path.join(root, "modernize", "native_generator.py")
    ]
    
    # Check if native_pipeline.py exists and add it
    pipeline_path = os.path.join(root, "modernize", "native_pipeline.py")
    if os.path.exists(pipeline_path):
        prod_files.append(pipeline_path)

    forbidden = ["BCMAIN", "CCMAIN01", "ClaimsCore", "BankCore"]
    
    for f in prod_files:
        if not os.path.exists(f):
            continue
        content = open(f, "r", encoding="utf-8").read()
        for term in forbidden:
            assert term not in content, f"Forbidden term '{term}' found in production native file {f}"
