import os
import re

class JclDD:
    def __init__(self, name, dsn=None, disp=None, sysin_data=None, is_sysin=False):
        self.name = name.upper() if name else None
        self.dsn = dsn
        self.disp = disp
        self.sysin_data = sysin_data
        self.is_sysin = is_sysin

    def to_dict(self):
        return {
            "name": self.name,
            "dsn": self.dsn,
            "disp": self.disp,
            "sysin_data": self.sysin_data,
            "is_sysin": self.is_sysin
        }


class JclStep:
    def __init__(self, name, pgm=None, proc=None, conds=None, dds=None, proc_args=None):
        self.name = name.upper() if name else None
        self.pgm = pgm.upper() if pgm else None
        self.proc = proc.upper() if proc else None
        self.conds = conds or []  # List of (code, operator, stepname)
        self.dds = dds or {}      # DDNAME -> JclDD
        self.proc_args = proc_args or {}

    def to_dict(self):
        return {
            "type": "STEP",
            "name": self.name,
            "pgm": self.pgm,
            "proc": self.proc,
            "conds": self.conds,
            "dds": {k: v.to_dict() for k, v in self.dds.items()},
            "proc_args": self.proc_args
        }


class JclIfBlock:
    def __init__(self, condition_str, then_steps=None, else_steps=None):
        self.condition_str = condition_str
        self.then_steps = then_steps or []
        self.else_steps = else_steps or []

    def to_dict(self):
        return {
            "type": "IF_BLOCK",
            "condition_str": self.condition_str,
            "then_steps": [s.to_dict() for s in self.then_steps],
            "else_steps": [s.to_dict() for s in self.else_steps]
        }


class JclJob:
    def __init__(self, name=None, steps=None, symbols=None, procs=None):
        self.name = name.upper() if name else None
        self.steps = steps or []
        self.symbols = symbols or {}
        self.procs = procs or {}

    def to_dict(self):
        return {
            "name": self.name,
            "steps": [s.to_dict() for s in self.steps],
            "symbols": self.symbols,
            "procs": {k: [s.to_dict() for s in v] for k, v in self.procs.items()}
        }


