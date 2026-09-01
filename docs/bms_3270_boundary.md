# BMS / 3270 Screen Boundary Specification
## Macro Parsing, Attribute Handling & Terminal Subsystem Classification

---

## 1. Scope & Execution Principles

Basic Mapping Support (BMS) defines 3270 character-mode screen layouts on IBM mainframes.

### 1.1 Supported BMS Macros
- **`DFHMSD`** (Mapset Definition): `TYPE=&SYSPARM`, `MODE=INOUT`, `LANG=COBOL`, `STORAGE=AUTO`, `CTRL=(FREEKB,FRSET,ALARM)`, `TERM=3270`.
- **`DFHMDI`** (Map Definition): `SIZE=(24,80)`, `LINE=1`, `COLUMN=1`, `CTRL=(FREEKB,ERASE)`.
- **`DFHMDF`** (Field Definition): `POS=(row,col)`, `LENGTH=n`, `INITIAL='...'`, `ATTRB=(ASKIP,PROT,UNPROT,NUM,BRT,NORM,DRK,FSET)`, `COLOR=GREEN/BLUE/RED/YELLOW`, `HILIGHT=UNDERLINE/BLINK/REVERSE`, `PICIN='...'`, `PICOUT='...'`, `JUSTIFY=RIGHT`.

---

## 2. Java DTO Generation

Each BMS map compiles into a Java Data Transfer Object (DTO):
- Input DTO (`*InDTO.java`): Fields marked with length and input values.
- Output DTO (`*OutDTO.java`): Fields marked with display values and attribute flags.

---

## 3. Boundary & Classification

- **BMS Macro Parsing & DTO Generation**: `COMPATIBILITY_PROVEN`
- **SEND MAP / RECEIVE MAP Procedural Flow**: `COMPATIBILITY_PROVEN`
- **Real IBM 3270 Terminal / SNA Hardware**: `UNPROVEN`
