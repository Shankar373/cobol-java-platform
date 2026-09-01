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

## 2. Coverage Tracking Matrices
We track and report coverage across multiple independent categories:
- **Program coverage**: Count of compiled programs.
- **Statement coverage**: Total statement nodes mapped.
- **CALL coverage**: Total call nodes resolved.
- **Data-flow coverage**: Total variables traced.
- **Business-rule coverage**: Total rules verified.
- **Execution coverage**: Live run checks.
- **Equivalence coverage**: Evaluated output checks.
