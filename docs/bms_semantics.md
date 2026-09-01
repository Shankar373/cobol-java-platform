# BMS (Basic Mapping Support) Screen Modernization Semantics

## 1. Overview

BMS screen definition macros (`DFHMSD`, `DFHMDI`, `DFHMDF`) define 3270 character-mode terminal screens. Modernization converts these into:
1. Typed Java Screen Data Transfer Objects (DTOs) with getter/setter methods, `toMap()`, `fromMap()`, and field metadata.
2. JSON representation of map definitions and coordinate metadata.
3. Accessible modern HTML screen templates.

---

## 2. Supported BMS Macro Options

| Macro | Supported Parameters | Modernized Mapping |
| :--- | :--- | :--- |
| **`DFHMSD`** | `TYPE`, `MODE`, `STORAGE`, `CTRL`, `LANG`, `TIOAPFX` | Mapset metadata container |
| **`DFHMDI`** | `SIZE=(rows, cols)`, `LINE`, `COLUMN`, `CTRL`, `DATA` | Map grid container (e.g. 24x80) |
| **`DFHMDF`** | `POS=(r, c)`, `LENGTH=n`, `ATTRB=(options)`, `INITIAL='val'`, `COLOR=col`, `HILIGHT=hi`, `PICIN`, `PICOUT`, `JUSTIFY` | Typed DTO field with attributes |

---

## 3. Field Attributes Mapping

- **`ATTRB=(PROT)`**: Protected/read-only field.
- **`ATTRB=(UNPROT)`**: Unprotected editable input field.
- **`ATTRB=(NUM)`**: Numeric input constraint.
- **`ATTRB=(DRK)`**: Hidden/password field.
- **`ATTRB=(BRT)`**: Highlighted/bold visual attribute.
- **`COLOR=(BLUE/RED/GREEN/NEUTRAL/TURQUOISE/YELLOW/PINK)`**: CSS text coloring.
- **`HILIGHT=(BLINK/REVERSE/UNDERLINE)`**: Modern typography decorators.
