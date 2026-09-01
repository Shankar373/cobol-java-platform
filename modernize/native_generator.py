import re
import os
from decimal import Decimal
from modernize.semantic_ir import SemanticIRNode

def to_java_var(name: str) -> str:
    # Check if name has subscript, e.g. ITEM-AMOUNT(3) or ITEM-AMOUNT ( WS-I )
    match = re.match(r'^([A-Za-z0-9_-]+)\s*\(\s*([^()]+)\s*\)$', name)
    if match:
        base = match.group(1).replace("-", "_").lower()
        inner = match.group(2).strip()
        if ":" in inner:
            # Reference Modification!
            parts = inner.split(":")
            start = parts[0].strip()
            length = parts[1].strip() if len(parts) > 1 else ""
            start_java = to_java_var(start)
            
            def is_int(s):
                try:
                    int(s)
                    return True
                except ValueError:
                    return False
            
            if is_int(start_java):
                begin_idx = int(start_java) - 1
                if length:
                    length_java = to_java_var(length)
                    if is_int(length_java):
                        end_idx = begin_idx + int(length_java)
                        return f"{base}.substring({begin_idx}, {end_idx})"
                    else:
                        return f"{base}.substring({begin_idx}, {begin_idx} + ({length_java}))"
                else:
                    return f"{base}.substring({begin_idx})"
            else:
                if length:
                    length_java = to_java_var(length)
                    if is_int(length_java):
                        return f"{base}.substring(({start_java}) - 1, ({start_java}) - 1 + {int(length_java)})"
                    else:
                        return f"{base}.substring(({start_java}) - 1, ({start_java}) - 1 + ({length_java}))"
                else:
                    return f"{base}.substring(({start_java}) - 1)"
        else:
            idx = inner
            idx_java = to_java_var(idx)
            if idx_java.isdigit():
                return f"{base}[{int(idx_java) - 1}]"
            return f"{base}[{idx_java} - 1]"

    name = name.replace("-", "_").lower()
    if name in ("class", "public", "private", "protected", "static", "final", "void", 
                "int", "double", "float", "long", "short", "char", "boolean", "byte", "new", "import", "package"):
        name = name + "_"
    return name


def to_java_method(name: str) -> str:
    parts = name.replace("-", "_").split("_")
    camel = "".join(p.capitalize() for p in parts if p)
    return "is" + camel


def is_input_file(logical: str, path: str) -> bool:
    logical_upper = logical.upper()
    path_lower = path.lower()
    if "IN-" in logical_upper or "SOURCE" in logical_upper or "SLS" in logical_upper or "INPUT" in logical_upper or "FILE-A" in logical_upper or "FILE-B" in logical_upper:
        return True
    if "OUT-" in logical_upper or "REPORT" in logical_upper or "RESULT" in logical_upper or "RPT" in logical_upper or "OUTPUT" in logical_upper:
        return False
    if "in" in path_lower or "source" in path_lower or "input" in path_lower:
        return True
    if "out" in path_lower or "report" in path_lower or "result" in path_lower:
        return False
    return True

def to_java_class(name: str) -> str:
    parts = name.replace("-", "_").split("_")
    return "".join(p.capitalize() for p in parts if p)

class NativeTypeMapper:
    @staticmethod
    def parse_pic(pic_str: str):
        pic = pic_str.upper()
        signed = pic.startswith("S")
        if signed:
            pic = pic[1:]
        
        expanded = []
        i = 0
        while i < len(pic):
            char = pic[i]
            if i + 1 < len(pic) and pic[i+1] == "(":
                end = pic.find(")", i + 1)
                if end != -1:
                    try:
                        count = int(pic[i+2:end])
                        expanded.append(char * count)
                    except ValueError:
                        expanded.append(char)
                    i = end + 1
                    continue
            expanded.append(char)
            i += 1
        
        expanded_str = "".join(expanded)
        is_edited = any(c in expanded_str for c in ("$", "Z", "*", ",", "CR", "DB")) or (expanded_str.count("+") > 1) or (expanded_str.count("-") > 1)
        if "X" in expanded_str or is_edited:
            return "String", len(expanded_str), 0, signed
        
        if "V" in expanded_str:
            parts = expanded_str.split("V")
            digits = parts[0].count("9") + parts[1].count("9")
            scale = parts[1].count("9")
            return "BigDecimal", digits, scale, signed
        else:
            digits = expanded_str.count("9")
            return "Integer" if digits <= 9 else "Long", digits, 0, signed

    @classmethod
    def get_java_type(cls, pic_str: str, usage: str = None) -> str:
        if usage:
            usage_upper = usage.upper()
            if usage_upper == "COMP-1":
                return "Float"
            if usage_upper == "COMP-2":
                return "Double"
            if usage_upper in ("COMP-3", "PACKED-DECIMAL"):
                return "BigDecimal"
        
        t_name, _, _, _ = cls.parse_pic(pic_str)
        return t_name

class LayoutNode:
    def __init__(self, name, level, parent=None):
        self.name = name
        self.level = level
        self.parent = parent
        self.children = []
        self.pic = None
        self.usage = None
        self.occurs = None
        self.occurs_min = None
        self.occurs_max = None
        self.depending_on = None
        self.redefines = None
        self.offset = 0
        self.length = 0
        self.occurs_list = []

class NativeExpressionTranslator:
    def __init__(self, variables_types: dict, redefines_layout: dict = None, occurs_depending_on: dict = None, is_child: bool = False, parent_global_vars: dict = None):
        self.var_types = variables_types
        self.redefines_layout = redefines_layout or {}
        self.occurs_depending_on = occurs_depending_on or {}
        self.is_child = is_child
        self.parent_global_vars = parent_global_vars or {}

    def _translate_subscripts(self, expr: str) -> str:
        pattern = r'(?<![A-Za-z0-9_-])([A-Za-z0-9_-]+)\s*\(\s*([^()]+)\s*\)'
        def repl(match):
            cobol_name = match.group(1).upper()
            is_parent_global = False
            parent_path = ""
            if cobol_name not in self.var_types and self.is_child and cobol_name in self.parent_global_vars:
                is_parent_global = True
                t, parent_path = self.parent_global_vars[cobol_name]
                
            if not is_parent_global and cobol_name not in self.var_types and cobol_name not in self.redefines_layout and cobol_name not in self.occurs_depending_on:
                return match.group(0)
                
            if is_parent_global:
                var_name = f"{parent_path}.{to_java_var(cobol_name)}"
            else:
                var_name = to_java_var(cobol_name)
            idx = match.group(2).strip()
            if ":" in idx:
                # Reference modification!
                parts = idx.split(":")
                start_expr = parts[0].strip()
                length_expr = parts[1].strip() if len(parts) > 1 else ""
                
                # Replace variable names in start_expr and length_expr
                for v in self.var_types.keys():
                    start_expr = re.sub(r'(?<![A-Za-z0-9_-])' + re.escape(v) + r'(?![A-Za-z0-9_-])', to_java_var(v), start_expr)
                    if length_expr:
                        length_expr = re.sub(r'(?<![A-Za-z0-9_-])' + re.escape(v) + r'(?![A-Za-z0-9_-])', to_java_var(v), length_expr)
                if self.is_child:
                    for v in self.parent_global_vars.keys():
                        t, parent_path = self.parent_global_vars[v]
                        start_expr = re.sub(r'(?<![A-Za-z0-9_-])' + re.escape(v) + r'(?![A-Za-z0-9_-])', f"{parent_path}.{to_java_var(v)}", start_expr)
                        if length_expr:
                            length_expr = re.sub(r'(?<![A-Za-z0-9_-])' + re.escape(v) + r'(?![A-Za-z0-9_-])', f"{parent_path}.{to_java_var(v)}", length_expr)
                        
                for v in self.redefines_layout.keys():
                    if not self.redefines_layout[v]["is_array"]:
                        start_expr = re.sub(r'\b' + re.escape(to_java_var(v)) + r'\b', f"get_{to_java_var(v)}()", start_expr)
                        if length_expr:
                            length_expr = re.sub(r'\b' + re.escape(to_java_var(v)) + r'\b', f"get_{to_java_var(v)}()", length_expr)

                def is_int(s):
                    try:
                        int(s)
                        return True
                    except ValueError:
                        return False

                if is_int(start_expr):
                    begin_idx = int(start_expr) - 1
                    if length_expr:
                        if is_int(length_expr):
                            end_idx = begin_idx + int(length_expr)
                            return f"{var_name}.substring({begin_idx}, {end_idx})"
                        else:
                            return f"{var_name}.substring({begin_idx}, {begin_idx} + ({length_expr}))"
                    else:
                        return f"{var_name}.substring({begin_idx})"
                else:
                    if length_expr:
                        if is_int(length_expr):
                            return f"{var_name}.substring(({start_expr}) - 1, ({start_expr}) - 1 + {int(length_expr)})"
                        else:
                            return f"{var_name}.substring(({start_expr}) - 1, ({start_expr}) - 1 + ({length_expr}))"
                    else:
                        return f"{var_name}.substring(({start_expr}) - 1)"
            
            for v in self.var_types.keys():
                idx = re.sub(r'(?<![A-Za-z0-9_-])' + re.escape(v) + r'(?![A-Za-z0-9_-])', to_java_var(v), idx)
                
            if self.is_child:
                for v in self.parent_global_vars.keys():
                    t, parent_path = self.parent_global_vars[v]
                    idx = re.sub(r'(?<![A-Za-z0-9_-])' + re.escape(v) + r'(?![A-Za-z0-9_-])', f"{parent_path}.{to_java_var(v)}", idx)
                    
            for v in self.redefines_layout.keys():
                if not self.redefines_layout[v]["is_array"]:
                    idx = re.sub(r'\b' + re.escape(to_java_var(v)) + r'\b', f"get_{to_java_var(v)}()", idx)
            
            if cobol_name in self.occurs_depending_on:
                dep_var, min_val, max_val = self.occurs_depending_on[cobol_name]
                dep_java = to_java_var(dep_var)
                if dep_var in self.redefines_layout:
                    dep_val_expr = f"get_{dep_java}()"
                else:
                    dep_val_expr = dep_java
                subscript_expr = f"checkBounds({idx}, {min_val}, \"{dep_java}\", {dep_val_expr})"
            else:
                subscript_expr = idx
                
            if cobol_name in self.redefines_layout:
                return f"get_{var_name}({subscript_expr})"
            else:
                if cobol_name in self.occurs_depending_on:
                    return f"{var_name}[{subscript_expr}]"
                else:
                    if idx.isdigit():
                        return f"{var_name}[{int(idx) - 1}]"
                    return f"{var_name}[{idx} - 1]"
        
        old = ""
        while old != expr:
            old = expr
            expr = re.sub(pattern, repl, expr)
        return expr

    def translate(self, expr_str: str) -> str:
        # Mask FUNCTION NUMVAL calls
        numval_placeholders = {}
        def _mask_numval(m):
            key = f"__numval_{len(numval_placeholders)}__"
            arg = m.group(1).strip()
            translated_arg = self.translate(arg)
            numval_placeholders[key] = f"com.systema.modernized.CobolFormatHelper.numval({translated_arg})"
            return key
            
        expr_str = re.sub(
            r'\bFUNCTION\s+NUMVAL\s*\(\s*([^()]+)\s*\)',
            _mask_numval,
            expr_str,
            flags=re.IGNORECASE
        )

        # Mask FUNCTION MOD calls
        mod_placeholders = {}
        def _mask_mod(m):
            key = f"__mod_{len(mod_placeholders)}__"
            arg1 = m.group(1).strip()
            arg2 = m.group(2).strip()
            translated_arg1 = self.translate(arg1)
            translated_arg2 = self.translate(arg2)
            mod_placeholders[key] = f"com.systema.modernized.CobolFormatHelper.mod({translated_arg1}, {translated_arg2})"
            return key
            
        expr_str = re.sub(
            r'\bFUNCTION\s+MOD\s*\(\s*([^,()]+)\s*,\s*([^()]+)\s*\)',
            _mask_mod,
            expr_str,
            flags=re.IGNORECASE
        )

        expr_str = self._translate_subscripts(expr_str)
        
        # Mask get_ accessor calls to protect them from operator tokenizer splitting
        get_placeholders = {}
        while True:
            match = re.search(r'\bget_[a-zA-Z0-9_]+\(', expr_str)
            if not match:
                break
            start_idx = match.end() - 1  # points to '('
            depth = 1
            curr = start_idx + 1
            while curr < len(expr_str) and depth > 0:
                if expr_str[curr] == '(':
                    depth += 1
                elif expr_str[curr] == ')':
                    depth -= 1
                curr += 1
            if depth == 0:
                full_call = expr_str[match.start():curr]
                key = f"\x00GET{len(get_placeholders)}\x00"
                get_placeholders[key] = full_call
                expr_str = expr_str[:match.start()] + key + expr_str[curr:]
            else:
                break
        
        # Mask substring calls to protect them from operator tokenizer splitting
        substring_placeholders = {}
        while True:
            idx = expr_str.find(".substring(")
            if idx == -1:
                break
            ident_start = idx
            while ident_start > 0 and (expr_str[ident_start - 1].isalnum() or expr_str[ident_start - 1] in ('_', '-')):
                ident_start -= 1
            start_idx = idx + len(".substring(")
            depth = 1
            curr = start_idx
            while curr < len(expr_str) and depth > 0:
                if expr_str[curr] == '(':
                    depth += 1
                elif expr_str[curr] == ')':
                    depth -= 1
                curr += 1
            if depth == 0:
                full_call = expr_str[ident_start:curr]
                key = f"\x00SUB{len(substring_placeholders)}\x00"
                substring_placeholders[key] = full_call
                expr_str = expr_str[:ident_start] + key + expr_str[curr:]
            else:
                break

        # Protect array subscript expressions from being split by operator tokenizer.
        # Replace [...] content with placeholders, restore after tokenizing.
        placeholders = {}
        def _mask(m):
            key = f"\x00BR{len(placeholders)}\x00"
            placeholders[key] = m.group(1)
            return "[" + key + "]"
        masked = re.sub(r'\[([^\[\]]*)\]', _mask, expr_str)
        
        _bare_op = r'(?<![a-zA-Z0-9_])(?:\*\*|[\+\-\*\/])'
        tokens = re.split(rf'(\s+\*\*\s+|\s+\*\*|\*\*\s+|\s+[\+\-\*\/]\s+|\s+[\+\-\*\/]|[\+\-\*\/]\s+|\(|\)|{_bare_op})', masked)
        
        def to_java_string_literal(cobol_lit: str) -> str:
            inner = cobol_lit[1:-1]
            escaped = inner.replace('\\', '\\\\')
            escaped = (escaped.replace('"', '\\"')
                              .replace('\n', '\\n')
                              .replace('\r', '\\r')
                              .replace('\t', '\\t'))
            result = f'"{escaped}"'
            assert result.startswith('"'), f"to_java_string_literal must return double-quoted string, got: {result}"
            return result

        translated_tokens = []
        for t in tokens:
            t_strip = t.strip()
            if not t_strip:
                continue
            if t_strip in ("+", "-", "*", "/", "**", "(", ")"):
                translated_tokens.append(t_strip)
            elif (t_strip.startswith("'") and t_strip.endswith("'")) or (t_strip.startswith('"') and t_strip.endswith('"')):
                translated_tokens.append(to_java_string_literal(t_strip))
            elif re.match(r'^-?\d*\.?\d+$', t_strip):
                translated_tokens.append(f"new BigDecimal(\"{t_strip}\")")
            else:
                # Restore any masked bracket contents for the raw token output
                raw_token = t_strip
                for ph, orig in placeholders.items():
                    raw_token = raw_token.replace(f"[{ph}]", f"[{orig}]")
                if raw_token.startswith("\x00GET"):
                    raw_token = get_placeholders[raw_token]
                
                if "[" in raw_token:
                    base_java = re.split(r'\[', raw_token)[0].strip()
                    v_type = "BigDecimal"
                    for cobol_var, c_type in self.var_types.items():
                        if to_java_var(cobol_var) == base_java:
                            v_type = c_type
                            break
                    if v_type in ("Integer", "Long"):
                        translated_tokens.append(f"BigDecimal.valueOf({raw_token})")
                    elif v_type == "BigDecimal":
                        translated_tokens.append(f"{raw_token}.getValue()")
                    else:
                        translated_tokens.append(raw_token)
                elif raw_token.startswith("get_"):
                    translated_tokens.append(raw_token)
                elif re.match(r'^__(?:numval|mod|substring)_\d+__$', raw_token):
                    # Masked placeholder for FUNCTION calls that return raw BigDecimal (not CobolNumeric)
                    translated_tokens.append(raw_token)
                else:
                    raw_upper = raw_token.upper()
                    if raw_upper not in self.var_types and self.is_child and raw_upper in self.parent_global_vars:
                        t, parent_path = self.parent_global_vars[raw_upper]
                        java_var = f"{parent_path}.{to_java_var(raw_token)}"
                        v_type = t
                    else:
                        java_var = to_java_var(raw_token)
                        if raw_upper in self.redefines_layout:
                            java_var = f"get_{java_var}()"
                            v_type = self.var_types.get(raw_upper, "BigDecimal")
                            if v_type in ("Integer", "Long"):
                                translated_tokens.append(f"BigDecimal.valueOf({java_var})")
                            else:
                                translated_tokens.append(java_var)
                            continue
                        v_type = self.var_types.get(raw_upper, "BigDecimal")
                    if v_type in ("Integer", "Long"):
                        translated_tokens.append(f"BigDecimal.valueOf({java_var})")
                    elif v_type == "BigDecimal":
                        translated_tokens.append(f"{java_var}.getValue()")
                    else:
                        translated_tokens.append(java_var)
 
        res = self._convert_to_bigdecimal_calls(translated_tokens)
        for ph, val in get_placeholders.items():
            res = res.replace(ph, val)
        for ph, val in numval_placeholders.items():
            res = res.replace(ph, val)
        for ph, val in mod_placeholders.items():
            res = res.replace(ph, val)
        for ph, val in substring_placeholders.items():
            res = res.replace(ph, val)
        return res

    def _convert_to_bigdecimal_calls(self, tokens: list) -> str:
        if not tokens:
            return "BigDecimal.ZERO"
        if len(tokens) == 1:
            return tokens[0]

        try:
            return self._parse_infix(tokens)
        except Exception:
            return "BigDecimal.ZERO"

    def _parse_infix(self, tokens: list) -> str:
        idx = 0
        def peek():
            nonlocal idx
            return tokens[idx] if idx < len(tokens) else None
        
        def consume():
            nonlocal idx
            val = peek()
            idx += 1
            return val
        
        def parse_factor() -> str:
            t = peek()
            if t == "(":
                consume()
                expr = parse_expr()
                consume()
                return expr
            if t == "-":
                consume()
                operand = parse_factor()
                return f"({operand}).negate()"
            if t == "+":
                consume()
                return parse_factor()
            return consume()

        def parse_power() -> str:
            left = parse_factor()
            while peek() == "**":
                consume()
                right = parse_factor()
                left = f"com.systema.modernized.runtime.CobolArithmetic.power({left}, {right})"
            return left

        def parse_term() -> str:
            left = parse_power()
            while peek() in ("*", "/"):
                op = consume()
                right = parse_power()
                if op == "*":
                    left = f"com.systema.modernized.runtime.CobolArithmetic.multiply({left}, {right})"
                else:
                    left = f"com.systema.modernized.runtime.CobolArithmetic.divide({left}, {right})"
            return left

        def parse_expr() -> str:
            left = parse_term()
            while peek() in ("+", "-"):
                op = consume()
                right = parse_term()
                if op == "+":
                    left = f"com.systema.modernized.runtime.CobolArithmetic.add({left}, {right})"
                else:
                    left = f"com.systema.modernized.runtime.CobolArithmetic.subtract({left}, {right})"
            return left

        return parse_expr()

