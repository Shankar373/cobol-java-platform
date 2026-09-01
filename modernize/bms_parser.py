import re
from typing import Dict, List, Optional, Tuple

class BmsField:
    def __init__(
        self,
        name: str,
        pos: Tuple[int, int],
        length: int,
        initial: Optional[str] = None,
        attrb: Optional[List[str]] = None,
        color: Optional[str] = None,
        hilight: Optional[str] = None,
        picin: Optional[str] = None,
        picout: Optional[str] = None,
        justify: Optional[str] = None
    ):
        self.name = name
        self.pos = pos  # (row, col)
        self.length = length
        self.initial = initial
        self.attrb = attrb or []
        self.color = color
        self.hilight = hilight
        self.picin = picin
        self.picout = picout
        self.justify = justify

    def is_protected(self) -> bool:
        return any(a in ("PROT", "ASKIP") for a in self.attrb)

    def is_numeric(self) -> bool:
        return "NUM" in self.attrb

    def is_modified(self) -> bool:
        return "FSET" in self.attrb

    def to_dict(self):
        return {
            "name": self.name,
            "pos": self.pos,
            "length": self.length,
            "initial": self.initial,
            "attrb": self.attrb,
            "color": self.color,
            "hilight": self.hilight,
            "picin": self.picin,
            "picout": self.picout,
            "justify": self.justify,
            "protected": self.is_protected(),
            "numeric": self.is_numeric()
        }

class BmsMap:
    def __init__(self, name: str, size: Tuple[int, int] = (24, 80), ctrl: Optional[List[str]] = None, line: int = 1, column: int = 1):
        self.name = name
        self.size = size  # (rows, cols)
        self.ctrl = ctrl or []
        self.line = line
        self.column = column
        self.fields: List[BmsField] = []

    def to_dict(self):
        return {
            "name": self.name,
            "size": self.size,
            "ctrl": self.ctrl,
            "line": self.line,
            "column": self.column,
            "fields": [f.to_dict() for f in self.fields]
        }

class BmsMapset:
    def __init__(
        self,
        name: str,
        mode: str = "INOUT",
        lang: str = "COBOL",
        storage: str = "AUTO",
        ctrl: Optional[List[str]] = None,
        term: str = "3270",
        mapatts: Optional[List[str]] = None,
        dsatts: Optional[List[str]] = None
    ):
        self.name = name
        self.mode = mode
        self.lang = lang
        self.storage = storage
        self.ctrl = ctrl or []
        self.term = term
        self.mapatts = mapatts or []
        self.dsatts = dsatts or []
        self.maps: List[BmsMap] = []

    def to_dict(self):
        return {
            "name": self.name,
            "mode": self.mode,
            "lang": self.lang,
            "storage": self.storage,
            "ctrl": self.ctrl,
            "term": self.term,
            "mapatts": self.mapatts,
            "dsatts": self.dsatts,
            "maps": [m.to_dict() for m in self.maps]
        }

