# Phase 11 — IMS / MQ / Mainframe Integration Boundary
## Zero-Assumption Audit, Diagnostic Boundary Hardening & Integration Classification

**Classification Standard**: Evidence-Driven Mainframe Modernization Taxonomy  
**Date**: September 2026  
**Status**: `PARTIAL` (`UNSUPPORTED` / `UNPROVEN` for IMS & MQ | Fail-Closed Diagnostic Enforcement)

---

## 1. Executive Summary

Phase 11 conducts a zero-assumption audit and boundary verification of mainframe external integration subsystems:
- **IBM IMS / DL/I**: Hierarchical databases (`CBLTDLI`, `ASMTDLI`, `PLITDLI`, `EXEC DLI`, PCBs, SSAs, `GU`, `GN`, `ISRT`, `DLET`, `REPL`) and IMS TM message transaction processing.
- **IBM MQ**: Mainframe message queueing (`MQCONN`, `MQOPEN`, `MQPUT`, `MQPUT1`, `MQGET`, `MQINQ`, `MQCLOSE`, `MQDISC`, `MQCMIT`, `MQBACK`, `MQMD`, `MQPMO`, `MQGMO`).
- **External Interfaces & Program Boundaries**: External program calls (`CALL literal/identifier`), dynamic program loading, HTTP/REST/socket interfaces, and character encoding conversions (ASCII vs EBCDIC IBM-037/1047).

### Core Certification Principles
- **`IMS COMPATIBILITY != REAL IMS DATABASE`**: Real IBM IMS subsystems and hierarchical DL/I buffer pools on z/OS are classified as **`UNPROVEN`**.
- **`MQ EMULATION != REAL IBM MQ`**: In-memory queues or generic message maps are not equivalent to transactional IBM MQ queue managers. Real IBM MQ is classified as **`UNPROVEN`**.
- **`FAIL-CLOSED DIAGNOSTICS`**: All invocations of `CBLTDLI`, `ASMTDLI`, `PLITDLI`, `MQCONN`, `MQOPEN`, `MQPUT`, `MQGET`, `MQCLOSE`, `MQDISC`, etc., emit `NATIVE_TRANSLATION_BLOCKED` diagnostics, preventing unverified or silent mis-translation into Java.

---

## 2. Zero-Assumption Audit & Discovery Inventory

| Subsystem | Construct / API | Modernization Engine Status | Parser & Diagnostic Behavior | Classification |
| :--- | :--- | :--- | :--- | :--- |
| **IMS / DL/I** | `CALL 'CBLTDLI'` (GU, GN, ISRT, DLET, REPL) | Not Translated Natively | Emits `NATIVE_TRANSLATION_BLOCKED` diagnostic (`IMS_MQ`) | `UNSUPPORTED` / `UNPROVEN` |
| **IMS / DL/I** | `CALL 'ASMTDLI'` / `'PLITDLI'` | Not Translated Natively | Emits `NATIVE_TRANSLATION_BLOCKED` diagnostic (`IMS_MQ`) | `UNSUPPORTED` / `UNPROVEN` |
| **IMS TM** | Message GU/GN, Transaction Codes | Not Translated Natively | Emits `NATIVE_TRANSLATION_BLOCKED` diagnostic (`IMS_MQ`) | `UNSUPPORTED` / `UNPROVEN` |
| **IBM MQ** | `CALL 'MQCONN'`, `'MQCONNX'` | Not Translated Natively | Emits `NATIVE_TRANSLATION_BLOCKED` diagnostic (`IMS_MQ`) | `UNSUPPORTED` / `UNPROVEN` |
| **IBM MQ** | `CALL 'MQOPEN'`, `'MQCLOSE'`, `'MQDISC'` | Not Translated Natively | Emits `NATIVE_TRANSLATION_BLOCKED` diagnostic (`IMS_MQ`) | `UNSUPPORTED` / `UNPROVEN` |
| **IBM MQ** | `CALL 'MQPUT'`, `'MQPUT1'`, `'MQGET'` | Not Translated Natively | Emits `NATIVE_TRANSLATION_BLOCKED` diagnostic (`IMS_MQ`) | `UNSUPPORTED` / `UNPROVEN` |
| **IBM MQ** | `CALL 'MQCMIT'`, `'MQBACK'` | Not Translated Natively | Emits `NATIVE_TRANSLATION_BLOCKED` diagnostic (`IMS_MQ`) | `UNSUPPORTED` / `UNPROVEN` |
| **External CALL** | `CALL 'UNRESOLVED_PROG'` | Dynamic Lookup / Stub | Emits diagnostic comment and fails closed if unresolved | `PARTIAL` |
| **Encoding** | Mainframe EBCDIC (IBM-037/1047) | Standard ASCII/UTF-8 | Custom collating sequences emit unsupported diagnostic | `UNSUPPORTED` |

