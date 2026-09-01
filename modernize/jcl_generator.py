import os
import re

class JclGenerator:
    def __init__(self, job, all_programs):
        self.job = job
        self.all_programs = all_programs # Set of program class names available in package (e.g. {"Cobprog1", "Cobprog2"})

    def generate(self) -> str:
        job_name = self.job.name or "UNNAMED"
        class_name = f"JclJob_{job_name.lower().capitalize()}"
        
        lines = []
        lines.append("package com.systema.modernized.native_gen;")
        lines.append("")
        lines.append("import com.systema.modernized.JclExecutionContext;")
        lines.append("import java.io.BufferedWriter;")
        lines.append("import java.io.IOException;")
        lines.append("import java.nio.file.Files;")
        lines.append("import java.nio.file.Path;")
        lines.append("import java.nio.file.Paths;")
        lines.append("")
        lines.append(f"public class {class_name} {{")
        
        # Main entry point
        lines.append("    public static void main(String[] args) throws Exception {")
        lines.append(f"        System.out.println(\"=== START JCL JOB: {job_name.upper()} ===\");")
        lines.append("        JclExecutionContext.clear();")
        lines.append("        try {")
        
        # Collect all steps recursively to generate run calls
        flat_steps = self.collect_all_steps(self.job.steps)
        
        # Generate recursive flow
        self.generate_step_flow(self.job.steps, lines, "            ")
        
        lines.append("        } finally {")
        lines.append("            JclExecutionContext.clear();")
        lines.append(f"            System.out.println(\"=== END JCL JOB: {job_name.upper()} ===\");")
        lines.append("        }")
        lines.append("    }")
        lines.append("")

        # Generate individual step run methods
        for step in flat_steps:
            self.generate_step_method(step, lines)

        lines.append("}")
        return "\n".join(lines)

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

    def generate_step_flow(self, steps, lines, indent):
        for step in steps:
            s_dict = step.to_dict() if not isinstance(step, dict) else step
            s_type = s_dict.get("type")
            
            if s_type == "STEP":
                name = s_dict["name"]
                step_func = f"runStep_{name.replace('.', '_')}"
                bypass_func = f"shouldBypassStep_{name.replace('.', '_')}"
                
                lines.append(f"{indent}if ({bypass_func}()) {{")
                lines.append(f"{indent}    System.out.println(\"STEP BYPASS: {name}\");")
                lines.append(f"{indent}}} else {{")
                lines.append(f"{indent}    {step_func}();")
                lines.append(f"{indent}}}")
                
            elif s_type == "IF_BLOCK":
                cond = s_dict["condition_str"]
                java_cond = self.translate_if_condition(cond)
                lines.append(f"{indent}if ({java_cond}) {{")
                self.generate_step_flow(s_dict["then_steps"], lines, indent + "    ")
                if s_dict["else_steps"]:
                    lines.append(f"{indent}}} else {{")
                    self.generate_step_flow(s_dict["else_steps"], lines, indent + "    ")
                lines.append(f"{indent}}}")

    def translate_if_condition(self, cond_str):
        """Translate supported JCL IF conditions to Java and fail closed otherwise."""
        cond = cond_str.strip()

        # JCL condition expressions are commonly wrapped in one or more
        # enclosing parentheses. Strip only balanced outer pairs so the
        # semantic expression remains unchanged.
        while cond.startswith("(") and cond.endswith(")"):
            depth = 0
            balanced = True
            for i, ch in enumerate(cond):
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0 and i != len(cond) - 1:
                        balanced = False
                        break
            if balanced and depth == 0:
                cond = cond[1:-1].strip()
            else:
                break

        operators = {
            "EQ": "==", "NE": "!=", "GT": ">", "LT": "<",
            "GE": ">=", "LE": "<=", "=": "==", "==": "==",
            "!=": "!=", "<>": "!=", ">": ">", "<": "<",
            ">=": ">=", "<=": "<=",
        }

        m = re.fullmatch(
            r'([A-Za-z0-9_$#.\-]+)\.RC\s*(EQ|NE|GT|LT|GE|LE|==|!=|<>|>=|<=|>|<|=)\s*(-?\d+)',
            cond, re.IGNORECASE
        )
        if m:
            step = m.group(1).upper()
            op = operators[m.group(2).upper()]
            val = m.group(3)
            return f'JclExecutionContext.getStepReturnCode("{step}") {op} {val}'

        m_rc = re.fullmatch(
            r'RC\s*(EQ|NE|GT|LT|GE|LE|==|!=|<>|>=|<=|>|<|=)\s*(-?\d+)',
            cond, re.IGNORECASE
        )
        if m_rc:
            op = operators[m_rc.group(1).upper()]
            val = m_rc.group(2)
            return f'JclExecutionContext.getLatestReturnCode() {op} {val}'

        m_run = re.fullmatch(r'([A-Za-z0-9_$#.\-]+)\.RUN', cond, re.IGNORECASE)
        if m_run:
            step = m_run.group(1).upper()
            return f'JclExecutionContext.getStepReturnCode("{step}") != 0'

        # Never turn an unrecognized condition into `true`; that would make
        # an unsupported JCL branch execute unconditionally.
        raise ValueError(f"Unsupported JCL IF condition: {cond_str!r}")

    def generate_step_method(self, step, lines):
        name = step["name"]
        pgm = step.get("pgm")
        conds = step.get("conds", [])
        dds = step.get("dds", {})
        
        # 1. Bypass check method
        lines.append(f"    private static boolean shouldBypassStep_{name.replace('.', '_')}() {{")
        has_even = any(code == "EVEN" for code, op, stepname in conds)
        has_only = any(code == "ONLY" for code, op, stepname in conds)
        normal_conds = [(code, op, stepname) for code, op, stepname in conds if code not in ("EVEN", "ONLY")]
        
        lines.append("        boolean abended = JclExecutionContext.hasJobAbended();")
        if has_only:
            lines.append("        if (!abended) return true;")
        elif not has_even:
            lines.append("        if (abended) return true;")
            
        for code, op, stepname in normal_conds:
            if stepname:
                lines.append(f"        if (JclExecutionContext.compareRc({code}, \"{op}\", JclExecutionContext.getStepReturnCode(\"{stepname.upper()}\"))) return true;")
            else:
                lines.append(f"        if (JclExecutionContext.checkAnyStepCond({code}, \"{op}\")) return true;")
        lines.append("        return false;")
        lines.append("    }")
        lines.append("")

        # 2. Run step method
        lines.append(f"    private static void runStep_{name.replace('.', '_')}() throws Exception {{")
        lines.append(f"        System.out.println(\"=== EXECUTE STEP: {name} (PGM: {pgm}) ===\");")
        
        # Register DD DSNs
        for dd_name, dd in dds.items():
            dsn = dd.get("dsn")
            if dsn:
                # Resolve local files for modern execution (map logical name to actual test data/outputs)
                # Map DSN path
                lines.append(f"        JclExecutionContext.setDdAssignment(\"{dd_name}\", \"{dsn}\");")
        
        # Handle SYSIN data writing to temp files
        sysin_var = None
        for dd_name, dd in dds.items():
            if dd.get("is_sysin") and dd.get("sysin_data") is not None:
                sysin_var = f"sysinTemp_{name.replace('.', '_')}"
                lines.append(f"        Path {sysin_var} = Files.createTempFile(\"sysin_{name.replace('.', '_')}_\", \".tmp\");")
                
                raw_data = dd.get("sysin_data")
                padded_lines = [l.ljust(80) for l in raw_data.splitlines()]
                padded_data = "\n".join(padded_lines) + "\n"
                data_escaped = padded_data.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
                
                lines.append(f"        Files.writeString({sysin_var}, \"{data_escaped}\");")
                lines.append(f"        JclExecutionContext.setDdAssignment(\"{dd_name}\", {sysin_var}.toAbsolutePath().toString());")

        lines.append("        int rc = 0;")
        
        # Map target program execution
        # Convert pgm (e.g. COBPROG1) to camel-cased class name (e.g. Cobprog1)
        if pgm:
            cleaned = pgm.replace("-", " ").replace("_", " ")
            parts = cleaned.split()
            class_name = "".join(p.capitalize() for p in parts)
            
            lines.append("        try {")
            lines.append(f"            Class<?> clazz = Class.forName(\"com.systema.modernized.native_gen.{class_name}\");")
            lines.append("            Object program = clazz.getDeclaredConstructor().newInstance();")
            lines.append("            try {")
            lines.append("                clazz.getMethod(\"execute\").invoke(program);")
            lines.append("            } catch (Throwable ite) {")
            lines.append("                Throwable cause = ite.getCause() != null ? ite.getCause() : ite;")
            lines.append("                if (!cause.getClass().getSimpleName().equals(\"StopRunException\")) {")
            lines.append("                    throw cause;")
            lines.append("                }")
            lines.append("            }")
            lines.append("            try {")
            lines.append("                java.lang.reflect.Field rcField = clazz.getField(\"return_code\");")
            lines.append("                Object valObj = rcField.get(program);")
            lines.append("                if (valObj instanceof Number) {")
            lines.append("                    rc = ((Number) valObj).intValue();")
            lines.append("                } else if (valObj != null) {")
            lines.append("                    rc = Integer.parseInt(valObj.toString().trim());")
            lines.append("                }")
            lines.append("            } catch (Exception e) {")
            lines.append("                try {")
            lines.append("                    java.lang.reflect.Field rcField = clazz.getField(\"returnCode\");")
            lines.append("                    Object valObj = rcField.get(program);")
            lines.append("                    if (valObj instanceof Number) {")
            lines.append("                        rc = ((Number) valObj).intValue();")
            lines.append("                    } else if (valObj != null) {")
            lines.append("                        rc = Integer.parseInt(valObj.toString().trim());")
            lines.append("                    }")
            lines.append("                } catch (Exception e2) {}")
            lines.append("            }")
            lines.append("            if (rc >= 8) {")
            lines.append("                com.systema.modernized.JclExecutionContext.setJobAbended(true);")
            lines.append("            }")
            lines.append("        } catch (ClassNotFoundException e) {")
            lines.append(f"            System.err.println(\"Warning: Program class '{class_name}' not found for step '{name}'\");")
            lines.append("        } catch (Throwable t) {")
            lines.append("            Throwable cause = t.getCause() != null ? t.getCause() : t;")
            lines.append(f"            System.err.println(\"Step {name} failed/abended: \" + cause);")
            lines.append("            cause.printStackTrace(System.err);")
            lines.append("            rc = 16;")
            lines.append("            com.systema.modernized.JclExecutionContext.setJobAbended(true);")
            lines.append("        }")
        
        # Cleanup SYSIN files in finally block
        if sysin_var:
            lines.append("        finally {")
            lines.append("            try {")
            lines.append(f"                Files.deleteIfExists({sysin_var});")
            lines.append("            } catch (Exception e) {}")
            lines.append("        }")
            
        lines.append(f"        System.out.println(\"STEP {name} FINISHED WITH RC: \" + rc);")
        lines.append(f"        JclExecutionContext.setStepReturnCode(\"{name}\", rc);")
        lines.append("    }")
        lines.append("")
