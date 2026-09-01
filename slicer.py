import re
import os
import sys

COBOL_KEYWORDS = {
    "MOVE", "TO", "ADD", "SUBTRACT", "COMPUTE", "IF", "ELSE", "PERFORM", "DISPLAY", 
    "GOBACK", "EXIT", "THRU", "UNTIL", "VARYING", "WITH", "TEST", "BEFORE", "AFTER",
    "IN", "OF", "BY", "INITIALIZE", "READ", "WRITE", "OPEN", "CLOSE", "NOT", "EQUAL",
    "GREATER", "THAN", "LESS", "AND", "OR", "ON", "SIZE", "ERROR", "SECTION", "STOP",
    "SPACES", "SPACE", "ZERO", "ZEROS", "ZEROES", "HIGH-VALUE", "HIGH-VALUES", "LOW-VALUE", "LOW-VALUES",
    "END-IF", "END-PERFORM", "END-READ", "END-WRITE", "END-EVALUATE", "EVALUATE", "WHEN", "TRUE", "FALSE"
}

class ParagraphSlicer:
    """Enterprise-grade paragraph slicing engine.
    Extracts a COBOL paragraph/section and wraps it as a valid standalone sub-program.
    """
    def __init__(self, source_path: str):
        self.source_path = source_path
        if not os.path.isfile(source_path):
            raise FileNotFoundError(f"Source file not found: {source_path}")
        with open(source_path, "r", encoding="utf-8", errors="replace") as fh:
            self.content = fh.read()

    def extract_variables_used(self, paragraph_text: str) -> list:
        """Find all variables referenced inside the paragraph in sequence of appearance."""
        # Clean comment lines out of text to avoid capturing commented variable names
        lines = [l for l in paragraph_text.splitlines() if not l.strip().startswith("*>") and not (len(l) > 6 and l[6] in ("*", "/"))]
        cleaned_text = "\n".join(lines)
        
        # Strip literal strings in double/single quotes to avoid capturing string content as variables
        cleaned_text = re.sub(r'"[^"]*"|\'[^\']*\'', "", cleaned_text)
        
        # Match standard alphanumeric COBOL identifiers (letters, numbers, hyphens)
        candidates = re.findall(r'\b([A-Za-z0-9\-]+)\b', cleaned_text)
        
        # Find defined paragraph names in source file to filter them out of the parameter list (case-insensitive)
        para_names = {x.upper() for x in re.findall(r'^\s*([A-Za-z0-9\-]+)\s*\.', self.content, re.MULTILINE)}
        
        seen = set()
        used = []
        for c in candidates:
            c_upper = c.upper()
            if c_upper.isdigit() or c_upper in COBOL_KEYWORDS or len(c_upper) <= 1:
                continue
            if c_upper in para_names:
                continue
            if c_upper not in seen:
                seen.add(c_upper)
                used.append(c_upper)
        return used

    def get_variables_from_copybook(self, copybook_path: str) -> set:
        """Read copybook file and extract all defined variables."""
        # Normalize quotes and resolve paths
        cb_name = copybook_path.replace('"', '').replace("'", "").strip()
        search_paths = [
            cb_name,
            os.path.join(os.path.dirname(self.source_path), cb_name),
            os.path.join(os.path.dirname(self.source_path), "copybooks", os.path.basename(cb_name)),
            os.path.join(os.path.dirname(self.source_path), "..", cb_name)
        ]
        content = ""
        for p in search_paths:
            if os.path.isfile(p):
                try:
                    with open(p, "r", encoding="utf-8", errors="replace") as fh:
                        content = fh.read()
                        break
                except OSError:
                    pass
        if not content:
            return set()
            
        lines = content.splitlines()
        vars_found = set()
        for line in lines:
            if line.strip().startswith("*>") or (len(line) > 6 and line[6] in ("*", "/")):
                continue
            m = re.match(r'^\s*(\d{2})\s+([A-Za-z0-9\-]+)', line)
            if m:
                vars_found.add(m.group(2).upper())
        return vars_found

    def find_variable_definitions(self, variables: list) -> list:
        """Locate level definitions (01, 05, etc.) for the target variables in WORKING-STORAGE."""
        lines = self.content.splitlines()
        definitions = []
        
        # Standard COBOL variable patterns: level variable-name
        # e.g., "       05  WS-CLAIM-COUNT   PIC 9(4) VALUE 0."
        for var in variables:
            found = False
            for line in lines:
                # Skip comments
                if line.strip().startswith("*>") or (len(line) > 6 and line[6] in ("*", "/")):
                    continue
                # Match variable definition
                m = re.search(r'^\s*(\d{2})\s+(' + re.escape(var) + r')\b', line, re.IGNORECASE)
                if m:
                    definitions.append(line)
                    found = True
                    break
            # If not defined as a standard level but referenced, note it
            if not found:
                # Generate a generic fallback PIC X(50) definition to preserve compilability
                definitions.append(f"       77  {var} PIC X(50).")
        return definitions

    def extract_file_declarations(self, file_name: str) -> tuple:
        """Find the SELECT and FD statements for the referenced file."""
        lines = self.content.splitlines()
        select_block = []
        fd_block = []
        
        # 1. Find SELECT statement (usually a single line or spans across continuation lines)
        in_select = False
        for line in lines:
            stripped = line.strip().upper()
            if stripped.startswith("SELECT ") and file_name.upper() in stripped:
                in_select = True
            if in_select:
                select_block.append(line)
                if line.endswith(".") or (len(line) > 6 and line.rstrip().endswith(".")):
                    in_select = False
                    
        # 2. Find FD block
        in_fd = False
        for line in lines:
            stripped = line.strip().upper()
            if stripped.startswith("FD ") and file_name.upper() in stripped:
                in_fd = True
            elif in_fd and (stripped.startswith("FD ") or stripped.startswith("WORKING-STORAGE") or stripped.startswith("PROCEDURE DIVISION")):
                in_fd = False
            if in_fd:
                fd_block.append(line)
                
        return select_block, fd_block

    def slice_paragraph(self, target_paragraph: str, output_path: str) -> bool:
        """Slice target paragraph out of source and assemble a valid sub-program."""
        lines = self.content.splitlines()
        sliced_lines = []
        capturing = False
        target_found = False
        
        # We look for the start paragraph/section line
        # e.g. "PROCESS-CLAIM." or "PROCESS-CLAIM SECTION."
        for line in lines:
            # Skip comments during start detection
            if line.strip().startswith("*>") or (len(line) > 6 and line[6] in ("*", "/")):
                if capturing:
                    sliced_lines.append(line)
                continue
                
            stripped = line.strip().upper()
            # Match start paragraph header
            if not capturing:
                if re.match(r'^' + re.escape(target_paragraph.upper()) + r'\s*\.\s*$', stripped) or \
                   re.match(r'^' + re.escape(target_paragraph.upper()) + r'\s+SECTION\s*\.\s*$', stripped):
                    capturing = True
                    target_found = True
                    sliced_lines.append(line)
            else:
                # Stop if we hit a new paragraph or section header at start of line content
                lead_space_len = len(line) - len(line.lstrip())
                if lead_space_len < 12 and re.match(r'^[A-Za-z0-9\-]+\s*\.', stripped):
                    # Filter out standard keywords like END-IF
                    m_word = re.match(r'^([A-Za-z0-9\-]+)', stripped)
                    if m_word and m_word.group(1) not in COBOL_KEYWORDS:
                        break
                if lead_space_len < 12 and " SECTION" in stripped:
                    break
                sliced_lines.append(line)
                
        if not target_found or not sliced_lines:
            return False
            
        p_text = "\n".join(sliced_lines)
        
        # Identify referenced files (e.g. READ POLICY-MASTER)
        referenced_files = set()
        for f_name in re.findall(r'(?i)\b(?:READ|WRITE|OPEN|CLOSE)\s+([A-Za-z0-9\-]+)', p_text):
            referenced_files.add(f_name.upper())
            
        # Pull SELECT and FD declarations for referenced files
        select_lines = []
        fd_lines = []
        fd_variables = set()
        for f in referenced_files:
            sel, fd = self.extract_file_declarations(f)
            select_lines.extend(sel)
            fd_lines.extend(fd)
            # Scan FD block for any COPY statements to parse copybook variables
            for line in fd:
                m = re.search(r'(?i)\bCOPY\s+["\']?([A-Za-z0-9_\-./\\]+)["\']?', line)
                if m:
                    fd_variables.update(self.get_variables_from_copybook(m.group(1)))
            
        # Get raw variables and filter out file names and copybook variables from linkage args
        vars_used = [v for v in self.extract_variables_used(p_text) if v not in referenced_files and v not in fd_variables]
        defs = self.find_variable_definitions(vars_used)
            
        # Build clean LINKAGE SECTION
        linkage_lines = []
        if defs:
            linkage_lines.append("       LINKAGE SECTION.")
            for d in defs:
                linkage_lines.append(d)
                
        # Format a standard valid sub-program ID
        clean_name = re.sub(r'[^A-Z0-9]', '', target_paragraph.upper())[:8]
        if not clean_name:
            clean_name = "SUBPROG"
            
        sub_program = [
            "       IDENTIFICATION DIVISION.",
            f"       PROGRAM-ID. {clean_name}.",
            "       ENVIRONMENT DIVISION.",
        ]
        
        if select_lines:
            sub_program.append("       INPUT-OUTPUT SECTION.")
            sub_program.append("       FILE-CONTROL.")
            sub_program.extend(select_lines)
            
        sub_program.append("       DATA DIVISION.")
        if fd_lines:
            sub_program.append("       FILE SECTION.")
            sub_program.extend(fd_lines)
            
        if linkage_lines:
            sub_program.extend(linkage_lines)
            
        # Add procedure division using standard parameters
        vars_args = " ".join(vars_used)
        using_clause = f" USING {vars_args}" if vars_used else ""
        sub_program.append(f"       PROCEDURE DIVISION{using_clause}.")
        
        # Inject sliced body
        sub_program.extend(sliced_lines)
        
        # Generate stubs for PERFORM calls that are not the target paragraph
        perf_targets = set(re.findall(r'(?i)\bPERFORM\s+([A-Za-z0-9\-]+)', p_text))
        for p in sorted(perf_targets):
            if p.upper() != target_paragraph.upper() and not p.isdigit():
                sub_program.append(f"       {p.upper()}.")
                sub_program.append("           EXIT.")
                
        # Close the sub-program cleanly
        sub_program.append("           GOBACK.")
        
        # Write output file
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(sub_program) + "\n")
        return True

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python slicer.py <source_path> <paragraph_name> <output_path>")
        sys.exit(1)
    src_file, para, out_file = sys.argv[1], sys.argv[2], sys.argv[3]
    slicer = ParagraphSlicer(src_file)
    if slicer.slice_paragraph(para, out_file):
        print(f"Successfully sliced paragraph '{para}' to {out_file}")
        sys.exit(0)
    else:
        print(f"Error: Paragraph '{para}' not found or could not be sliced.")
        sys.exit(1)
