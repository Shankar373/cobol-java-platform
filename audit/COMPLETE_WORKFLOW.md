# Phase 5: Complete Orchestration Workflow

The orchestration logic resides entirely within `cobol_migrate.py`.

## Key Architectural Highlights:
1. **Checkpoint & Resume State**: Run state is saved to `target/state.json` after every stage. The orchestrator accepts `--restart-from <N>` which resets all stages from index $N$ onward to `pending` and deletes corresponding snapshot directories.
2. **Docker Orchestration**: The pipeline wraps container commands cleanly. The baseline execution runs inside `gnucobol` container while transpilation and target execution runs inside `cobj` container.
3. **Log Feeder**: Logs are dynamically routed using a global `LOG_SINK` callback. The UI server (`ui.py`) registers a callback to capture log messages, appending them to a memory log list which is then served live to the frontend via HTML5 Server-Sent Events (SSE).
