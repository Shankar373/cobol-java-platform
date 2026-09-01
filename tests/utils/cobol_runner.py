import os
import shutil
import tempfile
import subprocess
from modernize.lexer import CobolLexer
from modernize.parser import CobolParser
from modernize.native_generator import NativeProgramGenerator

def run_cobol_code(program_name: str, code: str, input_files: dict = None, return_full: bool = False) -> tuple:
    filename = f"{program_name}.cob"
    lexer = CobolLexer(filename)
    tokens = lexer.tokenize(code)
    parser = CobolParser(tokens, filename)
    ir = parser.parse()
    
    gen = NativeProgramGenerator(program_name, list(ir.nodes.values()))
    all_generators = {program_name.upper(): gen}
    def register_child_generators(g):
        for c_name, c_gen in g.child_generators.items():
            all_generators[c_name.upper()] = c_gen
            register_child_generators(c_gen)
    register_child_generators(gen)
    java_source = gen.generate_class_source(all_generators)
    
    temp_dir = tempfile.mkdtemp()
    try:
        pkg_dir = os.path.join(temp_dir, "com", "systema", "modernized", "native_gen")
        os.makedirs(pkg_dir, exist_ok=True)
        
        # Write and compile JclExecutionContext.java to prevent compilation failures for programs with file IO
        jcl_context_dir = os.path.join(temp_dir, "com", "systema", "modernized")
        os.makedirs(jcl_context_dir, exist_ok=True)
        jcl_context_src = """package com.systema.modernized;
import java.util.HashMap;
import java.util.Map;
public class JclExecutionContext {
    private static final ThreadLocal<Map<String, String>> ddAssignments = ThreadLocal.withInitial(HashMap::new);
    private static final ThreadLocal<Map<String, String>> sysinData = ThreadLocal.withInitial(HashMap::new);
    private static final ThreadLocal<Map<String, Integer>> stepReturnCodes = ThreadLocal.withInitial(HashMap::new);
    
    public static void setDdAssignment(String ddName, String physicalPath) {
        ddAssignments.get().put(ddName.toUpperCase(), physicalPath);
    }
    
    public static String getDdAssignment(String ddName) {
        return ddAssignments.get().get(ddName.toUpperCase());
    }
    
    public static void setSysinData(String ddName, String data) {
        sysinData.get().put(ddName.toUpperCase(), data);
    }
    
    public static String getSysinData(String ddName) {
        return sysinData.get().get(ddName.toUpperCase());
    }
    
    public static void setStepReturnCode(String stepName, int rc) {
        stepReturnCodes.get().put(stepName.toUpperCase(), rc);
    }
    
    public static Integer getStepReturnCode(String stepName) {
        return stepReturnCodes.get().getOrDefault(stepName.toUpperCase(), 0);
    }
    
    public static boolean checkAnyStepCond(int code, String op) {
        for (int rc : stepReturnCodes.get().values()) {
            if (compareRc(code, op, rc)) {
                return true;
            }
        }
        return false;
    }
    
    public static boolean compareRc(int code, String op, int rc) {
        switch (op.toUpperCase()) {
            case "EQ": return code == rc;
            case "NE": return code != rc;
            case "GT": return code > rc;
            case "LT": return code < rc;
            case "GE": return code >= rc;
            case "LE": return code <= rc;
            default: return false;
        }
    }
    
    public static void clear() {
        ddAssignments.get().clear();
        sysinData.get().clear();
        stepReturnCodes.get().clear();
    }
}
"""
        with open(os.path.join(jcl_context_dir, "JclExecutionContext.java"), "w", encoding="utf-8") as f:
            f.write(jcl_context_src)
            
        subprocess.run(
            ["javac", os.path.join(jcl_context_dir, "JclExecutionContext.java")],
            capture_output=True,
            text=True,
            timeout=180
        )
        
         # Write and compile CobolFormatHelper.java to prevent compilation failures for programs with complex PICTURE editing
        format_helper_src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "modernize", "java_helpers", "CobolFormatHelper.java"), "r", encoding="utf-8").read()
        with open(os.path.join(jcl_context_dir, "CobolFormatHelper.java"), "w", encoding="utf-8") as f:
            f.write(format_helper_src)
            
        subprocess.run(
            ["javac", os.path.join(jcl_context_dir, "CobolFormatHelper.java")],
            capture_output=True,
            text=True,
            timeout=180
        )

        # Write and compile CobolNumeric helpers
        runtime_dir = os.path.join(temp_dir, "com", "systema", "modernized", "runtime")
        os.makedirs(runtime_dir, exist_ok=True)
        helpers_src_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "modernize", "java_helpers", "src", "main", "java", "com", "systema", "modernized", "runtime")
        
        for f_name in os.listdir(helpers_src_dir):
            if f_name.endswith(".java"):
                path = os.path.join(helpers_src_dir, f_name)
                with open(path, "r", encoding="utf-8") as f:
                    src = f.read()
                with open(os.path.join(runtime_dir, f_name), "w", encoding="utf-8") as f:
                    f.write(src)
        
        # Compile all java files in runtime directory
        java_files = [os.path.join(runtime_dir, f) for f in os.listdir(runtime_dir) if f.endswith(".java")]
        subprocess.run(
            ["javac", "-cp", temp_dir] + java_files,
            capture_output=True,
            text=True,
            timeout=180
        )

        # Write and compile CicsProgramRegistry.java
        registry_src = """package com.systema.modernized;
import java.util.HashMap;
import java.util.Map;
import java.util.function.Supplier;
public class CicsProgramRegistry {
    private static final Map<String, Supplier<Object>> registry = new HashMap<>();
    public static void register(String name, Supplier<Object> supplier) {
        registry.put(name.toUpperCase(), supplier);
    }
    public static Object invoke(String name, String commarea) throws Exception {
        Supplier<Object> supplier = registry.get(name.toUpperCase());
        if (supplier == null) {
            throw new IllegalArgumentException("CICS_INVALID_PROGRAM: Program " + name + " not registered in CICS registry");
        }
        Object program = supplier.get();
        try {
            java.lang.reflect.Field field = program.getClass().getField("commarea");
            field.set(program, commarea);
        } catch (NoSuchFieldException e) {}
        program.getClass().getMethod("execute").invoke(program);
        try {
            java.lang.reflect.Field field = program.getClass().getField("commarea");
            return field.get(program);
        } catch (NoSuchFieldException e) {
            return commarea;
        }
    }
}
"""
        with open(os.path.join(jcl_context_dir, "CicsProgramRegistry.java"), "w", encoding="utf-8") as f:
            f.write(registry_src)
            
        subprocess.run(
            ["javac", os.path.join(jcl_context_dir, "CicsProgramRegistry.java")],
            capture_output=True,
            text=True,
            timeout=180
        )

        # Write and compile SpringContextHelper.java
        spring_helper_src = """package com.systema.modernized;
public class SpringContextHelper {
    public static class MockResultSet {
        public String getString(String columnLabel) throws Exception { return null; }
        public String getString(int columnIndex) throws Exception { return null; }
    }
    public interface MockRowMapper<T> {
        T mapRow(MockResultSet rs, int rowNum) throws Exception;
    }
    public static class MockJdbcTemplate {
        public <T> java.util.List<T> query(String sql, MockRowMapper<T> rowMapper, Object... args) { return null; }
        public void execute(String sql) {}
        public int update(String sql, Object... args) { return 0; }
        public <T> T queryForObject(String sql, Class<T> requiredType, Object... args) { return null; }
    }
    public static MockJdbcTemplate jdbcTemplate = null;
}
"""
        with open(os.path.join(jcl_context_dir, "SpringContextHelper.java"), "w", encoding="utf-8") as f:
            f.write(spring_helper_src)
            
        subprocess.run(
            ["javac", os.path.join(jcl_context_dir, "SpringContextHelper.java")],
            capture_output=True,
            text=True,
            timeout=180
        )
        
        # Write input files if any
        if input_files:
            for k, v in input_files.items():
                p = os.path.join(temp_dir, k)
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "w", encoding="utf-8") as f:
                    f.write(v)
                    
        # Adjust assignments in generated Java to refer to absolute paths in temp_dir
        adjusted_java_source = java_source
        if hasattr(gen, "file_assigns") and gen.file_assigns:
            for assign in gen.file_assigns:
                k = assign.get("physical_path") or assign.get("assign_path")
                if k:
                    abs_p = os.path.abspath(os.path.join(temp_dir, k)).replace("\\", "/")
                    adjusted_java_source = adjusted_java_source.replace(f'"{k}"', f'"{abs_p}"')
            
        src_file = os.path.join(pkg_dir, f"{program_name.capitalize()}.java")
        with open(src_file, "w", encoding="utf-8") as f:
            f.write(adjusted_java_source)
            
        # Compile Java class
        helpers_path = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "modernize", "java_helpers", "src", "main", "java"))
        compile_res = subprocess.run(
            ["javac", "-cp", f"{temp_dir}{os.pathsep}{helpers_path}", "-d", temp_dir, src_file],
            capture_output=True,
            text=True,
            timeout=180
        )
        if compile_res.returncode != 0:
            raise RuntimeError(f"Java compilation failed:\n{compile_res.stderr}\nSource:\n{adjusted_java_source}")
            
        # Execute Java program
        run_res = subprocess.run(
            ["java", "-cp", temp_dir, f"com.systema.modernized.native_gen.{program_name.capitalize()}"],
            capture_output=True,
            text=True,
            timeout=180
        )
        
        if return_full:
            # Read output files
            outputs = {}
            for root, _, files in os.walk(temp_dir):
                for file in files:
                    if not file.endswith(".class") and not file.endswith(".java") and file not in (input_files or {}):
                        rel_p = os.path.relpath(os.path.join(root, file), temp_dir).replace("\\", "/")
                        with open(os.path.join(root, file), "r", encoding="utf-8") as f:
                            outputs[rel_p] = f.read()
            return run_res.returncode, run_res.stdout, run_res.stderr, adjusted_java_source, outputs
        else:
            return run_res.returncode, run_res.stdout.strip().splitlines()
    finally:
        import time
        for _ in range(5):
            try:
                shutil.rmtree(temp_dir)
                break
            except Exception:
                time.sleep(0.1)