class NativeStatementTranslator:
    def __init__(self, var_types: dict, file_assigns: list = None, record_to_fd: dict = None, all_generators: dict = None, current_generator = None, level88_map: dict = None, constants_map: dict = None, is_child: bool = False, parent_global_vars: dict = None):
        self.var_types = var_types
        self.file_assigns = file_assigns or []
        self.record_to_fd = record_to_fd or {}
        self.all_generators = all_generators or {}
        self.current_generator = current_generator
        self.level88_map = level88_map or {}
        self.constants_map = constants_map or {}
        self.redefines_layout = getattr(current_generator, "redefines_layout", {}) if current_generator else {}
        self.is_child = is_child
        self.parent_global_vars = parent_global_vars or {}
        
        redefs = self.redefines_layout
        odos = getattr(current_generator, "occurs_depending_on", {}) if current_generator else {}
        self.occurs_depending_on = odos
        self.expr_trans = NativeExpressionTranslator(var_types, redefines_layout=redefs, occurs_depending_on=odos, is_child=is_child, parent_global_vars=parent_global_vars)
        self.evaluate_count = 0
        self.evaluate_subject = None   # set when EVALUATE node is seen
        self.evaluate_subjects = []
        self.call_counter = 0
        self.loop_braces_stack = []

    def _is_variable(self, name: str) -> bool:
        base = re.split(r'\(', name)[0].strip()
        return base in self.var_types

    def _get_matched_fd(self, tgt) -> str:
        matched_fd = self.record_to_fd.get(tgt)
        if not matched_fd:
            for assign in self.file_assigns:
                logical = assign.get("logical_name", "")
                if logical.replace("-FILE", "") in tgt or tgt.replace("-REC", "") in logical:
                    matched_fd = logical
                    break
        if not matched_fd:
            matched_fd = tgt
        return matched_fd

    def _get_var_type(self, name: str, default: str = "String") -> str:
        base = re.split(r'\(', name)[0].strip()
        return self.var_types.get(base, default)

    def translate_math_operand(self, val: str, tgt_type: str) -> str:
        if re.match(r'^\d+(\.\d+)?$', val):
            if tgt_type == "BigDecimal":
                return f"new BigDecimal(\"{val}\")"
            elif tgt_type == "Long" and val.isdigit():
                return val + "L"
            else:
                return val
        expr = self.expr_trans.translate(val)
        if tgt_type in ("Integer", "Long"):
            if expr.startswith("BigDecimal.valueOf(") and expr.endswith(")"):
                return expr[19:-1]
        return expr

    def generate_initialization_statement(self, var_name):
        var_type = self._get_var_type(var_name, "String")
        if var_type == "BigDecimal":
            default_val = "BigDecimal.ZERO"
        elif var_type in ("Integer", "Long"):
            default_val = "0"
        else:
            default_val = '""'
        return self.generate_assignment(var_name, default_val)

    def generate_assignment(self, tgt: str, value_expr: str, rounded: bool = False) -> str:
        match = re.match(r'^([A-Za-z0-9_-]+)\s*\(\s*([^()]+)\s*\)$', tgt)
        if match:
            base = match.group(1).upper()
            idx = match.group(2).strip()
            
            if self.current_generator:
                for v in self.current_generator.var_types.keys():
                    idx = re.sub(r'(?<![A-Za-z0-9_-])' + re.escape(v) + r'(?![A-Za-z0-9_-])', to_java_var(v), idx)
                    
            if self.current_generator:
                for v in self.current_generator.redefines_layout.keys():
                    if not self.current_generator.redefines_layout[v]["is_array"]:
                        idx = re.sub(r'\b' + re.escape(to_java_var(v)) + r'\b', f"get_{to_java_var(v)}()", idx)
            
            if base not in self.var_types and self.is_child and base in self.parent_global_vars:
                _, parent_path = self.parent_global_vars[base]
                java_base = f"{parent_path}.{to_java_var(base)}"
            else:
                java_base = to_java_var(base)
            
            base_type = self.var_types.get(base)
            if self.current_generator:
                is_edited = getattr(self.current_generator, "var_edited", {}).get(base, False)
                if base_type == "String":
                    pic = self.current_generator.var_pics.get(base, "")
                    if pic:
                        if is_edited:
                            value_expr = f"com.systema.modernized.CobolFormatHelper.format({value_expr}, \"{pic}\")"
                        else:
                            _, length, _, _ = NativeTypeMapper.parse_pic(pic)
                            value_expr = f"padString(String.valueOf({value_expr}), {length})"
            
            if self.current_generator and base in self.current_generator.redefines_layout:
                layout = self.current_generator.redefines_layout[base]
                if base in self.current_generator.occurs_depending_on:
                    dep_var, min_val, max_val = self.current_generator.occurs_depending_on[base]
                    dep_java = to_java_var(dep_var)
                    if dep_var in self.current_generator.redefines_layout:
                        dep_val_expr = f"get_{dep_java}()"
                    else:
                        dep_val_expr = dep_java
                    subscript_expr = f"checkBounds({idx}, {min_val}, \"{dep_java}\", {dep_val_expr})"
                else:
                    subscript_expr = idx
                return f"set_{java_base}({subscript_expr}, {value_expr});"
            else:
                if self.current_generator and base in self.current_generator.occurs_depending_on:
                    dep_var, min_val, max_val = self.current_generator.occurs_depending_on[base]
                    dep_java = to_java_var(dep_var)
                    if dep_var in self.current_generator.redefines_layout:
                        dep_val_expr = f"get_{dep_java}()"
                    else:
                        dep_val_expr = dep_java
                    subscript_expr = f"checkBounds({idx}, {min_val}, \"{dep_java}\", {dep_val_expr})"
                else:
                    if idx.isdigit():
                        subscript_expr = f"{int(idx) - 1}"
                    else:
                        subscript_expr = f"{idx} - 1"
                if base_type == "BigDecimal":
                    rm = "com.systema.modernized.runtime.CobolRoundingMode.NEAREST_AWAY_FROM_ZERO" if rounded else "com.systema.modernized.runtime.CobolRoundingMode.TRUNCATION"
                    return f"{java_base}[{subscript_expr}].assign({value_expr}, {rm}, com.systema.modernized.runtime.SizeErrorPolicy.UNCHECKED);"
                else:
                    return f"{java_base}[{subscript_expr}] = {value_expr};"
        else:
            base = tgt.upper()
            if base not in self.var_types and self.is_child and base in self.parent_global_vars:
                _, parent_path = self.parent_global_vars[base]
                java_base = f"{parent_path}.{to_java_var(base)}"
            else:
                java_base = to_java_var(base)
            
            base_type = None
            is_edited = False
            pic = ""
            is_group = False
            is_redefine = False
            
            if self.current_generator:
                if base in self.current_generator.var_types:
                    base_type = self.current_generator.var_types.get(base)
                    is_edited = getattr(self.current_generator, "var_edited", {}).get(base, False)
                    pic = self.current_generator.var_pics.get(base, "")
                    is_group = base.upper() in self.current_generator.group_fields
                    is_redefine = base in self.current_generator.redefines_layout
                elif self.is_child and base in self.parent_global_vars:
                    curr_parent = self.current_generator.parent_generator
                    while curr_parent:
                        if base in curr_parent.var_types:
                            base_type = curr_parent.var_types.get(base)
                            is_edited = getattr(curr_parent, "var_edited", {}).get(base, False)
                            pic = curr_parent.var_pics.get(base, "")
                            is_group = base.upper() in curr_parent.group_fields
                            is_redefine = base in curr_parent.redefines_layout
                            break
                        curr_parent = curr_parent.parent_generator
            
            if not base_type:
                base_type = self.var_types.get(base)
            
            if base_type == "String" and pic:
                if is_edited:
                    value_expr = f"com.systema.modernized.CobolFormatHelper.format({value_expr}, \"{pic}\")"
                else:
                    _, length, _, _ = NativeTypeMapper.parse_pic(pic)
                    value_expr = f"padString(String.valueOf({value_expr}), {length})"
            
            if is_group:
                return f"populate_{java_base}({value_expr});"
            elif is_redefine:
                return f"set_{java_base}({value_expr});"
            else:
                if base_type == "BigDecimal":
                    rm = "com.systema.modernized.runtime.CobolRoundingMode.NEAREST_AWAY_FROM_ZERO" if rounded else "com.systema.modernized.runtime.CobolRoundingMode.TRUNCATION"
                    return f"{java_base}.assign({value_expr}, {rm}, com.systema.modernized.runtime.SizeErrorPolicy.UNCHECKED);"
                else:
                    return f"{java_base} = {value_expr};"

    def translate_statement(self, node) -> str:
        props = node.properties if hasattr(node, "properties") else node.get("properties", {})
        stype = props.get("statement_type", "").upper()
        
        java_stmt = self._translate_statement_inner(node)
        if java_stmt is None:
            return None
        if not java_stmt:
            return ""
            
        if self.current_generator is None:
            return java_stmt
            
        cleaned = java_stmt.strip()
        if cleaned.endswith("{") or cleaned == "}" or java_stmt.startswith("//") or (cleaned.startswith("}") and all(c in "}\n\r\t " for c in cleaned)):
            return java_stmt
            
        lines = java_stmt.splitlines()
        if len(lines) == 1:
            return f"if (!skipToNextSentence) {{ {java_stmt} }}"
        else:
            indented = "\n            ".join(lines)
            return f"if (!skipToNextSentence) {{\n            {indented}\n        }}"

    def wrap_math_with_size_error(self, tgt, val_expr, props, tgt_type, val_is_bigdecimal=True):
        on_size_nodes = props.get("on_size_error_nodes", [])
        not_size_nodes = props.get("not_on_size_error_nodes", [])

        tgt_base = re.split(r'\(', tgt)[0].strip()
        tgt_pic = self.current_generator.var_pics.get(tgt_base.upper(), "") if self.current_generator else ""
        if tgt_pic:
            _, digits, scale, signed = NativeTypeMapper.parse_pic(tgt_pic)
        else:
            digits, scale, signed = 18, 0, True

        rounded = props.get("rounded", False) if props else False
        rm = "com.systema.modernized.runtime.CobolRoundingMode.NEAREST_AWAY_FROM_ZERO" if rounded else "com.systema.modernized.runtime.CobolRoundingMode.TRUNCATION"

        # Check precision if division is involved (C2)
        prec_guard = ""
        if "com.systema.modernized.runtime.CobolArithmetic.divide(" in val_expr or (props and props.get("statement_type") == "DIVIDE"):
            prec_guard = f"com.systema.modernized.runtime.CobolArithmetic.checkPrecision({digits}, {scale});\n            "

        # Extract zero-division checks (C1)
        divisors = []
        if props and props.get("statement_type") == "DIVIDE":
            val = props.get("value", "")
            operand2 = props.get("operand2")
            divisor_var = operand2 if operand2 else val
            divisor_expr = self.translate_math_operand(divisor_var, tgt_type)
            divisors.append(divisor_expr)
        else:
            expr_str = str(val_expr)
            start = 0
            pattern = "com.systema.modernized.runtime.CobolArithmetic.divide("
            while True:
                idx = expr_str.find(pattern, start)
                if idx == -1:
                    break
                depth = 0
                comma_idx = -1
                for i in range(idx + len(pattern), len(expr_str)):
                    c = expr_str[i]
                    if c == '(':
                        depth += 1
                    elif c == ')':
                        if depth == 0:
                            if comma_idx != -1:
                                divisors.append(expr_str[comma_idx + 1:i].strip())
                            break
                        else:
                            depth -= 1
                    elif c == ',':
                        if depth == 0:
                            comma_idx = i
                start = idx + len(pattern)

        zero_checks = []
        for d in divisors:
            d_clean = d.strip()
            if tgt_type == "BigDecimal":
                zero_checks.append(f"({d_clean}).compareTo(BigDecimal.ZERO) == 0")
            else:
                zero_checks.append(f"({d_clean}) == 0")
        is_zero_expr = " || ".join(zero_checks) if zero_checks else ""

        # Map Java target base
        if tgt_base not in self.var_types and self.is_child and tgt_base in self.parent_global_vars:
            _, parent_path = self.parent_global_vars[tgt_base]
            java_base = f"{parent_path}.{to_java_var(tgt_base)}"
        else:
            java_base = to_java_var(tgt_base)

        match = re.match(r'^([A-Za-z0-9_-]+)\s*\(\s*([^()]+)\s*\)$', tgt)
        if match:
            idx = match.group(2).strip()
            if self.current_generator:
                for v in self.current_generator.var_types.keys():
                    idx = re.sub(r'(?<![A-Za-z0-9_-])' + re.escape(v) + r'(?![A-Za-z0-9_-])', to_java_var(v), idx)
                for v in self.current_generator.redefines_layout.keys():
                    if not self.current_generator.redefines_layout[v]["is_array"]:
                        idx = re.sub(r'\b' + re.escape(to_java_var(v)) + r'\b', f"get_{to_java_var(v)}()", idx)
            if idx.isdigit():
                subscript = f"{int(idx) - 1}"
            else:
                subscript = f"{idx} - 1"
            tgt_ref = f"{java_base}[{subscript}]"
        else:
            tgt_ref = java_base

        if tgt_type == "BigDecimal":
            # Real CobolNumeric variable assignment path
            if on_size_nodes or not_size_nodes:
                on_size_code = "\n            ".join(self.translate_statement(n) for n in on_size_nodes if self.translate_statement(n))
                not_size_code = "\n            ".join(self.translate_statement(n) for n in not_size_nodes if self.translate_statement(n))
                lines = [
                    "{",
                    f"    {prec_guard}"
                ]
                if is_zero_expr:
                    lines.append(f"    if ({is_zero_expr}) {{")
                    lines.append(f"        {on_size_code}")
                    lines.append("    } else {")
                    lines.append(f"        com.systema.modernized.runtime.AssignResult res = {tgt_ref}.assign({val_expr}, {rm}, com.systema.modernized.runtime.SizeErrorPolicy.CHECKED);")
                    lines.append("        if (res.sizeError) {")
                    lines.append(f"            {on_size_code}")
                    lines.append("        } else {")
                    lines.append(f"            {not_size_code}")
                    lines.append("        }")
                    lines.append("    }")
                else:
                    lines.append(f"    com.systema.modernized.runtime.AssignResult res = {tgt_ref}.assign({val_expr}, {rm}, com.systema.modernized.runtime.SizeErrorPolicy.CHECKED);")
                    lines.append("    if (res.sizeError) {")
                    lines.append(f"        {on_size_code}")
                    lines.append("    } else {")
                    lines.append(f"        {not_size_code}")
                    lines.append("    }")
                lines.append("}")
                return "\n        ".join(lines)
            else:
                if is_zero_expr:
                    lines = [
                        "{",
                        f"    {prec_guard}if (!({is_zero_expr})) {{",
                        f"        {tgt_ref}.assign({val_expr}, {rm}, com.systema.modernized.runtime.SizeErrorPolicy.UNCHECKED);",
                        "    }",
                        "}"
                    ]
                    return "\n        ".join(lines)
                else:
                    return f"{prec_guard}{tgt_ref}.assign({val_expr}, {rm}, com.systema.modernized.runtime.SizeErrorPolicy.UNCHECKED);"
        else:
            # Legacy integer/long target path
            on_size_code = "\n            ".join(self.translate_statement(n) for n in on_size_nodes if self.translate_statement(n))
            not_size_code = "\n            ".join(self.translate_statement(n) for n in not_size_nodes if self.translate_statement(n))
            cast_type = "int" if tgt_type == "Integer" else "long"
            
            signed_str = "true" if signed else "false"
            val_long_expr = f"({val_expr}).longValue()" if val_is_bigdecimal else f"({val_expr})"
            check_size_expr = f"checkSizeError({val_long_expr}, {digits}, {signed_str})"
            if is_zero_expr:
                size_cond = f"({is_zero_expr}) || {check_size_expr}"
            else:
                size_cond = check_size_expr
                
            limit_divisor = 10**digits
            assignment = f"{tgt_ref} = ({cast_type})({val_long_expr} % {limit_divisor}L);"
            
            if on_size_nodes or not_size_nodes:
                return f"{{\n        {prec_guard}if ({size_cond}) {{\n            {on_size_code}\n        }} else {{\n            {assignment}\n            {not_size_code}\n        }}\n    }}"
            else:
                if is_zero_expr:
                    return f"{{\n        {prec_guard}if (!({is_zero_expr})) {{\n            {assignment}\n        }}\n    }}"
                else:
                    return f"{prec_guard}{assignment}"

    def _translate_statement_inner(self, node) -> str:
        props = node.properties if hasattr(node, "properties") else node.get("properties", {})
        stype = props.get("statement_type", "").upper()
        
        if stype == "MOVE":
            src = props.get("source", "")
            raw_tgt = props.get("targets") or props.get("target")
            targets = raw_tgt if isinstance(raw_tgt, list) else ([raw_tgt] if raw_tgt else [])
            
            assignments = []
            for tgt in targets:
                tgt_type = self._get_var_type(tgt, "String")
                
                src_upper = src.upper()
                if "FUNCTION" in src_upper and "(" in src:
                    java_src = self.expr_trans.translate(src)
                    if tgt_type == "Integer":
                        java_src = f"({java_src}).intValue()"
                    elif tgt_type == "Long":
                        java_src = f"({java_src}).longValue()"
                    assignments.append(self.generate_assignment(tgt, java_src))
                    continue
                if src_upper in self.constants_map:
                    const_val = self.constants_map[src_upper]
                    if isinstance(const_val, str) and (const_val.startswith("'") or const_val.startswith('"')):
                        java_src = f"\"{const_val[1:-1]}\""
                    elif isinstance(const_val, str):
                        java_src = f"\"{const_val}\""
                    else:
                        java_src = str(const_val)
                elif src_upper in ("SPACE", "SPACES"):
                    java_src = '""'
                elif src_upper in ("ZERO", "ZEROS", "ZEROES"):
                    java_src = 'BigDecimal.ZERO' if tgt_type == "BigDecimal" else "0"
                    tgt_pic = self.current_generator.var_pics.get(re.split(r'\(', tgt)[0].strip(), "") if self.current_generator else ""
                    if tgt_type == "String" and "Z" in tgt_pic.upper():
                        _, length, _, _ = NativeTypeMapper.parse_pic(tgt_pic)
                        java_src = f"String.format(\"%{length}d\", 0)"
                elif src_upper in ("HIGH-VALUE", "HIGH-VALUES"):
                    java_src = '"\\uFFFF"'
                elif src.startswith("'") or src.startswith('"'):
                    java_str = '"' + src[1:-1] + '"'
                    if tgt_type in ("Integer", "Long", "int", "long"):
                        parse_method = "parseLongSafe" if tgt_type in ("Long", "long") else "parseIntSafe"
                        java_src = f"com.systema.modernized.CobolFormatHelper.{parse_method}({java_str})"
                    elif tgt_type == "BigDecimal":
                        java_src = (
                            f"({java_str} == null || {java_str}.trim().isEmpty()) ? BigDecimal.ZERO : "
                            f"({java_str}.trim().contains(\".\")) ? new BigDecimal({java_str}.trim()) : "
                            f"new BigDecimal({java_str}.trim())"
                        )
                    else:
                        java_src = java_str
                elif re.match(r'^[+-]?\d+(\.\d+)?$', src):
                    if tgt_type == "BigDecimal":
                        java_src = f"new BigDecimal(\"{src}\")"
                    elif tgt_type in ("Integer", "Long"):
                        java_src = src + "L" if tgt_type == "Long" else src
                    else:
                        tgt_pic = self.current_generator.var_pics.get(re.split(r'\(', tgt)[0].strip(), "") if self.current_generator else ""
                        if tgt_type == "String" and "Z" in tgt_pic.upper():
                            _, length, _, _ = NativeTypeMapper.parse_pic(tgt_pic)
                            java_src = f"String.format(\"%{length}d\", {src})"
                        else:
                            java_src = f"\"{src}\""
                elif self._is_variable(src):
                    java_src = self.translate_math_operand(src, tgt_type)
                    src_type = self._get_var_type(src, "String")
                    if tgt_type == "BigDecimal" and src_type in ("Integer", "Long"):
                        java_src = f"BigDecimal.valueOf({java_src})"
                    elif tgt_type == "BigDecimal" and src_type == "String":
                        tgt_base = re.split(r'\(', tgt)[0].strip()
                        tgt_pic = self.current_generator.var_pics.get(tgt_base.upper(), "") if self.current_generator else ""
                        scale = 0
                        if tgt_pic:
                            _, _, scale, _ = NativeTypeMapper.parse_pic(tgt_pic)
                        if scale > 0:
                            java_src = (
                                f"({java_src} == null || {java_src}.trim().isEmpty()) ? BigDecimal.ZERO : "
                                f"({java_src}.trim().contains(\".\")) ? new BigDecimal({java_src}.trim()) : new BigDecimal({java_src}.trim()).movePointLeft({scale})"
                            )
                        else:
                            java_src = f"({java_src} == null || {java_src}.trim().isEmpty()) ? BigDecimal.ZERO : new BigDecimal({java_src}.trim())"
                    elif tgt_type in ("Integer", "Long", "int", "long") and src_type == "String":
                        parse_method = "parseLongSafe" if tgt_type in ("Long", "long") else "parseIntSafe"
                        java_src = f"com.systema.modernized.CobolFormatHelper.{parse_method}({java_src})"
                    elif tgt_type == "String" and src_type != "String":
                        tgt_base = re.split(r'\(', tgt)[0].strip().upper()
                        tgt_pic = self.current_generator.var_pics.get(tgt_base, "") if self.current_generator else ""
                        is_tgt_edited = getattr(self.current_generator, "var_edited", {}).get(tgt_base, False) if self.current_generator else False
                        if "Z" in tgt_pic.upper() and not is_tgt_edited:
                            _, length, _, _ = NativeTypeMapper.parse_pic(tgt_pic)
                            java_src = f"String.format(\"%{length}d\", {java_src})"
                        else:
                            java_src = f"String.valueOf({java_src})"
                else:
                    java_src = f"\"{src}\""
                
                assignments.append(self.generate_assignment(tgt, java_src))
            
            return "\n        ".join(assignments) if assignments else ""
 
        elif stype == "MOVE_CORRESPONDING":
            src = props.get("source", "")
            raw_tgt = props.get("targets") or props.get("target")
            targets = raw_tgt if isinstance(raw_tgt, list) else ([raw_tgt] if raw_tgt else [])
            
            lines = []
            for tgt in targets:
                corr_str = self._generate_corresponding_statements("MOVE", src, tgt)
                if corr_str:
                    lines.append(corr_str)
            return "\n        ".join(lines) if lines else ""

        elif stype == "COMPUTE":
            tgt = props.get("target", "")
            expr = props.get("expression", "")
            tgt_type = self._get_var_type(tgt, "BigDecimal")
            translated_expr = self.expr_trans.translate(expr)
            return self.wrap_math_with_size_error(tgt, translated_expr, props, tgt_type, val_is_bigdecimal=True)

        elif stype in ("ADD_CORRESPONDING", "SUBTRACT_CORRESPONDING"):
            val = props.get("value", "")
            raw_targets = props.get("targets") or props.get("target")
            targets_list = raw_targets if isinstance(raw_targets, list) else ([raw_targets] if raw_targets else [])
            
            op = "ADD" if stype == "ADD_CORRESPONDING" else "SUBTRACT"
            
            lines = []
            for tgt_info in targets_list:
                tgt = tgt_info["name"] if isinstance(tgt_info, dict) else tgt_info
                corr_str = self._generate_corresponding_statements(op, val, tgt)
                if corr_str:
                    lines.append(corr_str)
            return "\n        ".join(lines) if lines else ""

        elif stype in ("ADD", "SUBTRACT", "MULTIPLY", "DIVIDE"):
            val = props.get("value", "")
            raw_targets = props.get("targets") or props.get("target")
            targets_list = raw_targets if isinstance(raw_targets, list) else ([raw_targets] if raw_targets else [])
            operand2 = props.get("operand2")

            stmts = []
            for cur_tgt_info in targets_list:
                cur_tgt = cur_tgt_info["name"] if isinstance(cur_tgt_info, dict) else cur_tgt_info
                cur_tgt_rounded = cur_tgt_info.get("rounded", False) if isinstance(cur_tgt_info, dict) else False
                
                tgt_type = self._get_var_type(cur_tgt, "BigDecimal")
                java_tgt_read = self.translate_math_operand(cur_tgt, tgt_type)

                if re.match(r'^\d+(\.\d+)?$', val):
                    if tgt_type == "BigDecimal":
                        java_val = f"new BigDecimal(\"{val}\")"
                    elif tgt_type == "Long" and val.isdigit():
                        java_val = val + "L"
                    else:
                        java_val = val
                else:
                    java_val = self.translate_math_operand(val, tgt_type)

                if operand2:
                    java_op2 = self.translate_math_operand(operand2, tgt_type)
                    if stype == "ADD":
                        val_expr = f"com.systema.modernized.runtime.CobolArithmetic.add({java_val}, {java_op2})" if tgt_type == "BigDecimal" else f"{java_val} + {java_op2}"
                    elif stype == "SUBTRACT":
                        val_expr = f"com.systema.modernized.runtime.CobolArithmetic.subtract({java_op2}, {java_val})" if tgt_type == "BigDecimal" else f"{java_op2} - {java_val}"
                    elif stype == "MULTIPLY":
                        val_expr = f"com.systema.modernized.runtime.CobolArithmetic.multiply({java_val}, {java_op2})" if tgt_type == "BigDecimal" else f"{java_val} * {java_op2}"
                    else:
                        val_expr = f"com.systema.modernized.runtime.CobolArithmetic.divide({java_val}, {java_op2})" if tgt_type == "BigDecimal" else f"{java_val} / {java_op2}"
                else:
                    if stype == "ADD":
                        val_expr = f"com.systema.modernized.runtime.CobolArithmetic.add({java_tgt_read}, {java_val})" if tgt_type == "BigDecimal" else f"{java_tgt_read} + {java_val}"
                    elif stype == "SUBTRACT":
                        val_expr = f"com.systema.modernized.runtime.CobolArithmetic.subtract({java_tgt_read}, {java_val})" if tgt_type == "BigDecimal" else f"{java_tgt_read} - {java_val}"
                    elif stype == "MULTIPLY":
                        val_expr = f"com.systema.modernized.runtime.CobolArithmetic.multiply({java_tgt_read}, {java_val})" if tgt_type == "BigDecimal" else f"{java_tgt_read} * {java_val}"
                    else:
                        val_expr = f"com.systema.modernized.runtime.CobolArithmetic.divide({java_tgt_read}, {java_val})" if tgt_type == "BigDecimal" else f"{java_tgt_read} / {java_val}"

                cur_props = dict(props)
                cur_props["rounded"] = cur_tgt_rounded
                stmts.append(self.wrap_math_with_size_error(cur_tgt, val_expr, cur_props, tgt_type, val_is_bigdecimal=(tgt_type == "BigDecimal")))

                # Remainder translation block
                if props.get("remainder"):
                    rem_tgt = props.get("remainder")
                    rem_type = self._get_var_type(rem_tgt, "BigDecimal")
                    
                    rem_div = f"BigDecimal.valueOf({java_val})" if tgt_type != "BigDecimal" else java_val
                    rem_op2 = f"BigDecimal.valueOf({java_op2})" if tgt_type != "BigDecimal" else java_op2
                    rem_tgt_q = f"BigDecimal.valueOf({java_tgt_read})" if tgt_type != "BigDecimal" else java_tgt_read
                    
                    if rem_type == "BigDecimal":
                        rem_val_expr = f"com.systema.modernized.runtime.CobolArithmetic.remainder({rem_div}, {rem_op2}, {rem_tgt_q})"
                    else:
                        rem_val_expr = f"{java_val} % {java_op2}"
                    
                    rem_props = {
                        "statement_type": "DIVIDE_REMAINDER",
                        "rounded": False,
                        "on_size_error_nodes": [],
                        "not_on_size_error_nodes": []
                    }
                    stmts.append(self.wrap_math_with_size_error(rem_tgt, rem_val_expr, rem_props, rem_type, val_is_bigdecimal=(rem_type == "BigDecimal")))

            return "\n        ".join(stmts) if stmts else ""

        elif stype == "IF":
            # Handle both full IR IF nodes and raw-token IF nodes captured inside AT-END clauses.
            raw_tokens = props.get("raw_tokens")
            if raw_tokens is not None:
                # raw_tokens is the token list between IF...END-IF.
                # Reconstruct a simple Java condition and body from it.
                tokens_str = " ".join(raw_tokens)
                cond = self._translate_condition(tokens_str)
                return f"if ({cond}) {{"
            cond = self._translate_condition(props.get("condition", ""))
            return f"if ({cond}) {{"
            
        elif stype == "ELSE":
            return "} else {"
            
        elif stype == "END-IF":
            return "}"

        elif stype == "PERFORM_UNTIL":
            cond = self._translate_condition(props.get("condition", ""))
            return f"while (!({cond}) && !programExited) {{"

        elif stype == "PERFORM_VARYING":
            idx = props.get("index", "")
            from_val = props.get("from_value", "1")
            by_val = props.get("by_value", "1")
            cond = props.get("condition", "")
            
            loops = []
            loops.append(self._make_loop_header(idx, from_val, by_val, cond))
            
            after_clauses = props.get("after_clauses", [])
            for acl in after_clauses:
                a_idx = acl["index"]
                a_from = acl["from_value"]
                a_by = acl["by_value"]
                a_cond = acl["condition"]
                loops.append("    " * len(loops) + self._make_loop_header(a_idx, a_from, a_by, a_cond))
                
            self.loop_braces_stack.append(len(loops))
            return "\n        ".join(loops)
 
        elif stype == "END-PERFORM":
            num_braces = self.loop_braces_stack.pop() if self.loop_braces_stack else 1
            braces = []
            for i in reversed(range(num_braces)):
                if i == num_braces - 1:
                    indent = "    " * i
                else:
                    indent = "        " + "    " * i
                braces.append(f"{indent}}}")
            return "\n".join(braces)
 
        elif stype == "PERFORM":
            tgt = props.get("target", "")
            thru = props.get("thru", None)
            java_tgt = to_java_var(tgt)
            java_thru = to_java_var(thru) if thru else None
            if java_thru:
                return f"perform(\"{java_tgt}\", \"{java_thru}\");\n        if (nextParagraphIndex != -1 || programExited) return;"
            else:
                return f"perform(\"{java_tgt}\", null);\n        if (nextParagraphIndex != -1 || programExited) return;"
 
        elif stype == "PERFORM_UNTIL_OUT":
            tgt = props.get("target", "")
            thru = props.get("thru", None)
            cond = self._translate_condition(props.get("condition", ""))
            java_tgt = to_java_var(tgt)
            java_thru = f"\"{to_java_var(thru)}\"" if thru else "null"
            return f"while (!({cond}) && !programExited) {{\n            perform(\"{java_tgt}\", {java_thru});\n            if (nextParagraphIndex != -1 || programExited) return;\n        }}"
 
        elif stype == "PERFORM_VARYING_OUT":
            tgt = props.get("target", "")
            thru = props.get("thru", None)
            idx = props.get("index", "")
            from_val = props.get("from_value", "1")
            by_val = props.get("by_value", "1")
            cond = props.get("condition", "")
            java_tgt = to_java_var(tgt)
            java_thru = f"\"{to_java_var(thru)}\"" if thru else "null"
            
            loops = []
            loops.append(self._make_loop_header(idx, from_val, by_val, cond))
            
            after_clauses = props.get("after_clauses", [])
            for acl in after_clauses:
                a_idx = acl["index"]
                a_from = acl["from_value"]
                a_by = acl["by_value"]
                a_cond = acl["condition"]
                loops.append(self._make_loop_header(a_idx, a_from, a_by, a_cond))
                
            body = f"perform(\"{java_tgt}\", {java_thru});\n"
            body += "if (nextParagraphIndex != -1 || programExited) return;"
            
            for i in reversed(range(len(loops))):
                header = loops[i]
                indent = "        " + "    " * i
                body_indented = "\n".join(indent + "    " + line for line in body.splitlines())
                body = f"{indent}{header}\n{body_indented}\n{indent}}}"
                
            return body.strip()

        elif stype == "OPEN":
            open_calls = []
            targets = props.get("targets", [])
            if not targets and props.get("target"):
                targets = [props.get("target")]
                
            curr_mode = "INPUT"
            for t in targets:
                t_upper = t.upper()
                if t_upper in ("INPUT", "OUTPUT", "I-O", "EXTEND"):
                    curr_mode = t_upper
                    continue
                
                org = "SEQUENTIAL"
                if self.current_generator:
                    org = self.current_generator.file_orgs.get(t_upper, "SEQUENTIAL")
                
                open_calls.append(f"open_{to_java_var(t)}(\"{curr_mode}\");")
            return "\n        ".join(open_calls)

        elif stype == "CLOSE":
            close_calls = []
            targets = props.get("targets", [])
            if not targets and props.get("target"):
                targets = [props.get("target")]
                
            for t in targets:
                t_upper = t.upper()
                if t_upper in ("INPUT", "OUTPUT", "I-O", "EXTEND"):
                    # skip mode keywords if any slip in
                    continue
                close_calls.append(f"close_{to_java_var(t)}();")
            return "\n        ".join(close_calls)

        elif stype in ("SORT", "MERGE"):
            wf = props.get("work_file", "").upper()
            wf_lower = to_java_var(wf)
            keys = props.get("keys", [])
            using_files = props.get("using_files", [])
            giving_files = props.get("giving_files", [])
            input_procedure = props.get("input_procedure")
            output_procedure = props.get("output_procedure")
            
            lines = []
            lines.append(f"{wf_lower}_list.clear();")
            lines.append(f"{wf_lower}_idx = 0;")
            
            sd_fields = []
            if self.current_generator:
                sd_fields = self.current_generator.fd_fields.get(wf, [])
                
            if using_files:
                for uf in using_files:
                    uf_upper = uf.upper()
                    uf_lower = to_java_var(uf)
                    lines.append(f"open_{uf_lower}();")
                    lines.append(f"while (read_{uf_lower}()) {{")
                    
                    in_fields = []
                    if self.current_generator:
                        in_fields = self.current_generator.fd_fields.get(uf_upper, [])
                        
                    in_offsets = []
                    curr = 0
                    for f, pic in in_fields:
                        _, length, _, _ = NativeTypeMapper.parse_pic(pic)
                        in_offsets.append((f, curr, curr + length))
                        curr += length
                        
                    sd_offsets = []
                    curr = 0
                    for f, pic in sd_fields:
                        _, length, _, _ = NativeTypeMapper.parse_pic(pic)
                        sd_offsets.append((f, curr, curr + length))
                        curr += length
                        
                    for sd_f, sd_s, sd_e in sd_offsets:
                        for in_f, in_s, in_e in in_offsets:
                            if sd_s == in_s and sd_e == in_e:
                                lines.append(f"    {to_java_var(sd_f)} = {to_java_var(in_f)};")
                                break
                    
                    lines.append(f"    java.util.Map<String, Object> rec = new java.util.HashMap<>();")
                    for sd_f, _ in sd_fields:
                        lines.append(f"    rec.put(\"{sd_f.upper()}\", {to_java_var(sd_f)});")
                    lines.append(f"    {wf_lower}_list.add(rec);")
                    lines.append(f"}}")
                    lines.append(f"close_{uf_lower}();")
            elif input_procedure:
                if " THRU " in input_procedure:
                    parts = input_procedure.split(" THRU ")
                    lines.append(f"perform(\"{to_java_var(parts[0])}\", \"{to_java_var(parts[1])}\");")
                else:
                    lines.append(f"perform(\"{to_java_var(input_procedure)}\", null);")
            
            cmp_body = []
            for k in keys:
                k_name = k["name"].upper()
                order = k["order"].upper()
                
                t = self.var_types.get(k_name, "String")
                if t == "BigDecimal":
                    cmp_expr = f"((BigDecimal)r1.get(\"{k_name}\")).compareTo((BigDecimal)r2.get(\"{k_name}\"))"
                elif t in ("Integer", "Long"):
                    cmp_expr = f"Long.compare(((Number)r1.get(\"{k_name}\")).longValue(), ((Number)r2.get(\"{k_name}\")).longValue())"
                else:
                    cmp_expr = f"((String)r1.get(\"{k_name}\")).compareTo((String)r2.get(\"{k_name}\"))"
                    
                if order == "DESCENDING":
                    cmp_expr = f"-({cmp_expr})"
                cmp_body.append(f"        int cmp_{to_java_var(k_name)} = {cmp_expr};")
                cmp_body.append(f"        if (cmp_{to_java_var(k_name)} != 0) return cmp_{to_java_var(k_name)};")
            
            lines.append(f"{wf_lower}_list.sort((r1, r2) -> {{")
            for cb in cmp_body:
                lines.append(cb)
            lines.append("        return 0;")
            lines.append("});")
            
            if giving_files:
                for gf in giving_files:
                    gf_upper = gf.upper()
                    gf_lower = to_java_var(gf)
                    lines.append(f"open_{gf_lower}();")
                    lines.append(f"for (java.util.Map<String, Object> rec : {wf_lower}_list) {{")
                    
                    out_fields = []
                    if self.current_generator:
                        out_fields = self.current_generator.fd_fields.get(gf_upper, [])
                        
                    out_offsets = []
                    curr = 0
                    for f, pic in out_fields:
                        _, length, _, _ = NativeTypeMapper.parse_pic(pic)
                        out_offsets.append((f, curr, curr + length))
                        curr += length
                        
                    sd_offsets = []
                    curr = 0
                    for f, pic in sd_fields:
                        _, length, _, _ = NativeTypeMapper.parse_pic(pic)
                        sd_offsets.append((f, curr, curr + length))
                        curr += length
                        
                    for sd_f, sd_s, sd_e in sd_offsets:
                        sd_f_upper = sd_f.upper()
                        t = self.var_types.get(sd_f_upper, "String")
                        cast = t if t in ("BigDecimal", "Integer", "Long") else "String"
                        lines.append(f"    {to_java_var(sd_f)} = ({cast}) rec.get(\"{sd_f_upper}\");")
                        
                        for out_f, out_s, out_e in out_offsets:
                            if out_s == sd_s and out_e == sd_e:
                                lines.append(f"    {to_java_var(out_f)} = {to_java_var(sd_f)};")
                                break
                    lines.append(f"    write_{gf_lower}();")
                    lines.append(f"}}")
                    lines.append(f"close_{gf_lower}();")
            elif output_procedure:
                if " THRU " in output_procedure:
                    parts = output_procedure.split(" THRU ")
                    lines.append(f"perform(\"{to_java_var(parts[0])}\", \"{to_java_var(parts[1])}\");")
                else:
                    lines.append(f"perform(\"{to_java_var(output_procedure)}\", null);")
            
            return "\n        ".join(lines)

        elif stype == "RELEASE":
            rec_name = props.get("record_name", "").upper()
            from_val = props.get("from_val")
            
            wf = self.record_to_fd.get(rec_name)
            if not wf and self.current_generator:
                for fd_name, fields in self.current_generator.fd_fields.items():
                    if rec_name in [f[0].upper() for f in fields]:
                        wf = fd_name
                        break
            if not wf:
                wf = rec_name
            wf_upper = wf.upper()
            wf_lower = to_java_var(wf)
            
            lines = []
            if from_val:
                lines.append(self.generate_assignment(rec_name, from_val))
                
            sd_fields = []
            if self.current_generator:
                sd_fields = self.current_generator.fd_fields.get(wf_upper, [])
            lines.append("java.util.Map<String, Object> rec = new java.util.HashMap<>();")
            for sd_f, _ in sd_fields:
                lines.append(f"rec.put(\"{sd_f.upper()}\", {to_java_var(sd_f)});")
            lines.append(f"{wf_lower}_list.add(rec);")
            return "\n        ".join(lines)

        elif stype == "RETURN":
            wf = props.get("work_file", "").upper()
            wf_lower = to_java_var(wf)
            into_val = props.get("into_val")
            at_end_action = props.get("at_end_action")
            
            lines = []
            lines.append(f"if ({wf_lower}_idx < {wf_lower}_list.size()) {{")
            lines.append(f"    java.util.Map<String, Object> rec = {wf_lower}_list.get({wf_lower}_idx++);")
            
            sd_fields = []
            if self.current_generator:
                sd_fields = self.current_generator.fd_fields.get(wf, [])
            for sd_f, _ in sd_fields:
                sd_f_upper = sd_f.upper()
                t = self.var_types.get(sd_f_upper, "String")
                cast = t if t in ("BigDecimal", "Integer", "Long") else "String"
                lines.append(f"    {to_java_var(sd_f)} = ({cast}) rec.get(\"{sd_f_upper}\");")
                
            if into_val:
                rec_var = to_java_var(sd_fields[0][0]) if sd_fields else wf_lower
                lines.append(f"    {to_java_var(into_val)} = {rec_var};")
            lines.append(f"}} else {{")
            
            if at_end_action:
                if at_end_action.startswith("MOVE "):
                    parts = at_end_action.split(" TO ")
                    src = parts[0][5:].strip()
                    tgt = parts[1].strip()
                    lines.append(f"    {self.generate_assignment(tgt, src)}")
                elif at_end_action.startswith("SET "):
                    parts = at_end_action.split(" TO ")
                    tgt = parts[0][4:].strip()
                    src = parts[1].strip()
                    lines.append(f"    {self.generate_assignment(tgt, src)}")
            lines.append(f"}}")
            return "\n        ".join(lines)

        elif stype == "SET":
            ref_vars = getattr(self.current_generator, "ref_vars", set())
            is_address_of_target = props.get("is_address_of_target")
            target_var = props.get("target_var", "")
            is_address_of_source = props.get("is_address_of_source")
            source_var = props.get("source_var", "")
            
            target_var_upper = target_var.upper()
            source_var_upper = str(source_var).upper()
            
            java_tgt = to_java_var(target_var)
            java_src = to_java_var(str(source_var))
            
            if is_address_of_target:
                if is_address_of_source:
                    if source_var_upper in ref_vars:
                        return f"{java_tgt}_ref = {java_src}_ref;"
                    else:
                        t = self.var_types.get(source_var_upper, "String")
                        return f"{java_tgt}_ref = new com.systema.modernized.CobolRef<{t}>(() -> {java_src}, val -> {java_src} = val);"
                else:
                    t = self.var_types.get(target_var_upper, "String")
                    return f"{java_tgt}_ref = (com.systema.modernized.CobolRef<{t}>) {java_src};"
            else:
                if is_address_of_source:
                    if source_var_upper in ref_vars:
                        return f"{java_tgt} = {java_src}_ref;"
                    else:
                        t = self.var_types.get(source_var_upper, "String")
                        return f"{java_tgt} = new com.systema.modernized.CobolRef<{t}>(() -> {java_src}, val -> {java_src} = val);"
                elif source_var_upper == "TRUE":
                    if target_var_upper in self.level88_map:
                        parent_name, values = self.level88_map[target_var_upper]
                        val = values[0] if values else "true"
                        return self.generate_assignment(parent_name, val)
                    else:
                        return f"// WARNING: Unknown 88 condition {target_var} in SET TO TRUE"
                elif source_var_upper == "FALSE":
                    if target_var_upper in self.level88_map:
                        parent_name, values = self.level88_map[target_var_upper]
                        val = "false"
                        return self.generate_assignment(parent_name, val)
                    else:
                        return f"// WARNING: Unknown 88 condition {target_var} in SET TO FALSE"
                else:
                    return self.generate_assignment(target_var, source_var)

        elif stype == "INITIATE":
            rd = props.get("report_name", "").upper()
            rd_lower = to_java_var(rd)
            lines = []
            lines.append(f"{rd_lower}_page_number = 1;")
            lines.append(f"{rd_lower}_line_number = 1;")
            sums = getattr(self.current_generator, "report_sum_fields", {}).get(rd, set())
            for s in sums:
                lines.append(f"sum_{to_java_var(s)} = BigDecimal.ZERO;")
                
            ph_group = None
            if self.current_generator:
                for g_node in self.current_generator.reports.get(rd, []):
                    if g_node.properties.get("report_type") == "PAGE HEADING":
                        ph_group = g_node.properties.get("name", "").upper()
                        break
            if ph_group:
                lines.append(f"print_report_group(\"{ph_group}\");")
                lines.append(f"{rd_lower}_line_number += 1;")
            return "\n        ".join(lines)
            
        elif stype == "GENERATE":
            target = props.get("target", "").upper()
            rd = None
            if self.current_generator:
                for r_name, groups in self.current_generator.reports.items():
                    if target in [g.properties.get("name", "").upper() for g in groups] or target == r_name:
                        rd = r_name
                        break
            if not rd:
                return f"// WARNING: Unknown GENERATE target {target}"
                
            rd_lower = to_java_var(rd)
            lines = []
            
            ph_group = None
            pf_group = None
            if self.current_generator:
                for g_node in self.current_generator.reports.get(rd, []):
                    if g_node.properties.get("report_type") == "PAGE HEADING":
                        ph_group = g_node.properties.get("name", "").upper()
                    elif g_node.properties.get("report_type") == "PAGE FOOTING":
                        pf_group = g_node.properties.get("name", "").upper()
                        
            lines.append(f"if ({rd_lower}_line_number > 5) {{")
            if pf_group:
                lines.append(f"    print_report_group(\"{pf_group}\");")
            lines.append(f"    {rd_lower}_page_number++;")
            lines.append(f"    {rd_lower}_line_number = 1;")
            if ph_group:
                lines.append(f"    print_report_group(\"{ph_group}\");")
                lines.append(f"    {rd_lower}_line_number++;")
            lines.append(f"}}")
            
            is_detail = False
            if self.current_generator:
                for g_node in self.current_generator.reports.get(rd, []):
                    if g_node.properties.get("name", "").upper() == target and g_node.properties.get("report_type") == "DETAIL":
                        is_detail = True
                        break
            if is_detail:
                lines.append(f"print_report_group(\"{target}\");")
                lines.append(f"{rd_lower}_line_number++;")
                
            sums = getattr(self.current_generator, "report_sum_fields", {}).get(rd, set())
            for s in sums:
                t = self.var_types.get(s, "String")
                if t == "BigDecimal":
                    lines.append(f"sum_{to_java_var(s)} = sum_{to_java_var(s)}.add({to_java_var(s)});")
                elif t in ("Integer", "Long"):
                    lines.append(f"sum_{to_java_var(s)} = sum_{to_java_var(s)}.add(new BigDecimal({to_java_var(s)}));")
                else:
                    lines.append(f"try {{ sum_{to_java_var(s)} = sum_{to_java_var(s)}.add(new BigDecimal({to_java_var(s)}.trim())); }} catch (Exception e) {{}}")
                    
            return "\n        ".join(lines)
            
        elif stype == "TERMINATE":
            rd = props.get("report_name", "").upper()
            pf_group = None
            if self.current_generator:
                for g_node in self.current_generator.reports.get(rd, []):
                    if g_node.properties.get("report_type") == "PAGE FOOTING":
                        pf_group = g_node.properties.get("name", "").upper()
                        break
            lines = []
            if pf_group:
                lines.append(f"print_report_group(\"{pf_group}\");")
            return "\n        ".join(lines)

        elif stype == "READ":
            tgt = props.get("target", "")
            into_target = props.get("into_target")
            at_end_nodes = props.get("at_end_nodes", [])
            not_at_end_nodes = props.get("not_at_end_nodes", [])
            invalid_key_nodes = props.get("invalid_key_nodes", [])
            not_invalid_key_nodes = props.get("not_invalid_key_nodes", [])
            
            java_tgt = to_java_var(tgt)
            
            rec_name = None
            for r, fd in self.record_to_fd.items():
                if fd.upper() == tgt.upper():
                    rec_name = r
                    break
            if not rec_name:
                rec_name = tgt
                
            org = "SEQUENTIAL"
            access_mode = "SEQUENTIAL"
            record_key = None
            if self.current_generator:
                org = self.current_generator.file_orgs.get(tgt.upper(), "SEQUENTIAL")
                access_mode = self.current_generator.file_access_modes.get(tgt.upper(), "SEQUENTIAL")
                record_key = self.current_generator.file_keys.get(tgt.upper())
                
            is_keyed = (org in ("INDEXED", "RELATIVE") and access_mode in ("RANDOM", "DYNAMIC") and not props.get("is_next", False))
            
            key_to_use = props.get("key_name")
            if not key_to_use:
                key_to_use = record_key
            
            key_expr = "null"
            if key_to_use:
                key_jvar = to_java_var(key_to_use)
                if self.current_generator and key_to_use.upper() in self.current_generator.redefines_layout:
                    key_expr = f"String.valueOf(get_{key_jvar}())"
                else:
                    key_expr = f"String.valueOf({key_jvar})"
            
            key_name_param = f"\"{key_to_use.upper()}\"" if key_to_use else "\"\""
            
            if not at_end_nodes and not not_at_end_nodes and not invalid_key_nodes and not not_invalid_key_nodes and not into_target:
                if is_keyed:
                    return f"read_{java_tgt}_key({key_expr}, {key_name_param});"
                else:
                    return f"read_{java_tgt}();"
                    
            lines = []
            if is_keyed:
                lines.append(f"if (!read_{java_tgt}_key({key_expr}, {key_name_param})) {{")
                for node in invalid_key_nodes:
                    stmt_str = self.translate_statement(node)
                    if stmt_str:
                        lines.append(f"    {stmt_str}")
                lines.append("} else {")
                if into_target:
                    java_rec = to_java_var(rec_name)
                    lines.append(f"    {self.generate_assignment(into_target, java_rec)}")
                for node in not_invalid_key_nodes:
                    stmt_str = self.translate_statement(node)
                    if stmt_str:
                        lines.append(f"    {stmt_str}")
                lines.append("}")
                return "\n        ".join(lines)
            else:
                lines.append(f"if (!read_{java_tgt}()) {{")
                for node in at_end_nodes:
                    stmt_str = self.translate_statement(node)
                    if stmt_str:
                        lines.append(f"    {stmt_str}")
                lines.append("} else {")
                if into_target:
                    java_rec = to_java_var(rec_name)
                    lines.append(f"    {self.generate_assignment(into_target, java_rec)}")
                for node in not_at_end_nodes:
                    stmt_str = self.translate_statement(node)
                    if stmt_str:
                        lines.append(f"    {stmt_str}")
                lines.append("}")
                return "\n        ".join(lines)

        elif stype == "WRITE":
            tgt = props.get("target", "")
            from_source = props.get("from_source")
            invalid_key_nodes = props.get("invalid_key_nodes", [])
            not_invalid_key_nodes = props.get("not_invalid_key_nodes", [])
            
            matched_fd = self._get_matched_fd(tgt)
            java_tgt = to_java_var(matched_fd)
            
            org = "SEQUENTIAL"
            if self.current_generator:
                org = self.current_generator.file_orgs.get(matched_fd.upper(), "SEQUENTIAL")
                
            lines = []
            if from_source:
                # Literal sources (quoted strings / numerics) pass through
                # verbatim — never mangled into a variable name.
                if (from_source.startswith("'") or from_source.startswith('"')
                        or re.fullmatch(r"[0-9]+(\.[0-9]+)?", str(from_source))):
                    java_src = from_source
                else:
                    java_src = to_java_var(from_source)
                lines.append(self.generate_assignment(tgt, java_src))

            if org in ("INDEXED", "RELATIVE") and (invalid_key_nodes or not_invalid_key_nodes):
                lines.append(f"if (!write_{java_tgt}()) {{")
                for node in invalid_key_nodes:
                    stmt_str = self.translate_statement(node)
                    if stmt_str:
                        lines.append(f"    {stmt_str}")
                lines.append("} else {")
                for node in not_invalid_key_nodes:
                    stmt_str = self.translate_statement(node)
                    if stmt_str:
                        lines.append(f"    {stmt_str}")
                lines.append("}")
            else:
                lines.append(f"write_{java_tgt}();")
            return "\n        ".join(lines)

        elif stype == "REWRITE":
            tgt = props.get("target", "")
            from_source = props.get("from_source")
            invalid_key_nodes = props.get("invalid_key_nodes", [])
            not_invalid_key_nodes = props.get("not_invalid_key_nodes", [])
            
            matched_fd = self._get_matched_fd(tgt)
            java_tgt = to_java_var(matched_fd)
            
            org = "SEQUENTIAL"
            if self.current_generator:
                org = self.current_generator.file_orgs.get(matched_fd.upper(), "SEQUENTIAL")
                
            lines = []
            if from_source:
                if (from_source.startswith("'") or from_source.startswith('"')
                        or re.fullmatch(r"[0-9]+(\.[0-9]+)?", str(from_source))):
                    java_src = from_source
                else:
                    java_src = to_java_var(from_source)
                java_rec = to_java_var(tgt)
                lines.append(f"{java_rec} = {java_src};")

            if org in ("INDEXED", "RELATIVE") and (invalid_key_nodes or not_invalid_key_nodes):
                lines.append(f"if (!rewrite_{java_tgt}()) {{")
                for node in invalid_key_nodes:
                    stmt_str = self.translate_statement(node)
                    if stmt_str:
                        lines.append(f"    {stmt_str}")
                lines.append("} else {")
                for node in not_invalid_key_nodes:
                    stmt_str = self.translate_statement(node)
                    if stmt_str:
                        lines.append(f"    {stmt_str}")
                lines.append("}")
            else:
                if org in ("INDEXED", "RELATIVE"):
                    lines.append(f"rewrite_{java_tgt}();")
                else:
                    lines.append(f"write_{java_tgt}();")
            return "\n        ".join(lines)

        elif stype == "DELETE":
            tgt = props.get("target", "")
            invalid_key_nodes = props.get("invalid_key_nodes", [])
            not_invalid_key_nodes = props.get("not_invalid_key_nodes", [])
            
            java_tgt = to_java_var(tgt)
            org = "SEQUENTIAL"
            access_mode = "SEQUENTIAL"
            record_key = None
            if self.current_generator:
                org = self.current_generator.file_orgs.get(tgt.upper(), "SEQUENTIAL")
                access_mode = self.current_generator.file_access_modes.get(tgt.upper(), "SEQUENTIAL")
                record_key = self.current_generator.file_keys.get(tgt.upper())
                
            is_keyed = (org in ("INDEXED", "RELATIVE") and access_mode in ("RANDOM", "DYNAMIC"))
            
            key_expr = "null"
            if record_key:
                key_jvar = to_java_var(record_key)
                if self.current_generator and record_key.upper() in self.current_generator.redefines_layout:
                    key_expr = f"String.valueOf(get_{key_jvar}())"
                else:
                    key_expr = f"String.valueOf({key_jvar})"
                    
            lines = []
            if not invalid_key_nodes and not not_invalid_key_nodes:
                if is_keyed:
                    return f"delete_{java_tgt}_key({key_expr});"
                else:
                    return f"delete_{java_tgt}();"
                    
            if is_keyed:
                lines.append(f"if (!delete_{java_tgt}_key({key_expr})) {{")
                for node in invalid_key_nodes:
                    stmt_str = self.translate_statement(node)
                    if stmt_str:
                        lines.append(f"    {stmt_str}")
                lines.append("} else {")
                for node in not_invalid_key_nodes:
                    stmt_str = self.translate_statement(node)
                    if stmt_str:
                        lines.append(f"    {stmt_str}")
                lines.append("}")
            else:
                lines.append(f"if (!delete_{java_tgt}()) {{")
                for node in invalid_key_nodes:
                    stmt_str = self.translate_statement(node)
                    if stmt_str:
                        lines.append(f"    {stmt_str}")
                lines.append("} else {")
                for node in not_invalid_key_nodes:
                    stmt_str = self.translate_statement(node)
                    if stmt_str:
                        lines.append(f"    {stmt_str}")
                lines.append("}")
            return "\n        ".join(lines)

        elif stype == "START":
            tgt = props.get("target", "")
            key_op = props.get("key_operator", "=") or "="
            key_var = props.get("key_name")
            invalid_key_nodes = props.get("invalid_key_nodes", [])
            not_invalid_key_nodes = props.get("not_invalid_key_nodes", [])
            
            java_tgt = to_java_var(tgt)
            if not key_var and self.current_generator:
                key_var = self.current_generator.file_keys.get(tgt.upper())
                
            key_expr = "null"
            if key_var:
                key_jvar = to_java_var(key_var)
                if self.current_generator and key_var.upper() in self.current_generator.redefines_layout:
                    key_expr = f"String.valueOf(get_{key_jvar}())"
                else:
                    key_expr = f"String.valueOf({key_jvar})"
                    
            key_name_param = f"\"{key_var.upper()}\"" if key_var else "\"\""
            
            lines = []
            if not invalid_key_nodes and not not_invalid_key_nodes:
                return f"start_{java_tgt}({key_expr}, \"{key_op}\", {key_name_param});"
                
            lines.append(f"if (!start_{java_tgt}({key_expr}, \"{key_op}\", {key_name_param})) {{")
            for node in invalid_key_nodes:
                stmt_str = self.translate_statement(node)
                if stmt_str:
                    lines.append(f"    {stmt_str}")
            lines.append("} else {")
            for node in not_invalid_key_nodes:
                stmt_str = self.translate_statement(node)
                if stmt_str:
                    lines.append(f"    {stmt_str}")
            lines.append("}")
            return "\n        ".join(lines)

        elif stype == "GOBACK":
            return "if (true) { programExited = true; return; }"
        elif stype == "STOP RUN":
            return "if (true) { throw new StopRunException(); }"
        elif stype == "INITIALIZE":
            targets = props.get("targets", [])
            lines = []
            for tgt in targets:
                tgt_upper = tgt.upper()
                if self.current_generator and tgt_upper in self.current_generator.group_fields:
                    for child in self.current_generator.group_fields[tgt_upper]:
                        lines.append(self.generate_initialization_statement(child))
                else:
                    lines.append(self.generate_initialization_statement(tgt))
            return "\n        ".join(lines)
        elif stype == "EXIT_PROGRAM":
            return "if (true) { programExited = true; return; }"
        elif stype == "EXIT":
            return ""

        elif stype == "GO TO":
            target = to_java_var(props.get("target", ""))
            # Unresolved target paragraph diagnostic
            if self.current_generator and target not in self.current_generator.paragraphs:
                diag = {
                    "construct": "GO TO",
                    "source": f"{node.source_file}:{node.source_line}",
                    "severity": "ERROR",
                    "status": "UNSUPPORTED",
                    "detail": f"Unresolved GO TO target paragraph '{target}'"
                }
                self.current_generator.diagnostics.append(diag)
            return f"if (true) {{ nextParagraphIndex = getParagraphIndex(\"{target}\"); return; }}"

        elif stype == "CONTINUE":
            return ";"

        elif stype == "EXIT PERFORM":
            return "if (true) break;"

        elif stype == "EXIT PARAGRAPH":
            return "if (true) return;"

        elif stype == "EXIT SECTION":
            next_sec = None
            if self.current_generator and hasattr(self.current_generator, "current_paragraph"):
                curr_p = self.current_generator.current_paragraph
                next_sec = self.current_generator.next_section_map.get(curr_p)
            
            if next_sec:
                return f"if (true) {{ nextParagraphIndex = getParagraphIndex(\"{next_sec}\"); return; }}"
            else:
                total_paras = len(self.current_generator.paragraphs) if self.current_generator else 9999
                return f"if (true) {{ nextParagraphIndex = {total_paras}; return; }}"

        elif stype == "NEXT SENTENCE":
            return "skipToNextSentence = true;"

        elif stype == "PERFORM_TIMES":
            count_var = props.get("count", "0")
            java_count = to_java_var(count_var)
            if self._is_variable(count_var):
                count_type = self._get_var_type(count_var, "Integer")
                if count_type == "BigDecimal":
                    limit_expr = f"{java_count}.intValue()"
                else:
                    limit_expr = java_count
            else:
                limit_expr = java_count
            
            loop_idx = f"loopIdx_{self.call_counter}"
            self.call_counter += 1
            return f"for (int {loop_idx} = 0; {loop_idx} < {limit_expr} && !programExited; {loop_idx}++) {{"

        elif stype == "PERFORM_TIMES_OUT":
            target = props.get("target", "")
            thru = props.get("thru")
            count_var = props.get("count", "0")
            java_tgt = to_java_var(target)
            java_thru = to_java_var(thru) if thru else None
            
            java_count = to_java_var(count_var)
            if self._is_variable(count_var):
                count_type = self._get_var_type(count_var, "Integer")
                if count_type == "BigDecimal":
                    limit_expr = f"{java_count}.intValue()"
                else:
                    limit_expr = java_count
            else:
                limit_expr = java_count
                
            loop_idx = f"loopIdx_{self.call_counter}"
            self.call_counter += 1
            
            thru_expr = f"\"{java_thru}\"" if java_thru else "null"
            lines = [
                f"for (int {loop_idx} = 0; {loop_idx} < {limit_expr} && !programExited; {loop_idx}++) {{",
                f"    if (skipToNextSentence) break;",
                f"    perform(\"{java_tgt}\", {thru_expr});",
                f"    if (nextParagraphIndex != -1 || programExited) return;",
                f"}}"
            ]
            return "\n        ".join(lines)

        elif stype == "STRING":
            parts = props.get("parts", [])
            tgt = props.get("target", "")
            java_tgt = to_java_var(tgt)
            
            java_parts = []
            for part in parts:
                val = part.get("value", "")
                val_type = part.get("type", "variable")
                delim_by = part.get("delimited_by", "SIZE")
                delim_type = part.get("delimited_by_type", "keyword")
                
                if val_type == "literal":
                    part_expr = f"\"{val}\""
                elif val in self.var_types:
                    java_var = to_java_var(val)
                    if val.upper() in self.redefines_layout and not self.redefines_layout[val.upper()]["is_array"]:
                        java_var = f"get_{java_var}()"
                    var_type = self.var_types.get(val, "String")
                    if var_type == "String":
                        part_expr = java_var
                    else:
                        part_expr = f"String.valueOf({java_var})"
                else:
                    part_expr = f"\"{val}\""
                
                if delim_by != "SIZE":
                    delim_str = ""
                    if delim_by == "SPACE":
                        delim_str = "\" \""
                    elif delim_type == "literal":
                        delim_str = f"\"{delim_by}\""
                    else:
                        delim_var = to_java_var(delim_by)
                        delim_str = delim_var
                        if self.var_types.get(delim_by, "String") != "String":
                            delim_str = f"String.valueOf({delim_str})"
                    part_expr = f"com.systema.modernized.CobolFormatHelper.delimitedString({part_expr}, {delim_str})"
                
                java_parts.append(part_expr)
            
            concat_expr = " + ".join(java_parts)
            return self.generate_assignment(tgt, concat_expr)

        elif stype == "UNSTRING":
            source = props.get("source", "")
            delimited_by = props.get("delimited_by")
            targets = props.get("targets", [])
            pointer = props.get("pointer")
            tallying = props.get("tallying")
            on_overflow = props.get("on_overflow_nodes", [])
            not_on_overflow = props.get("not_on_overflow_nodes", [])
            
            if source.startswith("'") or source.startswith('"'):
                escaped_source = source[1:-1].replace('"', '\\"')
                src_expr = f"\"{escaped_source}\""
            elif source in self.var_types:
                j_src = to_java_var(source)
                src_expr = f"get_{j_src}()" if source in self.redefines_layout else j_src
                if self.var_types.get(source) != "String":
                    src_expr = f"String.valueOf({src_expr})"
            else:
                src_expr = f"\"{source}\""
                
            if delimited_by:
                if delimited_by.startswith("'") or delimited_by.startswith('"'):
                    delim_expr = f"\"{delimited_by[1:-1].replace('\"', '\\\"')}\""
                elif delimited_by in self.var_types:
                    j_delim = to_java_var(delimited_by)
                    delim_expr = f"get_{j_delim}()" if delimited_by in self.redefines_layout else j_delim
                    if self.var_types.get(delimited_by) != "String":
                        delim_expr = f"String.valueOf({delim_expr})"
                else:
                    delim_expr = f"\"{delimited_by}\""
            else:
                delim_expr = "null"
                
            if pointer:
                j_ptr = to_java_var(pointer)
                ptr_init = f"get_{j_ptr}()" if pointer in self.redefines_layout else j_ptr
                if self.var_types.get(pointer) != "Integer" and self.var_types.get(pointer) != "Long":
                    ptr_init = f"((int) parseSignedLong(String.valueOf({ptr_init})))"
            else:
                ptr_init = "1"
                
            assignments = []
            for i, tgt in enumerate(targets):
                tgt_base = re.split(r'\(', tgt)[0].strip()
                tgt_type = self._get_var_type(tgt_base, "String")
                val_expr = f"unstring_targets[{i}]"
                
                if tgt_type == "BigDecimal":
                    conv_expr = f"new BigDecimal({val_expr}.trim().isEmpty() ? \"0\" : {val_expr}.trim())"
                elif tgt_type == "Integer":
                    conv_expr = f"Integer.parseInt({val_expr}.trim().isEmpty() ? \"0\" : {val_expr}.trim())"
                elif tgt_type == "Long":
                    conv_expr = f"Long.parseLong({val_expr}.trim().isEmpty() ? \"0\" : {val_expr}.trim())"
                else:
                    conv_expr = val_expr
                    
                assignments.append(self.generate_assignment(tgt, conv_expr))
            assignments_str = "\n            ".join(assignments)
            
            if pointer:
                ptr_upd = self.generate_assignment(pointer, "unstring_idx + 1")
            else:
                ptr_upd = ""
                
            if tallying:
                tally_upd = self.generate_assignment(tallying, f"({to_java_var(tallying)} + unstring_fields_processed)")
            else:
                tally_upd = ""
                
            on_overflow_code = "\n            ".join(self.translate_statement(n) for n in on_overflow if self.translate_statement(n))
            not_on_overflow_code = "\n            ".join(self.translate_statement(n) for n in not_on_overflow if self.translate_statement(n))
            
            lines = [
                "{",
                f"    String unstring_src = {src_expr};",
                f"    int unstring_ptr = {ptr_init};",
                "    boolean unstring_overflow = false;",
                "    if (unstring_ptr < 1 || unstring_ptr > unstring_src.length() + 1) {",
                "        unstring_overflow = true;",
                "    } else {",
                f"        String[] unstring_targets = new String[{len(targets)}];",
                "        int unstring_idx = unstring_ptr - 1;",
                f"        String unstring_delim = {delim_expr};",
                "        int unstring_fields_processed = 0;",
                f"        for (int i = 0; i < {len(targets)}; i++) {{",
                "            if (unstring_idx > unstring_src.length()) {",
                "                unstring_targets[i] = \"\";",
                "                continue;",
                "            }",
                "            int next_delim = -1;",
                "            if (unstring_delim != null && !unstring_delim.isEmpty()) {",
                "                next_delim = unstring_src.indexOf(unstring_delim, unstring_idx);",
                "            }",
                "            String field_val;",
                "            if (next_delim != -1) {",
                "                field_val = unstring_src.substring(unstring_idx, next_delim);",
                "                unstring_idx = next_delim + unstring_delim.length();",
                "            } else {",
                "                field_val = unstring_src.substring(unstring_idx);",
                "                unstring_idx = unstring_src.length() + 1;",
                "            }",
                "            unstring_targets[i] = field_val;",
                "            unstring_fields_processed++;",
                "        }",
                f"        {ptr_upd}",
                f"        {tally_upd}",
                f"        {assignments_str}",
                "    }",
                "    if (unstring_overflow) {",
                f"        {on_overflow_code}",
                "    } else {",
                f"        {not_on_overflow_code}",
                "    }",
                "}"
            ]
            return "\n        ".join(lines)

        elif stype == "INSPECT":
            target = props.get("target", "")
            inspect_type = props.get("inspect_type")
            tally_var = props.get("tally_var")
            tally_type = props.get("tally_type")
            tally_search = props.get("tally_search")
            replacements = props.get("replacements", [])
            converting_from = props.get("converting_from")
            converting_to = props.get("converting_to")
            
            java_tgt = to_java_var(target)
            tgt_read = f"get_{java_tgt}()" if target in self.redefines_layout else java_tgt
            
            def get_val_expr(val):
                if val is None:
                    return '""'
                if val.startswith("'") or val.startswith('"'):
                    return f"\"{val[1:-1].replace('\"', '\\\"')}\""
                elif val.upper() == "SPACE" or val.upper() == "SPACES":
                    return '" "'
                elif val.upper() == "ZERO" or val.upper() == "ZEROS":
                    return '"0"'
                elif val in self.var_types:
                    var_t = self.var_types.get(val, "String")
                    j_var = to_java_var(val)
                    j_val = f"get_{j_var}()" if val in self.redefines_layout else j_var
                    return j_val if var_t == "String" else f"String.valueOf({j_val})"
                else:
                    return f"\"{val}\""
                    
            if inspect_type == "TALLYING":
                j_tally = to_java_var(tally_var)
                tally_update_prefix = f"{j_tally} = get_{j_tally}()" if tally_var in self.redefines_layout else f"{j_tally} = {j_tally}"
                
                if tally_type == "CHARACTERS":
                    return self.generate_assignment(tally_var, f"({tally_update_prefix} + {tgt_read}.length())")
                elif tally_type == "ALL":
                    lines = [
                        "{",
                        "    int count = 0;",
                        "    int idx = 0;",
                        f"    String s_target = {tgt_read};",
                        f"    String s_search = {get_val_expr(tally_search)};",
                        "    if (!s_search.isEmpty()) {",
                        "        while ((idx = s_target.indexOf(s_search, idx)) != -1) {",
                        "            count++;",
                        "            idx += s_search.length();",
                        "        }",
                        "    }",
                        f"    {self.generate_assignment(tally_var, f'({tally_update_prefix} + count)')}",
                        "}"
                    ]
                    return "\n        ".join(lines)
                elif tally_type == "LEADING":
                    lines = [
                        "{",
                        "    int count = 0;",
                        f"    String s_target = {tgt_read};",
                        f"    String s_search = {get_val_expr(tally_search)};",
                        "    if (!s_search.isEmpty()) {",
                        "        int len = s_search.length();",
                        "        while (s_target.startsWith(s_search)) {",
                        "            count++;",
                        "            s_target = s_target.substring(len);",
                        "        }",
                        "    }",
                        f"    {self.generate_assignment(tally_var, f'({tally_update_prefix} + count)')}",
                        "}"
                    ]
                    return "\n        ".join(lines)
                    
            elif inspect_type == "REPLACING":
                lines = [
                    "{",
                    f"    String temp_inspect = {tgt_read};"
                ]
                for rep in replacements:
                    rep_t = rep.get("type")
                    search = get_val_expr(rep.get("search"))
                    replace = get_val_expr(rep.get("replace"))
                    
                    if rep_t == "ALL":
                        lines.append(f"    temp_inspect = temp_inspect.replace({search}, {replace});")
                    elif rep_t == "FIRST":
                        lines.append(f"    temp_inspect = temp_inspect.replaceFirst(java.util.regex.Pattern.quote({search}), {replace});")
                    elif rep_t == "CHARACTERS":
                        lines.append(f"    StringBuilder sb = new StringBuilder();")
                        lines.append(f"    char rep_char = {replace}.isEmpty() ? ' ' : {replace}.charAt(0);")
                        lines.append(f"    for (int i = 0; i < temp_inspect.length(); i++) sb.append(rep_char);")
                        lines.append(f"    temp_inspect = sb.toString();")
                    elif rep_t == "LEADING":
                        lines.append(f"    if (!{search}.isEmpty()) {{")
                        lines.append(f"        int len = {search}.length();")
                        lines.append(f"        StringBuilder sb = new StringBuilder();")
                        lines.append(f"        while (temp_inspect.startsWith({search})) {{")
                        lines.append(f"            sb.append({replace});")
                        lines.append(f"            temp_inspect = temp_inspect.substring(len);")
                        lines.append(f"        }}")
                        lines.append(f"        sb.append(temp_inspect);")
                        lines.append(f"        temp_inspect = sb.toString();")
                        lines.append(f"    }}")
                lines.append(f"    {self.generate_assignment(target, 'temp_inspect')}")
                lines.append("}")
                return "\n        ".join(lines)
                
            elif inspect_type == "CONVERTING":
                lines = [
                    "{",
                    f"    String from_chars = {get_val_expr(converting_from)};",
                    f"    String to_chars = {get_val_expr(converting_to)};",
                    f"    String s_target = {tgt_read};",
                    "    StringBuilder sb = new StringBuilder();",
                    "    for (int i = 0; i < s_target.length(); i++) {",
                    "        char c = s_target.charAt(i);",
                    "        int idx = from_chars.indexOf(c);",
                    "        if (idx != -1 && idx < to_chars.length()) {",
                    "            sb.append(to_chars.charAt(idx));",
                    "        } else {",
                    "            sb.append(c);",
                    "        }",
                    "    }",
                    f"    {self.generate_assignment(target, 'sb.toString()')}",
                    "}"
                ]
                return "\n        ".join(lines)

        elif stype == "CALL":
            target = props.get("target", "")
            arguments = props.get("arguments", [])
            args_info = props.get("arguments_info", [])
            returning = props.get("returning")
            
            def get_flat_vars(prog_gen, arg_names):
                flat = []
                for arg in arg_names:
                    arg_upper = arg.upper()
                    if arg_upper in prog_gen.group_fields:
                        for child in prog_gen.group_fields[arg_upper]:
                            flat.append(child)
                    else:
                        flat.append(arg)
                return flat

            if not self.current_generator:
                return f"// CALL translation error: current_generator not set"

            caller_vars = get_flat_vars(self.current_generator, arguments)
            is_dynamic = target in self.var_types
            
            if is_dynamic:
                java_var = to_java_var(target)
                lines = []
                lines.append(f"String targetProg_{java_var} = {java_var}.trim().toUpperCase();")
                first = True
                for other_prog_name, other_gen in self.all_generators.items():
                    if other_prog_name == self.current_generator.program_name:
                        continue
                    cond = "if" if first else "else if"
                    first = False
                    lines.append(f"{cond} (targetProg_{java_var}.equals(\"{other_prog_name.upper()}\")) {{")
                    lines.append(f"    // Call block with isolation mode")
                    call_lines = self._generate_call_block(other_prog_name, other_gen, caller_vars, returning, args_info)
                    for cl in call_lines:
                        lines.append(f"    {cl}")
                    lines.append("}")
                return "\n        ".join(lines)
            else:
                target_upper = target.strip('"').strip("'").upper()
                if target_upper in self.all_generators:
                    other_gen = self.all_generators[target_upper]
                    call_lines = self._generate_call_block(target_upper, other_gen, caller_vars, returning, args_info)
                    return "\n        ".join(call_lines)
                else:
                    target_clean = target.strip('"').strip("'").upper()
                    if target_clean in ("CBLTDLI", "ASMTDLI", "PLITDLI") or target_clean.startswith("MQ"):
                        self.current_generator.diagnostics.append({
                            "construct": "IMS_MQ",
                            "source_coordinate": f"{node.source_file}:{node.source_line}",
                            "semantic_ir_node": node.node_id,
                            "severity": "ERROR",
                            "status": "NATIVE_TRANSLATION_BLOCKED",
                            "reason": f"Mainframe IMS/MQ Call to '{target_clean}' is not supported natively."
                        })
                    return f"// Call to unknown program: {target}. Available: {list(self.all_generators.keys())}"
        elif stype == "EVALUATE":
            self.evaluate_count = 0
            self.evaluate_subject = props.get("subject", None)
            self.evaluate_subjects = props.get("subjects", [self.evaluate_subject] if self.evaluate_subject else [])
            return None  # emit nothing; WHEN handlers generate the if/else chain

        elif stype == "WHEN":
            self.evaluate_count += 1
            cond = props.get("condition", "")
            cond_upper = cond.upper().strip()
            if cond_upper == "OTHER":
                return "} else {"

            cond_parts = re.split(r'\s+ALSO\s+', cond, flags=re.IGNORECASE)
            subjects = getattr(self, "evaluate_subjects", [])
            if not subjects and self.evaluate_subject:
                subjects = [self.evaluate_subject]

            sub_conds = []
            for i, part in enumerate(cond_parts):
                part_upper = part.upper().strip()
                if part_upper == "ANY":
                    continue
                subj = subjects[i] if i < len(subjects) else "TRUE"
                sub_cond = self._build_single_when_condition(subj, part)
                sub_conds.append(sub_cond)

            java_cond = " && ".join(sub_conds) if sub_conds else "true"

            if self.evaluate_count == 1:
                return f"if ({java_cond}) {{"
            else:
                return f"}} else if ({java_cond}) {{"

        elif stype == "END-EVALUATE":
            return "}"

        elif stype == "DISPLAY":
            operands = props.get("operands", [])
            if not operands:
                return 'System.out.write(10); System.out.flush();'
            
            write_stmts = []
            for idx, op in enumerate(operands):
                val = op.get("value", "")
                op_type = op.get("type", "variable")
                if op_type == "literal":
                    clean = val.replace('"', '\\"')
                    write_stmts.append(f"writeBytes(\"{clean}\".getBytes(java.nio.charset.StandardCharsets.ISO_8859_1));")
                else:
                    v_type = self._get_var_type(val)
                    jv = self.expr_trans.translate(val)
                    if jv.startswith("BigDecimal.valueOf(") and jv.endswith(")"):
                        jv = jv[len("BigDecimal.valueOf("):-1]
                        
                    val_base = re.split(r'\(', val)[0].strip()
                    pic = self.current_generator.var_pics.get(val_base.upper(), "") if self.current_generator else ""
                    if pic and "9" in pic and "X" not in pic and v_type != "String":
                        val_upper = val_base.upper()
                        spec_init = "new com.systema.modernized.runtime.CobolNumericSpec(true, 18, 0, com.systema.modernized.runtime.CobolUsage.DISPLAY, com.systema.modernized.runtime.CobolSignPosition.TRAILING, false)"
                        if self.current_generator:
                            pic_val = self.current_generator.var_pics.get(val_upper, "")
                            usage = self.current_generator.var_usages.get(val_upper, "DISPLAY") or "DISPLAY"
                            sign_pos = self.current_generator.var_sign_positions.get(val_upper, "TRAILING")
                            sign_sep = "true" if self.current_generator.var_sign_separates.get(val_upper, False) else "false"
                            if pic_val:
                                _, digits, scale, signed = NativeTypeMapper.parse_pic(pic_val)
                            else:
                                digits, scale, signed = 18, 0, True
                            signed_str = "true" if signed else "false"
                            usage_enum_map = {
                                "DISPLAY": "com.systema.modernized.runtime.CobolUsage.DISPLAY",
                                "COMP": "com.systema.modernized.runtime.CobolUsage.COMP",
                                "COMP-3": "com.systema.modernized.runtime.CobolUsage.COMP_3",
                                "COMP_3": "com.systema.modernized.runtime.CobolUsage.COMP_3",
                                "COMP-5": "com.systema.modernized.runtime.CobolUsage.COMP_5",
                                "COMP_5": "com.systema.modernized.runtime.CobolUsage.COMP_5",
                                "BINARY": "com.systema.modernized.runtime.CobolUsage.COMP"
                            }
                            usage_val = usage_enum_map.get(usage.upper(), "com.systema.modernized.runtime.CobolUsage.DISPLAY")
                            if val_upper == "SQLCODE":
                                usage_val = "com.systema.modernized.runtime.CobolUsage.COMP_5"
                            sign_pos_val = f"com.systema.modernized.runtime.CobolSignPosition.{sign_pos}"
                            spec_init = f"new com.systema.modernized.runtime.CobolNumericSpec({signed_str}, {digits}, {scale}, {usage_val}, {sign_pos_val}, {sign_sep})"
                        
                        if v_type == "BigDecimal":
                            fmt_str = f"new com.systema.modernized.runtime.CobolNumeric({jv}, {spec_init}).toDisplayString()"
                        else:
                            fmt_str = f"new com.systema.modernized.runtime.CobolNumeric(java.math.BigDecimal.valueOf({jv}), {spec_init}).toDisplayString()"
                        write_stmts.append(f"writeBytes({fmt_str}.getBytes(java.nio.charset.StandardCharsets.ISO_8859_1));")
                    else:
                        if self.current_generator and val_base.upper() in self.current_generator.group_fields:
                            write_stmts.append(f"writeBytes(get_{to_java_var(val_base)}_bytes());")
                        elif v_type == "String":
                            write_stmts.append(f"writeBytes({jv}.getBytes(java.nio.charset.StandardCharsets.ISO_8859_1));")
                        else:
                            write_stmts.append(f"writeBytes(String.valueOf({jv}).getBytes(java.nio.charset.StandardCharsets.ISO_8859_1));")
            
            write_stmts.append("System.out.write(10);")
            write_stmts.append("System.out.flush();")
            body = "\n        ".join(write_stmts)
            return f"{{\n        {body}\n    }}"

        elif stype == "EXEC_SQL":
            sql_props = props.get("sql_props", {})
            sql_type = sql_props.get("sql_type", "").upper()
            
            def build_param_sql(props):
                original_sql = props.get("original_sql")
                sql_props_internal = props.get("sql_props")
                if not sql_props_internal:
                    sql_props_internal = props
                
                if not original_sql:
                    original_sql = sql_props_internal.get("original_sql")
                
                if original_sql:
                    import re
                    # Translate DB2 dummy tables and timestamps
                    original_sql = re.sub(r'(?i)\bFROM\s+SYSIBM\.SYSDUMMY1\b', '', original_sql)
                    original_sql = re.sub(r'(?i)\bCURRENT\s+TIMESTAMP\b', 'CURRENT_TIMESTAMP', original_sql)
                    
                    from modernize.parser import tokenize_sql
                    tokens = tokenize_sql(original_sql)
                    sql_parts = []
                    params = []
                    
                    query_verb = tokens[0].upper() if tokens else ""
                    skip_mode = False
                    i = 0
                    while i < len(tokens):
                        t = tokens[i]
                        t_upper = t.upper()
                        if t_upper == "INTO" and query_verb in ("SELECT", "FETCH"):
                            skip_mode = True
                            i += 1
                            continue
                        if skip_mode:
                            if t_upper in ("FROM", "WHERE", "ORDER", "GROUP", "HAVING", "JOIN", "INNER", "LEFT", "RIGHT"):
                                skip_mode = False
                            else:
                                i += 1
                                continue
                        
                        if t.startswith(":"):
                            # Check if next token is also a host variable (null indicator)
                            if i + 1 < len(tokens) and tokens[i+1].startswith(":"):
                                sql_parts.append("?")
                                params.append(f"INDICATOR:{t[1:]}:{tokens[i+1][1:]}")
                                i += 2
                                continue
                            else:
                                sql_parts.append("?")
                                params.append(t[1:])
                        else:
                            if t and t[0].isalnum() and "-" in t:
                                t = t.replace("-", "_")
                            sql_parts.append(t)
                        i += 1
                        
                    sql = " ".join(sql_parts)
                    sql = re.sub(r'\s*\.\s*', '.', sql)
                    return sql, params
                
                sql_type = sql_props_internal.get("sql_type")
                table = sql_props_internal.get("table")
                params = []
                
                if sql_type == "SELECT":
                    cols_str = ", ".join(sql_props_internal.get("columns", []))
                    sql = f"SELECT {cols_str} FROM {table}"
                    if sql_props_internal.get("predicates"):
                        sql += " WHERE "
                        pred_strs = []
                        for pred in sql_props_internal["predicates"]:
                            if "logical" in pred:
                                pred_strs.append(pred["logical"])
                            else:
                                col = pred["column"]
                                op = pred["op"]
                                val = pred["value"]
                                pred_strs.append(f"{col} {op} ?")
                                params.append(val[1:] if val.startswith(":") else val)
                        sql += " ".join(pred_strs)
                    return sql, params
                    
                elif sql_type == "INSERT":
                    cols = sql_props_internal.get("columns", [])
                    cols_str = f"({', '.join(cols)})" if cols else ""
                    placeholders = ", ".join(["?"] * len(sql_props_internal.get("values", [])))
                    sql = f"INSERT INTO {table} {cols_str} VALUES ({placeholders})"
                    for val in sql_props_internal.get("values", []):
                        params.append(val[1:] if val.startswith(":") else val)
                    return sql, params
                    
                elif sql_type == "UPDATE":
                    set_strs = []
                    for s in sql_props_internal.get("sets", []):
                        col = s["column"]
                        val = s["value"]
                        set_strs.append(f"{col} = ?")
                        params.append(val[1:] if val.startswith(":") else val)
                        
                    sql = f"UPDATE {table} SET {', '.join(set_strs)}"
                    if sql_props_internal.get("predicates"):
                        sql += " WHERE "
                        pred_strs = []
                        for pred in sql_props_internal["predicates"]:
                            if "logical" in pred:
                                pred_strs.append(pred["logical"])
                            else:
                                col = pred["column"]
                                op = pred["op"]
                                val = pred["value"]
                                pred_strs.append(f"{col} {op} ?")
                                params.append(val[1:] if val.startswith(":") else val)
                        sql += " ".join(pred_strs)
                    return sql, params
                    
                elif sql_type == "DELETE":
                    sql = f"DELETE FROM {table}"
                    if sql_props_internal.get("predicates"):
                        sql += " WHERE "
                        pred_strs = []
                        for pred in sql_props_internal["predicates"]:
                            if "logical" in pred:
                                pred_strs.append(pred["logical"])
                            else:
                                col = pred["column"]
                                op = pred["op"]
                                val = pred["value"]
                                pred_strs.append(f"{col} {op} ?")
                                params.append(val[1:] if val.startswith(":") else val)
                        sql += " ".join(pred_strs)
                    return sql, params
                    
                return "", []

            lines = []
            
            def get_status_updates(success=True, notfound=False, error=False):
                updates = []
                if "SQLCODE" in self.var_types:
                    code_val = "0"
                    if notfound:
                        code_val = "100"
                    elif error:
                        code_val = "-1"
                    updates.append(f"sqlcode = {code_val};")
                if "SQLSTATE" in self.var_types:
                    state_val = '"00000"'
                    if notfound:
                        state_val = '"02000"'
                    elif error:
                        state_val = '"99999"'
                    updates.append(f"sqlstate = {state_val};")
                return "\n            ".join(updates)

            def get_error_status_updates(e_var="e"):
                """Use Db2ErrorMapper to map the caught exception to SQLCODE/SQLSTATE."""
                updates = []
                if "SQLCODE" in self.var_types:
                    updates.append(f"sqlcode = com.systema.modernized.Db2ErrorMapper.getSqlCode({e_var});")
                if "SQLSTATE" in self.var_types:
                    updates.append(f"sqlstate = com.systema.modernized.Db2ErrorMapper.getSqlState({e_var});")
                if not updates:
                    # No SQLCA vars declared — still set a fallback
                    return ""
                return "\n            ".join(updates)

            if sql_type in ("COMMIT", "ROLLBACK"):
                lines.append("try {")
                lines.append("    if (com.systema.modernized.SpringContextHelper.transactionManager != null && txStatus != null) {")
                if sql_type == "COMMIT":
                    lines.append("        com.systema.modernized.SpringContextHelper.transactionManager.commit(txStatus);")
                else:
                    lines.append("        com.systema.modernized.SpringContextHelper.transactionManager.rollback(txStatus);")
                lines.append("        txStatus = com.systema.modernized.SpringContextHelper.transactionManager.getTransaction(new org.springframework.transaction.support.DefaultTransactionDefinition());")
                lines.append("    } else {")
                lines.append(f"        com.systema.modernized.SpringContextHelper.jdbcTemplate.execute(\"{sql_type}\");")
                lines.append("    }")
                lines.append(f"    {get_status_updates(success=True)}")
                lines.append("} catch (Exception e) {")
                lines.append(f"    {get_error_status_updates()}")
                lines.append("}")
                return "\n        ".join(lines)
                
            elif sql_type == "DECLARE_CURSOR":
                return f"// DECLARE CURSOR {sql_props.get('cursor_name')} Registered"
                
            elif sql_type == "OPEN":
                cname = sql_props.get("cursor_name", "").upper()
                query_props = None
                for n in (self.current_generator.ir_nodes if self.current_generator else []):
                    if n.kind == "STATEMENT" and n.properties.get("statement_type") == "EXEC_SQL":
                        sp = n.properties.get("sql_props", {})
                        if sp.get("sql_type") == "DECLARE_CURSOR" and sp.get("cursor_name", "").upper() == cname:
                            query_props = sp.get("cursor_query")
                            break
                if not query_props:
                    return f"// Error: cursor {cname} not declared"
                
                sql_str, params = build_param_sql(query_props)
                java_params = []
                for p in params:
                    if p.startswith("INDICATOR:"):
                        _, main_var, indicator = p.split(":")
                        java_params.append(f"({to_java_var(indicator)} == -1) ? null : {to_java_var(main_var)}")
                    else:
                        val_expr = self.expr_trans.translate(p)
                        var_name = p
                        if var_name.startswith(":"):
                            var_name = var_name[1:]
                        if self._get_var_type(var_name, "String") == "String":
                            val_expr = f"({val_expr} != null ? {val_expr}.trim() : null)"
                        java_params.append(val_expr)
                params_str = ", ".join(java_params)
                if params_str:
                    params_str = ", " + params_str
                
                lines.append("try {")
                lines.append(f"    cursor_{cname.lower()} = com.systema.modernized.SpringContextHelper.jdbcTemplate.queryForRowSet(\"{sql_str}\"{params_str});")
                lines.append(f"    {get_status_updates(success=True)}")
                lines.append("} catch (Exception e) {")
                lines.append(f"    {get_status_updates(error=True)}")
                lines.append("}")
                return "\n        ".join(lines)
                
            elif sql_type == "CLOSE":
                cname = sql_props.get("cursor_name", "").upper()
                lines.append(f"cursor_{cname.lower()} = null;")
                lines.append(get_status_updates(success=True))
                return "\n        ".join(lines)
                
            elif sql_type == "FETCH":
                cname = sql_props.get("cursor_name", "").upper()
                into_vars = sql_props.get("into_variables", [])
                into_indicators = sql_props.get("into_indicators", [])
                assignments = []
                for i, target in enumerate(into_vars):
                    tgt_jvar = to_java_var(target)
                    tgt_type = self._get_var_type(target, "String")
                    if tgt_type == "BigDecimal":
                        getter = f"cursor_{cname.lower()}.getBigDecimal({i+1})"
                    elif tgt_type == "Integer":
                        getter = f"cursor_{cname.lower()}.getInt({i+1})"
                    elif tgt_type == "Long":
                        getter = f"cursor_{cname.lower()}.getLong({i+1})"
                    else:
                        # Pad String to declared PIC X width so fixed-width COBOL fields are honoured
                        raw = f"cursor_{cname.lower()}.getString({i+1})"
                        pic_str = (self.current_generator.var_pics.get(target.upper(), "") if self.current_generator else "")
                        if pic_str:
                            _, str_len, _, _ = NativeTypeMapper.parse_pic(pic_str)
                        else:
                            str_len = 0
                        if str_len > 0:
                            getter = f"String.format(\"%-{str_len}s\", {raw} != null ? {raw} : \"\".repeat({str_len}))"
                        else:
                            getter = raw
                    
                    is_redef = target.upper() in self.redefines_layout and not self.redefines_layout[target.upper()]["is_array"]
                    
                    if i < len(into_indicators) and into_indicators[i]:
                        ind_jvar = to_java_var(into_indicators[i])
                        if is_redef:
                            assignments.append(f"set_{tgt_jvar}({getter});")
                        else:
                            assignments.append(f"{tgt_jvar} = {getter};")
                        assignments.append(f"if (cursor_{cname.lower()}.wasNull()) {{")
                        assignments.append(f"    {ind_jvar} = -1;")
                        assignments.append(f"}} else {{")
                        assignments.append(f"    {ind_jvar} = 0;")
                        assignments.append(f"}}")
                    else:
                        if is_redef:
                            assignments.append(f"set_{tgt_jvar}({getter});")
                        else:
                            assignments.append(f"{tgt_jvar} = {getter};")
                        
                assignments_code = "\n            ".join(assignments)
                
                lines.append("try {")
                lines.append(f"    if (cursor_{cname.lower()} != null && cursor_{cname.lower()}.next()) {{")
                lines.append(f"        {assignments_code}")
                lines.append(f"        {get_status_updates(success=True)}")
                lines.append("    } else {")
                lines.append(f"        {get_status_updates(notfound=True)}")
                lines.append("    }")
                lines.append("} catch (Exception e) {")
                lines.append(f"    {get_status_updates(error=True)}")
                lines.append("}")
                return "\n        ".join(lines)
                
            elif sql_type == "SELECT":
                sql_str, params = build_param_sql(props)
                java_params = []
                for p in params:
                    if p.startswith("INDICATOR:"):
                        _, main_var, indicator = p.split(":")
                        java_params.append(f"({to_java_var(indicator)} == -1) ? null : {to_java_var(main_var)}")
                    else:
                        val_expr = self.expr_trans.translate(p)
                        var_name = p
                        if var_name.startswith(":"):
                            var_name = var_name[1:]
                        if self._get_var_type(var_name, "String") == "String":
                            val_expr = f"({val_expr} != null ? {val_expr}.trim() : null)"
                        java_params.append(val_expr)
                params_str = ", ".join(java_params)
                if params_str:
                    params_str = ", " + params_str
                
                into_vars = sql_props.get("into_variables", [])
                into_indicators = sql_props.get("into_indicators", [])
                assignments = []
                for i, target in enumerate(into_vars):
                    tgt_jvar = to_java_var(target)
                    tgt_type = self._get_var_type(target, "String")
                    if tgt_type == "BigDecimal":
                        getter = f"rs.getBigDecimal({i+1})"
                    elif tgt_type == "Integer":
                        getter = f"rs.getInt({i+1})"
                    elif tgt_type == "Long":
                        getter = f"rs.getLong({i+1})"
                    else:
                        # Pad String to declared PIC X width so fixed-width COBOL fields are honoured
                        raw = f"rs.getString({i+1})"
                        pic_str = (self.current_generator.var_pics.get(target.upper(), "") if self.current_generator else "")
                        if pic_str:
                            _, str_len, _, _ = NativeTypeMapper.parse_pic(pic_str)
                        else:
                            str_len = 0
                        if str_len > 0:
                            getter = f"String.format(\"%-{str_len}s\", {raw} != null ? {raw} : \"\".repeat({str_len}))"
                        else:
                            getter = raw
                    
                    is_redef = target.upper() in self.redefines_layout and not self.redefines_layout[target.upper()]["is_array"]
                    
                    if i < len(into_indicators) and into_indicators[i]:
                        ind_jvar = to_java_var(into_indicators[i])
                        if is_redef:
                            assignments.append(f"set_{tgt_jvar}({getter});")
                        else:
                            assignments.append(f"{tgt_jvar} = {getter};")
                        assignments.append(f"if (rs.wasNull()) {{")
                        assignments.append(f"    {ind_jvar} = -1;")
                        assignments.append(f"}} else {{")
                        assignments.append(f"    {ind_jvar} = 0;")
                        assignments.append(f"}}")
                    else:
                        if is_redef:
                            assignments.append(f"set_{tgt_jvar}({getter});")
                        else:
                            assignments.append(f"{tgt_jvar} = {getter};")
                        
                assignments_code = "\n            ".join(assignments)
                
                lines.append("try {")
                lines.append(f"    org.springframework.jdbc.support.rowset.SqlRowSet rs = com.systema.modernized.SpringContextHelper.jdbcTemplate.queryForRowSet(\"{sql_str}\"{params_str});")
                lines.append("    if (rs.next()) {")
                lines.append(f"        {assignments_code}")
                lines.append(f"        {get_status_updates(success=True)}")
                lines.append("    } else {")
                lines.append(f"        {get_status_updates(notfound=True)}")
                lines.append("    }")
                lines.append("} catch (Exception e) {")
                lines.append(f"    System.err.println(\"[SQL-ERROR] SELECT on {sql_str}: \" + e.getMessage()); {get_error_status_updates()}")
                lines.append("}")
                return "\n        ".join(lines)
                
            elif sql_type in ("INSERT", "UPDATE", "DELETE"):
                sql_str, params = build_param_sql(props)
                java_params = []
                for p in params:
                    if p.startswith("INDICATOR:"):
                        _, main_var, indicator = p.split(":")
                        java_params.append(f"({to_java_var(indicator)} == -1) ? null : {to_java_var(main_var)}")
                    else:
                        val_expr = self.expr_trans.translate(p)
                        var_name = p
                        if var_name.startswith(":"):
                            var_name = var_name[1:]
                        if self._get_var_type(var_name, "String") == "String":
                            val_expr = f"({val_expr} != null ? {val_expr}.trim() : null)"
                        java_params.append(val_expr)
                params_str = ", ".join(java_params)
                if params_str:
                    params_str = ", " + params_str
                
                lines.append("try {")
                lines.append(f"    int rows = com.systema.modernized.SpringContextHelper.jdbcTemplate.update(\"{sql_str}\"{params_str});")
                lines.append("    if (rows > 0) {")
                lines.append(f"        {get_status_updates(success=True)}")
                lines.append("    } else {")
                is_modify = sql_type in ("UPDATE", "DELETE")
                lines.append(f"        {get_status_updates(notfound=is_modify, success=not is_modify)}")
                lines.append("    }")
                lines.append("} catch (Exception e) {")
                lines.append(f"    System.err.println(\"[SQL-ERROR] {sql_type} on {sql_str}: \" + e.getMessage()); {get_error_status_updates()}")
                lines.append("}")
                return "\n        ".join(lines)

        elif stype == "EXEC_CICS":
            cics_props = props.get("cics_props", {})
            cics_type = cics_props.get("cics_type", "").upper()
            
            lines = []
            
            def append_resp_updates():
                res = []
                if "resp" in cics_props:
                    resp_var = cics_props["resp"]
                    j_resp = to_java_var(resp_var)
                    res.append(f"{j_resp} = com.systema.modernized.CicsTransactionContext.getEibresp();")
                if "resp2" in cics_props:
                    resp2_var = cics_props["resp2"]
                    j_resp2 = to_java_var(resp2_var)
                    res.append(f"{j_resp2} = com.systema.modernized.CicsTransactionContext.getEibresp2();")
                res.append("eibresp = com.systema.modernized.CicsTransactionContext.getEibresp();")
                res.append("eibresp2 = com.systema.modernized.CicsTransactionContext.getEibresp2();")
                return res

            if cics_type == "SEND":
                map_val = cics_props.get("map", "")
                mapset_val = cics_props.get("mapset", "")
                from_var = cics_props.get("from", "")
                java_from = to_java_var(from_var) if from_var else "null"
                lines.append("java.util.Map<String, Object> sendOpts = new java.util.HashMap<>();")
                for key, val in cics_props.items():
                    if key not in ("cics_type", "map", "mapset", "from", "resp", "resp2"):
                        if isinstance(val, bool):
                            lines.append(f'sendOpts.put("{key.lower()}", {str(val).lower()});')
                        else:
                            lines.append(f'sendOpts.put("{key.lower()}", "{val}");')
                lines.append(f'com.systema.modernized.CicsTransactionContext.send("{map_val}", "{mapset_val}", {java_from}, sendOpts);')
                lines.extend(append_resp_updates())
                return "\n        ".join(lines)
                
            elif cics_type == "RECEIVE":
                map_val = cics_props.get("map", "")
                mapset_val = cics_props.get("mapset", "")
                into_var = cics_props.get("into", "")
                lines.append("java.util.Map<String, Object> recvOpts = new java.util.HashMap<>();")
                for key, val in cics_props.items():
                    if key not in ("cics_type", "map", "mapset", "into", "resp", "resp2"):
                        if isinstance(val, bool):
                            lines.append(f'recvOpts.put("{key.lower()}", {str(val).lower()});')
                        else:
                            lines.append(f'recvOpts.put("{key.lower()}", "{val}");')
                if into_var:
                    java_into = to_java_var(into_var)
                    lines.append(f'Object receivedData = com.systema.modernized.CicsTransactionContext.receive("{map_val}", "{mapset_val}", recvOpts);')
                    lines.append("if (receivedData != null) {")
                    lines.append(f"    {java_into} = receivedData.toString();")
                    lines.append("}")
                else:
                    lines.append(f'com.systema.modernized.CicsTransactionContext.receive("{map_val}", "{mapset_val}", recvOpts);')
                lines.extend(append_resp_updates())
                return "\n        ".join(lines)
                
            elif cics_type == "LINK":
                prog = cics_props.get("program", "")
                comm = cics_props.get("commarea", "")
                chan = cics_props.get("channel", "")
                if prog.upper() in self.var_types or prog.upper() in self.redefines_layout:
                    java_prog = to_java_var(prog)
                else:
                    java_prog = f'"{prog.upper()}"'
                    
                java_chan = f'"{chan}"' if chan else "null"
                if chan and chan.upper() in self.var_types:
                    java_chan = to_java_var(chan)

                lines.append("try {")
                if comm:
                    java_comm = to_java_var(comm)
                    lines.append(f"    Object resComm = com.systema.modernized.CicsProgramRegistry.invoke({java_prog}, {java_comm}, {java_chan});")
                    lines.append("    if (resComm != null) {")
                    lines.append(f"        {java_comm} = resComm.toString();")
                    lines.append("    }")
                else:
                    lines.append(f"    com.systema.modernized.CicsProgramRegistry.invoke({java_prog}, null, {java_chan});")
                lines.append("    com.systema.modernized.CicsTransactionContext.setEibresp(com.systema.modernized.CicsTransactionContext.DFHRESP_NORMAL);")
                lines.append("} catch (Exception e) {")
                lines.append("    System.err.println(\"[CICS-LINK-ERROR] \" + e.getMessage());")
                lines.append("    com.systema.modernized.CicsTransactionContext.setEibresp(com.systema.modernized.CicsTransactionContext.DFHRESP_PGMIDERR);")
                lines.append("}")
                lines.extend(append_resp_updates())
                return "\n        ".join(lines)
                
            elif cics_type == "XCTL":
                prog = cics_props.get("program", "")
                comm = cics_props.get("commarea", "")
                chan = cics_props.get("channel", "")
                if prog.upper() in self.var_types or prog.upper() in self.redefines_layout:
                    java_prog = to_java_var(prog)
                else:
                    java_prog = f'"{prog.upper()}"'
                    
                java_chan = f'"{chan}"' if chan else "null"
                if chan and chan.upper() in self.var_types:
                    java_chan = to_java_var(chan)

                lines.append("try {")
                if comm:
                    java_comm = to_java_var(comm)
                    lines.append(f"    com.systema.modernized.CicsProgramRegistry.invoke({java_prog}, {java_comm}, {java_chan});")
                else:
                    lines.append(f"    com.systema.modernized.CicsProgramRegistry.invoke({java_prog}, null, {java_chan});")
                lines.append("    com.systema.modernized.CicsTransactionContext.setEibresp(com.systema.modernized.CicsTransactionContext.DFHRESP_NORMAL);")
                lines.append("} catch (Exception e) {")
                lines.append("    System.err.println(\"[CICS-XCTL-ERROR] \" + e.getMessage());")
                lines.append("    com.systema.modernized.CicsTransactionContext.setEibresp(com.systema.modernized.CicsTransactionContext.DFHRESP_PGMIDERR);")
                lines.append("}")
                lines.extend(append_resp_updates())
                lines.append("programExited = true;")
                lines.append("return;")
                return "\n        ".join(lines)
                
            elif cics_type == "RETURN":
                transid = cics_props.get("transid", "")
                comm = cics_props.get("commarea", "")
                java_trans = f'"{transid}"' if transid else "null"
                if transid and transid.upper() in self.var_types:
                    java_trans = to_java_var(transid)
                java_comm = to_java_var(comm) if comm else "null"
                lines.append("try {")
                lines.append(f"    com.systema.modernized.CicsTransactionContext.cicsReturn({java_trans}, {java_comm});")
                lines.append("    com.systema.modernized.CicsTransactionContext.setEibresp(com.systema.modernized.CicsTransactionContext.DFHRESP_NORMAL);")
                lines.append("} catch (Exception e) {")
                lines.append("    com.systema.modernized.CicsTransactionContext.setEibresp(com.systema.modernized.CicsTransactionContext.DFHRESP_INVREQ);")
                lines.append("}")
                lines.extend(append_resp_updates())
                lines.append("programExited = true;")
                lines.append("return;")
                return "\n        ".join(lines)

            elif cics_type in ("GET", "PUT", "DELETE") and "container" in cics_props:
                cont = cics_props.get("container", "")
                chan = cics_props.get("channel", "")
                java_cont = f'"{cont}"' if cont else "null"
                if cont and cont.upper() in self.var_types:
                    java_cont = to_java_var(cont)
                java_chan = f'"{chan}"' if chan else '"DEFAULT"'
                if chan and chan.upper() in self.var_types:
                    java_chan = to_java_var(chan)
                
                lines.append("try {")
                if cics_type == "GET":
                    into_var = cics_props.get("into", "")
                    java_into = to_java_var(into_var) if into_var else "null"
                    lines.append(f"    String val = com.systema.modernized.CicsTransactionContext.getStringContainer({java_chan}, {java_cont});")
                    if java_into != "null":
                        lines.append(f"    if (val != null) {{ {java_into} = val; }}")
                elif cics_type == "PUT":
                    from_var = cics_props.get("from", "")
                    java_from = to_java_var(from_var) if from_var else '""'
                    lines.append(f"    com.systema.modernized.CicsTransactionContext.putStringContainer({java_chan}, {java_cont}, {java_from});")
                elif cics_type == "DELETE":
                    lines.append(f"    com.systema.modernized.CicsTransactionContext.deleteContainer({java_chan}, {java_cont});")
                lines.append("    com.systema.modernized.CicsTransactionContext.setEibresp(com.systema.modernized.CicsTransactionContext.DFHRESP_NORMAL);")
                lines.append("} catch (Exception e) {")
                lines.append("    com.systema.modernized.CicsTransactionContext.setEibresp(com.systema.modernized.CicsTransactionContext.DFHRESP_CONTAINERERR);")
                lines.append("}")
                lines.extend(append_resp_updates())
                return "\n        ".join(lines)

            elif cics_type == "ABEND":
                abcode = cics_props.get("abcode", "ABND")
                java_ab = f'"{abcode}"' if abcode else '"ABND"'
                if abcode and abcode.upper() in self.var_types:
                    java_ab = to_java_var(abcode)
                lines.append(f"com.systema.modernized.CicsTransactionContext.cicsAbend({java_ab});")
                lines.append("programExited = true;")
                lines.append("return;")
                return "\n        ".join(lines)

            elif cics_type == "ASKTIME":
                abstime = cics_props.get("abstime", "")
                if abstime:
                    java_abs = to_java_var(abstime)
                    lines.append(f"{java_abs} = System.currentTimeMillis();")
                lines.append("com.systema.modernized.CicsTransactionContext.setEibresp(com.systema.modernized.CicsTransactionContext.DFHRESP_NORMAL);")
                lines.extend(append_resp_updates())
                return "\n        ".join(lines)

            elif cics_type == "FORMATTIME":
                yyyymmdd = cics_props.get("yyyymmdd", "")
                time_var = cics_props.get("time", "")
                lines.append("java.time.LocalDateTime nowLdt = java.time.LocalDateTime.now();")
                if yyyymmdd:
                    lines.append(f'{to_java_var(yyyymmdd)} = nowLdt.format(java.time.format.DateTimeFormatter.ofPattern("yyyyMMdd"));')
                if time_var:
                    lines.append(f'{to_java_var(time_var)} = nowLdt.format(java.time.format.DateTimeFormatter.ofPattern("HHmmss"));')
                lines.append("com.systema.modernized.CicsTransactionContext.setEibresp(com.systema.modernized.CicsTransactionContext.DFHRESP_NORMAL);")
                lines.extend(append_resp_updates())
                return "\n        ".join(lines)

        if stype and self.current_generator is not None:
            node_id = None
            source_coord = "UNKNOWN"
            if hasattr(node, "node_id"):
                node_id = node.node_id
            if hasattr(node, "source_line") and node.source_line:
                src_file = getattr(node, "source_file", "") or ""
                source_coord = f"{os.path.basename(src_file)}:{node.source_line}" if src_file else f"line:{node.source_line}"
            self.current_generator.diagnostics.append({
                "construct": stype,
                "source_coordinate": source_coord,
                "semantic_ir_node": node_id,
                "severity": "ERROR",
                "status": "NATIVE_TRANSLATION_BLOCKED",
                "reason": f"Statement type '{stype}' has no native Java translation"
            })
        return f"// UNSUPPORTED: {stype}"

    def _translate_subscripts(self, expr: str) -> str:
        pattern = r'(?<![A-Za-z0-9_-])([A-Za-z0-9_-]+)\s*\(\s*([^()]+)\s*\)'
        def repl(match):
            cobol_name = match.group(1).upper()
            if cobol_name not in self.var_types and cobol_name not in self.redefines_layout and cobol_name not in self.occurs_depending_on:
                return match.group(0)
            var_name = to_java_var(cobol_name)
            idx = match.group(2).strip()
            if ":" in idx:
                # Reference modification!
                parts = idx.split(":")
                start_expr = parts[0].strip()
                length_expr = parts[1].strip() if len(parts) > 1 else ""
                
                # Replace variable names in start_expr and length_expr
                for v in self.var_types.keys():
                    start_expr = re.sub(r'(?<![A-Za-z0-9_-])' + re.escape(v) + r'(?![A-Za-z0-9_-])', to_java_var(v), start_expr)
                    if length_expr:
                        length_expr = re.sub(r'(?<![A-Za-z0-9_-])' + re.escape(v) + r'(?![A-Za-z0-9_-])', to_java_var(v), length_expr)

                def is_int(s):
                    try:
                        int(s)
                        return True
                    except ValueError:
                        return False

                if is_int(start_expr):
                    begin_idx = int(start_expr) - 1
                    if length_expr:
                        if is_int(length_expr):
                            end_idx = begin_idx + int(length_expr)
                            return f"{var_name}.substring({begin_idx}, {end_idx})"
                        else:
                            return f"{var_name}.substring({begin_idx}, {begin_idx} + ({length_expr}))"
                    else:
                        return f"{var_name}.substring({begin_idx})"
                else:
                    if length_expr:
                        if is_int(length_expr):
                            return f"{var_name}.substring(({start_expr}) - 1, ({start_expr}) - 1 + {int(length_expr)})"
                        else:
                            return f"{var_name}.substring(({start_expr}) - 1, ({start_expr}) - 1 + ({length_expr}))"
                    else:
                        return f"{var_name}.substring(({start_expr}) - 1)"

            for v in self.var_types.keys():
                idx = re.sub(r'(?<![A-Za-z0-9_-])' + re.escape(v) + r'(?![A-Za-z0-9_-])', to_java_var(v), idx)
            if idx.isdigit():
                return f"{var_name}[{int(idx) - 1}]"
            return f"{var_name}[{idx} - 1]"
        
        old = ""
        while old != expr:
            old = expr
            expr = re.sub(pattern, repl, expr)
        return expr

    def _make_loop_header(self, idx, from_val, by_val, cond):
        java_idx = to_java_var(idx)
        idx_upper = idx.upper() if isinstance(idx, str) else ""
        idx_type = self.var_types.get(idx_upper, self.var_types.get(idx, "Integer"))
        cond_trans = self._translate_condition(cond)
        if idx_type == "BigDecimal":
            by_expr = f"new BigDecimal(\"{by_val}\")" if re.match(r'^\d+(\.\d+)?$', str(by_val)) else to_java_var(str(by_val))
            from_expr = f"new BigDecimal(\"{from_val}\")" if re.match(r'^\d+(\.\d+)?$', str(from_val)) else to_java_var(str(from_val))
            return f"for ({java_idx} = {from_expr}; !({cond_trans}) && !programExited; {java_idx} = {java_idx}.add({by_expr})) {{"
        else:
            return f"for ({java_idx} = {from_val}; !({cond_trans}) && !programExited; {java_idx} += {by_val}) {{"

    def _build_single_when_condition(self, subject, cond) -> str:
        cond_upper = cond.upper().strip()
        if subject and subject.upper() != "TRUE":
            subj_java = to_java_var(subject) if subject in self.var_types else subject
            if subject.upper() in self.redefines_layout and not self.redefines_layout[subject.upper()]["is_array"]:
                subj_java = f"get_{subj_java}()"
            subj_type = self.var_types.get(subject, "String")
            cond_stripped = cond.strip().strip("'\"")
            if subj_type == "BigDecimal":
                r_val = (f"new BigDecimal(\"{cond_stripped}\")"
                         if re.match(r'^\d+(\.\d+)?$', cond_stripped)
                         else to_java_var(cond_stripped))
                if cond_stripped.upper() in self.redefines_layout and not self.redefines_layout[cond_stripped.upper()]["is_array"]:
                    r_val = f"get_{to_java_var(cond_stripped)}()"
                elif cond_stripped.upper() in self.var_types and self.var_types[cond_stripped.upper()] == "BigDecimal":
                    r_val = f"{to_java_var(cond_stripped)}.getValue()"
                
                subj_ref = subj_java
                if subject.upper() not in self.redefines_layout:
                    subj_ref = f"{subj_java}.getValue()"
                return f"{subj_ref}.compareTo({r_val}) == 0"
            elif subj_type in ("Integer", "Long"):
                r_val = cond_stripped
                if cond_stripped.upper() in self.var_types:
                    r_val = to_java_var(cond_stripped)
                    if cond_stripped.upper() in self.redefines_layout and not self.redefines_layout[cond_stripped.upper()]["is_array"]:
                        r_val = f"get_{r_val}()"
                return f"{subj_java} == {r_val}"
            else:
                r_val = cond_stripped
                if cond_stripped.upper() in self.var_types:
                    r_val = to_java_var(cond_stripped)
                    if cond_stripped.upper() in self.redefines_layout and not self.redefines_layout[cond_stripped.upper()]["is_array"]:
                        r_val = f"get_{r_val}()"
                    return f"Objects.equals({subj_java}, {r_val})"
                else:
                    return f"Objects.equals({subj_java}, \"{cond_stripped}\")"
        else:
            return self._translate_condition(cond)

    def _get_group_elementary_items(self, group_name):
        var_nodes = [n for n in self.current_generator.ir_nodes if n.kind in ("VARIABLE", "DATA_ITEM")]
        group_node = None
        group_idx = -1
        group_name_upper = group_name.upper().strip()
        for idx, n in enumerate(var_nodes):
            if n.properties.get("name", "").upper() == group_name_upper:
                group_node = n
                group_idx = idx
                break
        if not group_node:
            return []
        group_level = group_node.properties.get("level", 1)
        descendants = []
        for i in range(group_idx + 1, len(var_nodes)):
            n = var_nodes[i]
            lvl = n.properties.get("level", 1)
            if lvl <= group_level:
                break
            descendants.append(n)
        
        stack = [(group_level, group_name_upper)]
        elementary_items = []
        for n in descendants:
            lvl = n.properties.get("level", 1)
            name = n.properties.get("name", "").upper()
            is_group = n.properties.get("is_group", False)
            while stack and stack[-1][0] >= lvl:
                stack.pop()
            path = [item[1] for item in stack[1:]] + [name]
            if not is_group:
                elementary_items.append((tuple(path), n.properties.get("name", "")))
            if is_group:
                stack.append((lvl, name))
        return elementary_items

    def _generate_corresponding_statements(self, op, src_group, tgt_group) -> str:
        src_items = self._get_group_elementary_items(src_group)
        tgt_items = self._get_group_elementary_items(tgt_group)
        src_map = {path: name for path, name in src_items}
        tgt_map = {path: name for path, name in tgt_items}
        statements = []
        for path in src_map:
            if path in tgt_map:
                s_var = src_map[path]
                t_var = tgt_map[path]
                if op == "MOVE":
                    mock_node = SemanticIRNode(
                        node_id="mock", kind="STATEMENT",
                        properties={"statement_type": "MOVE", "source": s_var, "targets": [t_var]}
                    )
                    statements.append(self._translate_statement_inner(mock_node))
                elif op == "ADD":
                    mock_node = SemanticIRNode(
                        node_id="mock", kind="STATEMENT",
                        properties={"statement_type": "ADD", "value": s_var, "giving": False, "targets": [{"name": t_var, "rounded": False}]}
                    )
                    statements.append(self._translate_statement_inner(mock_node))
                elif op == "SUBTRACT":
                    mock_node = SemanticIRNode(
                        node_id="mock", kind="STATEMENT",
                        properties={"statement_type": "SUBTRACT", "value": s_var, "giving": False, "targets": [{"name": t_var, "rounded": False}]}
                    )
                    statements.append(self._translate_statement_inner(mock_node))
        return "\n        ".join(statements)

    def _translate_condition(self, cond: str) -> str:
        """Translate a COBOL condition string to Java boolean expression."""
        cond = self._translate_subscripts(cond)
        
        # Normalize COBOL relation keywords to symbols
        cond = re.sub(r'\bNOT\s+EQUAL\s+TO\b', '<>', cond, flags=re.IGNORECASE)
        cond = re.sub(r'\bNOT\s+EQUAL\b', '<>', cond, flags=re.IGNORECASE)
        cond = re.sub(r'\bEQUAL\s+TO\b', '=', cond, flags=re.IGNORECASE)
        cond = re.sub(r'\bEQUAL\b', '=', cond, flags=re.IGNORECASE)
        cond = re.sub(r'\bGREATER\s+THAN\s+OR\s+EQUAL\s+TO\b', '>=', cond, flags=re.IGNORECASE)
        cond = re.sub(r'\bGREATER\s+THAN\s+OR\s+EQUAL\b', '>=', cond, flags=re.IGNORECASE)
        cond = re.sub(r'\bGREATER\s+THAN\b', '>', cond, flags=re.IGNORECASE)
        cond = re.sub(r'\bGREATER\b', '>', cond, flags=re.IGNORECASE)
        cond = re.sub(r'\bLESS\s+THAN\s+OR\s+EQUAL\s+TO\b', '<=', cond, flags=re.IGNORECASE)
        cond = re.sub(r'\bLESS\s+THAN\s+OR\s+EQUAL\b', '<=', cond, flags=re.IGNORECASE)
        cond = re.sub(r'\bLESS\s+THAN\b', '<', cond, flags=re.IGNORECASE)
        cond = re.sub(r'\bLESS\b', '<', cond, flags=re.IGNORECASE)
        
        # Translate FUNCTION MOD(A, B) to com.systema.modernized.CobolFormatHelper.mod(A, B)
        cond = re.sub(
            r'\bFUNCTION\s+MOD\s*\(\s*([^,()]+)\s*,\s*([^()]+)\s*\)',
            r'com.systema.modernized.CobolFormatHelper.mod(\1, \2)',
            cond,
            flags=re.IGNORECASE
        )
        
        # Resolve Level-78 constants
        for const_name, const_val in self.constants_map.items():
            pattern = r'(?<![A-Za-z0-9_-])' + re.escape(const_name) + r'(?![A-Za-z0-9_-])'
            if isinstance(const_val, str) and (const_val.startswith("'") or const_val.startswith('"')):
                formatted_val = f"\"{const_val[1:-1]}\""
            elif isinstance(const_val, str):
                formatted_val = f"\"{const_val}\""
            else:
                formatted_val = str(const_val)
            cond = re.sub(pattern, formatted_val, cond, flags=re.IGNORECASE)

        # Resolve Level-88 conditions
        for cond_name in self.level88_map.keys():
            pattern = r'(?<![A-Za-z0-9_-])' + re.escape(cond_name) + r'(?![A-Za-z0-9_-])'
            method_call = to_java_method(cond_name) + "()"
            cond = re.sub(pattern, method_call, cond, flags=re.IGNORECASE)

        # Normalize NOT = to <>
        cond = re.sub(r'\bNOT\s*=\s*', '<>', cond, flags=re.IGNORECASE)

        # Relational operators mapping
        cond = cond.replace("<=", "_LTE_").replace(">=", "_GTE_")
        cond = cond.replace("=", "==").replace("<>", "!=")
        cond = cond.replace("_LTE_", "<=").replace("_GTE_", ">=")

        # Logical operators mapping
        cond = re.sub(r'\bAND\b', '&&', cond, flags=re.IGNORECASE)
        cond = re.sub(r'\bOR\b', '||', cond, flags=re.IGNORECASE)
        cond = re.sub(r'\bNOT\b', '!', cond, flags=re.IGNORECASE)
        for v in self.var_types.keys():
            cond = re.sub(r'(?<![A-Za-z0-9_-])' + re.escape(v) + r'(?![A-Za-z0-9_-])', to_java_var(v), cond)
        for v, t in self.var_types.items():
            jv = to_java_var(v)
            if t == "BigDecimal":
                pattern = r'\b' + re.escape(jv) + r'(\[[^\]]+\])?\s*(==|!=|>|<|>=|<=)\s*([A-Za-z0-9_\-\.]+)\b'
                def repl_bd(match, _jv=jv, _v=v):
                    sub = match.group(1) or ""
                    op = match.group(2)
                    right = match.group(3)
                    right_upper = right.upper()
                    if right_upper in self.var_types:
                        r_java = to_java_var(right)
                        if self.var_types[right_upper] == "BigDecimal":
                            if right_upper in self.redefines_layout:
                                r_val = r_java
                            else:
                                r_val = f"{r_java}.getValue()"
                        else:
                            r_val = r_java
                    else:
                        r_val = f"new BigDecimal(\"{right}\")" if re.match(r'^\d+(\.\d+)?$', right) else right
                    map_ops = {"==": "== 0", "!=": "!= 0", ">": "> 0", "<": "< 0", ">=": ">= 0", "<=": "<= 0"}
                    if _v.upper() in self.redefines_layout:
                        return f"{_jv}{sub}.compareTo({r_val}) {map_ops.get(op, op)}"
                    else:
                        return f"{_jv}{sub}.getValue().compareTo({r_val}) {map_ops.get(op, op)}"
                cond = re.sub(pattern, repl_bd, cond)
            elif t == "String":
                pattern = r'\b' + re.escape(jv) + r'(\[[^\]]+\]|\.substring\((?:[^()]+|\([^()]*\))*\))?\s*(==|!=)\s*(\"[^\"]*\"|\'[^\']*\'|[A-Za-z0-9_\-\.]+)'
                def repl_str(match, _jv=jv):
                    sub = match.group(1) or ""
                    op = match.group(2)
                    right = match.group(3)
                    if right.upper() in ("SPACE", "SPACES"):
                        right = '""'
                    elif right.startswith("'") or right.startswith('"'):
                        right = f"\"{right[1:-1]}\""
                    else:
                        right = to_java_var(right)
                    return f"{_jv}{sub}.equals({right})" if op == "==" else f"!{_jv}{sub}.equals({right})"
                cond = re.sub(pattern, repl_str, cond)
        # Resolve redefined variables to getter methods
        for v in self.redefines_layout.keys():
            if not self.redefines_layout[v]["is_array"]:
                pattern = r'(?<![A-Za-z0-9_-])' + re.escape(to_java_var(v)) + r'(?![A-Za-z0-9_-])'
                cond = re.sub(pattern, f"get_{to_java_var(v)}()", cond)
        return cond

    def _generate_call_block(self, target_name: str, target_gen, caller_vars: list,
                              returning: str = None, args_info: list = None) -> list:
        """Generate CALL linkage code.
        BY REFERENCE (default): value is written in AND written back after call.
        BY CONTENT: value is snapshot-copied in; no writeback after call.
        """
        self.call_counter += 1
        suffix = f"_{self.call_counter}"
        target_vars = []
        for arg in target_gen.using_args:
            arg_upper = arg.upper()
            if arg_upper in target_gen.group_fields:
                for child in target_gen.group_fields[arg_upper]:
                    target_vars.append(child)
            else:
                target_vars.append(arg)

        # Build a flat mode list aligned with caller_vars (after group expansion).
        # args_info items use original (non-expanded) argument names.
        flat_modes = []
        if args_info:
            for info in args_info:
                mode = info.get("mode", "REFERENCE")
                orig_name = info.get("value", "").upper()
                # If the arg is a group, expand mode for each child
                if orig_name in (self.current_generator.group_fields if self.current_generator else {}):
                    count = len(self.current_generator.group_fields[orig_name])
                    flat_modes.extend([mode] * count)
                else:
                    flat_modes.append(mode)
        # Pad with REFERENCE if args_info was shorter
        while len(flat_modes) < len(caller_vars):
            flat_modes.append("REFERENCE")

        java_class = to_java_class(target_name)
        var_name = to_java_var(target_name) + suffix

        lines = []
        is_child = getattr(target_gen, "is_child", False)
        if is_child:
            caller_is_child = getattr(self.current_generator, "is_child", False)
            parent_arg = "parent" if caller_is_child else "this"
            lines.append(f"{java_class} {var_name} = new {java_class}({parent_arg});")
        else:
            lines.append(f"{java_class} {var_name} = new {java_class}();")

        for i, c_var in enumerate(caller_vars):
            if i < len(target_vars):
                t_var = target_vars[i]
                c_jvar = to_java_var(c_var)
                t_jvar = to_java_var(t_var)
                mode = flat_modes[i] if i < len(flat_modes) else "REFERENCE"
                if mode == "CONTENT":
                    # Snapshot the caller value into a local before the call
                    snap_var = f"_snap_{c_jvar}_{suffix}"
                    c_type = "String"
                    c_var_upper = c_var.upper()
                    for k, t in self.var_types.items():
                        if k.upper() == c_var_upper:
                            c_type = t
                            break
                    if c_type in ("Integer", "int"):
                        lines.append(f"int {snap_var} = {c_jvar};")
                    elif c_type in ("Long", "long"):
                        lines.append(f"long {snap_var} = {c_jvar};")
                    elif c_type == "BigDecimal":
                        lines.append(f"java.math.BigDecimal {snap_var} = {c_jvar}.getValue();")
                    else:
                        lines.append(f"String {snap_var} = {c_jvar};")
                    
                    if c_type == "BigDecimal":
                        lines.append(f"{var_name}.{t_jvar}.assign({snap_var}, com.systema.modernized.runtime.CobolRoundingMode.TRUNCATION, com.systema.modernized.runtime.SizeErrorPolicy.UNCHECKED);")
                    else:
                        lines.append(f"{var_name}.{t_jvar} = {snap_var};")
                else:
                    c_type = "String"
                    c_var_upper = c_var.upper()
                    for k, t in self.var_types.items():
                        if k.upper() == c_var_upper:
                            c_type = t
                            break
                    if c_type == "BigDecimal":
                        lines.append(f"{var_name}.{t_jvar}.assign({c_jvar}.getValue(), com.systema.modernized.runtime.CobolRoundingMode.TRUNCATION, com.systema.modernized.runtime.SizeErrorPolicy.UNCHECKED);")
                    else:
                        lines.append(f"{var_name}.{t_jvar} = {c_jvar};")

        lines.append(f"{var_name}.execute();")
        lines.append(f"return_code = {var_name}.return_code;")
        if returning:
            ret_jvar = to_java_var(returning)
            lines.append(f"{ret_jvar} = {var_name}.return_code;")

        # Writeback: only for BY REFERENCE args
        for i, c_var in enumerate(caller_vars):
            if i < len(target_vars):
                t_var = target_vars[i]
                c_jvar = to_java_var(c_var)
                t_jvar = to_java_var(t_var)
                mode = flat_modes[i] if i < len(flat_modes) else "REFERENCE"
                if mode != "CONTENT":
                    c_type = "String"
                    c_var_upper = c_var.upper()
                    for k, t in self.var_types.items():
                        if k.upper() == c_var_upper:
                            c_type = t
                            break
                    if c_type == "BigDecimal":
                        lines.append(f"{c_jvar}.assign({var_name}.{t_jvar}.getValue(), com.systema.modernized.runtime.CobolRoundingMode.TRUNCATION, com.systema.modernized.runtime.SizeErrorPolicy.UNCHECKED);")
                    else:
                        lines.append(f"{c_jvar} = {var_name}.{t_jvar};")

        return lines

