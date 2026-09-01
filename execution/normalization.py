import re

class NormalizationRules:
    def __init__(self, rules_list: list = None):
        self.rules_list = rules_list or []  # List of dicts with keys: pattern, artifact, field, reason, scope

    def normalize(self, content: str, artifact: str, applied_logs: list) -> str:
        """Apply matching regex rules and append to applied_logs list for auditable reporting."""
        normalized_content = content
        for rule in self.rules_list:
            rule_art = rule.get("artifact", "*")
            if rule_art != "*" and rule_art != artifact:
                continue
            
            pattern_str = rule.get("pattern", "")
            if not pattern_str:
                continue

            try:
                pattern = re.compile(pattern_str)
            except re.error:
                continue

            # Find all matches before replacing
            for match in pattern.finditer(normalized_content):
                orig_val = match.group(0)
                norm_val = rule.get("replacement", "[NORMALIZED]")
                
                # Check if already logged to avoid duplicates
                log_entry = {
                    "pattern": pattern_str,
                    "artifact": artifact,
                    "field": rule.get("field", ""),
                    "reason": rule.get("reason", "nondeterministic content"),
                    "scope": rule.get("scope", "global"),
                    "original_value": orig_val,
                    "normalized_value": norm_val
                }
                if log_entry not in applied_logs:
                    applied_logs.append(log_entry)

            normalized_content = pattern.sub(rule.get("replacement", "[NORMALIZED]"), normalized_content)

        return normalized_content
