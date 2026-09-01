import os
import yaml

def generate_mock_cics_assets(yaml_path: str, generated_dir: str):
    """
    Parses mock_cics.yaml and generates MockCicsService.java.
    """
    if not os.path.exists(yaml_path):
        return

    with open(yaml_path, 'r', encoding='utf-8') as fh:
        config = yaml.safe_load(fh)

    scripted_responses = config.get('scripted_responses', [])
    eib_values = config.get('eib_values', {})

    lines = []
    lines.append("package com.systema.modernized;")
    lines.append("")
    lines.append("import java.util.HashMap;")
    lines.append("import java.util.Map;")
    lines.append("")
    lines.append("public class MockCicsService {")
    lines.append("    public static void initialize() {")

    # Add scripted responses
    for i, resp in enumerate(scripted_responses):
        trigger = resp.get('trigger', '')
        receive_fields = resp.get('receive_fields', {})
        
        var_name = f"resp{i}"
        lines.append(f"        Map<String, String> {var_name} = new HashMap<>();")
        for k, v in receive_fields.items():
            # Escape strings
            escaped_v = str(v).replace('"', '\\"')
            lines.append(f"        {var_name}.put(\"{k}\", \"{escaped_v}\");")
        lines.append(f"        CicsTransactionContext.addScriptedResponse(\"{trigger}\", {var_name});")
        lines.append("")

    # Add EIB values
    for k, v in eib_values.items():
        escaped_v = str(v).replace('"', '\\"')
        lines.append(f"        CicsTransactionContext.setEibValue(\"{k}\", \"{escaped_v}\");")

    lines.append("    }")
    lines.append("}")

    java_helpers_dir = os.path.join(generated_dir, "src", "main", "java", "com", "systema", "modernized")
    os.makedirs(java_helpers_dir, exist_ok=True)
    with open(os.path.join(java_helpers_dir, "MockCicsService.java"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
