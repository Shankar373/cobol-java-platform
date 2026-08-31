"""
generators/native_java/statements.py

Translates parsed COBOL statements (SemanticIR STATEMENT nodes) into
Java source lines.

This module handles the core statement set:
  MOVE, ADD, SUBTRACT, MULTIPLY, DIVIDE, COMPUTE,
  DISPLAY, PERFORM (inline + named paragraph), CALL,
  IF/ELSE/END-IF, EVALUATE/WHEN/END-EVALUATE,
  GOBACK, STOP RUN, EXIT, CONTINUE, NEXT SENTENCE

All Java output is plain Java (no libcobj, no jp.osscons imports).
All numeric operations use either primitive types (int/long) or
java.math.BigDecimal depending on the field type.
"""
from __future__ import annotations

import re
from typing import Optional

from generators.native_java.types import to_java_var, to_java_class


def translate_statement(stmt: dict, ctx: "GeneratorContext") -> list[str]:
    """
    Translate one STATEMENT node properties dict into Java lines.

    Parameters
    ----------
    stmt:  The ``properties`` dict from a SemanticIR STATEMENT node.
    ctx:   Generator context (field registry, program metadata).

    Returns
    -------
    List of Java source lines (no trailing newlines).
    """
    stype = stmt.get("statement_type", "").upper()

    handlers = {
        "MOVE":       _move,
        "ADD":        _add,
        "SUBTRACT":   _subtract,
        "MULTIPLY":   _multiply,
        "DIVIDE":     _divide,
        "COMPUTE":    _compute,
        "DISPLAY":    _display,
        "PERFORM":    _perform,
        "IF":         _if_stmt,
        "ELSE":       _else_stmt,
        "END-IF":     _end_if,
        "EVALUATE":   _evaluate,
        "WHEN":       _when,
        "END-EVALUATE": _end_evaluate,
        "CALL":       _call,
        "GOBACK":     _goback,
        "STOP RUN":   _stop_run,
        "STOP":       _stop_run,
        "EXIT":       _exit_stmt,
        "CONTINUE":   _continue_stmt,
        "NEXT SENTENCE": _continue_stmt,
        "INITIALIZE": _initialize,
        "SET":        _set_stmt,
        "GO TO":      _goto,
        "GO":         _goto,
    }

    handler = handlers.get(stype)
    if handler:
        return handler(stmt, ctx)

    # Unknown statement: generate a comment so the Java still compiles
    return [f"// UNIMPLEMENTED STATEMENT: {stype}"]


class GeneratorContext:
    """
    Holds per-program state needed by statement translators.

    Attributes
    ----------
    fields:
        Map from COBOL data-name (upper) to JavaTypeInfo.
    program_name:
        COBOL PROGRAM-ID value.
    paragraphs:
        Set of known paragraph names in the program.
    indent:
        Current indentation level (number of 4-space units).
    """

    def __init__(self, program_name: str = "PROGRAM"):
        self.program_name = program_name
        self.fields: dict = {}       # name.upper() -> JavaTypeInfo
        self.paragraphs: set = set()
        self.indent: int = 2
        self._if_depth: int = 0
        self._eval_depth: int = 0

    def field_type(self, cobol_name: str):
        """Return JavaTypeInfo for a field name, or None."""
        return self.fields.get(cobol_name.upper().replace("-", "_"))

    def is_numeric_field(self, cobol_name: str) -> bool:
        ti = self.field_type(cobol_name)
        return ti is not None and ti.is_numeric

    def java_name(self, cobol_name: str) -> str:
        return to_java_var(cobol_name)

    def literal_or_var(self, val) -> str:
        is_lit = False
        if isinstance(val, dict):
            if val.get('type') == 'literal':
                is_lit = True
            val = val.get('value', val.get('name', val.get('literal', str(val))))
        
        v = str(val or '').strip()
        if not v:
            return '""'
        
        if v.upper() in ('SPACES', 'SPACE'):
            return '""'
        if v.upper() in ('ZEROS', 'ZEROES', 'ZERO'):
            return '0'
        if v.upper() in ('HIGH-VALUES', 'HIGH-VALUE'):
            return '"\xFF"'
        if v.upper() in ('LOW-VALUES', 'LOW-VALUE'):
            return '"\x00"'
        if v.startswith('"') or v.startswith("'"):
            return f'"{v[1:-1]}"'
        try:
            int(v)
            return v
        except ValueError:
            pass
        try:
            float(v)
            return v
        except ValueError:
            pass
        
        field_name = v.upper().replace('-', '_')
        if is_lit or ' ' in v or (field_name not in self.fields and field_name != 'RETURN_CODE'):
            return f'"{v}"'

        return to_java_var(v)


