# Phase 2: Source-to-Target Traceability Model

We define the complete metadata mapping layout connecting COBOL sources to target Java classes:

## 1. Traceability Record layout
```json
{
  "rule_id": "RULE-017",
  "cobol_source": {
    "file": "PREMCALC.cob",
    "line": 120,
    "paragraph": "PROCESS-CALC"
  },
  "intermediate_representation": {
    "node_id": "COMPUTE_NODE_41"
  },
  "java_target": {
    "class": "PremiumService",
    "method": "calculatePremium",
    "statement": "this.total = qty.multiply(rate);"
  },
  "test_cases": [
    "PremiumServiceTest.testNormalCalculation",
    "PremiumServiceTest.testBoundaryCalculation"
  ],
  "verification": {
    "status": "VERIFIED",
    "timestamp": "2026-08-21T17:15:00Z"
  }
}
```
