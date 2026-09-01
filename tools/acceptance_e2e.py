"""Full-stack acceptance test driver (frontend + backend + pipeline E2E).

Drives the REAL documented startup path (python ui.py -> http://127.0.0.1:8787)
over pure HTTP exactly as the SPA does, for three repositories:
  A) claimscore-fixtures : the normal benchmark fixture (with repo-local config)
  B) payroll01-unseen    : genuinely different synthetic COBOL application
  C) broken01-negative   : intentional syntax failure -> must show FAILED/error

Also: independent javac compile+run of generated native Java, SSE log-stream
probe, optional Playwright dashboard click-through, continuous log capture,
clean shutdown. Writes structured results to acceptance_logs/results.json.
"""
import base64
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import zipfile

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS = os.path.join(ROOT, "acceptance_logs")
os.makedirs(LOGS, exist_ok=True)

SERVER = None
BASE = "http://127.0.0.1:8787"
RESULTS = {"checks": [], "runs": {}, "log_scan": {}, "ui": {}}


def check(name, ok, detail=""):
    RESULTS["checks"].append({"name": name, "ok": bool(ok), "detail": str(detail)[:500]})
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" :: {detail}"[:300] if detail else ""))
    return ok


# ---------------------------------------------------------------- fixtures --

def build_legacy_zip():
    buf = io.BytesIO()
    cfg = json.load(open(os.path.join(ROOT, "migration_config.json"), encoding="utf-8"))
    cfg.pop("repo", None)
    cfg.pop("out", None)
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("migration_config.json", json.dumps(cfg, indent=2))
        for rel in ("src/CCMAIN01.cob", "src/CCLOAD01.cob", "src/CCPROC01.cob",
                    "src/CCREPT01.cob", "src/CCLEGACYX.cob"):
            p = os.path.join(ROOT, "legacy", rel.replace("/", os.sep))
            z.write(p, rel)
        cb = os.path.join(ROOT, "legacy", "copybooks")
        for f in os.listdir(cb):
            z.write(os.path.join(cb, f), f"copybooks/{f}")
        zin = os.path.join(ROOT, "legacy", "data", "in", "claims.dat")
        z.write(zin, "data/in/claims.dat")
    return buf.getvalue()


UNSEEN_COB = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. PAYROLL01.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT EMP-IN ASSIGN TO "data/in/employees.dat"
               ORGANIZATION IS LINE SEQUENTIAL.
           SELECT PAY-OUT ASSIGN TO "data/out/payslips.dat"
               ORGANIZATION IS LINE SEQUENTIAL.
       DATA DIVISION.
       FILE SECTION.
       FD  EMP-IN.
       COPY EMPLREC.
       FD  PAY-OUT.
       01  PAY-REC.
           05  PY-ID      PIC X(5).
           05  PY-GROSS   PIC 9(6)V99.
           05  PY-TAX     PIC 9(5)V99.
           05  PY-NET     PIC 9(6)V99.
       WORKING-STORAGE SECTION.
       01  WS-EOF        PIC X VALUE 'N'.
       01  WS-TAX-RATE   PIC V99 VALUE 0.20.
       PROCEDURE DIVISION.
       MAIN-PARA.
           OPEN INPUT EMP-IN OUTPUT PAY-OUT.
           PERFORM UNTIL WS-EOF = 'Y'
               READ EMP-IN
                   AT END MOVE 'Y' TO WS-EOF
                   NOT AT END PERFORM PROCESS-EMP
               END-READ
           END-PERFORM.
           CLOSE EMP-IN PAY-OUT.
           DISPLAY "PAYROLL COMPLETE".
           STOP RUN.
       PROCESS-EMP.
           COMPUTE PY-GROSS = EP-SALARY * 12
           COMPUTE PY-TAX = PY-GROSS * WS-TAX-RATE
           COMPUTE PY-NET = PY-GROSS - PY-TAX
           MOVE EP-ID TO PY-ID
           WRITE PAY-REC.
"""

UNSEEN_CPY = """       01  EMP-REC.
           05  EP-ID      PIC X(5).
           05  EP-NAME    PIC X(20).
           05  EP-SALARY  PIC 9(6)V99.