class BmsParser:
    def __init__(self, content: str):
        self.content = content

    def parse(self) -> BmsMapset:
        # Pre-process lines to join continuation lines
        raw_lines = self.content.splitlines()
        joined_lines = []
        i = 0
        n = len(raw_lines)
        
        while i < n:
            line = raw_lines[i]
            # Strip trailing comments if they are separated by spaces or * in column 72
            # Mainframe JCL/BMS rules: if column 72 (1-indexed, i.e., index 71) has a non-blank character,
            # it indicates continuation.
            is_continued = False
            if len(line) >= 72:
                col72 = line[71]
                if col72 != ' ' and col72 != '\n':
                    is_continued = True
                    line = line[:71]
            
            stripped = line.rstrip()
            if is_continued or stripped.endswith(','):
                # Consume next line and join
                while i + 1 < n:
                    next_line = raw_lines[i+1]
                    next_continued = False
                    if len(next_line) >= 72:
                        next_col72 = next_line[71]
                        if next_col72 != ' ' and next_col72 != '\n':
                            next_continued = True
                            next_line = next_line[:71]
                    
                    line += " " + next_line.strip()
                    i += 1
                    if not next_continued and not next_line.rstrip().endswith(','):
                        break
            joined_lines.append(line)
            i += 1

        mapset = BmsMapset("UNNAMED")
        current_map = None

        for line in joined_lines:
            if not line or line.startswith('*'):
                continue
                
            stripped = line.strip()
            if not stripped:
                continue

            # Standard pattern: LABEL TYPE PARAMETERS
            # If line starts with whitespace, label is empty ""
            if line[0].isspace():
                parts = stripped.split(None, 1)
                label = ""
                macro_type = parts[0].upper() if len(parts) > 0 else ""
                params_str = parts[1] if len(parts) > 1 else ""
            else:
                parts = stripped.split(None, 2)
                label = parts[0]
                macro_type = parts[1].upper() if len(parts) > 1 else ""
                params_str = parts[2] if len(parts) > 2 else ""

            if macro_type == "DFHMSD":
                if label and label.upper() != "DFHMSD":
                    mapset.name = label
                mapset.mode = self._parse_param(params_str, "MODE") or mapset.mode
                mapset.lang = self._parse_param(params_str, "LANG") or mapset.lang
                mapset.storage = self._parse_param(params_str, "STORAGE") or mapset.storage
                mapset.term = self._parse_param(params_str, "TERM") or mapset.term
                mapset.ctrl = self._parse_list_param(params_str, "CTRL") or mapset.ctrl
            elif macro_type == "DFHMDI":
                size = self._parse_size(params_str)
                ctrl = self._parse_list_param(params_str, "CTRL")
                current_map = BmsMap(label, size, ctrl=ctrl)
                mapset.maps.append(current_map)
            elif macro_type == "DFHMDF":
                if current_map is not None:
                    field = self._parse_field(label, params_str)
                    if field:
                        current_map.fields.append(field)

        return mapset

    def _parse_size(self, params_str: str) -> Tuple[int, int]:
        m = re.search(r'SIZE\s*=\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)', params_str, re.IGNORECASE)
        if m:
            return (int(m.group(1)), int(m.group(2)))
        return (24, 80)

    def _parse_param(self, params_str: str, param_name: str) -> Optional[str]:
        m = re.search(rf'{param_name}\s*=\s*[\'"]?([A-Za-z0-9_&]+)[\'"]?', params_str, re.IGNORECASE)
        if m:
            return m.group(1).upper()
        return None

    def _parse_list_param(self, params_str: str, param_name: str) -> List[str]:
        m = re.search(rf'{param_name}\s*=\s*\(\s*([^\)]+)\s*\)', params_str, re.IGNORECASE)
        if m:
            return [x.strip().upper() for x in m.group(1).split(',')]
        m_single = re.search(rf'{param_name}\s*=\s*([A-Za-z0-9_]+)', params_str, re.IGNORECASE)
        if m_single:
            return [m_single.group(1).upper()]
        return []

    def _parse_field(self, label: str, params_str: str) -> BmsField:
        # Find POS=(row,col)
        pos = (1, 1)
        m_pos = re.search(r'POS\s*=\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)', params_str, re.IGNORECASE)
        if m_pos:
            pos = (int(m_pos.group(1)), int(m_pos.group(2)))
            
        # Find LENGTH
        length = 1
        m_len = re.search(r'LENGTH\s*=\s*(\d+)', params_str, re.IGNORECASE)
        if m_len:
            length = int(m_len.group(1))
            
        # Find INITIAL
        initial = None
        m_init = re.search(r'INITIAL\s*=\s*[\'"]([^\'"]*)[\'"]', params_str, re.IGNORECASE)
        if m_init:
            initial = m_init.group(1)
            
        # Find ATTRB
        attrb = self._parse_list_param(params_str, "ATTRB")
        color = self._parse_param(params_str, "COLOR")
        hilight = self._parse_param(params_str, "HILIGHT")
        picin = self._parse_param(params_str, "PICIN")
        picout = self._parse_param(params_str, "PICOUT")
        justify = self._parse_param(params_str, "JUSTIFY")

        # If label is DFHMDF or empty, field is unnamed
        name = label if label.upper() != "DFHMDF" else ""
        return BmsField(name, pos, length, initial, attrb, color, hilight, picin, picout, justify)


def generate_bms_java_dto(mapset: BmsMapset) -> Dict[str, str]:
    """Generates Java DTO classes for each map in a BMS mapset."""
    classes = {}
    mapset_clean = mapset.name.replace("-", "_").upper()
    
    for bms_map in mapset.maps:
        map_clean = bms_map.name.replace("-", "_").upper()
        class_name = f"{mapset_clean.capitalize()}_{map_clean.capitalize()}Dto"
        
        lines = []
        lines.append("package com.systema.modernized.bms;")
        lines.append("")
        lines.append("import java.util.HashMap;")
        lines.append("import java.util.Map;")
        lines.append("")
        lines.append(f"public class {class_name} {{")
        lines.append(f"    public static final String MAPSET = \"{mapset.name}\";")
        lines.append(f"    public static final String MAP = \"{bms_map.name}\";")
        lines.append(f"    public static final int ROWS = {bms_map.size[0]};")
        lines.append(f"    public static final int COLS = {bms_map.size[1]};")
        lines.append("")
        
        # Field members
        named_fields = [f for f in bms_map.fields if f.name]
        for f in named_fields:
            field_clean = f.name.replace("-", "_").lower()
            init_val = f'"{f.initial}"' if f.initial is not None else '""'
            lines.append(f"    private String {field_clean} = {init_val};")
        
        lines.append("")
        # Getters and setters
        for f in named_fields:
            field_clean = f.name.replace("-", "_").lower()
            cap = field_clean.capitalize()
            lines.append(f"    public String get{cap}() {{ return this.{field_clean}; }}")
            lines.append(f"    public void set{cap}(String val) {{ this.{field_clean} = val != null ? val : \"\"; }}")
        
        lines.append("")
        # toMap and fromMap
        lines.append("    public Map<String, Object> toMap() {")
        lines.append("        Map<String, Object> map = new HashMap<>();")
        for f in named_fields:
            field_clean = f.name.replace("-", "_").lower()
            lines.append(f"        map.put(\"{f.name.upper()}\", this.{field_clean});")
        lines.append("        return map;")
        lines.append("    }")
        lines.append("")
        lines.append(f"    public static {class_name} fromMap(Map<String, Object> map) {{")
        lines.append(f"        {class_name} dto = new {class_name}();")
        lines.append("        if (map == null) return dto;")
        for f in named_fields:
            field_clean = f.name.replace("-", "_").lower()
            cap = field_clean.capitalize()
            lines.append(f"        if (map.containsKey(\"{f.name.upper()}\")) {{")
            lines.append(f"            dto.set{cap}(String.valueOf(map.get(\"{f.name.upper()}\")));")
            lines.append("        }")
        lines.append("        return dto;")
        lines.append("    }")
        
        lines.append("}")
        classes[class_name] = "\n".join(lines)
        
    return classes