# ---------------------------------------------------------------------------
# Statement handlers
# ---------------------------------------------------------------------------

def _move(stmt: dict, ctx: GeneratorContext) -> list[str]:
    src = stmt.get("source", stmt.get("from", ""))
    targets = stmt.get("destinations", stmt.get("targets", []))
    if isinstance(targets, str):
        targets = [targets]
    if not targets and "to" in stmt:
        targets = [stmt["to"]]

    src_java = ctx.literal_or_var(src)
    lines = []
    for tgt in targets:
        tgt_java = ctx.java_name(tgt)
        # Coerce types where possible
        lines.append(f"{tgt_java} = {_coerce_assign(src_java, src, tgt, ctx)};")
    return lines or [f"// MOVE {src} (no target)"]


def _coerce_assign(src_java: str, src_cobol: str, tgt_cobol: str, ctx: GeneratorContext) -> str:
    """Generate the right-hand side expression for an assignment."""
    tgt_info = ctx.field_type(tgt_cobol)
    src_info = ctx.field_type(src_cobol) if src_cobol else None

    if tgt_info and tgt_info.is_numeric:
        # Moving string literal to numeric: parse it
        if src_java.startswith('"'):
            return f"Integer.parseInt({src_java}.trim())"
        if src_java in ("0", "0L"):
            return src_java
        return src_java

    if tgt_info and tgt_info.is_alpha:
        # Moving numeric to string: stringify
        if src_info and src_info.is_numeric:
            return f"String.valueOf({src_java})"
        return src_java

    return src_java


def _add(stmt: dict, ctx: GeneratorContext) -> list[str]:
    operands = stmt.get("operands", [])
    giving = stmt.get("giving")
    to_target = stmt.get("to", stmt.get("target", stmt.get("targets", "")))
    if isinstance(to_target, list) and to_target:
        first = to_target[0]
        if isinstance(first, dict):
            to_target = first.get("name", first.get("value", ""))
        else:
            to_target = str(first)

    if giving:
        addends = " + ".join(ctx.literal_or_var(o) for o in operands)
        tgt = ctx.java_name(giving)
        return [f"{tgt} = {addends};"]

    val = ctx.literal_or_var(stmt.get("value", operands[0] if operands else "0"))
    tgt = ctx.java_name(str(to_target))
    return [f"{tgt} += {val};"]


def _subtract(stmt: dict, ctx: GeneratorContext) -> list[str]:
    operands = stmt.get("operands", [])
    giving = stmt.get("giving")
    from_target = stmt.get("from", stmt.get("target", ""))

    if giving:
        minuend = ctx.literal_or_var(from_target)
        subtrahends = " - ".join(ctx.literal_or_var(o) for o in operands)
        tgt = ctx.java_name(giving)
        return [f"{tgt} = {minuend} - {subtrahends};"]

    val = ctx.literal_or_var(operands[0]) if operands else "0"
    tgt = ctx.java_name(from_target)
    return [f"{tgt} -= {val};"]


def _multiply(stmt: dict, ctx: GeneratorContext) -> list[str]:
    a = ctx.literal_or_var(stmt.get("operand_a", stmt.get("a", "0")))
    b = ctx.literal_or_var(stmt.get("operand_b", stmt.get("b", stmt.get("by", "0"))))
    giving = stmt.get("giving")
    if giving:
        tgt = ctx.java_name(giving)
        return [f"{tgt} = {a} * {b};"]
    tgt = ctx.java_name(b if not giving else giving)
    return [f"{tgt} *= {a};"]


def _divide(stmt: dict, ctx: GeneratorContext) -> list[str]:
    dividend = ctx.literal_or_var(stmt.get("dividend", stmt.get("into", "1")))
    divisor = ctx.literal_or_var(stmt.get("divisor", stmt.get("by", "1")))
    giving = stmt.get("giving")
    if giving:
        tgt = ctx.java_name(giving)
        return [f"{tgt} = {dividend} / {divisor};"]
    tgt = ctx.java_name(dividend)
    return [f"{tgt} /= {divisor};"]