"""

BROKEN_COB = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. BROKEN01.
       PROCEDURE DIVISION.
       MAIN-PARA.
           THIS IS NOT VALID COBOL AT ALL $$$
           DISPLAY "UNREACHABLE".
           STOP RUN.
"""


def build_unseen_zip():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("src/PAYROLL01.cob", UNSEEN_COB)
        z.writestr("copybooks/EMPLREC.cpy", UNSEEN_CPY)
        rows = "".join(f"E{i:03d}EMPLOYEE{i:<10}{10000+i*777:011d}\n" for i in range(1, 4))
        z.writestr("data/in/employees.dat", rows)
    return buf.getvalue()


def build_broken_zip():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("src/BROKEN01.cob", BROKEN_COB)
    return buf.getvalue()


# ---------------------------------------------------------------- server ----

def wait_port(timeout=30):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            s = socket.create_connection(("127.0.0.1", 8787), timeout=1)
            s.close()
            return True
        except OSError:
            time.sleep(0.4)
    return False


def start_server():
    global SERVER
    out = open(os.path.join(LOGS, "server.out.log"), "wb")
    err = open(os.path.join(LOGS, "server.err.log"), "wb")
    SERVER = subprocess.Popen(
        [sys.executable, "ui.py", "--host", "127.0.0.1", "--port", "8787"],
        cwd=ROOT, stdout=out, stderr=err, stdin=subprocess.DEVNULL)
    return wait_port(30)


def stop_server():
    if SERVER and SERVER.poll() is None:
        SERVER.terminate()
        try:
            SERVER.wait(timeout=10)
            return "terminated"
        except subprocess.TimeoutExpired:
            SERVER.kill()
            return "killed"
    return "already-exited"


# ---------------------------------------------------------------- driving ---

def ingest(name, data):
    r = requests.post(f"{BASE}/api/ingest", json={
        "source": "zip", "name": name,
        "data": base64.b64encode(data).decode("ascii")}, timeout=60)
    j = r.json()
    return (r.status_code == 200 and j.get("ok")), j.get("run_id") or j.get("error")


def start_run(run_id):
    r = requests.post(f"{BASE}/api/run", json={"run_id": run_id, "restart_from": 0},
                      timeout=30)
    return r.json()


def poll_run(run_id, timeout_s=1200):
    """Mirror the SPA poll loop; returns final run dict."""
    t0 = time.time()
    last_line = ""
    while time.time() - t0 < timeout_s:
        st = requests.get(f"{BASE}/api/state", timeout=30).json()
        run = next((r for r in st["runs"] if r["run_id"] == run_id), None)
        if run is None:
            time.sleep(2)
            continue
        done_stages = sum(1 for s in run["stages"] if s["status"] == "done")
        line = f"{run['status']:>11} | stages {done_stages:>2}/13 | verdict={run.get('verdict')}"
        if line != last_line:
            print(f"    {time.strftime('%H:%M:%S')} {line}")
            last_line = line
        if run["status"] in ("done", "error", "interrupted"):
            return run
        time.sleep(3)
    raise TimeoutError(f"run {run_id} did not finish in {timeout_s}s")


def sse_probe(run_id):
    """Confirm the log stream endpoint actually streams events."""
    got = 0
    try:
        with requests.get(f"{BASE}/api/log-stream", params={"run_id": run_id},
                          stream=True, timeout=(5, 6)) as resp:
            for raw in resp.iter_lines(decode_unicode=True):
                if raw and raw.startswith("data:"):
                    got += 1
                if got >= 3:
                    break
    except requests.RequestException:
        pass
    return got


def extract_package(run_id, dest):
    r = requests.get(f"{BASE}/package", params={"run_id": run_id}, timeout=120)
    if r.status_code != 200 or len(r.content) < 1000:
        return False, f"http {r.status_code} bytes {len(r.content)}"
    with open(dest, "wb") as fh:
        fh.write(r.content)
    with zipfile.ZipFile(dest) as z:
        names = z.namelist()
    return True, f"{len(r.content)} bytes, {len(names)} entries"


