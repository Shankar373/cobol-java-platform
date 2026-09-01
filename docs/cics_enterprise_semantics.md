# CICS Enterprise Semantics Specification
## Online Transaction Processing & Semantic Compatibility Architecture

---

## 1. Scope & Execution Principles

This document specifies the semantic translation of IBM CICS constructs from Enterprise COBOL into native Java 17 and Spring Boot 3 components.

### Core Principles
1. **Thread Isolation**: Each online transaction runs in a discrete thread with its own `TransactionState` stored in `CicsTransactionContext` (`ThreadLocal<TransactionState>`).
2. **Deterministic Control Flow**:
   - `EXEC CICS LINK` ➔ `CicsProgramRegistry.invoke(program, commarea, channel)` with caller/callee reflection.
   - `EXEC CICS XCTL` ➔ `CicsProgramRegistry.invoke(...)` followed by `programExited = true; return;`.
   - `EXEC CICS RETURN` ➔ `CicsTransactionContext.cicsReturn(transId, commarea); return;`.
3. **No Silent Swallowing**: Unregistered target programs raise `CICS_PGMIDERR` (numeric code 27), setting `EIBRESP = 27` and `RESP(var) = 27`.

---

## 2. Program Control Semantics

### 2.1 Static & Dynamic LINK
- **COBOL**: `EXEC CICS LINK PROGRAM('SUBPGM') COMMAREA(WS-COM) LENGTH(10) RESP(WS-RC) END-EXEC.`
- **Java Generation**:
  ```java
  try {
      Object resComm = com.systema.modernized.CicsProgramRegistry.invoke("SUBPGM", ws_com, null);
      if (resComm != null) {
          ws_com = resComm.toString();
      }
      com.systema.modernized.CicsTransactionContext.setEibresp(com.systema.modernized.CicsTransactionContext.DFHRESP_NORMAL);
  } catch (Exception e) {
      System.err.println("[CICS-LINK-ERROR] " + e.getMessage());
      com.systema.modernized.CicsTransactionContext.setEibresp(com.systema.modernized.CicsTransactionContext.DFHRESP_PGMIDERR);
  }
  ws_rc = com.systema.modernized.CicsTransactionContext.getEibresp();
  ```

### 2.2 Control Transfer (XCTL)
- **COBOL**: `EXEC CICS XCTL PROGRAM('NEXTPGM') COMMAREA(WS-COM) END-EXEC.`
- **Java Generation**:
  ```java
  try {
      com.systema.modernized.CicsProgramRegistry.invoke("NEXTPGM", ws_com, null);
      com.systema.modernized.CicsTransactionContext.setEibresp(com.systema.modernized.CicsTransactionContext.DFHRESP_NORMAL);
  } catch (Exception e) {
      com.systema.modernized.CicsTransactionContext.setEibresp(com.systema.modernized.CicsTransactionContext.DFHRESP_PGMIDERR);
  }
  programExited = true;
  return;
  ```

---

## 3. Channels & Containers Semantics

- **`PUT CONTAINER`**:
  `CicsTransactionContext.putStringContainer(channelName, containerName, payload)`
- **`GET CONTAINER`**:
  `String val = CicsTransactionContext.getStringContainer(channelName, containerName)`
- **`DELETE CONTAINER`**:
  `CicsTransactionContext.deleteContainer(channelName, containerName)`
- **Error Handling**: Missing container sets `DFHRESP_CONTAINERERR` (123); missing channel sets `DFHRESP_CHANNELERR` (122).