class NativeFileIOGenerator:
    @staticmethod
    def generate_io_methods(fd_name: str, assign_path: str, is_input: bool, record_fields: list,
                            redefined_record_name: str = None, redefined_record_len: int = None,
                            organization: str = "SEQUENTIAL", record_key: str = None,
                            alternate_keys: list = None,
                            status_var: str = None, redefines_layout: dict = None,
                            assign_name: str = None,
                            var_pics: dict = None, var_usages: dict = None,
                            var_sign_positions: dict = None, var_sign_separates: dict = None,
                            has_reports: bool = False) -> str:
        java_fd = to_java_var(fd_name)
        
        var_pics = var_pics or {}
        var_usages = var_usages or {}
        var_sign_positions = var_sign_positions or {}
        var_sign_separates = var_sign_separates or {}
        
        def get_cobol_numeric_spec_init_local(var_name):
            var_upper = var_name.upper()
            pic = var_pics.get(var_upper, "")
            usage = var_usages.get(var_upper, "DISPLAY") or "DISPLAY"
            if pic:
                _, digits, scale, signed = NativeTypeMapper.parse_pic(pic)
            else:
                digits, scale, signed = 18, 0, True
            signed_str = "true" if signed else "false"
            
            usage_enum_map = {
                "DISPLAY": "com.systema.modernized.runtime.CobolUsage.DISPLAY",
                "COMP": "com.systema.modernized.runtime.CobolUsage.COMP",
                "COMP-3": "com.systema.modernized.runtime.CobolUsage.COMP_3",
                "COMP_3": "com.systema.modernized.runtime.CobolUsage.COMP_3",
                "COMP-5": "com.systema.modernized.runtime.CobolUsage.COMP_5",
                "COMP_5": "com.systema.modernized.runtime.CobolUsage.COMP_5",
                "BINARY": "com.systema.modernized.runtime.CobolUsage.COMP"
            }
            usage_val = usage_enum_map.get(usage.upper(), "com.systema.modernized.runtime.CobolUsage.DISPLAY")
            
            sign_pos = var_sign_positions.get(var_upper, "TRAILING")
            sign_pos_val = f"com.systema.modernized.runtime.CobolSignPosition.{sign_pos}"
            sign_sep = "true" if var_sign_separates.get(var_upper, False) else "false"
            
            return f"new com.systema.modernized.runtime.CobolNumericSpec({signed_str}, {digits}, {scale}, {usage_val}, {sign_pos_val}, {sign_sep})"

        offsets = []
        curr = 0
        for f_name, pic in record_fields:
            f_upper = f_name.upper()
            _, length, _, _ = NativeTypeMapper.parse_pic(pic)
            usage = var_usages.get(f_upper, "DISPLAY") or "DISPLAY"
            if usage.upper() in ("COMP-3", "PACKED-DECIMAL"):
                length = length // 2 + 1
            elif var_sign_separates.get(f_upper, False):
                length = length + 1
            offsets.append((f_name, curr, curr + length))
            curr += length
            
        field_offsets = {}
        for f_name, start, end in offsets:
            field_offsets[f_name.upper()] = (start, end)

        alt_key_defs = []
        if alternate_keys:
            for ak in alternate_keys:
                ak_name = ak["name"]
                if ak_name.upper() in field_offsets:
                    s, e = field_offsets[ak_name.upper()]
                    alt_key_defs.append({
                        "name": ak_name,
                        "clean_name": ak_name.lower().replace("-", "_"),
                        "start": s,
                        "end": e,
                        "with_duplicates": ak.get("with_duplicates", False)
                    })
            
        def get_status_assign(val):
            if not status_var:
                return ""
            status_jvar = to_java_var(status_var)
            if redefines_layout and status_var.upper() in redefines_layout:
                return f"set_{status_jvar}(\"{val}\");"
            else:
                return f"{status_jvar} = \"{val}\";"

        lines = []
        lines.append(f"    private String resolve_path_{java_fd}() {{")
        lines.append(f"        String resolvedPath = com.systema.modernized.JclExecutionContext.getDdAssignment(\"{fd_name}\");")
        if assign_name:
            lines.append(f"        if (resolvedPath == null) {{")
            lines.append(f"            resolvedPath = com.systema.modernized.JclExecutionContext.getDdAssignment(\"{assign_name}\");")
            lines.append(f"        }}")
        lines.append(f"        if (resolvedPath == null) {{")
        lines.append(f"            String cleanLogical = \"{fd_name}\";")
        lines.append(f"            if (cleanLogical.startsWith(\"UT-S-\")) {{")
        lines.append(f"                cleanLogical = cleanLogical.substring(5);")
        lines.append(f"            }} else if (cleanLogical.startsWith(\"UT_S_\")) {{")
        lines.append(f"                cleanLogical = cleanLogical.substring(5);")
        lines.append(f"            }}")
        lines.append(f"            resolvedPath = com.systema.modernized.JclExecutionContext.getDdAssignment(cleanLogical);")
        lines.append(f"        }}")
        lines.append(f"        if (resolvedPath == null) {{")
        lines.append(f"            resolvedPath = \"{assign_path}\";")
        lines.append(f"        }}")
        lines.append(f"        return resolvedPath;")
        lines.append(f"    }}")
        lines.append("")
        if organization in ("INDEXED", "RELATIVE"):
            fd_name_clean = fd_name.lower().replace("-", "_")
            key_start = 0
            key_end = curr
            if record_key:
                for f_name, start, end in offsets:
                    if f_name.upper() == record_key.upper():
                        key_start = start
                        key_end = end
                        break
            
            lines.append(f"    private java.util.Map<String, String> {java_fd}_records = new java.util.LinkedHashMap<>();")
            lines.append(f"    private java.util.List<String> {java_fd}_db_list = new java.util.ArrayList<>();")
            lines.append(f"    private java.util.Iterator<String> {java_fd}_iterator;")
            lines.append(f"    private boolean {java_fd}_eof = false;")
            lines.append("")
            
            lines.append(f"    private void save_{java_fd}() {{")
            lines.append(f"        try {{")
            lines.append(f"            java.nio.file.Path p = Paths.get(resolve_path_{java_fd}());")
            lines.append(f"            if (p.getParent() != null) Files.createDirectories(p.getParent());")
            lines.append(f"            boolean hasDb = false;")
            lines.append(f"            try {{")
            lines.append(f"                if (com.systema.modernized.SpringContextHelper.jdbcTemplate != null) {{")
            lines.append(f"                    hasDb = true;")
            lines.append(f"                }}")
            lines.append(f"            }} catch (Throwable t) {{}}")
            lines.append(f"            java.util.Collection<String> linesToWrite;")
            lines.append(f"            if (hasDb) {{")
            lines.append(f"                linesToWrite = com.systema.modernized.SpringContextHelper.jdbcTemplate.query(")
            lines.append(f"                    \"SELECT record_col FROM {fd_name_clean}_vsam ORDER BY key_col\",")
            lines.append(f"                    (rs, rowNum) -> rs.getString(\"record_col\")")
            lines.append(f"                );")
            lines.append(f"            }} else {{")
            lines.append(f"                linesToWrite = {java_fd}_records.values();")
            lines.append(f"            }}")
            lines.append(f"            try (BufferedWriter w = Files.newBufferedWriter(p)) {{")
            lines.append(f"                for (String line : linesToWrite) {{")
            lines.append(f"                    w.write(line);")
            lines.append(f"                    w.newLine();")
            lines.append(f"                }}")
            lines.append(f"            }}")
            lines.append(f"        }} catch (IOException e) {{")
            lines.append(f"            throw new RuntimeException(e);")
            lines.append(f"        }}")
            lines.append(f"    }}")
            lines.append("")
            
            lines.append(f"    private void open_{java_fd}() {{")
            lines.append(f"        open_{java_fd}(\"INPUT\");")
            lines.append(f"    }}")
            lines.append("")
            lines.append(f"    private void open_{java_fd}(String mode) {{")
            lines.append(f"        try {{")
            lines.append(f"            {java_fd}_records.clear();")
            lines.append(f"            {java_fd}_db_list.clear();")
            lines.append(f"            {java_fd}_iterator = null;")
            lines.append(f"            {java_fd}_eof = false;")
            lines.append(f"            boolean hasDb = false;")
            lines.append(f"            try {{")
            lines.append(f"                if (com.systema.modernized.SpringContextHelper.jdbcTemplate != null) {{")
            lines.append(f"                    hasDb = true;")
            lines.append(f"                }}")
            lines.append(f"            }} catch (Throwable t) {{}}")
            lines.append(f"            java.nio.file.Path p = Paths.get(resolve_path_{java_fd}());")
            lines.append(f"            if (hasDb) {{")
            
            alt_cols_ddl = ""
            for akd in alt_key_defs:
                alt_cols_ddl += f", {akd['clean_name']} VARCHAR(255)"
            
            lines.append(f"                com.systema.modernized.SpringContextHelper.jdbcTemplate.execute(")
            lines.append(f"                    \"CREATE TABLE IF NOT EXISTS {fd_name_clean}_vsam (key_col VARCHAR(255) PRIMARY KEY{alt_cols_ddl}, record_col VARCHAR(4000))\"")
            lines.append(f"                );")
            
            for akd in alt_key_defs:
                lines.append(f"                com.systema.modernized.SpringContextHelper.jdbcTemplate.execute(")
                lines.append(f"                    \"CREATE INDEX IF NOT EXISTS {fd_name_clean}_{akd['clean_name']}_idx ON {fd_name_clean}_vsam ({akd['clean_name']})\"")
                lines.append(f"                );")
                
            lines.append(f"                if (\"OUTPUT\".equalsIgnoreCase(mode)) {{")
            lines.append(f"                    com.systema.modernized.SpringContextHelper.jdbcTemplate.execute(\"DELETE FROM {fd_name_clean}_vsam\");")
            lines.append(f"                }} else if (Files.exists(p)) {{")
            lines.append(f"                    try (BufferedReader r = Files.newBufferedReader(p)) {{")
            lines.append(f"                        String line;")
            lines.append(f"                        int rrn = 1;")
            lines.append(f"                        while ((line = r.readLine()) != null) {{")
            lines.append(f"                            String key = \"\";")
            if organization == "RELATIVE":
                lines.append(f"                            key = String.valueOf(rrn++);")
            else:
                lines.append(f"                            if (line.length() >= {key_end}) {{")
                lines.append(f"                                key = line.substring({key_start}, {key_end}).trim();")
                lines.append(f"                            }}")
                
            for akd in alt_key_defs:
                lines.append(f"                            String alt_val_{akd['clean_name']} = \"\";")
                lines.append(f"                            if (line.length() >= {akd['end']}) {{")
                lines.append(f"                                alt_val_{akd['clean_name']} = line.substring({akd['start']}, {akd['end']}).trim();")
                lines.append(f"                            }}")
                
            lines.append(f"                            if (!key.isEmpty()) {{")
            lines.append(f"                                try {{")
            
            ins_cols = ["key_col"]
            ins_placeholders = ["?"]
            ins_args = ["key"]
            for akd in alt_key_defs:
                ins_cols.append(akd["clean_name"])
                ins_placeholders.append("?")
                ins_args.append(f"alt_val_{akd['clean_name']}")
            ins_cols.append("record_col")
            ins_placeholders.append("?")
            ins_args.append("line")
            
            ins_query = f"INSERT INTO {fd_name_clean}_vsam (" + ", ".join(ins_cols) + ") VALUES (" + ", ".join(ins_placeholders) + ")"
            ins_args_str = ", ".join(ins_args)
            
            lines.append(f"                                    com.systema.modernized.SpringContextHelper.jdbcTemplate.update(")
            lines.append(f"                                        \"{ins_query}\",")
            lines.append(f"                                        {ins_args_str}")
            lines.append(f"                                    );")
            lines.append(f"                                }} catch (Exception e) {{}}")
            lines.append(f"                            }}")
            lines.append(f"                        }}")
            lines.append(f"                    }}")
            lines.append(f"                }}")
            lines.append(f"            }} else {{")
            lines.append(f"                if (\"OUTPUT\".equalsIgnoreCase(mode)) {{")
            lines.append(f"                    if (Files.exists(p)) Files.delete(p);")
            lines.append(f"                }} else if (Files.exists(p)) {{")
            lines.append(f"                    try (BufferedReader r = Files.newBufferedReader(p)) {{")
            lines.append(f"                        String line;")
            if organization == "RELATIVE":
                lines.append(f"                        int rrn = 1;")
                lines.append(f"                        while ((line = r.readLine()) != null) {{")
                lines.append(f"                            {java_fd}_records.put(String.valueOf(rrn++), line);")
                lines.append(f"                        }}")
            else:
                lines.append(f"                        while ((line = r.readLine()) != null) {{")
                lines.append(f"                            if (line.length() >= {key_end}) {{")
                lines.append(f"                                String key = line.substring({key_start}, {key_end}).trim();")
                lines.append(f"                                {java_fd}_records.put(key, line);")
                lines.append(f"                            }}")
                lines.append(f"                        }}")
            lines.append(f"                    }}")
            lines.append(f"                }}")
            lines.append(f"            }}")
            lines.append(f"            if (!hasDb) {java_fd}_iterator = {java_fd}_records.values().iterator();")
            status_ok = get_status_assign("00")
            if status_ok: lines.append(f"            {status_ok}")
            lines.append(f"        }} catch (IOException e) {{")
            status_err = get_status_assign("35")
            if status_err:
                lines.append(f"            {status_err}")
            else:
                lines.append(f"            throw new RuntimeException(e);")
            lines.append(f"        }}")
            lines.append(f"    }}")
            lines.append("")
            
            lines.append(f"    private void populate_{java_fd}_fields(String line) {{")
            if redefined_record_name:
                java_rec = to_java_var(redefined_record_name)
                backing_var = f"{java_rec}_backing"
                lines.append(f"        String padded = String.format(\"%-\" + {redefined_record_len} + \"s\", line);")
                lines.append(f"        if (padded.length() > {redefined_record_len}) padded = padded.substring(0, {redefined_record_len});")
                lines.append(f"        for (int i = 0; i < {redefined_record_len}; i++) {{")
                lines.append(f"            {backing_var}[i] = padded.charAt(i);")
                lines.append(f"        }}")
            else:
                for f_name, start, end in offsets:
                    java_var = to_java_var(f_name)
                    pic = [p for n, p in record_fields if n == f_name][0]
                    java_type = NativeTypeMapper.get_java_type(pic)
                    lines.append(f"        if (line.length() >= {end}) {{")
                    lines.append(f"            String val = line.substring({start}, {end});")
                    if java_type == "BigDecimal":
                        scale = NativeTypeMapper.parse_pic(pic)[2]
                        signed = NativeTypeMapper.parse_pic(pic)[3]
                        if signed:
                            lines.append(f"            {java_var}.assign(parseSigned(val.trim(), {scale}));")
                        else:
                            lines.append(f"            {java_var}.assign(val.trim().isEmpty() ? BigDecimal.ZERO : new BigDecimal(val.trim()).movePointLeft({scale}));")
                    elif java_type in ("Integer", "Long"):
                        signed = NativeTypeMapper.parse_pic(pic)[3]
                        t_cast = "int" if java_type == "Integer" else "long"
                        if signed:
                            lines.append(f"            {java_var} = ({t_cast}) parseSignedLong(val.trim());")
                        else:
                            parse_call = "Integer.parseInt(val.trim())" if java_type == "Integer" else "Long.parseLong(val.trim())"
                            zero_val = "0" if java_type == "Integer" else "0L"
                            lines.append(f"            {java_var} = val.trim().isEmpty() ? {zero_val} : {parse_call};")
                    else:
                        lines.append(f"            {java_var} = val;")
                    lines.append(f"        }}")
            lines.append(f"    }}")
            lines.append("")
            
            lines.append(f"    private String format_{java_fd}_record() {{")
            if redefined_record_name:
                java_rec = to_java_var(redefined_record_name)
                backing_var = f"{java_rec}_backing"
                lines.append(f"        return new String({backing_var});")
            else:
                fmt_parts = []
                fmt_args = []
                for f_name, pic in record_fields:
                    java_var = to_java_var(f_name)
                    java_type = NativeTypeMapper.get_java_type(pic)
                    _, length, scale, signed = NativeTypeMapper.parse_pic(pic)
                    if java_type == "BigDecimal":
                        fmt_parts.append(f"%0{length}d")
                        var_ref = java_var
                        _rdl = redefines_layout or {}
                        if f_name.upper() not in _rdl:
                            var_ref = f"{java_var}.getValue()"
                        fmt_args.append(f"({var_ref}.movePointRight({scale}).longValue())")
                    elif java_type in ("Integer", "Long"):
                        if signed:
                            fmt_parts.append(f"%{length}s")
                            fmt_args.append(f"formatSigned({java_var}, {length}, true)")
                        else:
                            fmt_parts.append(f"%0{length}d")
                            fmt_args.append(java_var)
                    else:
                        fmt_parts.append(f"%-{length}s")
                        fmt_args.append(java_var)
                fmt_str = "".join(fmt_parts)
                args_str = ", ".join(fmt_args)
                lines.append(f"        return String.format(\"{fmt_str}\", {args_str});")
            lines.append(f"    }}")
            lines.append("")
            
            lines.append(f"    private boolean read_{java_fd}() {{")
            lines.append(f"        if ({java_fd}_eof) {{")
            status_inv = get_status_assign("46")
            if status_inv: lines.append(f"            {status_inv}")
            lines.append(f"            return false;")
            lines.append(f"        }}")
            lines.append(f"        boolean hasDb = false;")
            lines.append(f"        try {{")
            lines.append(f"            if (com.systema.modernized.SpringContextHelper.jdbcTemplate != null) {{")
            lines.append(f"                hasDb = true;")
            lines.append(f"            }}")
            lines.append(f"        }} catch (Throwable t) {{}}")
            lines.append(f"        if (hasDb) {{")
            lines.append(f"            if ({java_fd}_iterator == null) {{")
            lines.append(f"                {java_fd}_db_list = com.systema.modernized.SpringContextHelper.jdbcTemplate.query(")
            lines.append(f"                    \"SELECT record_col FROM {fd_name_clean}_vsam ORDER BY key_col\",")
            lines.append(f"                    (rs, rowNum) -> rs.getString(\"record_col\")")
            lines.append(f"                );")
            lines.append(f"                {java_fd}_iterator = {java_fd}_db_list.iterator();")
            lines.append(f"            }}")
            lines.append(f"            if (!{java_fd}_iterator.hasNext()) {{")
            lines.append(f"                {java_fd}_eof = true;")
            status_eof = get_status_assign("10")
            if status_eof: lines.append(f"                {status_eof}")
            lines.append(f"                return false;")
            lines.append(f"            }}")
            lines.append(f"            String line = {java_fd}_iterator.next();")
            lines.append(f"            populate_{java_fd}_fields(line);")
            status_ok = get_status_assign("00")
            if status_ok: lines.append(f"            {status_ok}")
            lines.append(f"            return true;")
            lines.append(f"        }} else {{")
            lines.append(f"            if ({java_fd}_iterator == null) {{")
            lines.append(f"                {java_fd}_iterator = {java_fd}_records.values().iterator();")
            lines.append(f"            }}")
            lines.append(f"            if (!{java_fd}_iterator.hasNext()) {{")
            lines.append(f"                {java_fd}_eof = true;")
            status_eof = get_status_assign("10")
            if status_eof: lines.append(f"                {status_eof}")
            lines.append(f"                return false;")
            lines.append(f"            }}")
            lines.append(f"            String line = {java_fd}_iterator.next();")
            lines.append(f"            populate_{java_fd}_fields(line);")
            status_ok = get_status_assign("00")
            if status_ok: lines.append(f"            {status_ok}")
            lines.append(f"            return true;")
            lines.append(f"        }}")
            lines.append(f"    }}")
            lines.append("")
            
            lines.append(f"    private boolean read_{java_fd}_key(String key) {{")
            lines.append(f"        return read_{java_fd}_key(key, \"{record_key.upper() if record_key else ''}\");")
            lines.append(f"    }}")
            lines.append("")
            lines.append(f"    private boolean read_{java_fd}_key(String key, String keyName) {{")
            lines.append(f"        {java_fd}_eof = false;")
            lines.append(f"        boolean hasDb = false;")
            lines.append(f"        try {{")
            lines.append(f"            if (com.systema.modernized.SpringContextHelper.jdbcTemplate != null) {{")
            lines.append(f"                hasDb = true;")
            lines.append(f"            }}")
            lines.append(f"        }} catch (Throwable t) {{}}")
            lines.append(f"        if (hasDb) {{")
            lines.append(f"            String line = null;")
            lines.append(f"            String queryKey = keyName.toUpperCase();")
            lines.append(f"            try {{")
            lines.append(f"                boolean matched = false;")
            for akd in alt_key_defs:
                lines.append(f"                if (queryKey.equals(\"{akd['name'].upper()}\")) {{")
                lines.append(f"                    java.util.List<String> results = com.systema.modernized.SpringContextHelper.jdbcTemplate.query(")
                lines.append(f"                        \"SELECT record_col FROM {fd_name_clean}_vsam WHERE {akd['clean_name']} = ? ORDER BY key_col\",")
                lines.append(f"                        (rs, rowNum) -> rs.getString(\"record_col\"), key.trim()")
                lines.append(f"                    );")
                lines.append(f"                    if (!results.isEmpty()) line = results.get(0);")
                lines.append(f"                    matched = true;")
                lines.append(f"                }}")
            lines.append(f"                if (!matched) {{")
            lines.append(f"                    try {{")
            lines.append(f"                        line = com.systema.modernized.SpringContextHelper.jdbcTemplate.queryForObject(")
            lines.append(f"                            \"SELECT record_col FROM {fd_name_clean}_vsam WHERE key_col = ?\",")
            lines.append(f"                            String.class, key.trim()")
            lines.append(f"                        );")
            lines.append(f"                    }} catch (Exception e) {{")
            lines.append(f"                        try {{")
            lines.append(f"                            String keyWithLeadingZero = key.trim();")
            lines.append(f"                            try {{")
            lines.append(f"                                keyWithLeadingZero = String.valueOf(Integer.parseInt(keyWithLeadingZero));")
            lines.append(f"                            }} catch (Exception ex) {{}}")
            lines.append(f"                            line = com.systema.modernized.SpringContextHelper.jdbcTemplate.queryForObject(")
            lines.append(f"                                \"SELECT record_col FROM {fd_name_clean}_vsam WHERE key_col = ?\",")
            lines.append(f"                                String.class, keyWithLeadingZero")
            lines.append(f"                            );")
            lines.append(f"                        }} catch (Exception ex) {{}}")
            lines.append(f"                    }}")
            lines.append(f"                }}")
            lines.append(f"            }} catch (Exception e) {{}}")
            lines.append(f"            if (line == null) {{")
            status_err = get_status_assign("23")
            if status_err: lines.append(f"                {status_err}")
            lines.append(f"                return false;")
            lines.append(f"            }}")
            lines.append(f"            populate_{java_fd}_fields(line);")
            status_ok = get_status_assign("00")
            if status_ok: lines.append(f"            {status_ok}")
            lines.append(f"            return true;")
            lines.append(f"        }} else {{")
            lines.append(f"            String queryKey = keyName.toUpperCase();")
            lines.append(f"            String line = null;")
            lines.append(f"            boolean matched = false;")
            for akd in alt_key_defs:
                lines.append(f"            if (queryKey.equals(\"{akd['name'].upper()}\")) {{")
                lines.append(f"                for (String record : {java_fd}_records.values()) {{")
                lines.append(f"                    if (record.length() >= {akd['end']}) {{")
                lines.append(f"                        String val = record.substring({akd['start']}, {akd['end']}).trim();")
                lines.append(f"                        if (val.equals(key.trim())) {{")
                lines.append(f"                            line = record;")
                lines.append(f"                            break;")
                lines.append(f"                        }}")
                lines.append(f"                    }}")
                lines.append(f"                }}")
                lines.append(f"                matched = true;")
                lines.append(f"            }}")
            lines.append(f"            if (!matched) {{")
            lines.append(f"                line = {java_fd}_records.get(key.trim());")
            lines.append(f"                if (line == null) {{")
            lines.append(f"                    String keyWithLeadingZero = key.trim();")
            lines.append(f"                    try {{")
            lines.append(f"                        keyWithLeadingZero = String.valueOf(Integer.parseInt(keyWithLeadingZero));")
            lines.append(f"                    }} catch (Exception e) {{}}")
            lines.append(f"                    line = {java_fd}_records.get(keyWithLeadingZero);")
            lines.append(f"                }}")
            lines.append(f"            }}")
            lines.append(f"            if (line == null) {{")
            status_err = get_status_assign("23")
            if status_err: lines.append(f"                {status_err}")
            lines.append(f"                return false;")
            lines.append(f"            }}")
            lines.append(f"            populate_{java_fd}_fields(line);")
            status_ok = get_status_assign("00")
            if status_ok: lines.append(f"            {status_ok}")
            lines.append(f"            return true;")
            lines.append(f"        }}")
            lines.append(f"    }}")
            lines.append("")
            
            lines.append(f"    private boolean write_{java_fd}() {{")
            lines.append(f"        String line = format_{java_fd}_record();")
            lines.append(f"        boolean hasDb = false;")
            lines.append(f"        try {{")
            lines.append(f"            if (com.systema.modernized.SpringContextHelper.jdbcTemplate != null) {{")
            lines.append(f"                hasDb = true;")
            lines.append(f"            }}")
            lines.append(f"        }} catch (Throwable t) {{}}")
            lines.append(f"        if (hasDb) {{")
            lines.append(f"            String key = \"\";")
            if organization == "RELATIVE":
                if record_key:
                    lines.append(f"            key = String.valueOf({to_java_var(record_key)}).trim();")
                else:
                    lines.append(f"            int count = com.systema.modernized.SpringContextHelper.jdbcTemplate.queryForObject(")
                    lines.append(f"                \"SELECT COUNT(*) FROM {fd_name_clean}_vsam\", Integer.class")
                    lines.append(f"            );")
                    lines.append(f"            key = String.valueOf(count + 1);")
            else:
                lines.append(f"            if (line.length() >= {key_end}) {{")
                lines.append(f"                key = line.substring({key_start}, {key_end}).trim();")
                lines.append(f"            }}")
            lines.append(f"            try {{")
            for akd in alt_key_defs:
                lines.append(f"                String alt_val_{akd['clean_name']} = \"\";")
                lines.append(f"                if (line.length() >= {akd['end']}) {{")
                lines.append(f"                    alt_val_{akd['clean_name']} = line.substring({akd['start']}, {akd['end']}).trim();")
                lines.append(f"                }}")
            lines.append(f"                int existing = com.systema.modernized.SpringContextHelper.jdbcTemplate.queryForObject(")
            lines.append(f"                    \"SELECT COUNT(*) FROM {fd_name_clean}_vsam WHERE key_col = ?\", Integer.class, key")
            lines.append(f"                );")
            lines.append(f"                if (existing > 0) {{")
            status_dup = get_status_assign("22")
            if status_dup: lines.append(f"                    {status_dup}")
            lines.append(f"                    return false;")
            lines.append(f"                }}")
            for akd in alt_key_defs:
                if not akd["with_duplicates"]:
                    lines.append(f"                int existing_{akd['clean_name']} = com.systema.modernized.SpringContextHelper.jdbcTemplate.queryForObject(")
                    lines.append(f"                    \"SELECT COUNT(*) FROM {fd_name_clean}_vsam WHERE {akd['clean_name']} = ?\", Integer.class, alt_val_{akd['clean_name']}")
                    lines.append(f"                );")
                    lines.append(f"                if (existing_{akd['clean_name']} > 0) {{")
                    status_dup = get_status_assign("22")
                    if status_dup: lines.append(f"                    {status_dup}")
                    lines.append(f"                    return false;")
                    lines.append(f"                }}")
            ins_cols = ["key_col"]
            ins_placeholders = ["?"]
            ins_args = ["key"]
            for akd in alt_key_defs:
                ins_cols.append(akd["clean_name"])
                ins_placeholders.append("?")
                ins_args.append(f"alt_val_{akd['clean_name']}")
            ins_cols.append("record_col")
            ins_placeholders.append("?")
            ins_args.append("line")
            
            ins_query = f"INSERT INTO {fd_name_clean}_vsam (" + ", ".join(ins_cols) + ") VALUES (" + ", ".join(ins_placeholders) + ")"
            ins_args_str = ", ".join(ins_args)
            lines.append(f"                com.systema.modernized.SpringContextHelper.jdbcTemplate.update(")
            lines.append(f"                    \"{ins_query}\", {ins_args_str}")
            lines.append(f"                );")
            lines.append(f"                save_{java_fd}();")
            status_ok_00 = get_status_assign("00")
            status_ok_02 = get_status_assign("02")
            dup_alt_defs = [akd for akd in alt_key_defs if akd.get("with_duplicates")]
            if dup_alt_defs:
                lines.append(f"                boolean hasDupAlt = false;")
                for akd in dup_alt_defs:
                    lines.append(f"                if (com.systema.modernized.SpringContextHelper.jdbcTemplate.queryForObject(\"SELECT COUNT(*) FROM {fd_name_clean}_vsam WHERE {akd['clean_name']} = ?\", Integer.class, alt_val_{akd['clean_name']}) > 1) hasDupAlt = true;")
                lines.append(f"                if (hasDupAlt) {{")
                if status_ok_02: lines.append(f"                    {status_ok_02}")
                lines.append(f"                }} else {{")
                if status_ok_00: lines.append(f"                    {status_ok_00}")
                lines.append(f"                }}")
            else:
                if status_ok_00: lines.append(f"                {status_ok_00}")
            lines.append(f"                return true;")
            lines.append(f"            }} catch (Exception e) {{")
            status_dup = get_status_assign("22")
            if status_dup: lines.append(f"                {status_dup}")
            lines.append(f"                return false;")
            lines.append(f"            }}")
            lines.append(f"        }} else {{")
            if organization == "RELATIVE":
                if record_key:
                    lines.append(f"            String key = String.valueOf({to_java_var(record_key)}).trim();")
                else:
                    lines.append(f"            String key = String.valueOf({java_fd}_records.size() + 1);")
                lines.append(f"            if ({java_fd}_records.containsKey(key)) {{")
                status_dup = get_status_assign("22")
                if status_dup: lines.append(f"                {status_dup}")
                lines.append(f"                return false;")
                lines.append(f"            }}")
                lines.append(f"            {java_fd}_records.put(key, line);")
                lines.append(f"            save_{java_fd}();")
                status_ok = get_status_assign("00")
                if status_ok: lines.append(f"            {status_ok}")
                lines.append(f"            return true;")
            else:
                lines.append(f"            if (line.length() >= {key_end}) {{")
                lines.append(f"                String key = line.substring({key_start}, {key_end}).trim();")
                lines.append(f"                if ({java_fd}_records.containsKey(key)) {{")
                status_dup = get_status_assign("22")
                if status_dup: lines.append(f"                    {status_dup}")
                lines.append(f"                    return false;")
                lines.append(f"                }}")
                for akd in alt_key_defs:
                    if not akd["with_duplicates"]:
                        lines.append(f"                String ak_val_{akd['clean_name']} = line.length() >= {akd['end']} ? line.substring({akd['start']}, {akd['end']}).trim() : \"\";")
                        lines.append(f"                for (String r : {java_fd}_records.values()) {{")
                        lines.append(f"                    String r_ak = r.length() >= {akd['end']} ? r.substring({akd['start']}, {akd['end']}).trim() : \"\";")
                        lines.append(f"                    if (r_ak.equals(ak_val_{akd['clean_name']})) {{")
                        status_dup = get_status_assign("22")
                        if status_dup: lines.append(f"                        {status_dup}")
                        lines.append(f"                        return false;")
                        lines.append(f"                    }}")
                        lines.append(f"                }}")
                lines.append(f"                {java_fd}_records.put(key, line);")
                lines.append(f"                save_{java_fd}();")
                status_ok_00 = get_status_assign("00")
                status_ok_02 = get_status_assign("02")
                dup_alt_defs = [akd for akd in alt_key_defs if akd.get("with_duplicates")]
                if dup_alt_defs:
                    lines.append(f"                boolean hasDupAltNonDb = false;")
                    for akd in dup_alt_defs:
                        lines.append(f"                String ak_dup_val_{akd['clean_name']} = line.length() >= {akd['end']} ? line.substring({akd['start']}, {akd['end']}).trim() : \"\";")
                        lines.append(f"                int dup_count_{akd['clean_name']} = 0;")
                        lines.append(f"                for (String r : {java_fd}_records.values()) {{")
                        lines.append(f"                    String r_ak = r.length() >= {akd['end']} ? r.substring({akd['start']}, {akd['end']}).trim() : \"\";")
                        lines.append(f"                    if (r_ak.equals(ak_dup_val_{akd['clean_name']})) dup_count_{akd['clean_name']}++;")
                        lines.append(f"                }}")
                        lines.append(f"                if (dup_count_{akd['clean_name']} > 1) hasDupAltNonDb = true;")
                    lines.append(f"                if (hasDupAltNonDb) {{")
                    if status_ok_02: lines.append(f"                    {status_ok_02}")
                    lines.append(f"                }} else {{")
                    if status_ok_00: lines.append(f"                    {status_ok_00}")
                    lines.append(f"                }}")
                else:
                    if status_ok_00: lines.append(f"                {status_ok_00}")
                lines.append(f"                return true;")
                lines.append(f"            }}")
                lines.append(f"            return false;")
            lines.append(f"        }}")
            lines.append(f"    }}")
            lines.append("")
            
            lines.append(f"    private boolean rewrite_{java_fd}() {{")
            lines.append(f"        String line = format_{java_fd}_record();")
            lines.append(f"        boolean hasDb = false;")
            lines.append(f"        try {{")
            lines.append(f"            if (com.systema.modernized.SpringContextHelper.jdbcTemplate != null) {{")
            lines.append(f"                hasDb = true;")
            lines.append(f"            }}")
            lines.append(f"        }} catch (Throwable t) {{}}")
            lines.append(f"        if (hasDb) {{")
            lines.append(f"            String key = \"\";")
            if organization == "RELATIVE":
                if record_key:
                    lines.append(f"            key = String.valueOf({to_java_var(record_key)}).trim();")
                else:
                    lines.append(f"            int count = com.systema.modernized.SpringContextHelper.jdbcTemplate.queryForObject(")
                    lines.append(f"                \"SELECT COUNT(*) FROM {fd_name_clean}_vsam\", Integer.class")
                    lines.append(f"            );")
                    lines.append(f"            key = String.valueOf(count);")
            else:
                lines.append(f"            if (line.length() >= {key_end}) {{")
                lines.append(f"                key = line.substring({key_start}, {key_end}).trim();")
                lines.append(f"            }}")
            for akd in alt_key_defs:
                lines.append(f"            String alt_val_{akd['clean_name']} = \"\";")
                lines.append(f"            if (line.length() >= {akd['end']}) {{")
                lines.append(f"                alt_val_{akd['clean_name']} = line.substring({akd['start']}, {akd['end']}).trim();")
                lines.append(f"            }}")
            for akd in alt_key_defs:
                if not akd["with_duplicates"]:
                    lines.append(f"            int existing_{akd['clean_name']} = com.systema.modernized.SpringContextHelper.jdbcTemplate.queryForObject(")
                    lines.append(f"                \"SELECT COUNT(*) FROM {fd_name_clean}_vsam WHERE {akd['clean_name']} = ? AND key_col != ?\", Integer.class, alt_val_{akd['clean_name']}, key")
                    lines.append(f"            );")
                    lines.append(f"            if (existing_{akd['clean_name']} > 0) {{")
                    status_dup = get_status_assign("22")
                    if status_dup: lines.append(f"                {status_dup}")
                    lines.append(f"                return false;")
                    lines.append(f"            }}")
            upd_sets = ["record_col = ?"]
            upd_args = ["line"]
            for akd in alt_key_defs:
                upd_sets.append(f"{akd['clean_name']} = ?")
                upd_args.append(f"alt_val_{akd['clean_name']}")
            upd_args.append("key")
            upd_query = f"UPDATE {fd_name_clean}_vsam SET " + ", ".join(upd_sets) + " WHERE key_col = ?"
            upd_args_str = ", ".join(upd_args)
            lines.append(f"            int rows = com.systema.modernized.SpringContextHelper.jdbcTemplate.update(")
            lines.append(f"                \"{upd_query}\", {upd_args_str}")
            lines.append(f"            );")
            lines.append(f"            if (rows == 0) {{")
            status_miss = get_status_assign("23")
            if status_miss: lines.append(f"                {status_miss}")
            lines.append(f"                return false;")
            lines.append(f"            }}")
            lines.append(f"            save_{java_fd}();")
            status_ok = get_status_assign("00")
            if status_ok: lines.append(f"            {status_ok}")
            lines.append(f"            return true;")
            lines.append(f"        }} else {{")
            if organization == "RELATIVE":
                if record_key:
                    lines.append(f"            String key = String.valueOf({to_java_var(record_key)}).trim();")
                else:
                    lines.append(f"            String key = String.valueOf({java_fd}_records.size());")
                lines.append(f"            if (!{java_fd}_records.containsKey(key)) {{")
                status_miss = get_status_assign("23")
                if status_miss: lines.append(f"                {status_miss}")
                lines.append(f"                return false;")
                lines.append(f"            }}")
                lines.append(f"            {java_fd}_records.put(key, line);")
                lines.append(f"            save_{java_fd}();")
                status_ok = get_status_assign("00")
                if status_ok: lines.append(f"            {status_ok}")
                lines.append(f"            return true;")
            else:
                lines.append(f"            if (line.length() >= {key_end}) {{")
                lines.append(f"                String key = line.substring({key_start}, {key_end}).trim();")
                lines.append(f"                if (!{java_fd}_records.containsKey(key)) {{")
                status_miss = get_status_assign("23")
                if status_miss: lines.append(f"                    {status_miss}")
                lines.append(f"                    return false;")
                lines.append(f"                }}")
                for akd in alt_key_defs:
                    if not akd["with_duplicates"]:
                        lines.append(f"                String ak_val_{akd['clean_name']} = line.length() >= {akd['end']} ? line.substring({akd['start']}, {akd['end']}).trim() : \"\";")
                        lines.append(f"                for (java.util.Map.Entry<String, String> entry : {java_fd}_records.entrySet()) {{")
                        lines.append(f"                    if (!entry.getKey().equals(key)) {{")
                        lines.append(f"                        String r = entry.getValue();")
                        lines.append(f"                        String r_ak = r.length() >= {akd['end']} ? r.substring({akd['start']}, {akd['end']}).trim() : \"\";")
                        lines.append(f"                        if (r_ak.equals(ak_val_{akd['clean_name']})) {{")
                        status_dup = get_status_assign("22")
                        if status_dup: lines.append(f"                            {status_dup}")
                        lines.append(f"                            return false;")
                        lines.append(f"                        }}")
                        lines.append(f"                    }}")
                        lines.append(f"                }}")
                lines.append(f"                {java_fd}_records.put(key, line);")
                lines.append(f"                save_{java_fd}();")
                status_ok = get_status_assign("00")
                if status_ok: lines.append(f"                {status_ok}")
                lines.append(f"                return true;")
                lines.append(f"            }}")
                lines.append(f"            return false;")
            lines.append(f"        }}")
            lines.append(f"    }}")
            lines.append("")
            
            lines.append(f"    private boolean delete_{java_fd}() {{")
            lines.append(f"        String line = format_{java_fd}_record();")
            lines.append(f"        boolean hasDb = false;")
            lines.append(f"        try {{")
            lines.append(f"            if (com.systema.modernized.SpringContextHelper.jdbcTemplate != null) {{")
            lines.append(f"                hasDb = true;")
            lines.append(f"            }}")
            lines.append(f"        }} catch (Throwable t) {{}}")
            lines.append(f"        if (hasDb) {{")
            lines.append(f"            String key = \"\";")
            if organization == "RELATIVE":
                if record_key:
                    lines.append(f"            key = String.valueOf({to_java_var(record_key)}).trim();")
                else:
                    lines.append(f"            int count = com.systema.modernized.SpringContextHelper.jdbcTemplate.queryForObject(")
                    lines.append(f"                \"SELECT COUNT(*) FROM {fd_name_clean}_vsam\", Integer.class")
                    lines.append(f"            );")
                    lines.append(f"            key = String.valueOf(count);")
            else:
                lines.append(f"            if (line.length() >= {key_end}) {{")
                lines.append(f"                key = line.substring({key_start}, {key_end}).trim();")
                lines.append(f"            }}")
            lines.append(f"            int rows = com.systema.modernized.SpringContextHelper.jdbcTemplate.update(")
            lines.append(f"                \"DELETE FROM {fd_name_clean}_vsam WHERE key_col = ?\", key")
            lines.append(f"            );")
            lines.append(f"            if (rows == 0) {{")
            status_miss = get_status_assign("23")
            if status_miss: lines.append(f"                {status_miss}")
            lines.append(f"                return false;")
            lines.append(f"            }}")
            lines.append(f"            save_{java_fd}();")
            status_ok = get_status_assign("00")
            if status_ok: lines.append(f"            {status_ok}")
            lines.append(f"            return true;")
            lines.append(f"        }} else {{")
            if organization == "RELATIVE":
                if record_key:
                    lines.append(f"            String key = String.valueOf({to_java_var(record_key)}).trim();")
                else:
                    lines.append(f"            String key = String.valueOf({java_fd}_records.size());")
                lines.append(f"            if (!{java_fd}_records.containsKey(key)) {{")
                status_miss = get_status_assign("23")
                if status_miss: lines.append(f"                {status_miss}")
                lines.append(f"                return false;")
                lines.append(f"            }}")
                lines.append(f"            {java_fd}_records.remove(key);")
                lines.append(f"            save_{java_fd}();")
                status_ok = get_status_assign("00")
                if status_ok: lines.append(f"            {status_ok}")
                lines.append(f"            return true;")
            else:
                lines.append(f"            if (line.length() >= {key_end}) {{")
                lines.append(f"                String key = line.substring({key_start}, {key_end}).trim();")
                lines.append(f"                if (!{java_fd}_records.containsKey(key)) {{")
                status_miss = get_status_assign("23")
                if status_miss: lines.append(f"                    {status_miss}")
                lines.append(f"                    return false;")
                lines.append(f"                }}")
                lines.append(f"                {java_fd}_records.remove(key);")
                lines.append(f"                save_{java_fd}();")
                status_ok = get_status_assign("00")
                if status_ok: lines.append(f"                {status_ok}")
                lines.append(f"                return true;")
                lines.append(f"            }}")
                lines.append(f"            return false;")
            lines.append(f"        }}")
            lines.append(f"    }}")
            lines.append("")
            
            lines.append(f"    private boolean delete_{java_fd}_key(String key) {{")
            lines.append(f"        if (key == null) return false;")
            lines.append(f"        boolean hasDb = false;")
            lines.append(f"        try {{")
            lines.append(f"            if (com.systema.modernized.SpringContextHelper.jdbcTemplate != null) {{")
            lines.append(f"                hasDb = true;")
            lines.append(f"            }}")
            lines.append(f"        }} catch (Throwable t) {{}}")
            lines.append(f"        if (hasDb) {{")
            lines.append(f"            int rows = com.systema.modernized.SpringContextHelper.jdbcTemplate.update(")
            lines.append(f"                \"DELETE FROM {fd_name_clean}_vsam WHERE key_col = ?\", key.trim()")
            lines.append(f"            );")
            lines.append(f"            if (rows == 0) {{")
            status_miss = get_status_assign("23")
            if status_miss: lines.append(f"                {status_miss}")
            lines.append(f"                return false;")
            lines.append(f"            }}")
            lines.append(f"            save_{java_fd}();")
            status_ok = get_status_assign("00")
            if status_ok: lines.append(f"            {status_ok}")
            lines.append(f"            return true;")
            lines.append(f"        }} else {{")
            lines.append(f"            if (!{java_fd}_records.containsKey(key.trim())) {{")
            status_miss = get_status_assign("23")
            if status_miss: lines.append(f"                {status_miss}")
            lines.append(f"                return false;")
            lines.append(f"            }}")
            lines.append(f"            {java_fd}_records.remove(key.trim());")
            lines.append(f"            save_{java_fd}();")
            status_ok = get_status_assign("00")
            if status_ok: lines.append(f"            {status_ok}")
            lines.append(f"            return true;")
            lines.append(f"        }}")
            lines.append(f"    }}")
            lines.append("")
            lines.append(f"    private boolean start_{java_fd}(String key, String op) {{")
            lines.append(f"        return start_{java_fd}(key, op, \"{record_key.upper() if record_key else ''}\");")
            lines.append(f"    }}")
            lines.append("")
            lines.append(f"    private boolean start_{java_fd}(String key, String op, String keyName) {{")
            lines.append(f"        if (key == null) return false;")
            lines.append(f"        {java_fd}_eof = false;")
            lines.append(f"        boolean hasDb = false;")
            lines.append(f"        try {{")
            lines.append(f"            if (com.systema.modernized.SpringContextHelper.jdbcTemplate != null) {{")
            lines.append(f"                hasDb = true;")
            lines.append(f"            }}")
            lines.append(f"        }} catch (Throwable t) {{}}")
            lines.append(f"        if (hasDb) {{")
            lines.append(f"            String op_sql = op.trim();")
            lines.append(f"            if (op_sql.equals(\"NOT <\")) op_sql = \">=\";")
            lines.append(f"            String queryKey = keyName.toUpperCase();")
            lines.append(f"            boolean matched = false;")
            for akd in alt_key_defs:
                lines.append(f"            if (queryKey.equals(\"{akd['name'].upper()}\")) {{")
                lines.append(f"                {java_fd}_db_list = com.systema.modernized.SpringContextHelper.jdbcTemplate.query(")
                lines.append(f"                    \"SELECT record_col FROM {fd_name_clean}_vsam WHERE {akd['clean_name']} \" + op_sql + \" ? ORDER BY {akd['clean_name']}, key_col\",")
                lines.append(f"                    (rs, rowNum) -> rs.getString(\"record_col\"), key.trim()")
                lines.append(f"                );")
                lines.append(f"                matched = true;")
                lines.append(f"            }}")
            lines.append(f"            if (!matched) {{")
            lines.append(f"                {java_fd}_db_list = com.systema.modernized.SpringContextHelper.jdbcTemplate.query(")
            lines.append(f"                    \"SELECT record_col FROM {fd_name_clean}_vsam WHERE key_col \" + op_sql + \" ? ORDER BY key_col\",")
            lines.append(f"                    (rs, rowNum) -> rs.getString(\"record_col\"), key.trim()")
            lines.append(f"                );")
            lines.append(f"            }}")
            lines.append(f"            if ({java_fd}_db_list.isEmpty()) {{")
            status_miss = get_status_assign("23")
            if status_miss: lines.append(f"                {status_miss}")
            lines.append(f"                return false;")
            lines.append(f"            }}")
            lines.append(f"            {java_fd}_iterator = {java_fd}_db_list.iterator();")
            status_ok = get_status_assign("00")
            if status_ok: lines.append(f"            {status_ok}")
            lines.append(f"            return true;")
            lines.append(f"        }} else {{")
            if organization == "RELATIVE":
                lines.append(f"            java.util.List<java.util.Map.Entry<String, String>> sortedEntries = new java.util.ArrayList<>({java_fd}_records.entrySet());")
                lines.append(f"            sortedEntries.sort((e1, e2) -> {{")
                lines.append(f"                try {{ return Long.compare(Long.parseLong(e1.getKey().trim()), Long.parseLong(e2.getKey().trim())); }} catch (Exception ex) {{ return e1.getKey().compareTo(e2.getKey()); }}")
                lines.append(f"            }});")
                lines.append(f"            java.util.List<String> matchedRecords = new java.util.ArrayList<>();")
                lines.append(f"            String startOp = op.trim();")
                lines.append(f"            long targetRrn = 0;")
                lines.append(f"            try {{ targetRrn = Long.parseLong(key.trim()); }} catch (Exception ex) {{}}")
                lines.append(f"            boolean found = false;")
                lines.append(f"            for (java.util.Map.Entry<String, String> entry : sortedEntries) {{")
                lines.append(f"                long rrn = 0;")
                lines.append(f"                try {{ rrn = Long.parseLong(entry.getKey().trim()); }} catch (Exception ex) {{}}")
                lines.append(f"                int cmp = Long.compare(rrn, targetRrn);")
                lines.append(f"                boolean match = false;")
                lines.append(f"                if (startOp.equals(\"=\")) match = (cmp == 0);")
                lines.append(f"                else if (startOp.equals(\">\")) match = (cmp > 0);")
                lines.append(f"                else if (startOp.equals(\">=\") || startOp.equals(\"NOT <\")) match = (cmp >= 0);")
                lines.append(f"                if (found || match) {{")
                lines.append(f"                    found = true;")
                lines.append(f"                    matchedRecords.add(entry.getValue());")
                lines.append(f"                }}")
                lines.append(f"            }}")
                lines.append(f"            if (!found) {{")
                status_miss = get_status_assign("23")
                if status_miss: lines.append(f"                {status_miss}")
                lines.append(f"                return false;")
                lines.append(f"            }}")
                lines.append(f"            {java_fd}_iterator = matchedRecords.iterator();")
                status_ok = get_status_assign("00")
                if status_ok: lines.append(f"            {status_ok}")
                lines.append(f"            return true;")
            else:
                lines.append(f"            String queryKey = keyName.toUpperCase();")
                lines.append(f"            java.util.List<String> sortedRecords = new java.util.ArrayList<>({java_fd}_records.values());")
                lines.append(f"            boolean matched = false;")
                for akd in alt_key_defs:
                    lines.append(f"            if (queryKey.equals(\"{akd['name'].upper()}\")) {{")
                    lines.append(f"                sortedRecords.sort((r1, r2) -> {{")
                    lines.append(f"                    String v1 = r1.length() >= {akd['end']} ? r1.substring({akd['start']}, {akd['end']}) : \"\";")
                    lines.append(f"                    String v2 = r2.length() >= {akd['end']} ? r2.substring({akd['start']}, {akd['end']}) : \"\";")
                    lines.append(f"                    int cmp = v1.compareTo(v2);")
                    lines.append(f"                    if (cmp != 0) return cmp;")
                    lines.append(f"                    return r1.compareTo(r2);")
                    lines.append(f"                }});")
                    lines.append(f"                matched = true;")
                    lines.append(f"            }}")
                lines.append(f"            if (!matched) {{")
                lines.append(f"                sortedRecords.sort((r1, r2) -> {{")
                lines.append(f"                    String v1 = r1.length() >= {key_end} ? r1.substring({key_start}, {key_end}) : \"\";")
                lines.append(f"                    String v2 = r2.length() >= {key_end} ? r2.substring({key_start}, {key_end}) : \"\";")
                lines.append(f"                    return v1.compareTo(v2);")
                lines.append(f"                }});")
                lines.append(f"            }}")
                lines.append(f"            java.util.List<String> matchedRecords = new java.util.ArrayList<>();")
                lines.append(f"            String targetKey = key.trim();")
                lines.append(f"            String startOp = op.trim();")
                lines.append(f"            boolean found = false;")
                lines.append(f"            for (String record : sortedRecords) {{")
                lines.append(f"                String val = \"\";")
                lines.append(f"                boolean isAlt = false;")
                for akd in alt_key_defs:
                    lines.append(f"                if (queryKey.equals(\"{akd['name'].upper()}\")) {{")
                    lines.append(f"                    if (record.length() >= {akd['end']}) val = record.substring({akd['start']}, {akd['end']}).trim();")
                    lines.append(f"                    isAlt = true;")
                    lines.append(f"                }}")
                lines.append(f"                if (!isAlt) {{")
                lines.append(f"                    if (record.length() >= {key_end}) val = record.substring({key_start}, {key_end}).trim();")
                lines.append(f"                }}")
                lines.append(f"                int cmp = val.compareTo(targetKey);")
                lines.append(f"                boolean match = false;")
                lines.append(f"                if (startOp.equals(\"=\")) match = (cmp == 0);")
                lines.append(f"                else if (startOp.equals(\">\")) match = (cmp > 0);")
                lines.append(f"                else if (startOp.equals(\">=\") || startOp.equals(\"NOT <\")) match = (cmp >= 0);")
                lines.append(f"                if (found || match) {{")
                lines.append(f"                    found = true;")
                lines.append(f"                    matchedRecords.add(record);")
                lines.append(f"                }}")
                lines.append(f"            }}")
                lines.append(f"            if (!found) {{")
                status_miss = get_status_assign("23")
                if status_miss: lines.append(f"                {status_miss}")
                lines.append(f"                return false;")
                lines.append(f"            }}")
                lines.append(f"            {java_fd}_iterator = matchedRecords.iterator();")
                status_ok = get_status_assign("00")
                if status_ok: lines.append(f"            {status_ok}")
                lines.append(f"            return true;")
            lines.append(f"        }}")
            lines.append(f"    }}")
            lines.append("")
            
            lines.append(f"    private void close_{java_fd}() {{")
            lines.append(f"        save_{java_fd}();")
            lines.append(f"        {java_fd}_records.clear();")
            lines.append(f"        {java_fd}_db_list.clear();")
            lines.append(f"        {java_fd}_iterator = null;")
            status_ok = get_status_assign("00")
            if status_ok: lines.append(f"        {status_ok}")
            lines.append(f"    }}")
            
        else:
            rec_len = redefined_record_len if redefined_record_name else curr
            is_line_seq = organization.upper() == "LINE SEQUENTIAL" or (has_reports and not is_input)
            
            # Declare stream fields
            if is_line_seq:
                lines.append(f"    private BufferedReader {java_fd}_reader;")
                lines.append(f"    private BufferedWriter {java_fd}_writer;")
            else:
                lines.append(f"    private java.io.InputStream {java_fd}_stream_in;")
                lines.append(f"    private java.io.OutputStream {java_fd}_stream_out;")
            lines.append("")
            
            # Generate open method overload 1
            lines.append(f"    private void open_{java_fd}() {{")
            lines.append(f"        open_{java_fd}(\"{'INPUT' if is_input else 'OUTPUT'}\");")
            lines.append(f"    }}")
            lines.append("")
            
            # Generate open method overload 2 (mode-based)
            lines.append(f"    private void open_{java_fd}(String mode) {{")
            lines.append(f"        try {{")
            lines.append(f"            close_{java_fd}();")
            lines.append(f"            if (\"INPUT\".equalsIgnoreCase(mode)) {{")
            if is_line_seq:
                lines.append(f"                {java_fd}_reader = Files.newBufferedReader(Paths.get(resolve_path_{java_fd}()));")
            else:
                lines.append(f"                {java_fd}_stream_in = new java.io.BufferedInputStream(new java.io.FileInputStream(resolve_path_{java_fd}()));")
            lines.append(f"            }} else if (\"OUTPUT\".equalsIgnoreCase(mode)) {{")
            lines.append(f"                java.nio.file.Path parent = Paths.get(resolve_path_{java_fd}()).getParent();")
            lines.append(f"                if (parent != null) Files.createDirectories(parent);")
            if is_line_seq:
                lines.append(f"                {java_fd}_writer = Files.newBufferedWriter(Paths.get(resolve_path_{java_fd}()));")
            else:
                lines.append(f"                {java_fd}_stream_out = new java.io.BufferedOutputStream(new java.io.FileOutputStream(resolve_path_{java_fd}()));")
            lines.append(f"            }}")
            status_ok = get_status_assign("00")
            if status_ok: lines.append(f"            {status_ok}")
            lines.append(f"        }} catch (IOException e) {{")
            status_err = get_status_assign("35")
            if status_err:
                lines.append(f"            {status_err}")
            else:
                lines.append(f"            throw new RuntimeException(e);")
            lines.append(f"        }}")
            lines.append(f"    }}")
            lines.append("")
            
            # Generate read method
            lines.append(f"    private boolean read_{java_fd}() {{")
            lines.append(f"        try {{")
            if is_line_seq:
                lines.append(f"            if ({java_fd}_reader == null) return false;")
                lines.append(f"            String line = {java_fd}_reader.readLine();")
                lines.append(f"            if (line == null) {{")
                status_eof = get_status_assign("10")
                if status_eof: lines.append(f"                {status_eof}")
                lines.append(f"                return false;")
                lines.append(f"            }} else {{")
                if redefined_record_name:
                    java_rec = to_java_var(redefined_record_name)
                    backing_var = f"{java_rec}_backing"
                    lines.append(f"                String padded = String.format(\"%-\" + {redefined_record_len} + \"s\", line);")
                    lines.append(f"                if (padded.length() > {redefined_record_len}) padded = padded.substring(0, {redefined_record_len});")
                    lines.append(f"                for (int i = 0; i < {redefined_record_len}; i++) {{")
                    lines.append(f"                    {backing_var}[i] = (byte) padded.charAt(i);")
                    lines.append(f"                }}")
                else:
                    for f_name, start, end in offsets:
                        java_var = to_java_var(f_name)
                        pic = [p for n, p in record_fields if n == f_name][0]
                        java_type = NativeTypeMapper.get_java_type(pic)
                        lines.append(f"                String val_{java_var} = (line.length() >= {end}) ? line.substring({start}, {end}).trim() : (line.length() > {start} ? line.substring({start}).trim() : \"\");")
                        if java_type == "BigDecimal":
                            scale = NativeTypeMapper.parse_pic(pic)[2]
                            signed = NativeTypeMapper.parse_pic(pic)[3]
                            if signed:
                                lines.append(f"                {java_var}.assign(parseSigned(val_{java_var}, {scale}));")
                            else:
                                lines.append(f"                {java_var}.assign(val_{java_var}.isEmpty() ? BigDecimal.ZERO : new BigDecimal(val_{java_var}).movePointLeft({scale}));")
                        elif java_type in ("Integer", "Long"):
                            signed = NativeTypeMapper.parse_pic(pic)[3]
                            t_cast = "int" if java_type == "Integer" else "long"
                            if signed:
                                lines.append(f"                {java_var} = ({t_cast}) parseSignedLong(val_{java_var});")
                            else:
                                parse_call = f"Integer.parseInt(val_{java_var})" if java_type == "Integer" else f"Long.parseLong(val_{java_var})"
                                zero_val = "0" if java_type == "Integer" else "0L"
                                lines.append(f"                {java_var} = val_{java_var}.isEmpty() ? {zero_val} : {parse_call};")
                        else:
                            lines.append(f"                {java_var} = val_{java_var};")
                lines.append(f"            }}")
            else:
                lines.append(f"            if ({java_fd}_stream_in == null) return false;")
                lines.append(f"            byte[] buf = new byte[{rec_len}];")
                lines.append(f"            int bytesRead = 0;")
                lines.append(f"            while (bytesRead < {rec_len}) {{")
                lines.append(f"                int r = {java_fd}_stream_in.read(buf, bytesRead, {rec_len} - bytesRead);")
                lines.append(f"                if (r == -1) break;")
                lines.append(f"                bytesRead += r;")
                lines.append(f"            }}")
                lines.append(f"            if (bytesRead < {rec_len}) {{")
                status_eof = get_status_assign("10")
                if status_eof: lines.append(f"                {status_eof}")
                lines.append(f"                return false;")
                lines.append(f"            }}")
                if redefined_record_name:
                    java_rec = to_java_var(redefined_record_name)
                    backing_var = f"{java_rec}_backing"
                    lines.append(f"            System.arraycopy(buf, 0, {backing_var}, 0, {rec_len});")
                else:
                    for f_name, start, end in offsets:
                        java_var = to_java_var(f_name)
                        pic = [p for n, p in record_fields if n == f_name][0]
                        java_type = NativeTypeMapper.get_java_type(pic)
                        spec_init = get_cobol_numeric_spec_init_local(f_name)
                        f_len = end - start
                        if java_type == "BigDecimal":
                            lines.append(f"            {java_var}.assign(new com.systema.modernized.runtime.CobolNumeric(buf, {start}, {f_len}, {spec_init}).getValue());")
                        elif java_type in ("Integer", "Long"):
                            t_cast = "int" if java_type == "Integer" else "long"
                            val_getter = "intValue" if java_type == "Integer" else "longValue"
                            lines.append(f"            {java_var} = ({t_cast}) new com.systema.modernized.runtime.CobolNumeric(buf, {start}, {f_len}, {spec_init}).getValue().{val_getter}();")
                        else:
                            lines.append(f"            {java_var} = new String(buf, {start}, {f_len}, java.nio.charset.StandardCharsets.ISO_8859_1);")
                            
            status_ok = get_status_assign("00")
            if status_ok: lines.append(f"            {status_ok}")
            lines.append(f"            return true;")
            lines.append(f"        }} catch (IOException e) {{")
            status_err = get_status_assign("30")
            if status_err: lines.append(f"            {status_err}")
            lines.append(f"            return false;")
            lines.append(f"        }}")
            lines.append(f"    }}")
            lines.append("")
            
            # Generate write method
            lines.append(f"    private void write_{java_fd}() {{")
            lines.append(f"        try {{")
            if is_line_seq:
                lines.append(f"            if ({java_fd}_writer == null) return;")
                if redefined_record_name:
                    java_rec = to_java_var(redefined_record_name)
                    backing_var = f"{java_rec}_backing"
                    lines.append(f"            {java_fd}_writer.write(new String({backing_var}, java.nio.charset.StandardCharsets.ISO_8859_1).replaceAll(\"\\\\s+$\", \"\"));")
                else:
                    fmt_parts = []
                    fmt_args = []
                    for f_name, pic in record_fields:
                        java_var = to_java_var(f_name)
                        java_type = NativeTypeMapper.get_java_type(pic)
                        _, length, scale, signed = NativeTypeMapper.parse_pic(pic)
                        if java_type == "BigDecimal":
                            fmt_parts.append(f"%0{length}d")
                            var_ref = java_var
                            _rdl = redefines_layout or {}
                            if f_name.upper() not in _rdl:
                                var_ref = f"{java_var}.getValue()"
                            fmt_args.append(f"({var_ref}.movePointRight({scale}).longValue())")
                        elif java_type in ("Integer", "Long"):
                            if signed:
                                fmt_parts.append(f"%{length}s")
                                fmt_args.append(f"formatSigned({java_var}, {length}, true)")
                            else:
                                fmt_parts.append(f"%0{length}d")
                                fmt_args.append(java_var)
                        else:
                            fmt_parts.append(f"%-{length}s")
                            fmt_args.append(java_var)
                    fmt_str = "".join(fmt_parts)
                    args_str = ", ".join(fmt_args)
                    lines.append(f"            {java_fd}_writer.write(String.format(\"{fmt_str}\", {args_str}).replaceAll(\"\\\\s+$\", \"\"));")
                lines.append(f"            {java_fd}_writer.newLine();")
            else:
                lines.append(f"            if ({java_fd}_stream_out == null) return;")
                lines.append(f"            byte[] buf = new byte[{rec_len}];")
                if redefined_record_name:
                    java_rec = to_java_var(redefined_record_name)
                    backing_var = f"{java_rec}_backing"
                    lines.append(f"            System.arraycopy({backing_var}, 0, buf, 0, {rec_len});")
                else:
                    for f_name, pic in record_fields:
                        java_var = to_java_var(f_name)
                        java_type = NativeTypeMapper.get_java_type(pic)
                        _, length, scale, signed = NativeTypeMapper.parse_pic(pic)
                        signed_str = "true" if signed else "false"
                        start, end = [(s, e) for n, s, e in offsets if n == f_name][0]
                        f_width = end - start
                        if java_type == "BigDecimal":
                            lines.append(f"            byte[] c_{java_var} = {java_var}.toStorageImage();")
                            lines.append(f"            System.arraycopy(c_{java_var}, 0, buf, {start}, Math.min(c_{java_var}.length, {f_width}));")
                        elif java_type in ("Integer", "Long"):
                            spec_init = get_cobol_numeric_spec_init_local(f_name)
                            lines.append(f"            byte[] c_{java_var} = new com.systema.modernized.runtime.CobolNumeric(java.math.BigDecimal.valueOf({java_var}), {spec_init}).toStorageImage();")
                            lines.append(f"            System.arraycopy(c_{java_var}, 0, buf, {start}, Math.min(c_{java_var}.length, {f_width}));")
                        else:
                            lines.append(f"            byte[] c_{java_var} = padString({java_var}, {f_width}).getBytes(java.nio.charset.StandardCharsets.ISO_8859_1);")
                            lines.append(f"            System.arraycopy(c_{java_var}, 0, buf, {start}, Math.min(c_{java_var}.length, {f_width}));")
                lines.append(f"            {java_fd}_stream_out.write(buf);")
                lines.append(f"            {java_fd}_stream_out.flush();")
                
            status_ok = get_status_assign("00")
            if status_ok: lines.append(f"            {status_ok}")
            lines.append(f"        }} catch (IOException e) {{")
            status_err = get_status_assign("30")
            if status_err: lines.append(f"            {status_err}")
            lines.append(f"        }}")
            lines.append(f"    }}")
            lines.append("")
            
            # Generate close method
            lines.append(f"    private void close_{java_fd}() {{")
            lines.append(f"        try {{")
            if is_line_seq:
                lines.append(f"            if ({java_fd}_reader != null) {{ {java_fd}_reader.close(); {java_fd}_reader = null; }}")
                lines.append(f"            if ({java_fd}_writer != null) {{ {java_fd}_writer.close(); {java_fd}_writer = null; }}")
            else:
                lines.append(f"            if ({java_fd}_stream_in != null) {{ {java_fd}_stream_in.close(); {java_fd}_stream_in = null; }}")
                lines.append(f"            if ({java_fd}_stream_out != null) {{ {java_fd}_stream_out.close(); {java_fd}_stream_out = null; }}")
            status_ok = get_status_assign("00")
            if status_ok: lines.append(f"            {status_ok}")
            lines.append(f"        }} catch (IOException e) {{")
            status_err = get_status_assign("30")
            if status_err: lines.append(f"            {status_err}")
            lines.append(f"        }}")
            lines.append(f"    }}")
            
        return "\n".join(lines)