def independent_native_compile_run(pkg_zip, entry_class, tag):
    """Extract package, compile native_gen tree standalone (NO jars), run it."""
    ext = os.path.join(LOGS, f"pkg_{tag}")
    shutil.rmtree(ext, ignore_errors=True)
    with zipfile.ZipFile(pkg_zip) as z:
        z.extractall(ext)
    java_root = os.path.join(ext, "modernized", "src", "main", "java")
    if not os.path.isdir(java_root):
        return {"compile": False, "run": "NOT_VERIFIED", "why": "no modernized/src/main/java in package"}

    sources = []
    ng = os.path.join(java_root, "com", "systema", "modernized", "native_gen")
    if not os.path.isdir(ng):
        return {"compile": False, "run": "NOT_VERIFIED", "why": "no native_gen dir"}
    for root, _, files in os.walk(java_root):
        for f in files:
            rel = os.path.relpath(os.path.join(root, f), java_root).replace(os.sep, "/")
            # compile only the dependency-free subtree + plain helpers
            if ("/native_gen/" in "/" + rel) or rel.endswith(
                    ("/JclExecutionContext.java", "/CobolFormatHelper.java")):
                sources.append(os.path.join(root, f))
    out_classes = os.path.join(ext, "_classes")
    os.makedirs(out_classes, exist_ok=True)
    c = subprocess.run(["javac", "-d", out_classes] + sources,
                       capture_output=True, text=True, timeout=300)
    res = {"compile": c.returncode == 0}
    if c.returncode != 0:
        res["compile_err"] = c.stderr[-800:]
        res["run"] = "NOT_VERIFIED"
        return res
    forbidden = []
    for s in sources:
        t = open(s, encoding="utf-8").read()
        for bad in ("io.proleap", "org.antlr", "com.fasterxml.jackson",
                    "libcobj", "jp.osscons", "org.springframework"):
            if bad in t:
                forbidden.append((os.path.basename(s), bad))
    res["forbidden_deps"] = forbidden
    # Deployed layout: data/ lives under modernized/, matching how the
    # pipeline itself runs the packaged application during Gate 2.
    deploy_cwd = os.path.join(ext, "modernized")
    r = subprocess.run(["java", "-cp", out_classes,
                        f"com.systema.modernized.native_gen.{entry_class}"],
                       capture_output=True, text=True, timeout=180, cwd=deploy_cwd)
    res["run_rc"] = r.returncode
    res["run_stdout_tail"] = r.stdout.strip().splitlines()[-6:]
    if r.returncode != 0:
        res["run_stderr_tail"] = r.stderr.strip().splitlines()[-4:]
    res["run"] = r.returncode == 0
    return res


def _classify_err_log(text):
    """Split into traceback chunks; a chunk is EXPECTED noise iff its terminal
    exception is a client-socket reset caused by our own SSE probe aborts."""
    import re as _re
    chunks = ("Traceback" + x for x in text.split("Traceback")[1:])
    expected, unexpected = [], []
    for ch in chunks:
        m = _re.findall(r"^([\w\.]+(?:Error|Exception))(?::|$)", ch, _re.M)
        term = m[-1] if m else "?"
        if term in ("ConnectionResetError", "ConnectionAbortedError",
                    "BrokenPipeError"):
            expected.append(term)
        else:
            unexpected.append(term or ch[:200])
    return expected, unexpected


def scan_logs():
    pats = ["Traceback", "ERROR:", "CRITICAL", "Address already in use",
            "Permission denied", "Exception in thread"]
    out = {}
    for fname in ("server.out.log", "server.err.log"):
        p = os.path.join(LOGS, fname)
        if not os.path.exists(p):
            continue
        text = open(p, encoding="utf-8", errors="replace").read()
        hits = {}
        for pat in pats:
            n = text.count(pat)
            if n:
                idx = text.find(pat)
                hits[pat] = {"count": n, "sample": text[max(0, idx-80):idx+200]}
        entry = {"bytes": len(text), "hits": hits}
        if fname == "server.err.log":
            exp, unexp = _classify_err_log(text)
            entry["sse_probe_disconnects"] = len(exp)
            entry["unexpected_exceptions"] = unexp
        out[fname] = entry
    return out


