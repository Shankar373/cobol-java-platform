# Phase 2: Comparison Result Model

This document defines the structured ComparisonResult model:

## 1. ComparisonResult Schema
```json
{
  "status": "FAIL",
  "checks": {
    "output_presence": "PASS",
    "file_set": "PASS",
    "file_contents": "FAIL",
    "record_counts": "PASS",
    "stdout": "PASS",
    "stderr": "PASS",
    "exit_code": "PASS",
    "database_state": "PASS",
    "normalization": "PASS"
  },
  "differences": [
    {
      "artifact": "data/out/records.csv",
      "type": "content_mismatch",
      "expected": "10001,ACTIVE,95000.00",
      "actual": "10001,ACTIVE,35000.00"
    }
  ],
  "evidence": {
    "baseline_observation": "target/execution/SC-1002/observation_baseline.json",
    "java_observation": "target/execution/SC-1002/observation_execute.json"
  }
}
```
