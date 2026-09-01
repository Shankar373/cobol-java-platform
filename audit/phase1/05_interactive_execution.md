# Phase 1: Interactive Execution Layer Audit

We verified the interactive scenario discovery and execution logic inside `execution/`:

## 1. Stdin Scenario Matching
- **Interactive Detection**: Scans reachable sources for bare `ACCEPT` statements (ignoring environment/clock reads).
- **Scenario Discovery**: Prioritizes test shell scripts (`test/*.sh`), then raw stdin files (`test/*.stdin`), and finally configuration paths.
- **Scenario Parity**:
  - `scenario_id` is computed as a SHA-256 hash of the ordered input values.
  - The exact same `scenario_id` is mapped to both COBOL baseline (`execution_metadata_baseline.json`) and Java execute (`execution_metadata_execute.json`), ensuring identical stdin replays.
  - **Verdict**: **VERIFIED**. Both runs consume the exact same input lines.