def playwright_check(expect_texts):
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        RESULTS["ui"]["clickthrough"] = f"NOT_VERIFIED: playwright import failed: {e}"
        return
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(headless=True)
            page = b.new_page(viewport={"width": 1600, "height": 1000})
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(BASE, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_selector(".run-item", timeout=20000)
            body = page.inner_text("body")
            missing = [t for t in expect_texts if t not in body]
            page.screenshot(path=os.path.join(LOGS, "ui_dashboard.png"), full_page=True)
            b.close()
            RESULTS["ui"]["clickthrough"] = {
                "loaded": True, "missing_expected_text": missing,
                "js_page_errors": errors,
                "screenshot": "acceptance_logs/ui_dashboard.png"}
    except Exception as e:
        RESULTS["ui"]["clickthrough"] = f"NOT_VERIFIED: {type(e).__name__}: {e}"


# ---------------------------------------------------------------- main ------

def run_one(name, zip_bytes, expect_ok, entry_class=None, do_package=True,
            allowed_failure=None):
    """allowed_failure=(stage_label, detail_substring): the pipeline is
    expected to reach that stage and fail honestly there (no false PASS)."""
    print(f"\n=== RUN {name} ===")
    rec = {}
    ok, rid_or_err = ingest(name, zip_bytes)
    if not check(f"{name}: ingest", ok, rid_or_err):
        rec["ingest"] = rid_or_err
        RESULTS["runs"][name] = rec
        return rec
    rid = rid_or_err
    rec["run_id"] = rid

    jr = start_run(rid)
    check(f"{name}: run accepted", jr.get("ok") is True, jr.get("error"))

    final = poll_run(rid)
    rec["final_status"] = final["status"]
    rec["verdict"] = final.get("verdict")
    rec["stages"] = {s["label"]: {"status": s["status"], "detail": (s.get("detail") or "")[:220],
                                  "errors": s.get("errors", [])}
                     for s in final["stages"]}
    for s in final["stages"]:
        if s["errors"]:
            print(f"    stage[{s['label']}] ERRORS: {s['errors'][:2]}")

    if allowed_failure:
        lbl, substr = allowed_failure
        stage = rec["stages"].get(lbl, {})
        honest = (
            final["status"] == "error"
            and stage.get("status") in ("failed", "error")
            and substr in stage.get("detail", "")
            and final.get("verdict") not in ("PRODUCTION_READY", "PRODUCTION_CANDIDATE",
                                             "VERIFIED", "NATIVE_JAVA_VERIFIED",
                                             "NATIVE_SPRING_UNIFIED", "VERIFIED_WITH_LIMITATIONS")
        )
        check(f"{name}: honest failure at '{lbl}' ({final.get('verdict')})", honest,
              stage.get("detail", "")[:200])
    elif expect_ok:
        check(f"{name}: backend status done", final["status"] == "done", final["status"])
        tier_ok = final.get("verdict") in (
            "VERIFIED", "VERIFIED_WITH_LIMITATIONS", "NATIVE_JAVA_VERIFIED",
            "NATIVE_SPRING_UNIFIED", "PRODUCTION_CANDIDATE", "PRODUCTION_READY")
        check(f"{name}: verdict is pass-tier ({final.get('verdict')})", tier_ok)
        g1 = rec["stages"].get("Compare", {}).get("status")
        check(f"{name}: compare stage done", g1 == "done", g1)
    else:
        neg_ok = (final["status"] == "error") and final.get("verdict") not in (
            "PRODUCTION_READY", "PRODUCTION_CANDIDATE", "VERIFIED",
            "NATIVE_JAVA_VERIFIED", "NATIVE_SPRING_UNIFIED",
            "VERIFIED_WITH_LIMITATIONS")
        check(f"{name}: failure surfaced honestly (status={final['status']}, "
              f"verdict={final.get('verdict')})", neg_ok)

    # stale-PASS guard: a failed run must never expose pass-tier verdict later
    st2 = requests.get(f"{BASE}/api/state", timeout=30).json()
    run2 = next(r for r in st2["runs"] if r["run_id"] == rid)
    check(f"{name}: state stable on re-poll",
          run2["status"] == final["status"] and run2.get("verdict") == final.get("verdict"))

    completed = (final["status"] == "done")
    if expect_ok and completed and do_package:
        pkg = os.path.join(LOGS, f"package_{name}.zip")
        pok, pinfo = extract_package(rid, pkg)
        check(f"{name}: package downloadable", pok, pinfo)
        rep = requests.get(f"{BASE}/report", params={"run_id": rid}, timeout=60)
        check(f"{name}: report downloadable",
              rep.status_code == 200 and len(rep.text) > 200,
              f"{rep.status_code}, {len(rep.text)} chars")

    ev = sse_probe(rid)
    check(f"{name}: SSE log stream delivered events", ev >= 1, f"{ev} events")

    if expect_ok and entry_class:
        pkg = os.path.join(LOGS, f"package_{name}.zip")
        if os.path.exists(pkg):
            ind = independent_native_compile_run(pkg, entry_class, name)
            check(f"{name}: native Java compiles standalone (javac, zero deps)",
                  ind.get("compile") is True, ind.get("compile_err", "")[:250])
            check(f"{name}: native Java runs (java rc=0)", ind.get("run") is True,
                  f"rc={ind.get('run_rc')} tail={ind.get('run_stdout_tail')}")
            check(f"{name}: zero forbidden runtime deps in native_gen",
                  not ind.get("forbidden_deps"), str(ind.get("forbidden_deps"))[:200])
            rec["independent"] = {k: v for k, v in ind.items() if k != "compile_err"}

    RESULTS["runs"][name] = rec
    return rec


def main():
    t0 = time.time()
    check("server starts on 127.0.0.1:8787", start_server())

    r = requests.get(BASE, timeout=15)
    html_ok = r.status_code == 200 and all(
        m in r.text for m in ("Workspaces / Runs", "Ingest", "run-item", "api/state"))
    check("frontend HTML loads with dashboard markers", html_ok,
          f"{r.status_code}, {len(r.text)} bytes")
    st = requests.get(f"{BASE}/api/state", timeout=15).json()
    check("/api/state responds with runs array", isinstance(st.get("runs"), list))

    try:
        run_one("claimscore-fixtures", build_legacy_zip(), expect_ok=True,
                entry_class="Ccmain01")
        # Unseen repo: the native-arithmetic truncation defect is now FIXED, so
        # payroll01 is EXPECTED to pass Gate-2 with exact byte business
        # equivalence (no off-by-one). Assert a real pass, not a toleration.
        run_one("payroll01-unseen", build_unseen_zip(), expect_ok=True)
        run_one("broken01-negative", build_broken_zip(), expect_ok=False)
    finally:
        playwright_check([
            "claimscore-fixtures", "payroll01-unseen", "broken01-negative"])

    RESULTS["log_scan"] = scan_logs()
    # SSE probes intentionally abort mid-stream; classify those resets as
    # expected noise and demand zero OTHER exceptions.
    err = RESULTS["log_scan"].get("server.err.log", {})
    sse_n = err.get("sse_probe_disconnects", 0)
    unexpected = err.get("unexpected_exceptions", [])
    check(f"server logs free of UNEXPECTED exceptions "
          f"({sse_n} SSE-probe resets classified as expected noise)",
          not unexpected, json.dumps(unexpected)[:400])
    RESULTS["log_scan"]["expected_sse_probe_resets"] = {"count": sse_n}

    mode = stop_server()
    time.sleep(1)
    port_free = not wait_port(3)
    check("server stopped cleanly, port released", mode in ("terminated", "already-exited") and port_free, mode)

    RESULTS["elapsed_s"] = round(time.time() - t0, 1)
    with open(os.path.join(LOGS, "results.json"), "w", encoding="utf-8") as fh:
        json.dump(RESULTS, fh, indent=2)
    fails = [c for c in RESULTS["checks"] if not c["ok"]]
    print(f"\n==== ACCEPTANCE SUMMARY: {len(RESULTS['checks'])-len(fails)}/"
          f"{len(RESULTS['checks'])} checks passed ====")
    for c in fails:
        print(f"  FAILED: {c['name']} :: {c['detail'][:200]}")


if __name__ == "__main__":
    main()
