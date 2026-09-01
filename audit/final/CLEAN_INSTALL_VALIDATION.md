# SystemaOps Enterprise Application Modernization Platform
## CLEAN INSTALL VALIDATION MANUAL
**Author**: Antigravity  
**Status**: VERIFIED & REPRODUCIBLE  
**Date**: 2026-08-22  

---

### 1. Prerequisite Environment Check
Before extracting and initializing SystemaOps, verify that the clean target machine satisfies these bounds:

| Dependency | Required Role | Recommended Version Bounds |
|---|---|---|
| **Python** | Platform runtime | `Python 3.10` to `Python 3.14` |
| **GnuCOBOL (cobc)** | Legacy compilation baseline | `GnuCOBOL 3.1` or later |
| **Java JDK** | Modernized compilation target | `OpenJDK 17` or `OpenJDK 21` |
| **Maven (mvn)** | Java dependency orchestration | `Maven 3.8.x` or later |
| **Docker Engine** | Toolchain container runtime | `Docker Desktop 4.x` or later |

Verify standard CLI access:
```bash
python --version
cobc --version
java -version
mvn -version
docker --version
```

---

### 2. Sandbox Setup and Extraction Steps

1. Create a clean isolated workspace folder:
   ```bash
   mkdir C:\SystemaOpsRelease
   cd C:\SystemaOpsRelease
   ```
2. Extract the clean distribution package:
   ```bash
   tar -xf systemaops-release.zip -C C:\SystemaOpsRelease
   ```
3. Initialize the Python virtual environment:
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```
4. Install package requirements:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

---

### 3. Server Startup and Dashboard Authentication
Start the server:
```bash
python ui.py
```
* Confirm that ThreadingHTTPServer binds cleanly on port `8787` (`http://localhost:8787`).
* Confirm that fresh access displays an empty runs list without any stale metadata or workspace leaks.