def _compute(stmt: dict, ctx: GeneratorContext) -> list[str]:
    target = ctx.java_name(stmt.get("target", stmt.get("result", "")))
    expr_raw = stmt.get("expression", "0")
    expr = _cobol_expr_to_java(expr_raw, ctx)
    return [f"{target} = {expr};"]


def _cobol_expr_to_java(expr: str, ctx: GeneratorContext) -> str:
    """Convert a COBOL arithmetic expression string to Java."""
    # Replace ** with Math.pow (simple case)
    # Replace COBOL var names with Java var names
    tokens = re.split(r'(\s+|\*\*|[+\-*/()])', expr)
    result = []
    for tok in tokens:
        if tok.strip() in ("", "+", "-", "*", "/", "(", ")"):
            result.append(tok)
        elif tok.strip() == "**":
            result.append("/* ** unsupported: use Math.pow */ **")
        else:
            result.append(ctx.literal_or_var(tok.strip()) if tok.strip() else tok)
    return "".join(result)


def _display(stmt: dict, ctx: GeneratorContext) -> list[str]:
    operands = stmt.get("operands", stmt.get("args", []))
    if isinstance(operands, str):
        operands = [operands]

    if not operands:
        return ['System.out.println("");']

    parts = []
    for op in operands:
        java_val = ctx.literal_or_var(op)
        parts.append(java_val)

    if len(parts) == 1:
        return [f"System.out.println({parts[0]});"]

    concat = ' + String.valueOf('.join(parts)
    # Build: System.out.println(a + String.valueOf(b) + ...)
    expr = parts[0]
    for p in parts[1:]:
        expr += f" + String.valueOf({p})"
    return [f"System.out.println({expr});"]


def _perform(stmt: dict, ctx: GeneratorContext) -> list[str]:
    target = stmt.get("paragraph", stmt.get("section", stmt.get("target", "")))
    thru = stmt.get("thru")
    times = stmt.get("times")
    varying = stmt.get("varying")

    if varying:
        # PERFORM VARYING — complex; emit a comment + call
        return [f"// PERFORM VARYING (complex): {stmt}", f"{to_java_var(target)}();"]

    if times:
        times_java = ctx.literal_or_var(str(times))
        method = to_java_var(target)
        return [
            f"for (int _i = 0; _i < {times_java}; _i++) {{",
            f"    {method}();",
            "}",
        ]

    if not target:
        # Inline PERFORM ... END-PERFORM
        return ["// PERFORM inline begin"]

    method = to_java_var(target)
    return [f"{method}();"]


def _if_stmt(stmt: dict, ctx: GeneratorContext) -> list[str]:
    cond = stmt.get("condition", stmt.get("expr", "true"))
    java_cond = _cobol_condition_to_java(cond, ctx)
    ctx._if_depth += 1
    return [f"if ({java_cond}) {{"]


def _else_stmt(stmt: dict, ctx: GeneratorContext) -> list[str]:
    return ["} else {"]


def _end_if(stmt: dict, ctx: GeneratorContext) -> list[str]:
    ctx._if_depth = max(0, ctx._if_depth - 1)
    return ["}"]


def _evaluate(stmt: dict, ctx: GeneratorContext) -> list[str]:
    subject = ctx.literal_or_var(stmt.get("subject", stmt.get("expr", "true")))
    ctx._eval_depth += 1
    ctx._eval_subject = subject
    return [f"// EVALUATE {subject}"]


def _when(stmt: dict, ctx: GeneratorContext) -> list[str]:
    val = stmt.get("value", stmt.get("condition", "OTHER"))
    subject = getattr(ctx, "_eval_subject", "true")
    if val.upper() == "OTHER":
        return ["} else {"]
    java_val = ctx.literal_or_var(val)
    if not hasattr(ctx, "_eval_first_when"):
        ctx._eval_first_when = True
        return [f"if ({subject} == {java_val} || String.valueOf({subject}).equals(String.valueOf({java_val}))) {{"]
    return [f"}} else if ({subject} == {java_val} || String.valueOf({subject}).equals(String.valueOf({java_val}))) {{"]


