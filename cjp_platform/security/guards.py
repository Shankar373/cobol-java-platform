"""
platform/security/guards.py

Command injection and path traversal protection.

These guards are mandatory for any code that interpolates user-supplied
repository paths or filenames into shell commands or Docker sh -c strings.

Behaviour:
  - _validate_repo_path: rejects paths containing ".." traversal
  - shell_safe: rejects any token that contains characters outside the
    strict safe allowlist before it is interpolated into a container command

Source: verified guards from cobol-java-modernization/cobol_migrate.py
        (lines 129-160). Behaviour preserved exactly.
"""
from __future__ import annotations

import re

# Only allow characters that are safe to embed directly into a Docker
# "sh -c" string without quoting. This is intentionally strict.
_FILENAME_SAFE_RE = re.compile(r"^[A-Za-z0-9_./\-]+$")


def validate_repo_path(rel_path: str, what: str = "source") -> str:
    """
    Reject repository-relative paths that contain shell metacharacters or
    path traversal sequences.

    Parameters
    ----------
    rel_path:
        A path relative to the repository root, as it would appear in a
        migration_config.json ``sources`` list.
    what:
        A label used in the exception message (e.g. "source", "copybook").

    Returns
    -------
    rel_path if safe.

    Raises
    ------
    ValueError if the path is unsafe.
    """
    if not rel_path:
        raise ValueError(f"UNSAFE_{what.upper()}: empty path")
    parts_fwd = rel_path.split("/")
    parts_bwd = rel_path.split("\\")
    if ".." in parts_fwd or ".." in parts_bwd:
        raise ValueError(
            f"UNSAFE_{what.upper()}: path contains '..' traversal: {rel_path!r}"
        )
    if not _FILENAME_SAFE_RE.match(rel_path):
        raise ValueError(
            f"UNSAFE_{what.upper()}: {rel_path!r} contains characters that are "
            f"not permitted in container command interpolation"
        )
    return rel_path


def shell_safe(token: str, what: str = "value") -> str:
    """
    Validate a single token before it is interpolated into a container
    sh -c string.

    Parameters
    ----------
    token:
        The value to validate (e.g. a filename, executable name).
    what:
        A label used in the exception message.

    Returns
    -------
    token.strip() if safe.

    Raises
    ------
    ValueError if the token is unsafe.
    """
    token = (token or "").strip()
    if not token or len(token) > 512 or not _FILENAME_SAFE_RE.match(token):
        raise ValueError(
            f"UNSAFE_{what.upper()}: {token!r} contains characters that are "
            f"not permitted in container command interpolation"
        )
    return token