class NativeProgramGenerator:
    def __init__(self, program_name: str, ir_nodes: list, file_assigns: list = None, is_child: bool = False, parent_generator = None, repo_path: str = None):
        self.program_name = program_name
        self.file_assigns = file_assigns or []
        self.repo_path = repo_path
        
        self.child_generators = {}
        self.is_child = is_child
        self.parent_generator = parent_generator
        self.parent_global_vars = {}
        self.var_global = {}
        
        first_prog_id = None
        for n in ir_nodes:
            prog = n.properties.get("program")
            if prog:
                first_prog_id = prog
                break
        if not first_prog_id:
            first_prog_id = self.program_name

        program_nodes = {}
        for n in ir_nodes:
            prog = n.properties.get("program")
            if not prog:
                prog = first_prog_id
            prog_upper = prog.upper()
            if prog_upper not in program_nodes:
                program_nodes[prog_upper] = []
            program_nodes[prog_upper].append(n)
            
        if len(program_nodes) == 1:
            single_key = list(program_nodes.keys())[0]
            if single_key != self.program_name.upper():
                nodes = program_nodes.pop(single_key)
                for n in nodes:
                    if n.kind == "PROGRAM":
                        n.properties["name"] = self.program_name
                    n.properties["program"] = self.program_name
                program_nodes[self.program_name.upper()] = nodes
            
        self.ir_nodes = program_nodes.get(self.program_name.upper(), ir_nodes)
        
        self.var_types = {"RETURN-CODE": "Integer", "EIBRESP": "Integer", "EIBRESP2": "Integer"}
        self.var_pics = {}
        self.var_usages = {}
        self.var_sign_positions = {}
        self.var_sign_separates = {}
        self.var_edited = {}
        self.fd_fields = {}
        self.record_to_fd = {}
        self.group_fields = {}
        self.using_args = []
        self.constants_map = {}
        # level88_map: {condition_name: (parent_name, [values])}
        self.level88_map = {}
        # occurs_map: {array_var_name: (size, elem_java_type)}
        self.occurs_map = {}
        self.next_section_map = {}
        self.diagnostics = []
        self.paragraphs = {}
        self.para_names = []
        self.redefines_layout = {}
        self.redefined_records_backing = {}
        self.occurs_depending_on = {}
        
        self.file_status_vars = {}
        self.file_orgs = {}
        self.file_access_modes = {}
        self.file_keys = {}
        self.file_alt_keys = {}
        
        self._build_mappings()

        # Instantiate subprograms recursively AFTER parent _build_mappings has populated var_global
        for child_name, child_nodes in program_nodes.items():
            if child_name != self.program_name.upper():
                child_gen = NativeProgramGenerator(child_name, child_nodes, file_assigns, is_child=True, parent_generator=self)
                self.child_generators[child_name] = child_gen

    def _build_mappings(self):
        self.pointer_vars = set()
        self.ref_vars = set()
        self.reports = {}
        self.report_groups_fields = {}
        self.report_sum_fields = {}
        
        sorted_nodes = sorted(self.ir_nodes, key=lambda n: n.source_line)
        current_group_item = None
        for n in sorted_nodes:
            if n.kind in ("VARIABLE", "DATA_ITEM"):
                props = n.properties
                name = props.get("name", "").upper()
                lvl = props.get("level", 1)
                if props.get("usage") == "POINTER":
                    self.pointer_vars.add(name)
                
                rd = props.get("rd_name")
                if rd:
                    rd_upper = rd.upper()
                    if rd_upper not in self.reports:
                        self.reports[rd_upper] = []
                    if lvl == 1:
                        self.reports[rd_upper].append(n)
                        current_group_item = name
                        self.report_groups_fields[name] = []
                    elif lvl > 1 and current_group_item:
                        self.report_groups_fields[current_group_item].append(n)
                        if props.get("sum_expr"):
                            sum_expr = props.get("sum_expr").upper()
                            if rd_upper not in self.report_sum_fields:
                                self.report_sum_fields[rd_upper] = set()
                            self.report_sum_fields[rd_upper].add(sum_expr)
            elif n.kind == "STATEMENT" and n.properties.get("statement_type") == "SET":
                props = n.properties
                t_var = props.get("target_var", "").upper()
                if props.get("is_address_of_target"):
                    self.ref_vars.add(t_var)
                    
        self._analyze_redefines_and_layout(sorted_nodes)
        
        # Collect FILE_CONTROL info
        select_files = {}
        for n in sorted_nodes:
            if n.kind == "FILE_CONTROL":
                f_name = n.properties.get("file_name", "").upper()
                status_var = n.properties.get("status_var")
                org = n.properties.get("organization", "SEQUENTIAL")
                mode = n.properties.get("access_mode", "SEQUENTIAL")
                key = n.properties.get("record_key")
                assign_name = n.properties.get("assign_name", "")
                
                if status_var:
                    self.file_status_vars[f_name] = status_var
                self.file_orgs[f_name] = org
                self.file_access_modes[f_name] = mode
                alt_keys = n.properties.get("alternate_keys", [])
                self.file_alt_keys[f_name] = alt_keys
                if key:
                    self.file_keys[f_name] = key
                select_files[f_name] = {
                    "assign_name": assign_name,
                    "organization": org
                }
                
        # Determine is_input based on OPEN statements and SORT/MERGE statements.
        # All modes are tracked so files reopened in a DIFFERENT mode can be
        # flagged explicitly (only one IO method family is generated today).
        file_io_modes = {}
        file_all_modes = {}
        for n in sorted_nodes:
            if n.kind == "STATEMENT" and n.properties.get("statement_type") == "OPEN":
                targets = n.properties.get("targets", [])
                curr_mode = "INPUT"
                for t in targets:
                    if t in ("INPUT", "OUTPUT", "I-O", "EXTEND"):
                        curr_mode = t
                    else:
                        file_io_modes[t.upper()] = curr_mode
                        file_all_modes.setdefault(t.upper(), set()).add(curr_mode)
            elif n.kind == "STATEMENT" and n.properties.get("statement_type") in ("SORT", "MERGE"):
                using_files = n.properties.get("using_files", [])
                giving_files = n.properties.get("giving_files", [])
                for uf in using_files:
                    file_io_modes[uf.upper()] = "INPUT"
                    file_all_modes.setdefault(uf.upper(), set()).add("INPUT")
                for gf in giving_files:
                    file_io_modes[gf.upper()] = "OUTPUT"
                    file_all_modes.setdefault(gf.upper(), set()).add("OUTPUT")

        self.select_files = select_files
        self.file_io_modes = file_io_modes
        self.file_all_modes = file_all_modes
        
        # No mutation of shared self.file_assigns list

        if not self.file_assigns:
            for f_name, info in select_files.items():
                assign_name = info["assign_name"]
                if assign_name:
                    if assign_name.startswith("'") or assign_name.startswith('"'):
                        assign_path = assign_name[1:-1]
                    else:
                        assign_path = assign_name
                else:
                    assign_path = f_name.lower() + ".dat"
                
                mode = file_io_modes.get(f_name, "INPUT")
                is_input = (mode != "OUTPUT")
                self.file_assigns.append({
                    "logical_name": f_name,
                    "physical_path": assign_path,
                    "is_input": is_input
                })
        print("SELECT FILES:", select_files)
        print("FILE ASSIGNS:", self.file_assigns)
        
        # Populate using_args
        for n in sorted_nodes:
            if n.kind == "DIVISION" and n.properties.get("name") == "PROCEDURE":
                self.using_args = n.properties.get("using_args", [])
                break

        last_non88 = None   # track parent of 88 conditions
        current_section = None
        self.linkage_vars = set()
        for n in sorted_nodes:
            props = n.properties
            kind = n.kind
            if kind == "SECTION":
                current_section = props.get("name", "").upper()
            if kind in ("VARIABLE", "DATA_ITEM"):
                name = props.get("name", "")
                if current_section == "LINKAGE" and name:
                    self.linkage_vars.add(name.upper())
                pic = props.get("picture", "")
                usage = props.get("usage", "")
                level = props.get("level", 1)
                is_group = props.get("is_group", False)
                if level == 88:
                    # Level-88 condition: map to parent
                    values = props.get("condition_values", [])
                    parent = last_non88 if last_non88 else ""
                    self.level88_map[name] = (parent, values)
                elif level == 78:
                    val = props.get("value", "")
                    self.constants_map[name.upper()] = val
                else:
                    if name:
                        last_non88 = name
                    if name:
                        name_u = name.upper()
                        self.var_global[name] = props.get("is_global", False)
                        self.var_global[name_u] = props.get("is_global", False)
                        if pic:
                            if name_u == "SQLCODE":
                                usage = "COMP-5"
                            is_ed = props.get("is_edited", False)
                            self.var_edited[name] = is_ed
                            self.var_edited[name_u] = is_ed
                            if is_ed:
                                self.var_types[name] = "String"
                                self.var_types[name_u] = "String"
                            else:
                                j_type = NativeTypeMapper.get_java_type(pic, usage)
                                self.var_types[name] = j_type
                                self.var_types[name_u] = j_type
                            self.var_pics[name] = pic
                            self.var_pics[name_u] = pic
                            self.var_usages[name] = usage
                            self.var_usages[name_u] = usage
                            self.var_sign_positions[name] = props.get("sign_position", "TRAILING")
                            self.var_sign_positions[name_u] = props.get("sign_position", "TRAILING")
                            self.var_sign_separates[name] = props.get("sign_separate", False)
                            self.var_sign_separates[name_u] = props.get("sign_separate", False)
                        elif is_group:
                            self.var_types[name] = "String"
                            self.var_types[name_u] = "String"
                            self.var_pics[name] = ""
                            self.var_pics[name_u] = ""
                            self.var_usages[name] = ""
                            self.var_usages[name_u] = ""
                            self.var_sign_positions[name] = "TRAILING"
                            self.var_sign_positions[name_u] = "TRAILING"
                            self.var_sign_separates[name] = False
                            self.var_sign_separates[name_u] = False
                    # OCCURS table
                    occurs = props.get("occurs", 0)
                    is_array = False
                    if name in self.redefines_layout:
                        is_array = self.redefines_layout[name]["is_array"]
                        occurs = self.redefines_layout[name]["occurs_max"]
                    occurs_val = int(occurs) if occurs else 0
                    if name and (occurs_val > 1 or is_array):
                        elem_type = NativeTypeMapper.get_java_type(pic, usage) if pic else "String"
                        self.occurs_map[name] = (occurs_val, elem_type)

        # Populate group_fields
        current_group = None
        for n in sorted_nodes:
            if n.kind in ("VARIABLE", "DATA_ITEM"):
                name = n.properties.get("name", "")
                level = n.properties.get("level", 1)
                is_group = n.properties.get("is_group", False)
                if level == 1:
                    if is_group:
                        current_group = name.upper()
                        self.group_fields[current_group] = []
                    else:
                        current_group = None
                elif level > 1 and current_group:
                    self.group_fields[current_group].append(name)

        in_file_section = False
        curr_fd = None
        curr_record_fields = []
        curr_record_name = None
        
        for n in sorted_nodes:
            props = n.properties
            kind = n.kind
            if kind == "SECTION":
                sec_name = props.get("name", "").upper()
                if sec_name == "FILE":
                    in_file_section = True
                elif sec_name == "WORKING-STORAGE":
                    in_file_section = False
                    if curr_fd and curr_record_fields:
                        self.fd_fields[curr_fd] = curr_record_fields
                        if curr_record_name:
                            self.record_to_fd[curr_record_name] = curr_fd
                        curr_record_fields = []
                        
            elif in_file_section and kind in ("VARIABLE", "DATA_ITEM"):
                name = props.get("name", "")
                level = props.get("level", 1)
                pic = props.get("picture", "")
                
                if level == 1:
                    if curr_fd and curr_record_fields:
                        self.fd_fields[curr_fd] = curr_record_fields
                        if curr_record_name:
                            self.record_to_fd[curr_record_name] = curr_fd
                    curr_record_fields = []
                    curr_fd = props.get("fd_name")
                    if curr_fd:
                        curr_fd = curr_fd.upper()
                    curr_record_name = name.upper() if name else None
                    if pic:
                        curr_record_fields.append((name, pic))
                elif level > 1 and name and pic:
                    curr_record_fields.append((name, pic))
                    
        if curr_fd and curr_record_fields:
            self.fd_fields[curr_fd] = curr_record_fields
            if curr_record_name:
                self.record_to_fd[curr_record_name] = curr_fd

        # Populate next_section_map
        sections = []
        for n in sorted_nodes:
            if n.kind == "SECTION":
                sections.append(to_java_var(n.properties.get("name", "")))
        
        current_section = None
        for n in sorted_nodes:
            if n.kind == "SECTION":
                current_section = to_java_var(n.properties.get("name", ""))
            
            if n.kind in ("PARAGRAPH", "SECTION"):
                name = to_java_var(n.properties.get("name", ""))
                next_sec = None
                if current_section:
                    try:
                        idx = sections.index(current_section)
                        if idx + 1 < len(sections):
                            next_sec = sections[idx + 1]
                    except ValueError:
                        pass
                else:
                    if sections:
                        next_sec = sections[0]
                self.next_section_map[name] = next_sec
                
        # Resolve parent global variables
        if self.is_child and self.parent_generator:
            curr_parent = self.parent_generator
            depth = 1
            while curr_parent:
                parent_path = ".".join(["parent"] * depth)
                for v, t in curr_parent.var_types.items():
                    if curr_parent.var_global.get(v, False) and v not in self.parent_global_vars:
                        self.parent_global_vars[v] = (t, parent_path)
                curr_parent = curr_parent.parent_generator
                depth += 1
                
        for r_var in self.ref_vars:
            self.redefines_layout[r_var] = {
                "is_array": False,
                "occurs_max": 1,
                "offset": 0,
                "length": 0,
                "type": "String",
                "scale": 0,
                "signed": False,
                "record_name": "",
                "occurs_step": 0,
                "depending_on": None
            }
            
        for p_var in self.pointer_vars:
            self.var_types[p_var] = "com.systema.modernized.CobolRef"

    def _analyze_redefines_and_layout(self, sorted_nodes):
        records = []
        current_record = []
        has_redefines_or_odo = False
        
        for n in sorted_nodes:
            if n.kind in ("VARIABLE", "DATA_ITEM"):
                lvl = n.properties.get("level", 1)
                if lvl == 88:
                    continue
                if lvl == 1:
                    if current_record:
                        records.append((current_record, has_redefines_or_odo))
                    current_record = [n]
                    has_redefines_or_odo = False
                else:
                    if current_record:
                        current_record.append(n)
                        if n.properties.get("redefines") or n.properties.get("depending_on"):
                            has_redefines_or_odo = True
                            
        if current_record:
            records.append((current_record, has_redefines_or_odo))

        # 1. Map each variable to its root record name
        var_to_root = {}
        current_root = None
        for n in sorted_nodes:
            if n.kind in ("VARIABLE", "DATA_ITEM"):
                lvl = n.properties.get("level", 1)
                if lvl == 88:
                    continue
                if lvl == 1:
                    current_root = n.properties.get("name")
                if current_root:
                    var_to_root[n.properties.get("name")] = current_root

        # 2. Trace REDEFINES parent mapping between roots, and identify participating roots
        redefs_parent = {}
        participating_roots = set()
        
        for n in sorted_nodes:
            if n.kind in ("VARIABLE", "DATA_ITEM"):
                redef_target = n.properties.get("redefines")
                if redef_target:
                    my_root = var_to_root.get(n.properties.get("name"))
                    tgt_root = var_to_root.get(redef_target)
                    if my_root:
                        participating_roots.add(my_root)
                    if tgt_root:
                        participating_roots.add(tgt_root)
                    if my_root and tgt_root and my_root != tgt_root:
                        redefs_parent[my_root] = tgt_root

        # Helper to find ultimate root of a root-level chain
        def get_ultimate_root(r):
            visited = set()
            while r in redefs_parent:
                if r in visited:
                    break
                visited.add(r)
                r = redefs_parent[r]
            return r

        for rec_nodes, is_special in records:
            if not rec_nodes:
                continue
            root_node = rec_nodes[0]
            root_name = root_node.properties.get("name")
            
            root_layout, nodes_map = self._build_layout_tree(rec_nodes)
            if not root_layout:
                continue
                
            self._inherit_occurs(root_layout)
            total_len = self._compute_layout_offsets(root_layout)
            
            # Check if this record participates in a redefines chain
            is_participating = root_name in participating_roots
            
            if is_participating:
                ult_root = get_ultimate_root(root_name)
                # Keep the maximum length among all records in the chain
                self.redefined_records_backing[ult_root] = max(
                    self.redefined_records_backing.get(ult_root, 0),
                    total_len
                )
            
            for name, layout_node in nodes_map.items():
                if layout_node.depending_on:
                    self.occurs_depending_on[name] = (
                        layout_node.depending_on,
                        layout_node.occurs_min if layout_node.occurs_min is not None else 1,
                        layout_node.occurs_max if layout_node.occurs_max is not None else layout_node.occurs
                    )
                
                if is_participating:
                    ult_root = get_ultimate_root(root_name)
                    java_type = "String"
                    pic = layout_node.pic
                    scale = 0
                    signed = False
                    if pic:
                        java_type = NativeTypeMapper.get_java_type(pic, layout_node.usage)
                        _, _, scale, signed = NativeTypeMapper.parse_pic(pic)
                    elif layout_node.children:
                        java_type = "String"
                        
                    occurs_step = layout_node.length
                    if layout_node.occurs and layout_node.occurs > 1:
                        occurs_step = layout_node.length // layout_node.occurs
                    parent_occurs = False
                    p = layout_node.parent
                    while p:
                        if p.occurs and p.occurs > 1:
                            parent_occurs = True
                            occurs_step = p.length // p.occurs
                            break
                        p = p.parent
                        
                    is_array = len(layout_node.occurs_list) >= 1
                    elem_len = layout_node.length // layout_node.occurs if (layout_node.occurs and layout_node.occurs > 1) else layout_node.length
                    
                    self.redefines_layout[name] = {
                        "offset": layout_node.offset,
                        "length": layout_node.length,
                        "element_length": elem_len,
                        "type": java_type,
                        "scale": scale,
                        "signed": signed,
                        "record_name": ult_root,   # SHARED BACKING BUFFER!
                        "is_array": is_array,
                        "occurs_step": occurs_step,
                        "occurs_max": layout_node.occurs_max or layout_node.occurs or 1,
                        "depending_on": layout_node.depending_on
                    }

    def _build_layout_tree(self, data_items):
        root = None
        stack = []
        nodes_map = {}
        
        for item in data_items:
            props = item.properties
            name = props.get("name")
            lvl = props.get("level", 1)
            
            node = LayoutNode(name, lvl)
            node.pic = props.get("picture")
            node.usage = props.get("usage")
            node.occurs = props.get("occurs")
            node.occurs_min = props.get("occurs_min")
            node.occurs_max = props.get("occurs_max")
            node.depending_on = props.get("depending_on")
            node.redefines = props.get("redefines")
            
            nodes_map[name] = node
            
            if lvl == 1:
                root = node
                stack = [root]
            else:
                while stack and stack[-1].level >= lvl:
                    stack.pop()
                if stack:
                    parent = stack[-1]
                    node.parent = parent
                    parent.children.append(node)
                stack.append(node)
                
        return root, nodes_map

    def _inherit_occurs(self, node, current_occurs=None):
        if current_occurs:
            node.occurs_list = current_occurs + ([node.occurs] if node.occurs else [])
        else:
            node.occurs_list = [node.occurs] if node.occurs else []
            
        for child in node.children:
            self._inherit_occurs(child, node.occurs_list)

    def _compute_layout_offsets(self, node, current_offset=0):
        node.offset = current_offset
        
        if not node.children:
            if node.pic:
                _, base_len, _, _ = NativeTypeMapper.parse_pic(node.pic)
                if node.usage and node.usage.upper() in ("COMP-3", "PACKED-DECIMAL"):
                    base_len = base_len // 2 + 1
            else:
                base_len = 0
            occurs = node.occurs if node.occurs else 1
            node.length = base_len * occurs
            return node.length
        else:
            max_child_end = current_offset
            curr = current_offset
            
            for child in node.children:
                if child.redefines:
                    ref_node = None
                    for sib in node.children:
                        if sib.name == child.redefines:
                            ref_node = sib
                            break
                    if ref_node:
                        child_len = self._compute_layout_offsets(child, ref_node.offset)
                        max_child_end = max(max_child_end, ref_node.offset + child_len)
                    else:
                        child_len = self._compute_layout_offsets(child, curr)
                        curr += child_len
                        max_child_end = max(max_child_end, curr)
                else:
                    curr = max_child_end
                    child_len = self._compute_layout_offsets(child, curr)
                    max_child_end = max(max_child_end, curr + child_len)
                    
            occurs = node.occurs if node.occurs else 1
            group_base_len = max_child_end - current_offset
            node.length = group_base_len * occurs
            return node.length

    def _get_var_line(self, var_name: str) -> int:
        for n in self.ir_nodes:
            if n.kind in ("VARIABLE", "DATA_ITEM") and n.properties.get("name") == var_name:
                return n.source_line
        return 9999

    def _generate_redefines_storage(self) -> list:
        lines = []
        if not self.redefined_records_backing:
            return lines
            
        lines.append("    // --- REDEFINES Backing Storage ---")
        for rec_name, length in self.redefined_records_backing.items():
            backing_var = to_java_var(rec_name) + "_backing"
            lines.append(f"    private final byte[] {backing_var} = new byte[{length}];")
            lines.append(f"    {{")
            lines.append(f"        java.util.Arrays.fill({backing_var}, (byte) 32);")
            lines.append(f"    }}")
            lines.append("")
            
        lines.append("    // --- REDEFINES Accessors ---")
        for v, layout in self.redefines_layout.items():
            java_var = to_java_var(v)
            offset = layout["offset"]
            length = layout["length"]
            elem_len = layout.get("element_length", length)
            java_type = layout["type"]
            backing_var = to_java_var(layout["record_name"]) + "_backing"
            is_array = layout["is_array"]
            occurs_step = layout["occurs_step"]
            spec_init = self.get_cobol_numeric_spec_init(v)
            
            # --- GETTER ---
            if is_array:
                lines.append(f"    public {java_type} get_{java_var}(int idx) {{")
                lines.append(f"        int off = {offset} + (idx - 1) * {occurs_step};")
            else:
                lines.append(f"    public {java_type} get_{java_var}() {{")
                lines.append(f"        int off = {offset};")
                
            if java_type == "String":
                lines.append(f"        return new String({backing_var}, off, {elem_len}, java.nio.charset.StandardCharsets.ISO_8859_1);")
            elif java_type == "BigDecimal":
                lines.append(f"        return new com.systema.modernized.runtime.CobolNumeric({backing_var}, off, {elem_len}, {spec_init}).getValue();")
            else:
                cast = "int" if java_type == "Integer" else "long"
                val_getter = "intValue" if java_type == "Integer" else "longValue"
                lines.append(f"        return ({cast}) new com.systema.modernized.runtime.CobolNumeric({backing_var}, off, {elem_len}, {spec_init}).getValue().{val_getter}();")
            lines.append("    }")
            lines.append("")
            
            # --- SETTER ---
            if is_array:
                lines.append(f"    public void set_{java_var}(int idx, {java_type} val) {{")
                lines.append(f"        int off = {offset} + (idx - 1) * {occurs_step};")
            else:
                lines.append(f"    public void set_{java_var}({java_type} val) {{")
                lines.append(f"        int off = {offset};")
                
            if java_type == "String":
                lines.append(f"        if (val == null) val = \"\";")
                lines.append(f"        String padded = padString(val, {elem_len});")
                lines.append(f"        byte[] src = padded.getBytes(java.nio.charset.StandardCharsets.ISO_8859_1);")
                lines.append(f"        System.arraycopy(src, 0, {backing_var}, off, {elem_len});")
            elif java_type == "BigDecimal":
                lines.append(f"        new com.systema.modernized.runtime.CobolNumeric({backing_var}, off, {elem_len}, {spec_init}).assign(val);")
            else:
                lines.append(f"        new com.systema.modernized.runtime.CobolNumeric({backing_var}, off, {elem_len}, {spec_init}).assign(java.math.BigDecimal.valueOf(val));")
            lines.append("    }")
            lines.append("")
            
        return lines

    def get_cobol_numeric_spec_init(self, var_name):
        pic = self.var_pics.get(var_name, "")
        usage = self.var_usages.get(var_name, "DISPLAY") or "DISPLAY"
        if pic:
            _, digits, scale, signed = NativeTypeMapper.parse_pic(pic)
        else:
            digits, scale, signed = 18, 0, True
        signed_str = "true" if signed else "false"
        
        usage_enum_map = {
            "DISPLAY": "com.systema.modernized.runtime.CobolUsage.DISPLAY",
            "COMP": "com.systema.modernized.runtime.CobolUsage.COMP",
            "COMP-3": "com.systema.modernized.runtime.CobolUsage.COMP_3",
            "COMP_3": "com.systema.modernized.runtime.CobolUsage.COMP_3",
            "COMP-5": "com.systema.modernized.runtime.CobolUsage.COMP_5",
            "COMP_5": "com.systema.modernized.runtime.CobolUsage.COMP_5",
            "BINARY": "com.systema.modernized.runtime.CobolUsage.COMP"
        }
        usage_val = usage_enum_map.get(usage.upper(), "com.systema.modernized.runtime.CobolUsage.DISPLAY")
        
        sign_pos = self.var_sign_positions.get(var_name, "TRAILING")
        sign_pos_val = f"com.systema.modernized.runtime.CobolSignPosition.{sign_pos}"
        sign_sep = "true" if self.var_sign_separates.get(var_name, False) else "false"
        
        return f"new com.systema.modernized.runtime.CobolNumericSpec({signed_str}, {digits}, {scale}, {usage_val}, {sign_pos_val}, {sign_sep})"

    def generate_class_source(self, all_generators: dict = None) -> str:
        if all_generators is None:
            all_generators = {}
        all_generators = dict(all_generators)
        all_generators[self.program_name.upper()] = self
        def reg_children(g):
            for c_name, c_gen in g.child_generators.items():
                all_generators[c_name.upper()] = c_gen
                reg_children(c_gen)
        reg_children(self)
        
        class_name = to_java_class(self.program_name)
        
        lines = []
        if not self.is_child:
            lines.append("package com.systema.modernized.native_gen;")
            lines.append("")
            lines.append("import java.io.BufferedReader;")
            lines.append("import java.io.BufferedWriter;")
            lines.append("import java.io.IOException;")
            lines.append("import java.math.BigDecimal;")
            lines.append("import java.math.RoundingMode;")
            lines.append("import java.nio.file.Files;")
            lines.append("import java.nio.file.Paths;")
            lines.append("import java.util.Objects;")
            lines.append("")
            lines.append(f"public class {class_name} {{")
        else:
            parent_class = to_java_class(self.parent_generator.program_name)
            lines.append(f"public static class {class_name} {{")
            lines.append(f"    private final {parent_class} parent;")
            lines.append(f"    public {class_name}({parent_class} parent) {{")
            lines.append("        this.parent = parent;")
            lines.append("    }")
        lines.append("")
        
        # Check if CICS is active anywhere in this compilation unit
        has_any_cics = False
        if all_generators:
            has_any_cics = any(
                any(n.kind == "STATEMENT" and n.properties.get("statement_type") == "EXEC_CICS" for n in gen.ir_nodes)
                for gen in all_generators.values()
            )
        
        has_cics = any(n.kind == "STATEMENT" and n.properties.get("statement_type") == "EXEC_CICS" for n in self.ir_nodes)
        if has_cics or has_any_cics:
            lines.append("    static {")
            lines.append(f"        com.systema.modernized.CicsProgramRegistry.register(\"{self.program_name.upper()}\", () -> new {class_name}());")
            lines.append("    }")
            lines.append("")
            lines.append("    public int eibresp = 0;")
            lines.append("    public int eibresp2 = 0;")
            lines.append("    public String commarea = \"\";")
            lines.append("")
        
        has_sql = False
        sql_cursors = set()
        for n in self.ir_nodes:
            if n.kind == "STATEMENT" and n.properties.get("statement_type") == "EXEC_SQL":
                has_sql = True
                sql_props = n.properties.get("sql_props", {})
                cname = sql_props.get("cursor_name")
                if cname:
                    sql_cursors.add(cname.lower())
        for cname in sorted(sql_cursors):
            lines.append(f"    private org.springframework.jdbc.support.rowset.SqlRowSet cursor_{cname} = null;")
        if has_sql:
            lines.append("    private org.springframework.transaction.TransactionStatus txStatus = null;")
        
        for v, java_type in self.var_types.items():
            if v in self.occurs_map or v in self.redefines_layout or v in ("EIBRESP", "EIBRESP2"):
                continue
            java_var = to_java_var(v)
            if java_type.startswith("com.systema.modernized.CobolRef"):
                lines.append(f"    public com.systema.modernized.CobolRef {java_var} = null;")
                continue
            initial_val = None
            for n in self.ir_nodes:
                if n.kind in ("VARIABLE", "DATA_ITEM") and n.properties.get("name") == v:
                    initial_val = n.properties.get("value")
                    break
            
            if initial_val is not None:
                initial_val = str(initial_val).strip()
                if initial_val.upper() in ("ZERO", "ZEROS", "ZEROES"):
                    if java_type == "BigDecimal":
                        spec_init = self.get_cobol_numeric_spec_init(v)
                        lines.append(f"    public com.systema.modernized.runtime.CobolNumeric {java_var} = new com.systema.modernized.runtime.CobolNumeric(BigDecimal.ZERO, {spec_init});")
                    elif java_type in ("Integer", "Long", "int", "long"):
                        t_prim = "int" if java_type in ("Integer", "int") else "long"
                        lines.append(f"    public {t_prim} {java_var} = 0;")
                    else:
                        pic = self.var_pics.get(v, "")
                        if pic:
                            _, length, _, _ = NativeTypeMapper.parse_pic(pic)
                            padded_val = "0".ljust(length)
                        else:
                            padded_val = "0"
                        lines.append(f"    public String {java_var} = \"{padded_val}\";")
                elif initial_val.upper() in ("SPACE", "SPACES"):
                    pic = self.var_pics.get(v, "")
                    if pic:
                        _, length, _, _ = NativeTypeMapper.parse_pic(pic)
                        padded_val = "".ljust(length)
                    else:
                        padded_val = ""
                    lines.append(f"    public String {java_var} = \"{padded_val}\";")
                else:
                    if (initial_val.startswith("'") and initial_val.endswith("'")) or \
                       (initial_val.startswith('"') and initial_val.endswith('"')):
                        initial_val = initial_val[1:-1]
                    
                    if java_type == "BigDecimal":
                        spec_init = self.get_cobol_numeric_spec_init(v)
                        lines.append(f"    public com.systema.modernized.runtime.CobolNumeric {java_var} = new com.systema.modernized.runtime.CobolNumeric(new BigDecimal(\"{initial_val}\"), {spec_init});")
                    elif java_type in ("Integer", "Long", "int", "long"):
                        cleaned_val = re.sub(r'[^\d\-]', '', initial_val)
                        if not cleaned_val:
                            cleaned_val = "0"
                        t_prim = "int" if java_type in ("Integer", "int") else "long"
                        lines.append(f"    public {t_prim} {java_var} = {cleaned_val};")
                    else:
                        pic = self.var_pics.get(v, "")
                        if pic:
                            _, length, _, _ = NativeTypeMapper.parse_pic(pic)
                            padded_val = initial_val.ljust(length)
                        else:
                            padded_val = initial_val
                        lines.append(f"    public String {java_var} = \"{padded_val}\";")
            else:
                if java_type == "BigDecimal":
                    spec_init = self.get_cobol_numeric_spec_init(v)
                    lines.append(f"    public com.systema.modernized.runtime.CobolNumeric {java_var} = new com.systema.modernized.runtime.CobolNumeric({spec_init});")
                elif java_type in ("Integer", "Long", "int", "long"):
                    t_prim = "int" if java_type in ("Integer", "int") else "long"
                    lines.append(f"    public {t_prim} {java_var} = 0;")
                else:
                    pic = self.var_pics.get(v, "")
                    if pic:
                        _, length, _, _ = NativeTypeMapper.parse_pic(pic)
                        padded_val = "".ljust(length)
                    else:
                        padded_val = ""
                    lines.append(f"    public String {java_var} = \"{padded_val}\";")
        # Generate ref vars fields and helpers
        for r_var in sorted(getattr(self, "ref_vars", [])):
            java_var = to_java_var(r_var)
            orig_type = self.var_types.get(r_var, "String")
            default_val = '""'
            if orig_type == "BigDecimal":
                default_val = "BigDecimal.ZERO"
                prim_type = "BigDecimal"
                wrapper_type = "BigDecimal"
            elif orig_type in ("Integer", "int"):
                default_val = "0"
                prim_type = "int"
                wrapper_type = "Integer"
            elif orig_type in ("Long", "long"):
                default_val = "0L"
                prim_type = "long"
                wrapper_type = "Long"
            else:
                prim_type = "String"
                wrapper_type = "String"
                
            lines.append(f"    public com.systema.modernized.CobolRef<{wrapper_type}> {java_var}_ref = null;")
            lines.append(f"    public {prim_type} get_{java_var}() {{")
            lines.append(f"        return {java_var}_ref != null ? {java_var}_ref.get() : {default_val};")
            lines.append(f"    }}")
            lines.append(f"    public void set_{java_var}({prim_type} val) {{")
            lines.append(f"        if ({java_var}_ref != null) {java_var}_ref.set(val);")
            lines.append(f"    }}")
            lines.append("")
            
        # Emit Report Writer fields and sum accumulators
        for rd_name in sorted(getattr(self, "reports", {}).keys()):
            rd_lower = to_java_var(rd_name)
            lines.append(f"    public int {rd_lower}_page_number = 1;")
            lines.append(f"    public int {rd_lower}_line_number = 1;")
            for sum_var in sorted(getattr(self, "report_sum_fields", {}).get(rd_name, set())):
                lines.append(f"    public BigDecimal sum_{to_java_var(sum_var)} = BigDecimal.ZERO;")
            lines.append("")
        # Emit OCCURS array fields (skip scalars already emitted above)
        for arr_name, (arr_size, elem_type) in self.occurs_map.items():
            if arr_name in self.redefines_layout:
                continue
            java_arr = to_java_var(arr_name)
            if elem_type == "BigDecimal":
                spec_init = self.get_cobol_numeric_spec_init(arr_name)
                lines.append(f"    public com.systema.modernized.runtime.CobolNumeric[] {java_arr} = new com.systema.modernized.runtime.CobolNumeric[{arr_size}];")
                lines.append(f"    {{  // initialise array elements")
                lines.append(f"        for (int i = 0; i < {arr_size}; i++) {{")
                lines.append(f"            {java_arr}[i] = new com.systema.modernized.runtime.CobolNumeric({spec_init});")
                lines.append(f"        }}")
                lines.append(f"    }}")
            elif elem_type == "Integer":
                lines.append(f"    public int[] {java_arr} = new int[{arr_size}];")
            elif elem_type == "Long":
                lines.append(f"    public long[] {java_arr} = new long[{arr_size}];")
            else:
                lines.append(f"    public String[] {java_arr} = new String[{arr_size}];")
                lines.append(f"    {{  // initialise array elements")
                lines.append(f"        java.util.Arrays.fill({java_arr}, \"\");")
                lines.append(f"    }}")

        # NOTE: DataSource initialization is handled in main() / entry method via
        # the PGHOST-aware block that chooses PostgreSQL, DB2, or H2 fallback.
        # A class-level initializer block here would pre-empt that logic.

        # Emit REDEFINES Storage & Accessors
        redefs_lines = self._generate_redefines_storage()
        lines.extend(redefs_lines)
        
        # Emit Initial value setter calls for redefines
        lines.append("    {  // Initialise redefines values")
        for v in self.redefines_layout.keys():
            initial_val = None
            for n in self.ir_nodes:
                if n.kind in ("VARIABLE", "DATA_ITEM") and n.properties.get("name") == v:
                    initial_val = n.properties.get("value")
                    break
            if initial_val is not None:
                initial_val = str(initial_val).strip()
                java_var = to_java_var(v)
                layout = self.redefines_layout[v]
                java_type = layout["type"]
                
                # Check for String quotes
                if (initial_val.startswith("'") and initial_val.endswith("'")) or \
                   (initial_val.startswith('"') and initial_val.endswith('"')):
                    initial_val = initial_val[1:-1]
                    
                if java_type == "BigDecimal":
                    lines.append(f"        set_{java_var}(new BigDecimal(\"{initial_val}\"));")
                elif java_type in ("Integer", "Long"):
                    cleaned_val = re.sub(r'[^\d\-]', '', initial_val)
                    if not cleaned_val:
                        cleaned_val = "0"
                    lines.append(f"        set_{java_var}({cleaned_val});")
                else:
                    lines.append(f"        set_{java_var}(\"{initial_val}\");")
        lines.append("    }")
        lines.append("")

        # Emit print_report_group helper method
        if getattr(self, "reports", {}):
            lines.append("    private void print_report_group(String groupName) {")
            lines.append("        try {")
            out_fd = None
            for logical, mode in getattr(self, "file_io_modes", {}).items():
                if mode == "OUTPUT":
                    out_fd = to_java_var(logical)
                    break
            if not out_fd:
                out_fd = "outfile"
            lines.append(f"            if ({out_fd}_writer == null) return;")
            lines.append("            StringBuilder sb = new StringBuilder();")
            lines.append("            switch (groupName.toUpperCase()) {")
            for g, fields in getattr(self, "report_groups_fields", {}).items():
                lines.append(f"                case \"{g}\": {{")
                # Handle LINE NUMBER IS PLUS N extra spacing
                for f in fields:
                    ln = f.properties.get("line_number")
                    if ln and str(ln).startswith("+"):
                        try:
                            val = int(str(ln)[1:]) - 1
                            if val > 0:
                                lines.append(f"                    for (int i = 0; i < {val}; i++) {out_fd}_writer.newLine();")
                        except ValueError:
                            pass
                sorted_fields = []
                for f in fields:
                    col = f.properties.get("column_number")
                    if col is not None:
                        sorted_fields.append((int(col), f))
                sorted_fields.sort(key=lambda x: x[0])
                for col, f in sorted_fields:
                    lines.append(f"                    while (sb.length() < {col - 1}) sb.append(' ');")
                    val_expr = '""'
                    if f.properties.get("value") is not None:
                        val_expr = f"\"{f.properties.get('value').replace('\\\"', '\"').replace('\"', '\\\"')}\""
                    elif f.properties.get("source_expr") is not None:
                        src = f.properties.get("source_expr")
                        if src.upper() == "PAGE-COUNTER":
                            rd_name = f.properties.get("rd_name", "")
                            val_expr = f"String.valueOf({to_java_var(rd_name)}_page_number)"
                        else:
                            val_expr = f"String.valueOf({to_java_var(src)})"
                    elif f.properties.get("sum_expr") is not None:
                        sum_expr = f.properties.get("sum_expr")
                        val_expr = f"String.valueOf(sum_{to_java_var(sum_expr)})"
                    pic = f.properties.get("picture")
                    if pic:
                        # Let's expand picture repeats first
                        raw_pic = pic.upper()
                        expanded = []
                        idx = 0
                        while idx < len(raw_pic):
                            char = raw_pic[idx]
                            if idx + 1 < len(raw_pic) and raw_pic[idx+1] == "(":
                                end_idx = raw_pic.find(")", idx + 1)
                                if end_idx != -1:
                                    try:
                                        count = int(raw_pic[idx+2:end_idx])
                                        expanded.append(char * count)
                                    except ValueError:
                                        expanded.append(char)
                                    idx = end_idx + 1
                                    continue
                            expanded.append(char)
                            idx += 1
                        expanded_pic = "".join(expanded)
                        lines.append(f"                    sb.append(com.systema.modernized.CobolFormatHelper.format({val_expr}, \"{expanded_pic}\"));")
                    else:
                        lines.append(f"                    sb.append({val_expr});")
                lines.append(f"                    {out_fd}_writer.write(sb.toString());")
                lines.append(f"                    {out_fd}_writer.newLine();")
                lines.append("                    break;")
                lines.append("                }")
            lines.append("            }")
            lines.append("        } catch (IOException e) {")
            lines.append("            throw new RuntimeException(e);")
            lines.append("        }")
            lines.append("    }")
            lines.append("")

        # Emit ODO bounds verification helper method
        lines.append("    private int checkBounds(int subscript, int minOccurs, String dependingVarName, int dependingVarValue) {")
        lines.append("        if (subscript < minOccurs || subscript > dependingVarValue) {")
        lines.append("            throw new IndexOutOfBoundsException(\"Subscript \" + subscript + \" out of active bounds [\" + minOccurs + \", \" + dependingVarValue + \"] depending on \" + dependingVarName);")
        lines.append("        }")
        lines.append("        return subscript - 1;")
        lines.append("    }")
        lines.append("")

        # Emit level-88 boolean helpers
        for cond_name, (parent_name, values) in self.level88_map.items():
            if not parent_name:
                continue
            method_name = to_java_method(cond_name)
            parent_java = to_java_var(parent_name)
            parent_type = self.var_types.get(parent_name, "String")
            if parent_name in self.redefines_layout:
                parent_expr = f"get_{parent_java}()"
            else:
                parent_expr = parent_java
                if parent_type == "BigDecimal":
                    parent_expr = f"{parent_expr}.getValue()"
            if parent_type == "BigDecimal":
                conds = " || ".join(
                    f"{parent_expr}.compareTo(new BigDecimal(\"{v}\")) == 0" for v in values
                )
            elif parent_type in ("Integer", "Long"):
                conds = " || ".join(f"{parent_expr} == {v}" for v in values)
            else:
                conds = " || ".join(f'Objects.equals({parent_expr}, "{v}")' for v in values)
            lines.append(f"    public boolean {method_name}() {{ return {conds}; }}")

        # Emit group variable bytes getters
        for g, children in self.group_fields.items():
            if g.upper() in self.pointer_vars or g.upper() in self.ref_vars:
                continue
            g_var = to_java_var(g)
            if g in self.redefined_records_backing:
                backing_var = to_java_var(g) + "_backing"
                lines.append(f"    public byte[] get_{g_var}_bytes() {{")
                lines.append(f"        return {backing_var};")
                lines.append("    }")
                continue
            elif g in self.redefines_layout:
                layout = self.redefines_layout[g]
                backing_var = to_java_var(layout["record_name"]) + "_backing"
                off = layout["offset"]
                length = layout["length"]
                lines.append(f"    public byte[] get_{g_var}_bytes() {{")
                lines.append(f"        byte[] res = new byte[{length}];")
                lines.append(f"        System.arraycopy({backing_var}, {off}, res, 0, {length});")
                lines.append(f"        return res;")
                lines.append("    }")
                continue
                
            lines.append(f"    public byte[] get_{g_var}_bytes() {{")
            child_byte_exprs = []
            for i, child in enumerate(children):
                child_var = to_java_var(child)
                child_type = self.var_types.get(child, "String")
                pic = self.var_pics.get(child, "")
                if pic:
                    _, digits, scale, signed = NativeTypeMapper.parse_pic(pic)
                    _, length, _, _ = NativeTypeMapper.parse_pic(pic)
                else:
                    digits, scale, signed = 18, 0, True
                    length = 0
                signed_str = "true" if signed else "false"
                
                if child in self.occurs_map:
                    occurs_val, elem_type = self.occurs_map[child]
                    lines.append(f"        java.io.ByteArrayOutputStream baos_{i} = new java.io.ByteArrayOutputStream();")
                    lines.append(f"        for (int idx = 0; idx < {occurs_val}; idx++) {{")
                    lines.append(f"            try {{")
                    if elem_type == "BigDecimal":
                        lines.append(f"                baos_{i}.write({child_var}[idx].toStorageImage());")
                    elif elem_type in ("Integer", "Long", "int", "long"):
                        lines.append(f"                baos_{i}.write(formatSigned({child_var}[idx], {digits}, {signed_str}).getBytes(java.nio.charset.StandardCharsets.ISO_8859_1));")
                    else:
                        lines.append(f"                baos_{i}.write(padString({child_var}[idx], {length}).getBytes(java.nio.charset.StandardCharsets.ISO_8859_1));")
                    lines.append(f"            }} catch (Exception e) {{}}")
                    lines.append(f"        }}")
                    lines.append(f"        byte[] c_{i} = baos_{i}.toByteArray();")
                else:
                    if child_type == "BigDecimal":
                        lines.append(f"        byte[] c_{i} = {child_var}.toStorageImage();")
                    elif child_type in ("Integer", "Long", "int", "long"):
                        lines.append(f"        byte[] c_{i} = formatSigned({child_var}, {digits}, {signed_str}).getBytes(java.nio.charset.StandardCharsets.ISO_8859_1);")
                    else:
                        lines.append(f"        byte[] c_{i} = {child_var}.getBytes(java.nio.charset.StandardCharsets.ISO_8859_1);")
                child_byte_exprs.append(f"c_{i}")
            
            if not child_byte_exprs:
                lines.append("        return new byte[0];")
            else:
                total_len_expr = " + ".join(f"{expr}.length" for expr in child_byte_exprs)
                lines.append(f"        byte[] res = new byte[{total_len_expr}];")
                curr_offset_expr = "0"
                for i, expr in enumerate(child_byte_exprs):
                    lines.append(f"        System.arraycopy({expr}, 0, res, {curr_offset_expr}, {expr}.length);")
                    curr_offset_expr += f" + {expr}.length"
                lines.append("        return res;")
            lines.append("    }")

        # Emit group variable populate helper methods
        for g, children in self.group_fields.items():
            if g.upper() in self.pointer_vars or g.upper() in self.ref_vars:
                continue
            g_var = to_java_var(g)
            if g in self.redefined_records_backing:
                backing_var = to_java_var(g) + "_backing"
                length = self.redefined_records_backing[g]
                lines.append(f"    private void populate_{g_var}(String line) {{")
                lines.append(f"        if (line == null) line = \"\";")
                lines.append(f"        byte[] src = line.getBytes(java.nio.charset.StandardCharsets.ISO_8859_1);")
                lines.append(f"        System.arraycopy(src, 0, {backing_var}, 0, Math.min(src.length, {length}));")
                lines.append("    }")
                continue
                
            lines.append(f"    private void populate_{g_var}(String line) {{")
            lines.append(f"        if (line == null) line = \"\";")
            if g in self.redefines_layout and not self.redefines_layout[g]["is_array"]:
                lines.append(f"        set_{g_var}(line);")
            else:
                lines.append(f"        {g_var} = line;")
            curr = 0
            for child in children:
                child_var = to_java_var(child)
                pic = self.var_pics.get(child, "")
                if not pic:
                    continue
                _, length, scale, signed = NativeTypeMapper.parse_pic(pic)
                child_type = self.var_types.get(child, "String")
                if child in self.occurs_map:
                    occurs_count, elem_type = self.occurs_map[child]
                    for idx in range(1, occurs_count + 1):
                        elem_start = curr
                        elem_end = curr + length
                        curr += length
                        lines.append(f"        if (line.length() >= {elem_end}) {{")
                        elem_val = f"line.substring({elem_start}, {elem_end}).trim()"
                        if child_type == "BigDecimal":
                            if signed:
                                val_expr = f"parseSigned({elem_val}, {scale})"
                            else:
                                val_expr = f"{elem_val}.isEmpty() ? BigDecimal.ZERO : new BigDecimal({elem_val}).movePointLeft({scale})"
                        elif child_type in ("Integer", "Long"):
                            t_cast = "int" if child_type == "Integer" else "long"
                            if signed:
                                val_expr = f"({t_cast}) parseSignedLong({elem_val})"
                            else:
                                parse_call = f"Integer.parseInt({elem_val})" if child_type == "Integer" else f"Long.parseLong({elem_val})"
                                zero_val = "0" if child_type == "Integer" else "0L"
                                val_expr = f"{elem_val}.isEmpty() ? {zero_val} : {parse_call}"
                        else:
                            val_expr = elem_val
                        if child in self.redefines_layout:
                            lines.append(f"            set_{child_var}({idx}, {val_expr});")
                        else:
                            if child_type == "BigDecimal":
                                lines.append(f"            {child_var}[{idx - 1}].assign({val_expr});")
                            else:
                                lines.append(f"            {child_var}[{idx - 1}] = {val_expr};")
                        lines.append(f"        }}")
                    continue
                start = curr
                end = curr + length
                curr += length
                lines.append(f"        if (line.length() >= {end}) {{")
                lines.append(f"            String val = line.substring({start}, {end}).trim();")
                if child_type == "BigDecimal":
                    if signed:
                        val_expr = f"parseSigned(val, {scale})"
                    else:
                        val_expr = f"val.isEmpty() ? BigDecimal.ZERO : new BigDecimal(val).movePointLeft({scale})"
                elif child_type in ("Integer", "Long"):
                    t_cast = "int" if child_type == "Integer" else "long"
                    if signed:
                        val_expr = f"({t_cast}) parseSignedLong(val)"
                    else:
                        parse_call = "Integer.parseInt(val)" if child_type == "Integer" else "Long.parseLong(val)"
                        zero_val = "0" if child_type == "Integer" else "0L"
                        val_expr = f"val.isEmpty() ? {zero_val} : {parse_call}"
                else:
                    val_expr = "val"
                if child in self.redefines_layout and not self.redefines_layout[child]["is_array"]:
                    lines.append(f"            set_{child_var}({val_expr});")
                else:
                    if child_type == "BigDecimal":
                        lines.append(f"            {child_var}.assign({val_expr});")
                    else:
                        lines.append(f"            {child_var} = {val_expr};")
                lines.append(f"        }}")
            lines.append(f"    }}")
            lines.append("")

        lines.append("")
        
        for logical in self.fd_fields.keys():
            assign_name = self.select_files.get(logical, {}).get("assign_name", "")
            path = ""
            is_input = (self.file_io_modes.get(logical, "INPUT") != "OUTPUT")
            all_modes = sorted(self.file_all_modes.get(logical.upper(), set()))
            if len(all_modes) > 1:
                # KNOWN LIMITATION: only one IO method family is generated per
                # file. Emit an explicit diagnostic — never fail silently.
                self.diagnostics.append({
                    "construct": "FILE-REOPEN-DIFFERENT-MODE",
                    "source_coordinate": f"{logical}",
                    "severity": "WARNING",
                    "status": "NATIVE_TRANSLATION_LIMITED",
                    "reason": (
                        f"file '{logical}' opened in multiple modes {all_modes}; "
                        f"only '{'INPUT' if is_input else 'OUTPUT'}'-mode IO "
                        f"methods were generated"
                    ),
                })
            for assign in self.file_assigns:
                if assign.get("logical_name", "").upper() in (logical.upper(), assign_name.upper()):
                    path = assign.get("assign_path") or assign.get("physical_path") or ""
                    break
            if not path:
                path = assign_name
                
            fields = self.fd_fields[logical]
            
            rec_name = None
            for r, fd in self.record_to_fd.items():
                if fd == logical:
                    rec_name = r
                    break
            redef_name = rec_name if (rec_name and rec_name in self.redefined_records_backing) else None
            redef_len = self.redefined_records_backing.get(redef_name) if redef_name else None
            org = self.file_orgs.get(logical.upper(), "SEQUENTIAL")
            key = self.file_keys.get(logical.upper())
            alt_keys = self.file_alt_keys.get(logical.upper(), [])
            status_var = self.file_status_vars.get(logical.upper())
            
            lines.append(NativeFileIOGenerator.generate_io_methods(
                logical, path, is_input, fields,
                redefined_record_name=redef_name,
                redefined_record_len=redef_len,
                organization=org,
                record_key=key,
                alternate_keys=alt_keys,
                status_var=status_var,
                redefines_layout=self.redefines_layout,
                assign_name=assign_name,
                var_pics=self.var_pics,
                var_usages=self.var_usages,
                var_sign_positions=self.var_sign_positions,
                var_sign_separates=self.var_sign_separates,
                has_reports=bool(getattr(self, "reports", {}))
            ))
            lines.append("")

        proc_nodes = [n for n in self.ir_nodes if n.kind == "STATEMENT"]
        
        paragraphs = {}
        curr_p = None
        in_procedure = False
        
        for n in self.ir_nodes:
            kind = n.kind
            if kind == "DIVISION" and n.properties.get("name") == "PROCEDURE":
                in_procedure = True
                continue
            if in_procedure:
                if kind in ("PARAGRAPH", "SECTION"):
                    curr_p = to_java_var(n.properties.get("name", ""))
                    paragraphs[curr_p] = []
                elif kind == "STATEMENT":
                    if curr_p is None:
                        curr_p = "main_process"
                        paragraphs[curr_p] = []
                    paragraphs[curr_p].append(n)

        # Build paragraph list in definition order
        self.paragraphs = paragraphs
        para_names = list(paragraphs.keys())
        if not para_names:
            para_names = ["main_process"]
            paragraphs["main_process"] = [n for n in self.ir_nodes if n.kind == "STATEMENT"]
        self.para_names = para_names
        total_paras = len(para_names)
            
        stmt_trans = NativeStatementTranslator(self.var_types, self.file_assigns, self.record_to_fd, all_generators=all_generators, current_generator=self, level88_map=self.level88_map, constants_map=self.constants_map, is_child=self.is_child, parent_global_vars=self.parent_global_vars)

        # Scan for SORT/MERGE work files
        sort_files = set()
        for n in self.ir_nodes:
            if n.kind == "STATEMENT":
                st = n.properties.get("statement_type", "")
                if st in ("SORT", "MERGE"):
                    wf = n.properties.get("work_file")
                    if wf:
                        sort_files.add(wf.upper())
        for wf in sorted(sort_files):
            wf_lower = to_java_var(wf)
            lines.append(f"    private final java.util.List<java.util.Map<String, Object>> {wf_lower}_list = new java.util.ArrayList<>();")
            lines.append(f"    private int {wf_lower}_idx = 0;")
        if sort_files:
            lines.append("")

        lines.append("    private boolean programExited = false;")
        lines.append("    private int nextParagraphIndex = -1;")
        lines.append("    private boolean skipToNextSentence = false;")
        lines.append(f"    private final int total_paras = {total_paras};")
        lines.append("")
        lines.append("    public static class StopRunException extends RuntimeException {}")
        lines.append("")
        
        lines.append("    private int getParagraphIndex(String name) {")
        lines.append("        if (name == null) return -1;")
        lines.append("        switch (name) {")
        for idx, p in enumerate(para_names):
            lines.append(f"            case \"{p}\": return {idx};")
        lines.append("            default: return -1;")
        lines.append("        }")
        lines.append("    }")
        lines.append("")

        lines.append("    private void runParagraph(int idx) {")
        lines.append("        if (programExited) return;")
        lines.append("        switch (idx) {")
        for idx, p in enumerate(para_names):
            lines.append(f"            case {idx}: {p}(); break;")
        lines.append("            default: break;")
        lines.append("        }")
        lines.append("    }")
        lines.append("")

        lines.append("    private void perform(String target, String thru) {")
        lines.append("        int startIdx = getParagraphIndex(target);")
        lines.append("        int endIdx = (thru != null) ? getParagraphIndex(thru) : startIdx;")
        lines.append("        if (startIdx == -1 || endIdx == -1 || startIdx > endIdx) return;")
        lines.append("        int i = startIdx;")
        lines.append("        while (i <= endIdx) {")
        lines.append("            if (programExited) return;")
        lines.append("            nextParagraphIndex = -1;")
        lines.append("            runParagraph(i);")
        lines.append("            if (nextParagraphIndex != -1) {")
        lines.append("                if (nextParagraphIndex >= startIdx && nextParagraphIndex <= endIdx) {")
        lines.append("                    i = nextParagraphIndex;")
        lines.append("                } else {")
        lines.append("                    return;")
        lines.append("                }")
        lines.append("            } else {")
        lines.append("                i++;")
        lines.append("            }")
        lines.append("        }")
        lines.append("    }")
        lines.append("")

        total_paras = len(para_names)
        lines.append("    public void execute() {")
        if "DFHCOMMAREA" in self.var_types and ("DFHCOMMAREA" in self.linkage_vars or "DFHCOMMAREA" in [x.upper() for x in self.using_args]):
            lines.append("        if (commarea != null && !commarea.isEmpty()) {")
            lines.append("            dfhcommarea = commarea;")
            lines.append("        }")
        has_sql = any(n.kind == "STATEMENT" and n.properties.get("statement_type") == "EXEC_SQL" for n in self.ir_nodes)
        if has_sql:
            # 1. Extract tables and columns dynamically
            tables = {}
            
            def is_valid_column_name(name):
                if not name:
                    return False
                name_upper = name.upper()
                if name_upper in ("COUNT", "SUM", "MIN", "MAX", "AVG", "COALESCE", "NULL", "SELECT", "FROM", "WHERE", "JOIN", "DISTINCT"):
                    return False
                import re
                return bool(re.match(r'^[A-Z_][A-Z0-9_]*$', name_upper))

            def record_column(table_name, col_name, var_name, sp=None):
                table_name = table_name.upper()
                col_name = col_name.upper()
                resolved_table = table_name
                if "SYSDUMMY1" in resolved_table.upper():
                    return
                actual_col = col_name
                if "." in col_name:
                    parts = col_name.split(".")
                    prefix = parts[0].upper()
                    actual_col = parts[-1]
                    if sp:
                        alias_map = sp.get("alias_map", {})
                        if prefix in alias_map:
                            resolved_table = alias_map[prefix]
                        elif prefix in sp.get("tables", []):
                            resolved_table = prefix
                
                if not is_valid_column_name(actual_col):
                    return
                
                if resolved_table not in tables:
                    tables[resolved_table] = {}
                if actual_col not in tables[resolved_table]:
                    t = "VARCHAR(100)"
                    is_pk = (actual_col == "ID") or (actual_col == f"{resolved_table}_ID") or (actual_col == f"{resolved_table[:-1]}_ID") or (resolved_table == "CUSTOMER" and actual_col == "CUST_ID")
                    if is_pk:
                        t = "INT PRIMARY KEY"
                    elif var_name:
                        v = var_name
                        if v.startswith(":"):
                            v = v[1:]
                        v_type = self.var_types.get(v, "String")
                        if v_type == "BigDecimal":
                            t = "DECIMAL(18, 2)"
                        elif v_type in ("Integer", "Long"):
                            t = "INT"
                    tables[resolved_table][actual_col] = t

            def process_sql_props(sp):
                if not sp:
                    return
                stype = sp.get("sql_type", "").upper()
                table = sp.get("table")
                if table and "SYSDUMMY1" in table.upper():
                    return
                
                if stype == "DECLARE_CURSOR":
                    process_sql_props(sp.get("cursor_query"))
                    return
                    
                if not table:
                    return
                    
                if stype == "SELECT":
                    cols = sp.get("columns", [])
                    into = sp.get("into_variables", [])
                    for idx, c in enumerate(cols):
                        v = into[idx] if idx < len(into) else None
                        record_column(table, c, v, sp)
                    for pred in sp.get("predicates", []):
                        if "column" in pred:
                            record_column(table, pred["column"], pred.get("value") or pred.get("values", [None])[0], sp)
                elif stype == "INSERT":
                    cols = sp.get("columns", [])
                    vals = sp.get("values", [])
                    for idx, c in enumerate(cols):
                        v = vals[idx] if idx < len(vals) else None
                        record_column(table, c, v, sp)
                elif stype == "UPDATE":
                    for s in sp.get("sets", []):
                        record_column(table, s["column"], s.get("value"), sp)
                    for pred in sp.get("predicates", []):
                        if "column" in pred:
                            record_column(table, pred["column"], pred.get("value") or pred.get("values", [None])[0], sp)
                elif stype == "DELETE":
                    for pred in sp.get("predicates", []):
                        if "column" in pred:
                            record_column(table, pred["column"], pred.get("value") or pred.get("values", [None])[0], sp)
                
            def extract_tables_from_raw_sql(sql_text):
                if not sql_text:
                    return []
                from modernize.parser import tokenize_sql
                tokens = tokenize_sql(sql_text)
                found_tables = []
                i = 0
                while i < len(tokens):
                    t_upper = tokens[i].upper()
                    if t_upper in ("FROM", "JOIN", "UPDATE"):
                        next_idx = i + 1
                        if next_idx < len(tokens):
                            tbl = tokens[next_idx].upper()
                            if tbl != "(" and tbl not in ("SELECT", "VALUES") and not tbl.startswith(":"):
                                if "." in tbl:
                                    tbl = tbl.split(".")[-1]
                                found_tables.append(tbl)
                    elif t_upper == "INSERT" and i + 2 < len(tokens) and tokens[i+1].upper() == "INTO":
                        tbl = tokens[i+2].upper()
                        if not tbl.startswith(":"):
                            if "." in tbl:
                                tbl = tbl.split(".")[-1]
                            found_tables.append(tbl)
                    i += 1
                return found_tables

            for node in self.ir_nodes:
                if node.kind == "STATEMENT" and node.properties.get("statement_type") == "EXEC_SQL":
                    process_sql_props(node.properties.get("sql_props"))
                    sql_text = node.properties.get("original_sql")
                    if sql_text:
                        for tbl in extract_tables_from_raw_sql(sql_text):
                            if tbl not in tables:
                                tables[tbl] = {}
                    
            # 2. Seed queries list
            seed_queries = []
            if hasattr(self, "repo_path") and self.repo_path:
                for table_name in tables:
                    data_dir = os.path.join(self.repo_path, "data")
                    if os.path.exists(data_dir):
                        sql_file = None
                        for name in os.listdir(data_dir):
                            if name.upper() == f"{table_name}.SQL":
                                sql_file = os.path.join(data_dir, name)
                                break
                        if sql_file:
                            with open(sql_file, "r", encoding="utf-8", errors="replace") as fh:
                                for line in fh:
                                    line_clean = line.strip()
                                    if line_clean and not line_clean.startswith("--") and not line_clean.startswith("*"):
                                        stmt = line_clean
                                        if stmt.endswith(";"):
                                            stmt = stmt[:-1]
                                        stmt_esc = stmt.replace('"', '\\"')
                                        seed_queries.append(stmt_esc)
                                        # Extract columns from seed SQL
                                        m = re.search(r'(?i)\bINSERT\s+INTO\s+(\w+)\s*\(([^)]+)\)', stmt)
                                        if m:
                                            tbl = m.group(1).upper()
                                            cols_str = m.group(2)
                                            for c in cols_str.split(","):
                                                c_clean = c.strip().upper()
                                                if tbl not in tables:
                                                    tables[tbl] = {}
                                                if c_clean not in tables[tbl]:
                                                    tables[tbl][c_clean] = "VARCHAR(100)"
                                        
                        csv_file = None
                        for name in os.listdir(data_dir):
                            if name.upper() == f"{table_name}.CSV":
                                csv_file = os.path.join(data_dir, name)
                                break
                        if csv_file:
                            with open(csv_file, "r", encoding="utf-8", errors="replace") as fh:
                                for line in fh:
                                    line_clean = line.strip()
                                    if line_clean:
                                        parts = [p.strip().strip("'").strip('"') for p in line_clean.split(",")]
                                        cols = list(tables[table_name].keys())
                                        if cols:
                                            cols_str = ", ".join(cols)
                                            vals_formatted = []
                                            for idx, val in enumerate(parts):
                                                if idx < len(cols):
                                                    c_type = tables[table_name].get(cols[idx], "VARCHAR(100)")
                                                    if "INT" in c_type.upper() or "DECIMAL" in c_type.upper():
                                                        vals_formatted.append(val)
                                                    else:
                                                        vals_formatted.append(f"'{val}'")
                                            vals_str = ", ".join(vals_formatted)
                                            seed_queries.append(f"INSERT INTO {table_name} ({cols_str}) VALUES ({vals_str})")

            lines.append("        if (com.systema.modernized.SpringContextHelper.jdbcTemplate == null) {")
            lines.append("            org.springframework.jdbc.datasource.SingleConnectionDataSource dataSource = new org.springframework.jdbc.datasource.SingleConnectionDataSource();")
            lines.append("            dataSource.setSuppressClose(true);")
            lines.append("            String pgHost = System.getenv(\"PGHOST\");")
            lines.append("            String dbMode = System.getenv(\"REAL_DB2_MODE\");")
            lines.append("            if (pgHost != null) {")
            lines.append("                String pgPort = System.getenv(\"PGPORT\") != null ? System.getenv(\"PGPORT\") : \"5432\";")
            lines.append("                String pgUser = System.getenv(\"PGUSER\") != null ? System.getenv(\"PGUSER\") : \"modernize\";")
            lines.append("                String pgPass = System.getenv(\"PGPASSWORD\") != null ? System.getenv(\"PGPASSWORD\") : \"modernize\";")
            lines.append("                String pgDb = System.getenv(\"PGDATABASE\") != null ? System.getenv(\"PGDATABASE\") : \"modernization_db\";")
            lines.append("                dataSource.setDriverClassName(\"org.postgresql.Driver\");")
            lines.append("                dataSource.setUrl(\"jdbc:postgresql://\" + pgHost + \":\" + pgPort + \"/\" + pgDb);")
            lines.append("                dataSource.setUsername(pgUser);")
            lines.append("                dataSource.setPassword(pgPass);")
            lines.append("                com.systema.modernized.SpringContextHelper.jdbcTemplate = new org.springframework.jdbc.core.JdbcTemplate(dataSource);")
            lines.append("                com.systema.modernized.SpringContextHelper.transactionManager = new org.springframework.jdbc.datasource.DataSourceTransactionManager(dataSource);")
            # Apply per-repo seed data to PG for test isolation (same as H2 path)
            if seed_queries:
                lines.append("                try {")
                for table_name in tables:
                    lines.append(f"                    try {{ com.systema.modernized.SpringContextHelper.jdbcTemplate.execute(\"TRUNCATE TABLE {table_name} RESTART IDENTITY CASCADE\"); }} catch (Exception _e) {{ try {{ com.systema.modernized.SpringContextHelper.jdbcTemplate.execute(\"DELETE FROM {table_name}\"); }} catch (Exception _e2) {{}} }}")
                for q in seed_queries:
                    q_esc = q.replace("\\", "\\\\")
                    lines.append(f"                    try {{ com.systema.modernized.SpringContextHelper.jdbcTemplate.execute(\"{q_esc}\"); }} catch (Exception _e) {{ /* ignore duplicate seed */ }}")
                lines.append("                } catch (Exception e) { System.err.println(\"[PG-SEED] Per-repo seed failed: \" + e.getMessage()); }")
            lines.append("            } else if (\"1\".equals(dbMode)) {")
            lines.append("                String dbUrl = System.getenv(\"DB2_URL\");")
            lines.append("                String dbUser = System.getenv(\"DB2_USERNAME\");")
            lines.append("                String dbPass = System.getenv(\"DB2_PASSWORD\");")
            lines.append("                String dbSchema = System.getenv(\"DB2_SCHEMA\");")
            lines.append("                dataSource.setDriverClassName(\"com.ibm.db2.jcc.DB2Driver\");")
            lines.append("                dataSource.setUrl(dbUrl);")
            lines.append("                dataSource.setUsername(dbUser);")
            lines.append("                dataSource.setPassword(dbPass);")
            lines.append("                com.systema.modernized.SpringContextHelper.jdbcTemplate = new org.springframework.jdbc.core.JdbcTemplate(dataSource);")
            lines.append("                com.systema.modernized.SpringContextHelper.transactionManager = new org.springframework.jdbc.datasource.DataSourceTransactionManager(dataSource);")
            lines.append("                if (dbSchema != null && !dbSchema.trim().isEmpty()) {")
            lines.append("                    try {")
            lines.append("                        com.systema.modernized.SpringContextHelper.jdbcTemplate.execute(\"SET SCHEMA \" + dbSchema.trim());")
            lines.append("                    } catch (Exception e) {}")
            lines.append("                }")
            lines.append("            } else {")
            lines.append("                dataSource.setDriverClassName(\"org.h2.Driver\");")
            lines.append("                dataSource.setUrl(\"jdbc:h2:mem:testdb;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;DEFAULT_NULL_ORDERING=HIGH;DB_CLOSE_DELAY=-1;DB_CLOSE_ON_EXIT=FALSE\");")
            lines.append("                dataSource.setUsername(\"sa\");")
            lines.append("                dataSource.setPassword(\"\");")
            lines.append("                com.systema.modernized.SpringContextHelper.jdbcTemplate = new org.springframework.jdbc.core.JdbcTemplate(dataSource);")
            lines.append("                com.systema.modernized.SpringContextHelper.transactionManager = new org.springframework.jdbc.datasource.DataSourceTransactionManager(dataSource);")
            lines.append("                try {")
            for table_name, cols in tables.items():
                if not cols:
                    cols["ID"] = "INT"
                col_defs = ", ".join(f"{c} {t}" for c, t in cols.items())
                create_query = f"CREATE TABLE IF NOT EXISTS {table_name} ({col_defs})"
                lines.append(f"                    com.systema.modernized.SpringContextHelper.jdbcTemplate.execute(\"{create_query}\");")
                lines.append(f"                    com.systema.modernized.SpringContextHelper.jdbcTemplate.execute(\"DELETE FROM {table_name}\");")
            for q in seed_queries:
                lines.append(f"                    com.systema.modernized.SpringContextHelper.jdbcTemplate.execute(\"{q}\");")
            lines.append("                } catch (Exception e) { System.err.println(\"[SQL-INIT] Schema/seed setup failed: \" + e.getMessage()); }")
            lines.append("            }")
            lines.append("        }")
        if has_sql:
            lines.append("        if (com.systema.modernized.SpringContextHelper.transactionManager != null) {")
            lines.append("            txStatus = com.systema.modernized.SpringContextHelper.transactionManager.getTransaction(new org.springframework.transaction.support.DefaultTransactionDefinition());")
            lines.append("        }")
        if total_paras == 0 and self.child_generators:
            first_child_name = list(self.child_generators.keys())[0]
            first_child_class = to_java_class(first_child_name)
            lines.append(f"        {first_child_class} child = new {first_child_class}(this);")
            lines.append("        child.execute();")
        else:
            lines.append("        int i = 0;")
            lines.append(f"        while (i < {total_paras}) {{")
            lines.append("            if (programExited) break;")
            lines.append("            nextParagraphIndex = -1;")
            lines.append("            runParagraph(i);")
            lines.append("            if (nextParagraphIndex != -1) {")
            lines.append("                i = nextParagraphIndex;")
            lines.append("            } else {")
            lines.append("                i++;")
            lines.append("            }")
            lines.append("        }")
        if has_sql:
            lines.append("        if (com.systema.modernized.SpringContextHelper.transactionManager != null && txStatus != null) {")
            lines.append("            try {")
            lines.append("                if (!txStatus.isCompleted()) {")
            lines.append("                    com.systema.modernized.SpringContextHelper.transactionManager.commit(txStatus);")
            lines.append("                }")
            lines.append("            } catch (Exception e) {}")
            lines.append("        }")
        if "DFHCOMMAREA" in self.var_types:
            lines.append("        commarea = dfhcommarea;")
        lines.append("    }")
        lines.append("")

        for p_name, stmts in paragraphs.items():
            self.current_paragraph = p_name
            lines.append(f"    private void {p_name}() {{")
            skip_loop = False
            last_sentence_id = None
            for s in stmts:
                props = s.properties if hasattr(s, "properties") else s.get("properties", {})
                stype = props.get("statement_type", "").upper()
                
                sentence_id = props.get("sentence_id")
                if sentence_id is not None and sentence_id != last_sentence_id:
                    lines.append("        skipToNextSentence = false;")
                    last_sentence_id = sentence_id
                
                if stype in ("PERFORM_UNTIL", "PERFORM_VARYING", "PERFORM_TIMES"):
                    java_stmt = stmt_trans.translate_statement(s)
                    lines.append(f"        {java_stmt}")
                    lines.append("        if (skipToNextSentence) break;")
                    continue
                
                if stype == "END-PERFORM":
                    java_stmt = stmt_trans.translate_statement(s)
                    lines.append(f"        {java_stmt}")
                    continue
                    
                java_stmt = stmt_trans.translate_statement(s)
                if java_stmt and not java_stmt.startswith("// Unsupported statement:"):
                    lines.append(f"        {java_stmt}")
            lines.append("    }")
            lines.append("")

        if self.is_child:
            lines.append("}")
            return "\n".join(lines)

        lines.append("    public static void main(String[] args) {")
        has_cics = any(n.kind == "STATEMENT" and n.properties.get("statement_type") == "EXEC_CICS" for n in self.ir_nodes)
        # Check if CICS is active anywhere in this compilation unit
        has_any_cics = False
        if all_generators:
            has_any_cics = any(
                any(n.kind == "STATEMENT" and n.properties.get("statement_type") == "EXEC_CICS" for n in gen.ir_nodes)
                for gen in all_generators.values()
            )
        if has_cics or has_any_cics:
            lines.append("        if (args.length > 0) {")
            lines.append("            com.systema.modernized.CicsTransactionContext.setSessionInput(\"INPUTMAP\", \"MSET\", args[0]);")
            lines.append("        }")
        if has_sql:
            lines.append("        com.systema.modernized.MockSqlService.initialize();")
        lines.append("        try {")
        lines.append(f"            new {class_name}().execute();")
        lines.append("        } catch (StopRunException e) {")
        lines.append("            System.exit(0);")
        lines.append("        }")
        lines.append("    }")
        lines.append("")
        lines.append("    private static String formatSigned(long value, int length, boolean signed) {")
        lines.append("        if (!signed) {")
        lines.append("            return String.format(\"%0\" + length + \"d\", Math.abs(value));")
        lines.append("        }")
        lines.append("        if (value >= 0) {")
        lines.append("            return String.format(\"%0\" + length + \"d\", value);")
        lines.append("        } else {")
        lines.append("            long absVal = Math.abs(value);")
        lines.append("            String absStr = String.format(\"%0\" + length + \"d\", absVal);")
        lines.append("            char lastChar = absStr.charAt(absStr.length() - 1);")
        lines.append("            char signChar;")
        lines.append("            switch (lastChar) {")
        lines.append("                case '0': signChar = 'p'; break;")
        lines.append("                case '1': signChar = 'q'; break;")
        lines.append("                case '2': signChar = 'r'; break;")
        lines.append("                case '3': signChar = 's'; break;")
        lines.append("                case '4': signChar = 't'; break;")
        lines.append("                case '5': signChar = 'u'; break;")
        lines.append("                case '6': signChar = 'v'; break;")
        lines.append("                case '7': signChar = 'w'; break;")
        lines.append("                case '8': signChar = 'x'; break;")
        lines.append("                case '9': signChar = 'y'; break;")
        lines.append("                default: signChar = lastChar;")
        lines.append("            }")
        lines.append("            return absStr.substring(0, absStr.length() - 1) + signChar;")
        lines.append("        }")
        lines.append("    }")
        lines.append("")
        lines.append("    private static BigDecimal parseSigned(String val, int scale) {")
        lines.append("        if (val == null || val.trim().isEmpty()) {")
        lines.append("            return BigDecimal.ZERO;")
        lines.append("        }")
        lines.append("        val = val.trim();")
        lines.append("        char last = val.charAt(val.length() - 1);")
        lines.append("        boolean negative = false;")
        lines.append("        char replacement = last;")
        lines.append("        if (last >= 'p' && last <= 'y') {")
        lines.append("            negative = true;")
        lines.append("            replacement = (char) ('0' + (last - 'p'));")
        lines.append("        }")
        lines.append("        String cleanVal = val.substring(0, val.length() - 1) + replacement;")
        lines.append("        BigDecimal bd = new BigDecimal(cleanVal);")
        lines.append("        if (negative) {")
        lines.append("            bd = bd.negate();")
        lines.append("        }")
        lines.append("        return bd.movePointLeft(scale);")
        lines.append("    }")
        lines.append("")
        lines.append("    private static long parseSignedLong(String val) {")
        lines.append("        if (val == null || val.trim().isEmpty()) {")
        lines.append("            return 0;")
        lines.append("        }")
        lines.append("        val = val.trim();")
        lines.append("        char last = val.charAt(val.length() - 1);")
        lines.append("        boolean negative = false;")
        lines.append("        char replacement = last;")
        lines.append("        if (last >= 'p' && last <= 'y') {")
        lines.append("            negative = true;")
        lines.append("            replacement = (char) ('0' + (last - 'p'));")
        lines.append("        }")
        lines.append("        String cleanVal = val.substring(0, val.length() - 1) + replacement;")
        lines.append("        long l = Long.parseLong(cleanVal);")
        lines.append("        return negative ? -l : l;")
        lines.append("    }")
        lines.append("")
        lines.append("    private static boolean checkSizeError(BigDecimal val, int digits, int scale, boolean signed) {")
        lines.append("        if (val == null) return true;")
        lines.append("        try {")
        lines.append("            BigDecimal limit = BigDecimal.TEN.pow(digits - scale).subtract(BigDecimal.ONE.movePointLeft(scale));")
        lines.append("            BigDecimal minLimit = signed ? limit.negate() : BigDecimal.ZERO;")
        lines.append("            return val.compareTo(limit) > 0 || val.compareTo(minLimit) < 0;")
        lines.append("        } catch (Exception e) {")
        lines.append("            return true;")
        lines.append("        }")
        lines.append("    }")
        lines.append("")
        lines.append("    private static boolean checkSizeError(long val, int digits, boolean signed) {")
        lines.append("        long limit = java.math.BigInteger.TEN.pow(digits).subtract(java.math.BigInteger.ONE).longValueExact();")
        lines.append("        long minLimit = signed ? -limit : 0;")
        lines.append("        return val > limit || val < minLimit;")
        lines.append("    }")
        lines.append("")
        lines.append("    private static String padString(String val, int length) {")
        lines.append("        if (val == null) val = \"\";")
        lines.append("        String padded = String.format(\"%-\" + length + \"s\", val);")
        lines.append("        if (padded.length() > length) return padded.substring(0, length);")
        lines.append("        return padded;")
        lines.append("    }")
        lines.append("")
        lines.append("    private static void writeBytes(byte[] b) {")
        lines.append("        if (b != null) {")
        lines.append("            System.out.write(b, 0, b.length);")
        lines.append("        }")
        lines.append("    }")
        lines.append("")
        for child_name, child_gen in self.child_generators.items():
            child_src = child_gen.generate_class_source(all_generators)
            for line in child_src.splitlines():
                lines.append("    " + line)
            lines.append("")

        lines.append("}")
        return "\n".join(lines)