def _end_evaluate(stmt: dict, ctx: GeneratorContext) -> list[str]:
    ctx._eval_depth = max(0, ctx._eval_depth - 1)
    if hasattr(ctx, "_eval_first_when"):
        del ctx._eval_first_when
    if hasattr(ctx, "_eval_subject"):
        del ctx._eval_subject
    return ["}"]


def _call(stmt: dict, ctx: GeneratorContext) -> list[str]:
    target = stmt.get("target", stmt.get("program", "UNKNOWN"))
    if target.startswith('"') or target.startswith("'"):
        target = target[1:-1]
    java_method = to_java_var(target)
    return [
        f"// CALL '{target}' — dynamic dispatch",
        f"// TODO: Register {target} in ProgramRegistry before use",
        f"// {java_method}();",
    ]


def _goback(stmt: dict, ctx: GeneratorContext) -> list[str]:
    return ["return;"]


def _stop_run(stmt: dict, ctx: GeneratorContext) -> list[str]:
    return ["System.exit(0);"]


def _exit_stmt(stmt: dict, ctx: GeneratorContext) -> list[str]:
    return ["// EXIT (paragraph terminator — no-op in Java method)"]


def _continue_stmt(stmt: dict, ctx: GeneratorContext) -> list[str]:
    return ["// CONTINUE (no-op)"]


def _initialize(stmt: dict, ctx: GeneratorContext) -> list[str]:
    targets = stmt.get("targets", [])
    if isinstance(targets, str):
        targets = [targets]
    lines = []
    for tgt in targets:
        ti = ctx.field_type(tgt)
        if ti:
            lines.append(f"{ctx.java_name(tgt)} = {ti.init_expr};")
        else:
            lines.append(f"{ctx.java_name(tgt)} = null; // INITIALIZE")
    return lines or ["// INITIALIZE (no targets)"]


def _set_stmt(stmt: dict, ctx: GeneratorContext) -> list[str]:
    targets = stmt.get("targets", [])
    value = stmt.get("value", "TRUE")
    if isinstance(targets, str):
        targets = [targets]
    lines = []
    for t in targets:
        lines.append(f"{ctx.java_name(t)} = {ctx.literal_or_var(value)};")
    return lines or ["// SET (no targets)"]


def _goto(stmt: dict, ctx: GeneratorContext) -> list[str]:
    target = stmt.get("target", stmt.get("paragraph", ""))
    if target:
        return [f"// GO TO {target} — translated as method call",
                f"{to_java_var(target)}(); return;"]
    return ["// GO TO (no target)"]


def _cobol_condition_to_java(cond: str, ctx: GeneratorContext) -> str:
    """Best-effort translation of a COBOL condition expression to Java."""
    if not cond or cond.strip().upper() == "TRUE":
        return "true"

    cond = cond.strip()

    # Replace COBOL operators with Java operators
    replacements = [
        (r'\bIS\s+NOT\s+EQUAL\s+TO\b', '!='),
        (r'\bIS\s+NOT\s+GREATER\s+THAN\b', '<='),
        (r'\bIS\s+NOT\s+LESS\s+THAN\b', '>='),
        (r'\bIS\s+EQUAL\s+TO\b', '=='),
        (r'\bIS\s+GREATER\s+THAN\b', '>'),
        (r'\bIS\s+LESS\s+THAN\b', '<'),
        (r'\bNOT\s+=\b', '!='),
        (r'\bNOT\s+EQUAL\b', '!='),
        (r'\bNOT\s+>\b', '<='),
        (r'\bNOT\s+<\b', '>='),
        (r'\bEQUAL\b', '=='),
        (r'\bGREATER\b', '>'),
        (r'\bLESS\b', '<'),
        (r'\bAND\b', '&&'),
        (r'\bOR\b', '||'),
        (r'\bNOT\b', '!'),
        (r'\s+=\s', ' == '),
        (r'\s+>\s', ' > '),
        (r'\s+<\s', ' < '),
    ]

    result = cond
    for pattern, replacement in replacements:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

    # Replace COBOL data names with Java names
    parts = re.split(r'(\s+|[=<>!&|()]+)', result)
    out = []
    for part in parts:
        stripped = part.strip()
        if stripped and re.match(r'^[A-Za-z][A-Za-z0-9\-_]*$', stripped):
            # Looks like a COBOL data name
            java = ctx.literal_or_var(stripped)
            out.append(java)
        else:
            out.append(part)
    return "".join(out)

