# SystemaOps Enterprise Application Modernization Platform
## FINAL INSTALLATION & ENVIRONMENT VALIDATION
**Author**: Antigravity  
**Status**: VERIFIED  
**Date**: 2026-08-22  

---

### 1. Platform Prerequisites & Requirements

#### A. REQUIRED (Core Engine & Server)
* **Python**: 3.10 or newer (Tested under Python 3.14.3).
* **GnuCOBOL (`cobc`)**: 3.1 or newer. Must be added to `PATH` (Used for compiling and executing COBOL baseline verification).
* **Java Development Kit (JDK)**: 17 or newer. `JAVA_HOME` must be set.
* **Apache Maven (`mvn`)**: 3.8 or newer. Must be added to `PATH` (Used to compile and package generated Spring Boot Java output).
* **Port Availability**: Port `8787` (HTTP Server) and a random available port for SSE connections.
* **Filesystem Permissions**: Write permissions in workspace directory to extract repositories and compile code.

#### B. DEMO-ONLY (E2E Automated Testing)
* **Playwright Chromium**: Playwright browser binary requirements (installed via `playwright install chromium`). Only needed to run browser E2E test scripts.

---

### 2. Clean Installation Verification Steps

To perform a clean installation check on a target machine, run the following commands sequentially:

```bash
# 1. Clone/extract the release package to a clean folder
cd clean-release-directory

# 2. Set up virtual environment
python -m venv venv

# 3. Activate virtual environment
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# 4. Install python dependencies
pip install -r requirements.txt

# 5. Install Playwright browser binaries (Demo-Only)
playwright install chromium

# 6. Verify environment binaries are in PATH
cobc --version
java -version
mvn -version

# 7. Start the SystemaOps Web Portal
python ui.py
```

After startup, open the web browser and verify:
* URL: `http://127.0.0.1:8787`
* Landing Page: Displays "Select Modernization Input Source" with no console errors or tracebacks.
