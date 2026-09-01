# Phase 2: Execution Observation Model

This document defines the ExecutionObservation model:

## 1. ExecutionObservation Model Layout
The container records the observable state of a process execution:

```json
{
  "scenario_id": "SC-1002",
  "execution_status": "normal",
  "exit_code": 0,
  "stdout": "Processing complete.",
  "stderr": "",
  "files": ["data/out/records.csv"],
  "file_contents": {
    "data/out/records.csv": "10001,ACTIVE,95000.00"
  },
  "file_sizes": {
    "data/out/records.csv": 22
  },
  "record_counts": {
    "data/out/records.csv": 1
  },
  "database_observations": {},
  "structured_output": {},
  "duration": 0.45,
  "normalization_metadata": {}
}
```
