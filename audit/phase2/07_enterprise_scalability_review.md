# Phase 2: Enterprise Scalability & Watchdog Analysis

This document outlines pipeline robustness under scale loads:

## 1. Watchdog Properties
- **Time Limits**: `timeout_seconds` kills runaway processes.
- **Size Limits**: `max_output_bytes` terminates infinite logging loops.
- **Process Cleanup**: PGID process tree termination prevents orphan Docker containers.

## 2. Scalability Bottlenecks
- **Docker Launch Overhead**: Instantiating Docker containers per stage compiles slower.
- **State Serialization**: Large `state.json` updates slow disk operations.
