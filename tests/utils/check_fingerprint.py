import subprocess
import hashlib
import sys
import os

EXPECTED_HASH = "4b4796423e607a4e0aff9d68940ac5ff6545ddf8776c957c4b0525159bbaf31e"
IMAGE = os.environ.get("PARITY_GNUCOBOL_IMAGE", "hurriedreformist/gnucobol:3.1-builder")
PARITY_ALLOW_SKIP = os.environ.get("PARITY_ALLOW_SKIP", "false").lower() == "true"

def main():
    # If Docker check skips and PARITY_ALLOW_SKIP is true, allow skipping
    try:
        docker_check = subprocess.run(["docker", "info"], capture_output=True, timeout=5)
        if docker_check.returncode != 0:
            if PARITY_ALLOW_SKIP:
                print("Skipping fingerprint check: Docker not available.")
                sys.exit(0)
            else:
                print("Error: Docker not available and PARITY_ALLOW_SKIP is false.", file=sys.stderr)
                sys.exit(1)
    except Exception:
        if PARITY_ALLOW_SKIP:
            print("Skipping fingerprint check: Docker command failed/missing.")
            sys.exit(0)
        else:
            print("Error: Docker not available and PARITY_ALLOW_SKIP is false.", file=sys.stderr)
            sys.exit(1)

    cmd = ["docker", "run", "--rm", IMAGE, "cobc", "--info"]
    try:
        res = subprocess.run(cmd, capture_output=True, timeout=30)
    except Exception as e:
        print(f"Error running cobc --info: {e}", file=sys.stderr)
        sys.exit(1)

    if res.returncode != 0:
        print(f"Error: cobc --info exited with code {res.returncode}", file=sys.stderr)
        print(res.stderr.decode("utf-8", errors="replace"), file=sys.stderr)
        sys.exit(1)

    output_bytes = res.stdout
    h = hashlib.sha256(output_bytes).hexdigest().lower()
    
    print(f"Fingerprint raw length: {len(output_bytes)} bytes")
    print(f"Fingerprint SHA-256: {h}")

    if h != EXPECTED_HASH:
        print("CRITICAL ERROR: Pinned GnuCOBOL Docker image fingerprint has changed!", file=sys.stderr)
        print(f"Expected: {EXPECTED_HASH}", file=sys.stderr)
        print(f"Actual:   {h}", file=sys.stderr)
        sys.exit(1)

    print("Fingerprint matches pinned hash successfully.")
    sys.exit(0)

if __name__ == "__main__":
    main()
