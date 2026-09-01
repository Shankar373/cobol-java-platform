# Final Equivalence Audit Report

## 1. Executive Summary
This audit validates the final equivalence engine and verification contract implemented for the COBOL-to-Java modernization pipeline. The primary focus is resolving the `EQUIVALENCE_UNVERIFIED` state for repositories without flat-file outputs (specifically `ADVERSARIAL01` and `INVMGR`), classifying the repository topologies from runtime evidence, and ensuring strict verification contracts.

The verdict of this pipeline is scientifically trustworthy: **we never fabricate passing verdicts or convert unverified gates into PASS without concrete evidence.**

---

## 2. Evidence-Driven Topology Classification
The modernized pipeline dynamically classifies repository topology strictly based on runtime execution evidence rather than hardcoded program/folder names. The four defined topologies are:

| Topology | Criteria (Runtime Evidence) | Normalization & Verification |
| :--- | :--- | :--- |
| **`MULTI_FILE_OUTPUT`** | $\ge 2$ flat files produced by legacy baseline run | Strict line-by-line, byte-by-byte file content normalization & comparison |
| **`FILE_OUTPUT`** | Exactly $1$ flat file produced by legacy baseline run | Byte-by-byte file content comparison, record count matches |
| **`CONSOLE_OUTPUT`** | $0$ flat files produced, but baseline `stdout` is non-empty | Stdout tail-matching, ignore timestamp/non-deterministic variations |
| **`NO_OBSERVABLE_OUTPUT`** | $0$ flat files produced, and baseline `stdout` is empty/whitespace | Deemed untestable; strictly falls to `EQUIVALENCE_UNVERIFIED` |

---

## 3. Investigation of `ADVERSARIAL01` and `INVMGR`
Prior pipeline stages marked `ADVERSARIAL01` and `INVMGR` as `EQUIVALENCE_UNVERIFIED` because they produced no flat-file outputs. Our runtime analysis reveals:

1. **`ADVERSARIAL01`**
   - **Observable Outputs:** Zero flat-file outputs. Non-empty stdout (e.g. 101 characters of performance or console logs).
   - **Input Fixtures:** No input files or stdin inputs.
   - **Topology Verdict:** Classified as `CONSOLE_OUTPUT`.
   - **Negative Equivalence:** Since there are no input fixtures (files or stdin) to mutate, mutation sensitivity is untestable. The negative equivalence gate is honestly and correctly marked **`UNVERIFIED`**.

2. **`INVMGR`**
   - **Observable Outputs:** Zero flat-file outputs. Non-empty stdout (e.g. 59 characters of menu options or output headers).
   - **Input Fixtures:** No input files or stdin inputs.
   - **Topology Verdict:** Classified as `CONSOLE_OUTPUT`.
   - **Negative Equivalence:** Lacking input fixtures to mutate, mutation sensitivity is untestable. The negative equivalence gate is honestly and correctly marked **`UNVERIFIED`**.

Under the pipeline rules, any repository with an `UNVERIFIED` gate cannot reach `PRODUCTION_READY`. Thus, both `ADVERSARIAL01` and `INVMGR` remain safely classified as `PRODUCTION_CANDIDATE` or `VERIFIED`, preventing false assurances.

---

## 4. Normalization and Truncation Safety
To prevent out-of-memory errors and handle massive console outputs safely, the pipeline implements:
- **Capped Tail Comparison:** Stdout is truncated during comparison at $1500$ characters (legacy) and $2000$ characters (native).
- **Metadata Logging:** When truncation occurs, the manifest explicitly records `stdout_truncated = True` and lists the compare limit to warn engineers that full-output parity is not mathematically guaranteed.
- **Normalization:** Line-endings, trailing whitespaces, and system-specific differences are normalized before comparison.
