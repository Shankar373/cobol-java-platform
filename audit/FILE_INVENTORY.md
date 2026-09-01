# Phase 1: Complete File Inventory

| Path | Type | Purpose | Risk Level |
| :--- | :--- | :--- | :---: |
| `cobol_migrate.py` | Python | Orchestrates the 13-stage migration pipeline | High |
| `ui.py` | Python | Serves REST endpoints and updates SSE log stream | Medium |
| `ui.html` | HTML | Renders the pipeline monitoring web page | Low |
| `audit_engine.py` | Python | Runs verification suite and writes audit markdown reports | Low |
| `slicer.py` | Python | Slices COBOL paragraphs and parses variable references | Low |
| `execution/__init__.py` | Python | Exports scenario detectors and runner triggers | Low |
| `execution/interactive_detector.py` | Python | Parses bare ACCEPT statements | Low |
| `execution/scenario_discovery.py` | Python | Resolves smoke scripts, heredocs, and configs | Medium |
| `execution/scenario_parser.py` | Python | Extracts stdin lines from echo, printf, and redirections | Medium |
| `execution/scenario_runner.py` | Python | Subprocess execution wrapped in time/byte watchdogs | High |
| `execution/models.py` | Python | Structures dataclasses for scenarios and results | Low |
| `execution/artifacts.py` | Python | Writes baseline/execute stdout and run metadata files | Low |
| `migration_config.json` | JSON | Holds path mappings, entries, and interactive settings | Low |
| `requirements.txt` | Text | Declares python libraries (pytest, greenlet, playwright) | Low |
