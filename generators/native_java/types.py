"""
generators/native_java/types.py

COBOL PIC/USAGE → Java type mapping.

Maps COBOL data item declarations (PIC clause + USAGE clause) to
their Java representation:
  - Java type name (String, long, int, BigDecimal)
  - CobolNumericSpec parameters for numeric fields
  - Initialisation expression
  - Whether the field participates in REDEFINES byte-level overlay

No generator state is held here; all functions are pure.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class JavaTypeInfo:
    """Describes how a COBOL data item maps to Java."""
    java_type: str
    """Java type name, e.g. 'String', 'long', 'BigDecimal'."""

    init_expr: str
    """Java initialisation expression, e.g. '""', '0L', 'BigDecimal.ZERO'."""

    is_numeric: bool = False
    is_alpha: bool = False
    is_comp3: bool = False
    is_comp5: bool = False

    digits: int = 0
    scale: int = 0
    signed: bool = False
    display_length: int = 0
    """Byte length of the display-format value (for MOVE/STRING/INSPECT)."""

    use_cobol_numeric: bool = False
    """If True, use CobolNumeric runtime class for this field."""


def parse_pic(pic_str: str) -> tuple[bool, int, int, bool]:
    """
    Parse a PIC clause string.

    Returns (signed, digits, scale, is_edited).
    """
    pic = (pic_str or "").upper().strip()
    signed = pic.startswith("S") or "+" in pic or "-" in pic or "CR" in pic or "DB" in pic
    if pic.startswith("S"):
        pic = pic[1:]

    # Expand repetition: 9(5) -> 99999
    expanded = []
    i = 0
    while i < len(pic):
        ch = pic[i]
        if i + 1 < len(pic) and pic[i + 1] == "(":
            end = pic.find(")", i + 1)
            if end != -1:
                try:
                    count = int(pic[i + 2:end])
                    expanded.append(ch * count)
                except ValueError:
                    expanded.append(ch)
                i = end + 1
                continue
        expanded.append(ch)
        i += 1

    expanded_str = "".join(expanded)

    is_edited = any(c in expanded_str for c in ("$", "Z", "*", ",", "CR", "DB")) or \
                expanded_str.count("+") > 1 or expanded_str.count("-") > 1

    digit_chars = "9Z*"
    if "V" in expanded_str:
        parts = expanded_str.split("V")
        digits = sum(1 for c in parts[0] if c in digit_chars) + \
                 sum(1 for c in parts[1] if c in digit_chars)
        scale = sum(1 for c in parts[1] if c in digit_chars)
    elif "." in expanded_str:
        parts = expanded_str.split(".")
        digits = sum(1 for c in parts[0] if c in digit_chars) + \
                 sum(1 for c in parts[1] if c in digit_chars)
        scale = sum(1 for c in parts[1] if c in digit_chars)
    else:
        digits = sum(1 for c in expanded_str if c in digit_chars)
        scale = 0

    for sym in ("$", "+", "-"):
        c = expanded_str.count(sym)
        if c > 1:
            digits += (c - 1)

    return signed, digits, scale, is_edited


def map_data_item(
    pic: Optional[str],
    usage: Optional[str],
    signed: Optional[bool] = None,
    digits: Optional[int] = None,
    scale: Optional[int] = None,
) -> JavaTypeInfo:
    """
    Map a COBOL data item (PIC + USAGE) to a JavaTypeInfo.

    Parameters
    ----------
    pic:   PIC string, e.g. "9(9)" or "X(20)" or "S9(7)V99"
    usage: USAGE string, e.g. "COMP", "COMP-3", "DISPLAY", None
    signed, digits, scale: pre-parsed values (if already available)
    """
    usage_upper = (usage or "DISPLAY").upper().replace(" ", "-")
    pic_upper = (pic or "").upper().strip()

    # Pre-parse PIC if not provided
    if digits is None or scale is None:
        _signed, _digits, _scale, _edited = parse_pic(pic_upper)
        if signed is None:
            signed = _signed
        digits = _digits
        scale = _scale
    elif signed is None:
        signed = False

    is_alpha = bool(pic_upper) and (
        pic_upper.startswith("X") or
        pic_upper.startswith("A") or
        (not any(c in pic_upper for c in "9SV.Z*$"))
    )

    is_numeric = bool(digits > 0 or (pic_upper and "9" in pic_upper))
    is_comp3 = usage_upper in ("COMP-3", "PACKED-DECIMAL")
    is_comp5 = usage_upper in ("COMP-5", "BINARY-LONG", "BINARY-SHORT", "BINARY-DOUBLE")
    is_binary = usage_upper in ("COMP", "BINARY", "COMP-4", "COMP-5")

    if is_alpha and not is_numeric:
        # Pure alphanumeric field
        display_len = _alpha_len(pic_upper)
        return JavaTypeInfo(
            java_type="String",
            init_expr='""',
            is_alpha=True,
            display_length=display_len,
        )

    if is_numeric:
        if is_comp3 or (scale > 0):
            return JavaTypeInfo(
                java_type="java.math.BigDecimal",
                init_expr="java.math.BigDecimal.ZERO",
                is_numeric=True,
                is_comp3=is_comp3,
                digits=digits,
                scale=scale,
                signed=signed,
                use_cobol_numeric=True,
            )
        if is_binary or is_comp5:
            if digits <= 9:
                return JavaTypeInfo(
                    java_type="int",
                    init_expr="0",
                    is_numeric=True,
                    is_comp5=is_comp5,
                    digits=digits,
                    signed=signed,
                )
            return JavaTypeInfo(
                java_type="long",
                init_expr="0L",
                is_numeric=True,
                is_comp5=is_comp5,
                digits=digits,
                signed=signed,
            )
        # DISPLAY numeric
        if digits <= 9:
            return JavaTypeInfo(
                java_type="int",
                init_expr="0",
                is_numeric=True,
                digits=digits,
                scale=scale,
                signed=signed,
            )
        return JavaTypeInfo(
            java_type="long",
            init_expr="0L",
            is_numeric=True,
            digits=digits,
            scale=scale,
            signed=signed,
        )

    # Fallback: treat as String
    return JavaTypeInfo(java_type="String", init_expr='""', is_alpha=True)


def _alpha_len(pic: str) -> int:
    """Return the display length of an alphanumeric PIC clause."""
    total = 0
    i = 0
    while i < len(pic):
        ch = pic[i]
        if i + 1 < len(pic) and pic[i + 1] == "(":
            end = pic.find(")", i + 1)
            if end != -1:
                try:
                    total += int(pic[i + 2:end])
                except ValueError:
                    total += 1
                i = end + 1
                continue
        if ch.isalpha():
            total += 1
        i += 1
    return max(total, 1)


# ---------------------------------------------------------------------------
# Java name utilities
# ---------------------------------------------------------------------------

_JAVA_RESERVED = frozenset({
    "class", "public", "private", "protected", "static", "final", "void",
    "int", "double", "float", "long", "short", "char", "boolean", "byte",
    "new", "import", "package", "return", "this", "super", "interface",
    "abstract", "extends", "implements", "throws", "try", "catch", "finally",
    "throw", "instanceof", "null", "true", "false",
})


def to_java_var(name: str) -> str:
    """
    Convert a COBOL data-name to a Java field/variable name.
    Handles subscripts ITEM(3) and reference modification FIELD(1:5).
    """
    # Subscript / reference modification
    m = re.match(r'^([A-Za-z0-9_-]+)\s*\(\s*([^()]+)\s*\)$', name)
    if m:
        base = _name_to_var(m.group(1))
        inner = m.group(2).strip()
        if ":" in inner:
            # Reference modification: FIELD(start:length)
            parts = inner.split(":", 1)
            start_expr = to_java_var(parts[0].strip())
            len_expr = to_java_var(parts[1].strip()) if parts[1].strip() else ""
            try:
                start_i = int(start_expr) - 1
                if len_expr:
                    try:
                        end_i = start_i + int(len_expr)
                        return f"{base}.substring({start_i}, {end_i})"
                    except ValueError:
                        return f"{base}.substring({start_i}, {start_i} + ({len_expr}))"
                return f"{base}.substring({start_i})"
            except ValueError:
                if len_expr:
                    return f"{base}.substring(({start_expr}) - 1, ({start_expr}) - 1 + ({len_expr}))"
                return f"{base}.substring(({start_expr}) - 1)"
        else:
            # Array subscript: ITEM(3) -> item[2]
            idx = to_java_var(inner)
            try:
                return f"{base}[{int(idx) - 1}]"
            except ValueError:
                return f"{base}[{idx} - 1]"

    return _name_to_var(name)


def _name_to_var(name: str) -> str:
    result = name.replace("-", "_").lower()
    if result in _JAVA_RESERVED:
        result = result + "_"
    return result


def to_java_class(name: str) -> str:
    """Convert a COBOL program-name or data-name to a Java class name."""
    parts = re.sub(r"[^a-zA-Z0-9]", "_", name).split("_")
    return "".join(p.capitalize() for p in parts if p)
