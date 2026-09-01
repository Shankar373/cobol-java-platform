"""Parse stdin input from shell smoke-test scripts.

Extracts only the values that form the program's actual stdin stream.
Does NOT extract shell variable assignments, path arguments, or command flags.

Supported patterns:

  Heredoc (cat or program direct):
    program <<EOF
    1
    10001
    EOF

    cat > /tmp/input <<'EOF'
    1
    10001
    EOF

  echo pipe:
    echo "1" | program
    echo -e "1\n2\n3" | program

  printf pipe:
    printf '%s\n' 1 2 3 | program
    printf "1\n2\n9\n" | program

  stdin redirect:
    program < input.txt     (resolves to the file if accessible)

  printf with quoted values (multi-arg):
    printf '%s\n' "choice1" "choice2"
"""

import os
import re


# ---------------------------------------------------------------------------
# Heredoc extraction
# ---------------------------------------------------------------------------

def _extract_heredocs(text: str) -> list[list[str]]:
    """Extract all heredoc bodies from a shell script.

    Handles both <<EOF and <<'EOF' (no-interpolation form).
    Returns list of line-lists, one per heredoc.
    """
    results = []
    # Match: [optional leading program | cat | pipe] <<['"]?MARKER['"]?
    re_start = re.compile(r"""<<\s*['"]?([A-Z_a-z][A-Z_a-z0-9]*)['"]?""")
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        m = re_start.search(lines[i])
        if m:
            marker = m.group(1)
            body = []
            i += 1
            while i < len(lines):
                stripped = lines[i].rstrip()
                if stripped.strip() == marker:
                    break
                body.append(lines[i])
                i += 1
            if body:
                results.append(body)
        i += 1
    return results


# ---------------------------------------------------------------------------
# echo pipe extraction
# ---------------------------------------------------------------------------

_RE_ECHO_PIPE = re.compile(
    r'(?:^|\|\s*)echo(?:\s+-[en]+)?\s+"([^"]+)"(?:\s*\|)',
    re.MULTILINE,
)
_RE_ECHO_SIMPLE = re.compile(
    r'\becho(?:\s+-[en]+)?\s+"([^"]+)"\s*\|',
)


def _expand_escape(s: str) -> list[str]:
    r"""Split an echo -e string on \n into separate lines."""
    return [part for part in s.replace("\\n", "\n").split("\n")]


def _extract_echo_pipe(text: str) -> list[str]:
    """Extract lines from:  echo "1\n2\n9" | program"""
    values = []
    for m in _RE_ECHO_SIMPLE.finditer(text):
        values.extend(_expand_escape(m.group(1)))
    return values


# ---------------------------------------------------------------------------
# printf extraction
# ---------------------------------------------------------------------------

# printf '%s\n' val1 val2 val3
_RE_PRINTF_PERCENT = re.compile(
    r"""printf\s+['"]%s\\n['"]\s+(.+?)(?:\s*\||\s*$)""",
    re.MULTILINE,
)
# printf "val1\nval2\n"
_RE_PRINTF_EMBEDDED = re.compile(
    r"""printf\s+["']([^"']+)["']\s*\|""",
    re.MULTILINE,
)
# Word tokenizer for shell arguments (handles both quoted and bare tokens)
_RE_SH_TOKEN = re.compile(r'"([^"]+)"|\'([^\']+)\'|(\S+)')


def _extract_printf_pipe(text: str) -> list[str]:
    """Extract lines from printf variations piped to a program."""
    values = []
    # printf '%s\n' val1 val2 ...
    for m in _RE_PRINTF_PERCENT.finditer(text):
        args_str = m.group(1)
        for tm in _RE_SH_TOKEN.finditer(args_str):
            tok = tm.group(1) or tm.group(2) or tm.group(3) or ""
            tok = tok.strip()
            if tok and not tok.startswith("|"):
                values.append(tok)

    # printf "1\n2\n9\n" | prog
    for m in _RE_PRINTF_EMBEDDED.finditer(text):
        raw = m.group(1)
        lines = raw.replace("\\n", "\n").split("\n")
        values.extend(l for l in lines if l)  # skip empty from trailing \n

    return values


# ---------------------------------------------------------------------------
# stdin redirect extraction  (program < input.txt)
# ---------------------------------------------------------------------------

_RE_STDIN_REDIRECT = re.compile(r"""[.\/\w]+\s*<\s*["']?(\S+)["']?""")


def _extract_stdin_redirect(text: str, script_dir: str) -> list[str] | None:
    """If the script redirects stdin from a file, read that file.

    Returns None if no redirect found or file not accessible.
    """
    for m in _RE_STDIN_REDIRECT.finditer(text):
        candidate = m.group(1).strip("\"'")
        # Try absolute, then relative to script_dir
        for base in ("", script_dir):
            p = os.path.join(base, candidate) if base else candidate
            if os.path.isfile(p):
                try:
                    return open(p, encoding="utf-8", errors="replace").read().splitlines()
                except OSError:
                    pass
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_stdin_from_script(script_path: str) -> list[str] | None:
    """Extract stdin values from a shell smoke-test script.

    Priority:
      1. Heredoc bodies (most explicit)
      2. printf '%s\\n' ... | program
      3. printf "...\\n..." | program
      4. echo "..." | program
      5. program < input.txt

    Returns an ordered list of stdin lines, or None if nothing found.
    The caller is responsible for deciding whether None is acceptable.

    Important: only returns actual stdin values — NOT shell variable exports
    like  export ACCOUNT_ID=10001.
    """
    if not os.path.isfile(script_path):
        return None
    try:
        text = open(script_path, encoding="utf-8", errors="replace").read()
    except OSError:
        return None

    script_dir = os.path.dirname(os.path.abspath(script_path))

    # 1. Heredocs are the most reliable — prefer the first one found
    heredocs = _extract_heredocs(text)
    if heredocs:
        # Return the first heredoc that has at least one non-whitespace line
        for hd in heredocs:
            clean = [l.strip() for l in hd if l.strip()]
            if clean:
                return clean

    # 2. printf '%s\n' ...
    vals = _extract_printf_pipe(text)
    if vals:
        return [v.strip() for v in vals if v.strip()]

    # 3. echo pipe
    vals = _extract_echo_pipe(text)
    if vals:
        return [v.strip() for v in vals if v.strip()]

    # 4. stdin file redirect
    vals = _extract_stdin_redirect(text, script_dir)
    if vals is not None:
        return [v.strip() for v in vals if v.strip()]

    return None
