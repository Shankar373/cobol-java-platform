# 02. P1 libcobj.jar Dependency Diagnostic Report

This report documents the verification and diagnostics of the `libcobj.jar` classpath dependency.

---

## 1. Import Registries in Generated Java

Every transpiled Java file under `target/generated/` imports the following namespaces:
```java
import jp.osscons.opensourcecobol.libcobj.*;
import jp.osscons.opensourcecobol.libcobj.common.*;
import jp.osscons.opensourcecobol.libcobj.data.*;
import jp.osscons.opensourcecobol.libcobj.exceptions.*;
import jp.osscons.opensourcecobol.libcobj.termio.*;
import jp.osscons.opensourcecobol.libcobj.call.*;
import jp.osscons.opensourcecobol.libcobj.file.*;
import jp.osscons.opensourcecobol.libcobj.ui.*;
import jp.osscons.opensourcecobol.libcobj.sql.*;
```

---

## 2. Compilation and Execution Verifications

- **Compilation without jar**: If `libcobj.jar` is missing, `javac` fails immediately with compile errors on all imported classes.
- **Execution without jar**: The compiled class files cannot run (throws `NoClassDefFoundError: jp.osscons.opensourcecobol.libcobj.CobolRunnable`).
- **Direct vs Transitive**: The dependency is **direct**. Generated Java classes inherit from `CobolRunnable` and utilize `CobolDecimal` and `CobolModule` wrappers natively.
- **Emulation logic**: Variable values and binary structures (like COMP-3 packed decimal storage) are emulated via OpenSource COBOL runtime classes rather than translated to native Java variables (`BigDecimal` / `int`).