class JclParser:
    def __init__(self, content, repo_dir=None):
        self.content = content
        self.repo_dir = os.path.abspath(repo_dir) if repo_dir else None
        self.symbols = {}
        self.procs = {}    # PROCNAME -> list of statement dicts/objects
        self.diagnostics = []

    def log_diag(self, status, construct, reason, line=0):
        self.diagnostics.append({
            "status": status,
            "construct": construct,
            "reason": reason,
            "line": line
        })

    def collect_all_steps(self, steps):
        collected = []
        for step in steps:
            if hasattr(step, "then_steps"):  # JclIfBlock object
                collected.extend(self.collect_all_steps(step.then_steps))
                collected.extend(self.collect_all_steps(step.else_steps))
            elif isinstance(step, dict):
                s_type = step.get("type")
                if s_type == "STEP":
                    collected.append(step)
                elif s_type == "IF_BLOCK":
                    collected.extend(self.collect_all_steps(step.get("then_steps", [])))
                    collected.extend(self.collect_all_steps(step.get("else_steps", [])))
            else:
                # JclStep object
                collected.append(step.to_dict())
        return collected

    def parse(self) -> JclJob:
        lines = self.content.splitlines()
        statements = []
        i = 0
        n = len(lines)

        while i < n:
            line = lines[i].rstrip()
            if not line:
                i += 1
                continue
            if line.startswith("//*"):
                i += 1
                continue

            if line.startswith("//"):
                stmt = line
                # Handle JCL continuation lines (ends with comma, next line starts with // followed by spaces)
                while i + 1 < n:
                    next_line = lines[i+1].rstrip()
                    if next_line.startswith("//") and not next_line.startswith("//*") and next_line[2:3].isspace() and stmt.endswith(","):
                        stmt += " " + next_line[2:].lstrip()
                        i += 1
                    else:
                        break
                
                parsed = self.parse_statement(stmt, i + 1)
                if parsed:
                    statements.append(parsed)
                    # Check if SYSIN follows
                    if parsed.get("op") == "DD" and parsed.get("is_sysin"):
                        sysin_lines = []
                        i += 1
                        while i < n:
                            sysin_line = lines[i]
                            if sysin_line.startswith("/*"):
                                i += 1
                                break
                            if sysin_line.startswith("//"):
                                # Statement boundary, do not consume
                                i -= 1
                                break
                            sysin_lines.append(sysin_line)
                            i += 1
                        parsed["sysin_data"] = "\n".join(sysin_lines)
                i += 1
            else:
                # Skip any raw line outside active JCL statements
                i += 1

        return self.build_job_flow(statements)

    def parse_statement(self, stmt_str, line_num):
        content = stmt_str[2:].strip()
        if not content:
            return None

        # Split into name, operation, and parameters
        # Check standard keywords
        jcl_ops = {"JOB", "EXEC", "DD", "PROC", "PEND", "SET", "IF", "THEN", "ELSE", "ENDIF", "JCLLIB", "INCLUDE"}
        
        parts = content.split(None, 2)
        if len(parts) == 0:
            return None
            
        name = None
        op = None
        params_str = ""
        
        first_word = parts[0].upper()
        if first_word in jcl_ops:
            op = first_word
            if len(parts) > 1:
                params_str = content[len(first_word):].strip()
        else:
            name = parts[0]
            if len(parts) > 1:
                op = parts[1].upper()
                if len(parts) > 2:
                    params_str = parts[2].strip()
            else:
                op = "UNKNOWN"

        # Resolve symbol substitutions in parameter string
        params_str = self.substitute_symbols(params_str)

        params = {}
        if op in ("JOB", "EXEC", "DD", "SET", "PROC"):
            params = self.parse_params(params_str)

        # SET symbol assignment
        if op == "SET":
            for k, v in params.items():
                self.symbols[k] = v

        is_sysin = False
        if op == "DD":
            params_upper = params_str.upper()
            if params_str.strip() == "*" or params_str.strip().startswith("*") or "DD *" in stmt_str or params_upper == "DATA" or params_upper.startswith("DATA"):
                is_sysin = True

        return {
            "name": name,
            "op": op,
            "params": params,
            "params_str": params_str,
            "is_sysin": is_sysin,
            "line_num": line_num
        }

    def parse_params(self, params_str):
        params = {}
        if not params_str:
            return params
            
        chunks = []
        current_chunk = []
        paren_depth = 0
        in_quotes = False
        quote_char = None
        
        for char in params_str:
            if in_quotes:
                if char == quote_char:
                    in_quotes = False
                current_chunk.append(char)
            else:
                if char in ("'", '"'):
                    in_quotes = True
                    quote_char = char
                    current_chunk.append(char)
                elif char == '(':
                    paren_depth += 1
                    current_chunk.append(char)
                elif char == ')':
                    paren_depth -= 1
                    current_chunk.append(char)
                elif char == ',' and paren_depth == 0:
                    chunks.append("".join(current_chunk).strip())
                    current_chunk = []
                else:
                    current_chunk.append(char)
        if current_chunk:
            chunks.append("".join(current_chunk).strip())
            
        for chunk in chunks:
            if not chunk:
                continue
            if "=" in chunk:
                key, val = chunk.split("=", 1)
                params[key.strip().upper()] = val.strip().strip("'\"")
            else:
                params[chunk.upper()] = True
        return params

    def substitute_symbols(self, text):
        if not text:
            return text
        resolved = text
        
        # Protect double ampersands (&&) from being matched as symbol references
        placeholder = "\u0000JCL_TEMP_DSN\u0000"
        resolved = resolved.replace("&&", placeholder)
        
        # Resolve patterns like &VAR. or &VAR
        for sym_name, sym_val in sorted(self.symbols.items(), key=lambda x: len(x[0]), reverse=True):
            if isinstance(sym_val, str):
                resolved = resolved.replace(f"&{sym_name}.", sym_val)
                resolved = resolved.replace(f"&{sym_name}", sym_val)

        # Detect any remaining unreplaced symbol references
        unresolved = re.findall(r'&([A-Za-z0-9_]+)', resolved)
        if unresolved:
            for u in unresolved:
                self.log_diag("NATIVE_TRANSLATION_BLOCKED", "SYMBOL", f"JCL_UNRESOLVED_SYMBOL: Unresolved symbol reference &{u}")
                
        # Restore double ampersands
        resolved = resolved.replace(placeholder, "&&")
        return resolved

    def parse_cond_param(self, cond_val, line_num):
        # Parses COND=(code,operator[,step]) or COND=((code,operator[,step]),(code,operator))
        # Also handles COND=ONLY and COND=EVEN
        conds = []
        if not cond_val:
            return conds
        
        val = cond_val.strip()
        val_upper = val.upper()
        
        # Check for standalone EVEN / ONLY
        if val_upper == "EVEN":
            return [("EVEN", None, None)]
        if val_upper == "ONLY":
            return [("ONLY", None, None)]

        has_even = False
        has_only = False
        if "EVEN" in val_upper:
            has_even = True
            # remove EVEN term to parse the rest
            val = re.sub(r',?\bEVEN\b,?', '', val, flags=re.IGNORECASE).strip("(), ")
        if "ONLY" in val_upper:
            has_only = True
            # remove ONLY term to parse the rest
            val = re.sub(r',?\bONLY\b,?', '', val, flags=re.IGNORECASE).strip("(), ")
            
        if has_even:
            conds.append(("EVEN", None, None))
        if has_only:
            conds.append(("ONLY", None, None))
            
        if not val or val == "()":
            return conds
        
        # Strip outer parentheses if double parentheses, e.g. ((4,LT),(8,LE,STEP1))
        val = val.strip()
        
        # Helper to parse a single condition tuple like "4,LT" or "4,LT,STEP1"
        def parse_single_tuple(t_str):
            t_str = t_str.strip("() ")
            parts = [p.strip() for p in t_str.split(",")]
            if len(parts) < 2:
                self.log_diag("NATIVE_TRANSLATION_BLOCKED", "COND", f"JCL_UNSUPPORTED_CONDITION: Invalid condition tuple '{t_str}'", line_num)
                return None
            try:
                code = int(parts[0])
            except ValueError:
                self.log_diag("NATIVE_TRANSLATION_BLOCKED", "COND", f"JCL_UNSUPPORTED_CONDITION: Non-numeric code in condition '{parts[0]}'", line_num)
                return None
            op = parts[1].upper()
            if op not in ("EQ", "NE", "GT", "LT", "GE", "LE"):
                self.log_diag("NATIVE_TRANSLATION_BLOCKED", "COND", f"JCL_UNSUPPORTED_CONDITION: Invalid operator '{op}'", line_num)
                return None
            step = parts[2].upper() if len(parts) > 2 else None
            return (code, op, step)

        # If starts with ((, split into individual parenthesis blocks
        if val.startswith("((") and val.endswith("))"):
            # strip outer one pair of parens -> (4,LT),(8,LE,STEP1)
            val = val[1:-1]
            # split by ),(
            tuples = val.split("),(")
            for t in tuples:
                parsed_t = parse_single_tuple(t)
                if parsed_t:
                    conds.append(parsed_t)
        elif val.startswith("("):
            # Could be (4,LT) or (4,LT,STEP1) or a list like (4,LT),(8,LE)
            # Let's count comma outside parens or use split
            # If there's a comma separating multiple tuples e.g. (4,LT),(8,LE)
            if "),(" in val:
                tuples = val.split("),(")
                for t in tuples:
                    parsed_t = parse_single_tuple(t)
                    if parsed_t:
                        conds.append(parsed_t)
            else:
                parsed_t = parse_single_tuple(val)
                if parsed_t:
                    conds.append(parsed_t)
        else:
            self.log_diag("NATIVE_TRANSLATION_BLOCKED", "COND", f"JCL_UNSUPPORTED_CONDITION: Malformed condition '{val}'", line_num)

        return conds

    def build_job_flow(self, statements) -> JclJob:
        job = JclJob()
        steps = []
        i = 0
        n = len(statements)

        # Phase 1: extract all PROC / PEND declarations
        # A PROC declaration starts with a PROC statement and ends with PEND
        proc_name = None
        proc_stmts = []
        in_proc = False
        
        jcl_stmts = [] # Clean statements outside procs
        
        for stmt in statements:
            op = stmt["op"]
            name = stmt["name"]
            
            if op == "PROC":
                in_proc = True
                proc_name = name.upper() if name else "ANON_PROC"
                proc_stmts = []
                # Keep the PROC statement itself to record parameters
                proc_stmts.append(stmt)
            elif op == "PEND":
                if in_proc:
                    self.procs[proc_name] = proc_stmts
                    in_proc = False
            else:
                if in_proc:
                    proc_stmts.append(stmt)
                else:
                    jcl_stmts.append(stmt)

        # Phase 2: process job cards and execute steps
        job_name = None
        active_steps = []
        
        # We need to build steps, keeping track of nested IF blocks
        # IF block stack
        if_stack = []  # List of list of steps

        i = 0
        m = len(jcl_stmts)
        while i < m:
            stmt = jcl_stmts[i]
            op = stmt["op"]
            name = stmt["name"]
            line_num = stmt["line_num"]
            params = stmt["params"]

            if op == "JOB":
                job_name = name
                job.name = job_name
            elif op == "EXEC":
                pgm = params.get("PGM")
                proc = params.get("PROC")
                
                # EXEC positional parameter could be PROC name if neither PGM nor PROC key is present
                # e.g. //STEP1 EXEC MYPROC
                if not pgm and not proc:
                    # Find first positional or clean parameter
                    for k, v in params.items():
                        if v is True: # Positional indicator
                            proc = k
                            break
                
                if not pgm and not proc:
                    self.log_diag("NATIVE_TRANSLATION_BLOCKED", "EXEC", "JCL_INVALID_STEP: EXEC card has neither PGM nor PGM target", line_num)
                    i += 1
                    continue

                cond_val = params.get("COND")
                conds = self.parse_cond_param(cond_val, line_num)

                # Collect all subsequent DD statements belonging to this step
                dds = {}
                i += 1
                while i < m:
                    next_stmt = jcl_stmts[i]
                    if next_stmt["op"] == "DD":
                        dd_name = next_stmt["name"]
                        if not dd_name:
                            self.log_diag("NATIVE_TRANSLATION_BLOCKED", "DD", "JCL_INVALID_DD: DD card is missing ddname", next_stmt["line_num"])
                            i += 1
                            continue
                        
                        dsn = next_stmt["params"].get("DSN")
                        disp = next_stmt["params"].get("DISP")
                        sysin_data = next_stmt.get("sysin_data")
                        is_sysin = next_stmt.get("is_sysin", False)
                        
                        # Validate dataset existence if DISP=SHR or DISP=OLD
                        self.validate_dataset(dsn, disp, next_stmt["line_num"])

                        dds[dd_name.upper()] = JclDD(
                            name=dd_name,
                            dsn=dsn,
                            disp=disp,
                            sysin_data=sysin_data,
                            is_sysin=is_sysin
                        )
                        i += 1
                    elif next_stmt["op"] in ("EXEC", "IF", "ELSE", "ENDIF", "SET"):
                        # Step boundary or IF boundary, do not consume
                        i -= 1
                        break
                    else:
                        i += 1

                # If executing a PROC, expand it!
                if proc:
                    proc_upper = proc.upper()
                    if proc_upper not in self.procs:
                        self.log_diag("NATIVE_TRANSLATION_BLOCKED", "EXEC", f"JCL_UNRESOLVED_PROC: Referenced PROC '{proc}' not found", line_num)
                    else:
                        # Expand PROC statements into job steps
                        expanded_steps = self.expand_proc(proc_upper, name, params, dds)
                        # Apply step conds to all expanded steps
                        for es in expanded_steps:
                            es.conds.extend(conds)
                            if if_stack:
                                if_stack[-1].append(es)
                            else:
                                active_steps.append(es)
                else:
                    step_obj = JclStep(
                        name=name,
                        pgm=pgm,
                        conds=conds,
                        dds=dds
                    )
                    if if_stack:
                        if_stack[-1].append(step_obj)
                    else:
                        active_steps.append(step_obj)
            
            elif op == "IF":
                # Handle IF block condition
                cond_str = stmt.get("params_str", "")
                if cond_str.upper().endswith("THEN"):
                    cond_str = cond_str[:-4].strip()
                
                # Push new JclIfBlock onto the if_stack
                if_block = JclIfBlock(condition_str=cond_str)
                if if_stack:
                    if_stack[-1].append(if_block)
                else:
                    active_steps.append(if_block)
                
                # We will collect steps inside then_steps
                if_stack.append(if_block.then_steps)
                
            elif op == "ELSE":
                if len(if_stack) > 0:
                    # Pop then_steps
                    if_stack.pop()
                    # Find the last JclIfBlock added to add else_steps to
                    # It will be at the end of the previous level
                    parent_list = if_stack[-1] if if_stack else active_steps
                    last_block = parent_list[-1]
                    if isinstance(last_block, JclIfBlock):
                        if_stack.append(last_block.else_steps)
                else:
                    self.log_diag("NATIVE_TRANSLATION_BLOCKED", "ELSE", "JCL_UNSUPPORTED_CONDITION: ELSE without matching IF", line_num)
                    
            elif op == "ENDIF":
                if len(if_stack) > 0:
                    if_stack.pop()
                else:
                    self.log_diag("NATIVE_TRANSLATION_BLOCKED", "ENDIF", "JCL_UNSUPPORTED_CONDITION: ENDIF without matching IF", line_num)

            i += 1

        job.steps = active_steps
        job.symbols = self.symbols
        job.procs = {k: [self.convert_stmt_to_step(s) for s in v if s["op"] == "EXEC"] for k, v in self.procs.items()}
        return job

    def convert_stmt_to_step(self, stmt):
        params = stmt["params"]
        return JclStep(
            name=stmt["name"],
            pgm=params.get("PGM"),
            proc=params.get("PROC")
        )

    def validate_dataset(self, dsn, disp, line_num):
        if not dsn:
            return
        
        # DISP can be string e.g. SHR or OLD
        disp_str = str(disp).upper()
        if "SHR" in disp_str or "OLD" in disp_str:
            # If dataset name contains symbol reference & (which wasn't replaced), it is unresolved
            if "&" in dsn:
                self.log_diag("NATIVE_TRANSLATION_BLOCKED", "DD", f"UNRESOLVED_DATASET: DSN contains unresolved symbol references: {dsn}", line_num)
                return
            
            # Check locally in repo or workspace
            # Let's map mainframe DSN format e.g. MY.INPUT.DATA to local file paths
            # In our system: resolve dataset name to a local path
            resolved_path = dsn
            if self.repo_dir:
                # E.g. DSN=MY.INPUT.DATA -> check if file exists directly or in repo
                # Also check clean names e.g. replace dot with slash
                paths_to_try = [
                    os.path.join(self.repo_dir, dsn),
                    os.path.join(self.repo_dir, dsn.lower()),
                    os.path.join(self.repo_dir, dsn.replace(".", "/")),
                    os.path.join(self.repo_dir, dsn.replace(".", "/").lower()),
                ]
                exists = any(os.path.exists(p) for p in paths_to_try)
                if not exists:
                    # Categorize missing dataset
                    if dsn.startswith("SYS1.") or dsn.startswith("SYS2."):
                        self.log_diag("NATIVE_TRANSLATION_WARNING", "DD", f"EXTERNAL_DATASET: Mainframe system dataset '{dsn}' assumed external", line_num)
                    else:
                        self.log_diag("NATIVE_TRANSLATION_WARNING", "DD", f"STATIC_DATASET_MISSING: Dataset '{dsn}' defined as DISP={disp_str} is missing locally", line_num)
            else:
                self.log_diag("NATIVE_TRANSLATION_WARNING", "DD", f"STATIC_DATASET_MISSING: Dataset '{dsn}' is missing locally (no repo context)", line_num)

    def expand_proc(self, proc_name, step_prefix, override_args, step_dds):
        # Instantiate a copy of PROC statements
        proc_stmts = self.procs[proc_name]
        
        # Get default parameters from PROC card (first card in proc_stmts)
        default_args = {}
        first_stmt = proc_stmts[0]
        if first_stmt["op"] == "PROC":
            default_args = first_stmt["params"]
            
        # Combine args: defaults overridden by override_args
        merged_args = {}
        for k, v in default_args.items():
            merged_args[k.upper()] = v
        for k, v in override_args.items():
            # Skip standard EXEC parameters (PGM, PROC, COND)
            k_upper = k.upper()
            if k_upper not in ("PGM", "PROC", "COND"):
                merged_args[k_upper] = v
                
        # Define local JclParser with local symbols inheriting global symbols
        local_parser = JclParser("", self.repo_dir)
        for k, v in self.symbols.items():
            local_parser.symbols[k] = v
        for k, v in merged_args.items():
            local_parser.symbols[k] = v
            
        # Parse statements inside the PROC
        expanded_steps = []
        
        # Process statement list inside PROC
        i = 1 # Skip PROC card
        m = len(proc_stmts)
        while i < m:
            stmt = proc_stmts[i]
            op = stmt["op"]
            name = stmt["name"]
            line_num = stmt["line_num"]
            
            # Form step name: prefix.proc_step_name
            # E.g. if EXEC PROC=MYPROC inside step STEP1, and PROC has step PROCSTEP, the resolved step name is STEP1.PROCSTEP
            local_step_name = f"{step_prefix}.{name}" if step_prefix and name else (name or step_prefix)
            
            # Substitute symbols in parameter string
            params_str = local_parser.substitute_symbols(stmt["params_str"])
            params = local_parser.parse_params(params_str)
            
            if op == "EXEC":
                pgm = params.get("PGM")
                cond_val = params.get("COND")
                conds = local_parser.parse_cond_param(cond_val, line_num)
                
                # Collect DD statements inside PROC
                dds = {}
                i += 1
                while i < m:
                    next_stmt = proc_stmts[i]
                    if next_stmt["op"] == "DD":
                        dd_name = next_stmt["name"]
                        dsn = local_parser.substitute_symbols(next_stmt["params_str"])
                        dd_params = local_parser.parse_params(dsn)
                        
                        dsn_val = dd_params.get("DSN")
                        disp_val = dd_params.get("DISP")
                        sysin_data = next_stmt.get("sysin_data")
                        is_sysin = next_stmt.get("is_sysin", False)
                        
                        self.validate_dataset(dsn_val, disp_val, next_stmt["line_num"])
                        
                        dds[dd_name.upper()] = JclDD(
                            name=dd_name,
                            dsn=dsn_val,
                            disp=disp_val,
                            sysin_data=sysin_data,
                            is_sysin=is_sysin
                        )
                        i += 1
                    else:
                        i -= 1
                        break
                        
                # Merge with step override DDs if any
                # JCL allows overriding DDs in PROC steps via:
                # //STEPNAME.DDNAME DD DSN=...
                # We can check step_dds keys matching STEP_PREFIX.DDNAME
                for k, v in step_dds.items():
                    # E.g. if step_dds contains "STEP1.DD1" or "DD1" (which overrides MYPROC's DD1)
                    # Standard JCL override uses name: STEP_NAME.DD_NAME
                    # E.g. STEP1.DD1
                    if "." in k:
                        step_ref, dd_ref = k.split(".", 1)
                        if step_ref.upper() == name.upper():
                            dds[dd_ref.upper()] = v
                            
                step_obj = JclStep(
                    name=local_step_name,
                    pgm=pgm,
                    conds=conds,
                    dds=dds
                )
                expanded_steps.append(step_obj)
            i += 1
            
        return expanded_steps
