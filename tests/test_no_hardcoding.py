import os
import re

BENCHMARK_NAMES = [
    r"\bBANKMAIN\b",
    r"\bBCMAIN\b",
    r"\bCCMAIN\b",
    r"\bCCPROC01\b",
    r"\bCCREPT01\b",
    r"\bCCLOAD01\b",
    r"\bEodReportService\b",
    r"\bClaimException\b",
    r"\bClaimAudit\b",
    r"\bLegacyFeatureService\b",
    r"\bprocessClaimsJob\b",
    r"\bprocessTransactionsJob\b",
    r"\bPolicyRepository\b",
    r"\bTransactionRepository\b",
    r"\bCustomerRepository\b",
    r"\bAccountRepository\b",
    r"\bClaimRepository\b",
    r"\bClaimsCore\b",
    r"\bBankCore\b",
    r"\bClaim_Exception\b",
    r"\bLegacyFeature_Service\b",
    r"\bEodReport_Service\b",
    r"\bClaim_Audit\b",
]

def test_production_no_benchmark_hardcoding():
    # Production source files list to scan
    production_files = ["cobol_migrate.py"]
    for root, dirs, files in os.walk("modernize"):
        for f in files:
            if f.endswith(".py"):
                production_files.append(os.path.join(root, f))

    violations = []
    for path in production_files:
        if not os.path.isfile(path):
            continue
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
        
        for i, line in enumerate(lines):
            for pattern in BENCHMARK_NAMES:
                if re.search(pattern, line, re.IGNORECASE):
                    # Exclude orchestrator-only report/orchestration patterns in cobol_migrate.py
                    if path == "cobol_migrate.py" and any(p in pattern for p in ("ClaimsCore", "BankCore", "Claim_", "LegacyFeature", "EodReport")):
                        continue
                    trimmed = line.strip()
                    # Skip comment lines and docstrings
                    if trimmed.startswith("#") or trimmed.startswith('"""') or trimmed.startswith("'''"):
                        continue
                    if "#" in trimmed:
                        # If comment is trailing, check the code part
                        parts = trimmed.split("#", 1)
                        if not parts[0].strip():
                            continue
                        trimmed = parts[0].strip()
                    if "self.log(" in trimmed or "logger." in trimmed or "print(" in trimmed:
                        continue
                    
                    violations.append(f"{path}:{i+1}: {line.strip()}")

    # Report violations if any
    if violations:
        print("\nViolations found in active validation/modernization logic:")
        for v in violations:
            print(f"  - {v}")
    assert not violations, f"Benchmark-specific logic hardcoded in execution verification/modernization code: {violations}"
