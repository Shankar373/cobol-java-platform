# Phase 2: Security & Execution Hardening Design

This document details the hardening design for security and execution stability:

## 1. Security Enhancements
- **Command Argument Injection**: Refactor all process execution blocks (`subprocess.Popen`) to list-based arguments with `shell=False`, preventing shell injections.
- **Unsafe Zip extraction**: Enforce strict checks on relative path traversals (`..`) and check canonical path starting bounds.

## 2. Reliability Controls
- **Watchdog Protection**: Process watchdogs monitor and limit executing runtimes.
- **Atomic State checkpoints**: Writes `state.json` updates transactionally to temp files before replacing target states, preventing corruption.