---

## 3. Diagnostic Enforcement Architecture

When any unsupported IMS or MQ call is encountered during code generation in [`modernize/native_generator.py`](file:///c:/Users/bandi/Desktop/ai-workspace/Cobol-to-java-modernization/modernize/native_generator.py#L2259):

```python
target_clean = target.strip('"').strip("'").upper()
if target_clean in ("CBLTDLI", "ASMTDLI", "PLITDLI") or target_clean.startswith("MQ"):
    self.current_generator.diagnostics.append({
        "construct": "IMS_MQ",
        "source_coordinate": f"{node.source_file}:{node.source_line}",
        "semantic_ir_node": node.node_id,
        "severity": "ERROR",
        "status": "NATIVE_TRANSLATION_BLOCKED",
        "reason": f"Mainframe IMS/MQ Call to '{target_clean}' is not supported natively."
    })
```

This diagnostic feeds directly into `stage_dependency_gate()` and `stage_translation_gate()`, ensuring that unverified migrations cannot silently succeed.

---

## 4. Test & Verification Evidence

All 5 Phase 11 tests executed successfully in `tests/test_phase11_ims_mq.py`:
- `test_ims_dli_cbltdli_diagnostic`: Verified `CBLTDLI` triggers `NATIVE_TRANSLATION_BLOCKED`.
- `test_ims_dli_asmtdli_diagnostic`: Verified `ASMTDLI` triggers `NATIVE_TRANSLATION_BLOCKED`.
- `test_ibm_mq_mqconn_diagnostic`: Verified `MQCONN` triggers `NATIVE_TRANSLATION_BLOCKED`.
- `test_ibm_mq_mqput_mqget_diagnostics`: Verified `MQPUT`, `MQGET`, `MQDISC` trigger `NATIVE_TRANSLATION_BLOCKED`.
- `test_capability_matrix_ims_mq_unproven_and_unsupported`: Verified capability matrix invariants.

---

## 5. Final Phase 11 Classification Verdict

```
================================================================================
                   PHASE 11 FINAL CLASSIFICATION VERDICT
================================================================================

Overall Phase 11 Verdict: PARTIAL

Breakdown:
  1. IMS / DL/I Database Calls (CBLTDLI):             UNSUPPORTED (Fail-Closed)
  2. IMS TM Transaction Management:                  UNSUPPORTED (Fail-Closed)
  3. IBM MQ Messaging Calls (MQCONN, MQPUT, MQGET):  UNSUPPORTED (Fail-Closed)
  4. Real IBM z/OS IMS Subsystems:                   UNPROVEN
  5. Real IBM MQ Queue Manager Infrastructure:       UNPROVEN
  6. EBCDIC Mainframe Collating Sequences:           UNSUPPORTED
  7. Fail-Closed Diagnostic Enforcement:             UNIT_PROVEN / E2E_PROVEN

Justification:
  The platform strictly enforces fail-closed diagnostics for all IMS and MQ
  mainframe integration calls, preventing unverified or broken code generation.
  Because real IBM IMS and real IBM MQ infrastructure were not executed, the
  accurate and honest verdict remains PARTIAL.
================================================================================
```
