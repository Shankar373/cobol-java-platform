# Phase 2: Data-Flow & Variable-Dependency Tracking

This document defines the variable dependency tracking contract:

## 1. Data-Flow Tracking
Traces data dependencies:
`INPUT -> FIELD -> VARIABLE -> CALCULATION -> CONDITION -> STATE -> OUTPUT`
This enables mapping target variables back to source input operations.
