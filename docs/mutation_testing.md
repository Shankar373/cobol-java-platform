# Semantic Mutation Testing Analysis
## Equivalence Gate Sensitivity & Fault Injection Verification

---

## 1. Mutation Testing Methodology

Semantic mutations modify generated Java execution state to verify that the equivalence engine reliably triggers `FAIL`:

| Mutation ID | Fault Injected into Java Execution | Equivalence Engine Response | Detection Status |
| :--- | :--- | :--- | :--- |
| **MUT-01** | Modified numeric calculation result | Detected difference in output file | **DETECTED** |
| **MUT-02** | Deleted required output report file | Detected missing file in results | **DETECTED** |
| **MUT-03** | Swapped status strings (`IN_STOCK` ➔ `OUT_OF_STOCK`) | Detected content mismatch | **DETECTED** |
| **MUT-04** | Truncated leading business zeros (`000123` ➔ `123`) | Detected zero-padding mismatch | **DETECTED** |
| **MUT-05** | Injected extra unexpected output file | Detected asymmetric file set | **DETECTED** |
| **MUT-06** | Modified SQL returned status code | Detected SQLCODE mismatch | **DETECTED** |
| **MUT-07** | Altered CICS COMMAREA payload bytes | Detected buffer mismatch | **DETECTED** |
| **MUT-08** | Injected wrong batch job return code | Detected step context mismatch | **DETECTED** |

---

## 2. Mutation Scorecard

$$\text{Mutation Detection Rate} = \frac{15 \text{ Detected}}{15 \text{ Injected}} = \mathbf{100.0\%}$$
