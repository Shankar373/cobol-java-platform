# Phase 2: Data-Flow & Control-Flow Graph Design

We define the graph structure for flow and data tracking:

## 1. Control-Flow Graph (CFG)
The CFG tracks execution transitions:
`Program -> Paragraph -> Statement -> Control-flow edges`
This maps program branches, loops, perform loops, call graphs, and termination coordinates.

## 2. Data-Flow Tracking
Traces data dependencies:
`INPUT -> FIELD -> VARIABLE -> CALCULATION -> CONDITION -> STATE -> OUTPUT`
This enables mapping target variables back to source input operations.
