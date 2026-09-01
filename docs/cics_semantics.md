# CICS Online Transaction Modernization Semantics

## 1. Scope & Execution Boundary

Mainframe CICS (Customer Information Control System) provides multi-user online transaction processing. In this modernization architecture:

1. **Real IBM z/OS CICS Middleware**: Explicitly classified as **`UNPROVEN`** because real z/OS CICS regions with 3270 hardware are not present in local test environments.
2. **Native Java / Spring Transaction Compatibility Layer**: Implemented via `CicsTransactionContext` (ThreadLocal) and `CicsProgramRegistry` to provide semantic equivalence for modernized Spring microservices and web applications.

---

## 2. Supported CICS Command Subset

### `EXEC CICS LINK`
- **Syntax**: `EXEC CICS LINK PROGRAM(name) [COMMAREA(var)] [LENGTH(len)] [CHANNEL(chan)] [RESP(rc)] [RESP2(rc2)] END-EXEC`
- **Semantics**: Calls the target program synchronously.
- **Data Passing**:
  - `COMMAREA`: Bidirectional in/out parameter. Mutated state is reflected back to the caller.
  - `CHANNEL`: Passes named container groups to the target program.
- **Error Behavior**: If the target program cannot be resolved, sets `EIBRESP = 27 (DFHRESP(PGMIDERR))` and logs a diagnostic without crashing the JVM.

### `EXEC CICS XCTL`
- **Syntax**: `EXEC CICS XCTL PROGRAM(name) [COMMAREA(var)] [LENGTH(len)] [CHANNEL(chan)] [RESP(rc)] [RESP2(rc2)] END-EXEC`
- **Semantics**: Transfers control to the target program and terminates the caller's execution slice (`programExited = true; return;`).

### `EXEC CICS RETURN`
- **Syntax**: `EXEC CICS RETURN [TRANSID(id)] [COMMAREA(var)] [IMMEDIATE] END-EXEC`
- **Semantics**: Terminates current program execution. Supports pseudo-conversational state transitions by registering next `TRANSID` and `COMMAREA` in `CicsTransactionContext`.

### `EXEC CICS GET / PUT / DELETE CONTAINER`
- **Syntax**:
  - `EXEC CICS PUT CONTAINER(name) CHANNEL(chan) FROM(var) [RESP(rc)] END-EXEC`
  - `EXEC CICS GET CONTAINER(name) CHANNEL(chan) INTO(var) [RESP(rc)] END-EXEC`
  - `EXEC CICS DELETE CONTAINER(name) CHANNEL(chan) [RESP(rc)] END-EXEC`
- **Semantics**: Storage and retrieval of named byte/string payloads in channels. Container errors set `DFHRESP(CONTAINERERR)` or `DFHRESP(CHANNELERR)`.

### `EXEC CICS SEND / RECEIVE MAP`
- **Syntax**:
  - `EXEC CICS SEND MAP(m) MAPSET(ms) FROM(var) [DATAONLY] [MAPONLY] [ERASE] [FREEKB] [ALARM] [RESP(rc)] END-EXEC`
  - `EXEC CICS RECEIVE MAP(m) MAPSET(ms) INTO(var) [RESP(rc)] END-EXEC`
- **Semantics**: Screen I/O mapped to typed Java Screen DTOs and session context.

### `EXEC CICS ABEND`
- **Syntax**: `EXEC CICS ABEND [ABCODE(code)] [CANCEL] [NODUMP] END-EXEC`
- **Semantics**: Marks transaction as abended (`hasAbended() == true`), sets `EIBRESP = 999`, and throws `CicsAbendException`.

### `EXEC CICS ASKTIME / FORMATTIME`
- **Syntax**:
  - `EXEC CICS ASKTIME ABSTIME(var) END-EXEC`
  - `EXEC CICS FORMATTIME ABSTIME(var) [YYYYMMDD(d)] [TIME(t)] END-EXEC`
- **Semantics**: Modernized to Java 8+ `java.time.LocalDateTime` and epoch milliseconds.

---

## 3. Fail-Closed Unsupported Command Diagnostics

Commands outside the supported online transaction subset (e.g. `EXEC CICS READ`, `WRITE`, `START`, `SYNCPOINT`) immediately emit parser diagnostics with:
`CICS_UNSUPPORTED_COMMAND: EXEC CICS <COMMAND> is unsupported in Track-B native Java`
