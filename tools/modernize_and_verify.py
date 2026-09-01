#!/usr/bin/env python3
"""COBOL 4J modernization test harness for the ClaimsCore sample.

Pipeline (all inside Docker):
  1. transpile  cobj -free  (COBOL -> Java) using opensourcecobol4j:2.0.0
  2. run        java CCMAIN01  (the transpiled ClaimsCore batch)
  3. verify     audit / exceptions / report against the 7 documented outcomes

Exit code 0 == all business outcomes verified.
"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
LEGACY = os.path.join(ROOT, "legacy")
IMAGE = "opensourcecobol/opensourcecobol4j:2.0.0"
COBJ = "cobj"
JAVA_CP = "generated:/usr/lib/opensourcecobol4j/libcobj.jar"

# ---------------------------------------------------------------------------
# Business rules extracted from CCPROC01 (ClaimsCore COBOL)
# ---------------------------------------------------------------------------
# Expected per-claim outcome from data/in/claims.dat (EXPECTED_BEHAVIOR.md):
#  1 CLM000000001 MV PL00000001  120000.00 -> APPROVED        95000.00
#  2 CLM000000002 HE PL00000002   45000.00 -> APPROVED        35000.00
#  3 CLM000000003 MV PL00000001  320000.00 -> MANUAL_REVIEW   295000.00
#  4 CLM000000004 PR PL00000003   60000.00 -> REJECTED P002   POLICY INACTIVE OR EXPIRED
#  5 CLM000000005 MV PL99999999   25000.00 -> REJECTED P001   POLICY NOT FOUND
#  6 CLM000000006 MV PL00000002   50000.00 -> REJECTED P003   CLAIM TYPE NOT COVERED BY POLICY
#  7 CLM000000007 HE PL00000002  350000.00 -> MANUAL_REVIEW   300000.00

EXPECTED_AUDIT = [
    {"id": "CLM000000001", "policy": "PL00000001", "status": "APPROVED",      "amount": 95000.00},
    {"id": "CLM000000002", "policy": "PL00000002", "status": "APPROVED",      "amount": 35000.00},
    {"id": "CLM000000003", "policy": "PL00000001", "status": "MANUAL_REVIEW", "amount": 295000.00},
    {"id": "CLM000000007", "policy": "PL00000002", "status": "MANUAL_REVIEW", "amount": 300000.00},
]

EXPECTED_EXCEPTIONS = [
    {"id": "CLM000000004", "policy": "PL00000003", "code": "P002", "text": "POLICY INACTIVE OR EXPIRED"},
    {"id": "CLM000000005", "policy": "PL99999999", "code": "P001", "text": "POLICY NOT FOUND"},
    {"id": "CLM000000006", "policy": "PL00000002", "code": "P003", "text": "CLAIM TYPE NOT COVERED BY POLICY"},
]

EXPECTED_REPORT = {"audit": 4, "exceptions": 3, "reviews": 2}

OUT_AUDIT = os.path.join(LEGACY, "data", "out", "claim-audit.dat")
OUT_EXCEPT = os.path.join(LEGACY, "data", "out", "claim-exceptions.dat")
OUT_REPORT = os.path.join(LEGACY, "data", "out", "eod-claims-report.txt")


# ---------------------------------------------------------------------------
def docker_run(cmd, workdir=None):
    full = ["docker", "run", "--rm", "-v", f"{LEGACY}:/legacy", IMAGE, "bash", "-c", cmd]
    proc = subprocess.run(full, capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def transpile():
    """COBOL -> Java via cobj inside the container."""
    cmd = (
        "cd /legacy && rm -rf generated && mkdir -p generated && "
        "cobj -free -o generated -j generated "
        "src/CCMAIN01.cob src/CCLOAD01.cob src/CCPROC01.cob src/CCREPT01.cob src/CCLEGACYX.cob"
    )
    rc, out, err = docker_run(cmd)
    if rc != 0:
        print("FAIL: cobj transpilation failed")
        print(err)
        sys.exit(1)
    return out


def run_batch():
    """Execute the transpiled batch (entry point CCMAIN01)."""
    for f in ("data/work/policy.dat", "data/work/customer.dat",
              "data/out/claim-audit.dat", "data/out/claim-exceptions.dat",
              "data/out/eod-claims-report.txt"):
        p = os.path.join(LEGACY, f)
        if os.path.exists(p):
            os.remove(p)
    cmd = f"cd /legacy && java -cp '{JAVA_CP}' CCMAIN01"
    rc, out, err = docker_run(cmd)
    if rc != 0:
        print("FAIL: batch execution failed")
        print(out)
        print(err)
        sys.exit(1)
    return out


def decode_comp3(data):
    """Decode COBOL COMP-3 (S9(11)V99, 7 bytes, big-endian, sign in last nibble)."""
    if len(data) != 7:
        raise ValueError(f"expected 7 COMP-3 bytes, got {len(data)}")
    digits = []
    for i, b in enumerate(data):
        hi, lo = b >> 4, b & 0x0F
        if i == 6:  # last byte carries the sign in its low nibble
            digits.append(hi)
            sign = lo
        else:
            digits.append(hi)
            digits.append(lo)
    num = int("".join(str(d) for d in digits)) / 100.0
    if sign in (0x0B, 0x0D):  # negative
        num = -num
    return num


def read_audit():
    """Parse the audit file. Each record: id|policy|STATUS|<comp3 amount>|desc"""
    with open(OUT_AUDIT, "rb") as fh:
        data = fh.read()
    records = []
    for raw in data.split(b"\n"):
        if not raw:
            continue
        parts = raw.split(b"|")
        if len(parts) < 5:
            raise ValueError(f"unexpected audit record format (got {len(parts)} fields, need 5): {raw!r}")
        records.append({
            "id": parts[0].decode("ascii").strip(),
            "policy": parts[1].decode("ascii").strip(),
            "status": parts[2].decode("ascii").strip(),
            "amount": decode_comp3(parts[3]),
        })
    return records


def read_exceptions():
    records = []
    with open(OUT_EXCEPT, "rb") as fh:
        for raw in fh:
            line = raw.rstrip(b"\r\n")
            if not line:
                continue
            parts = line.split(b"|")
            records.append({
                "id": parts[0].decode("ascii").strip(),
                "policy": parts[1].decode("ascii").strip(),
                "code": parts[2].decode("ascii").strip(),
                "text": parts[3].decode("ascii").strip(),
            })
    return records


def read_report():
    with open(OUT_REPORT, "rb") as fh:
        lines = [l.decode("ascii", "replace").strip() for l in fh.read().split(b"\n") if l.strip()]
    def count(key):
        for line in lines:
            if line.startswith(key):
                return int(line.split(":")[1].strip()[:7])
        return None
    return {
        "audit": count("AUDIT RECORDS"),
        "exceptions": count("EXCEPTIONS"),
        "reviews": count("MANUAL REVIEWS"),
    }


def check(name, actual, expected):
    ok = actual == expected
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        print(f"        expected: {expected}")
        print(f"        actual:   {actual}")
    return ok


def verify():
    audit = read_audit()
    exceptions = read_exceptions()
    report = read_report()

    ok = True
    ok &= check("audit records", audit, EXPECTED_AUDIT)
    ok &= check("exception records", exceptions, EXPECTED_EXCEPTIONS)
    ok &= check("report counts", report, EXPECTED_REPORT)
    return ok


def main():
    print("== [1/3] transpile COBOL -> Java (COBOL 4J / cobj) ==")
    transpile()
    print("  transpile OK")

    print("== [2/3] run transpiled batch (CCMAIN01) ==")
    out = run_batch()
    for line in out.splitlines():
        if "CLAIMS PROCESSED" in line:
            print(f"  {line.strip()}")
    if "CLAIMS PROCESSED: 0000007" not in out:
        print("FAIL: expected 'CLAIMS PROCESSED: 0000007'")
        sys.exit(1)

    print("== [3/3] verify business outcomes ==")
    if not verify():
        print("\nRESULT: FAIL")
        sys.exit(1)

    print("\nRESULT: ALL CHECKS PASSED (7/7 claims, report counts, COMP-3 amounts)")
    sys.exit(0)


if __name__ == "__main__":
    main()
