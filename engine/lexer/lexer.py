"""
COBOL Lexer — engine/lexer/lexer.py

Tokenizes fixed-format and free-format COBOL source into CobolToken objects.
Handles:
  - Fixed-format column rules (cols 7-72 active area, continuation, comment)
  - Free-format COBOL (minimal column constraints)
  - COPY statement inline resolution
  - Source location tracking (file, line, column, byte offsets)

Refactored from cobol-java-modernization/modernize/lexer.py.
Original behaviour preserved; module interface cleaned.
"""
import os
import re

COBOL_KEYWORDS = {
    "IDENTIFICATION", "PROGRAM-ID", "ENVIRONMENT", "CONFIGURATION", "INPUT-OUTPUT", "FILE-CONTROL",
    "SELECT", "ASSIGN", "ORGANIZATION", "INDEXED", "ACCESS", "DYNAMIC", "RECORD", "KEY", "STATUS", "ALTERNATE",
    "DATA", "FILE", "FD", "WORKING-STORAGE", "LINKAGE", "PROCEDURE", "DIVISION", "SECTION",
    "MOVE", "TO", "ADD", "SUBTRACT", "MULTIPLY", "DIVIDE", "COMPUTE", "IF", "ELSE", "PERFORM", "THRU", "UNTIL",
    "DISPLAY", "GOBACK", "EXIT", "INITIALIZE", "READ", "WRITE", "REWRITE", "OPEN", "CLOSE",
    "STOP", "RUN", "COPY", "PIC", "PICTURE", "USAGE", "COMP", "COMP-3", "DISPLAY", "BINARY", "PACKED-DECIMAL",
    "REDEFINES", "OCCURS", "JUSTIFIED", "JUST", "VALUE", "VALUES", "WHEN", "TRUE", "FALSE", "EVALUATE",
    "END-IF", "END-PERFORM", "END-READ", "END-WRITE", "END-EVALUATE", "END-ADD", "END-SUBTRACT", "END-MULTIPLY", "END-DIVIDE", "END-COMPUTE", "NOT", "EQUAL", "GREATER", "THAN", "LESS",
    "AND", "OR", "ON", "SIZE", "ERROR", "DECLARATIVES", "END-DECLARATIVES", "RETURN", "VARYING", "CALL", "USING",
    "BY", "GIVING", "FROM", "INPUT", "OUTPUT", "STRING", "DELIMITED", "INTO", "I-O", "EXTEND", "AT", "END", "IN",
    "GO", "CONTINUE", "NEXT", "SENTENCE", "DEPENDING", "TIMES", "INVALID", "RANDOM", "MODE", "OVERFLOW", "FUNCTION",
    "UNSTRING", "INSPECT", "TALLYING", "REPLACING", "CONVERTING", "POINTER", "CHARACTERS", "FIRST", "END-UNSTRING",
    "ALL", "LEADING", "WITH", "FOR", "GLOBAL", "PROGRAM", "END-PROGRAM", "SD", "SORT", "MERGE", "RELEASE", "ASCENDING", "DESCENDING", "SET", "ADDRESS", "OF", "DUPLICATES",
    "REPORT", "REPORTS", "INITIATE", "GENERATE", "TERMINATE", "LINE", "COLUMN", "SOURCE", "SUM", "CONTROL", "RD",
    "DELETE", "START", "END-DELETE", "END-START", "IS", "REMAINDER", "ROUNDED",
    "SIGN", "TRAILING", "SEPARATE", "CHARACTER"
}

class CobolToken:
    def __init__(self, type_: str, value: str, file: str, line: int, column: int, start_offset: int, end_offset: int):
        self.type = type_
        self.value = value
        self.file = file
        self.line = line
        self.column = column
        self.start_offset = start_offset
        self.end_offset = end_offset

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "value": self.value,
            "source_location": {
                "file": self.file,
                "line": self.line,
                "column": self.column,
                "start_offset": self.start_offset,
                "end_offset": self.end_offset
            }
        }

    def __repr__(self):
        return f"Token({self.type}, {repr(self.value)}, line={self.line}, col={self.column})"


class CobolLexer:
    def __init__(self, file_path: str, format_mode: str = None):
        self.file_path = file_path
        self.format_mode = format_mode
        self.tokens = []
        self.unsupported = []

    def detect_format(self, text: str) -> str:
        fixed_signals = 0
        free_signals = 0
        for line in text.splitlines():
            if len(line) > 6 and line[6] in ("*", "/"):
                fixed_signals += 1
            elif "*>" in line:
                free_signals += 1
            elif len(line) > 72:
                free_signals += 1
        if fixed_signals > 2:
            return "fixed"
        return "fixed" if fixed_signals > free_signals else "free"

    def preprocess_copybooks(self, text: str) -> str:
        # Regex to match COPY statements (with or without quotes/dots/directories/extensions)
        pattern = re.compile(
            r'^\s*COPY\s+["\'\s]?([A-Za-z0-9\-\._/]+)["\'\s]?(?:\s*\.?)\s*$', 
            re.IGNORECASE
        )
        lines = text.splitlines()
        new_lines = []
        
        base_dir = "."
        if self.file_path:
            base_dir = os.path.dirname(os.path.abspath(self.file_path))
            
        for line in lines:
            # Check fixed format indicator first, just in case
            indicator = " "
            if self.format_mode == "fixed" and len(line) > 6:
                indicator = line[6]
            
            # If it's a comment, don't try to preprocess it as a COPY statement
            if indicator in ("*", "/"):
                new_lines.append(line)
                continue
                
            match = pattern.match(line)
            if match:
                cp_path = match.group(1)
                # Candidates search paths
                candidates = [
                    os.path.join(base_dir, cp_path),
                    os.path.join(base_dir, "copybooks", cp_path),
                    os.path.join(base_dir, "copybook", cp_path),
                ]
                
                cp_base = os.path.basename(cp_path)
                if "." in cp_base:
                    cp_name_only = cp_base.rsplit(".", 1)[0]
                else:
                    cp_name_only = cp_base
                
                for subdir in ("", "copybooks", "copybook", "..", "../copybooks", "../copybook"):
                    for ext in ("", ".cpy", ".cob", ".cbl"):
                        candidates.append(os.path.join(base_dir, subdir, cp_name_only + ext))
                        candidates.append(os.path.join(base_dir, subdir, cp_path + ext))
                
                cp_file = None
                for candidate in candidates:
                    norm_candidate = os.path.normpath(candidate)
                    if os.path.exists(norm_candidate) and os.path.isfile(norm_candidate):
                        cp_file = norm_candidate
                        break
                
                if cp_file:
                    try:
                        with open(cp_file, "r", encoding="utf-8") as fh:
                            cp_content = fh.read()
                        # Use sub_lexer to recursively preprocess
                        sub_lexer = CobolLexer(cp_file, format_mode=self.format_mode)
                        expanded = sub_lexer.preprocess_copybooks(cp_content)
                        new_lines.append(expanded)
                    except Exception:
                        new_lines.append(line)
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)
        return "\n".join(new_lines)

    def tokenize(self, text: str) -> list:
        # Resolve and expand COPY statements first
        text = self.preprocess_copybooks(text)
        if not self.format_mode:
            self.format_mode = self.detect_format(text)

        # Find all EXEC SQL blocks first in the full text
        sql_blocks = []
        for m in re.finditer(r'\bEXEC\s+SQL\b(.*?)\bEND-EXEC\.?', text, re.IGNORECASE | re.DOTALL):
            sql_blocks.append({
                "start": m.start(),
                "end": m.end(),
                "content": m.group(1).strip()
            })

        # Find all EXEC CICS blocks first in the full text
        cics_blocks = []
        for m in re.finditer(r'\bEXEC\s+CICS\b(.*?)\bEND-EXEC\.?', text, re.IGNORECASE | re.DOTALL):
            cics_blocks.append({
                "start": m.start(),
                "end": m.end(),
                "content": m.group(1).strip()
            })
            
        line_starts = [0]
        for i, char in enumerate(text):
            if char == '\n':
                line_starts.append(i + 1)
                
        def get_line_col(offset):
            for idx, start in enumerate(line_starts):
                if idx + 1 < len(line_starts):
                    if start <= offset < line_starts[idx + 1]:
                        return idx + 1, offset - start + 1
                else:
                    if start <= offset:
                        return idx + 1, offset - start + 1
            return 1, 1
            
        sql_ranges = [(b["start"], b["end"]) for b in sql_blocks]
        cics_ranges = [(b["start"], b["end"]) for b in cics_blocks]
        
        def is_in_sql_range(offset):
            for start, end in sql_ranges:
                if start <= offset < end:
                    return True
            return False

        def is_in_cics_range(offset):
            for start, end in cics_ranges:
                if start <= offset < end:
                    return True
            return False

        lines = text.splitlines()
        abs_offset = 0

        for idx, line in enumerate(lines):
            line_num = idx + 1
            line_len = len(line)
            
            # Handle Fixed Format line divisions
            if self.format_mode == "fixed":
                indicator = line[6] if line_len > 6 else " "
                
                # Comment line
                if indicator in ("*", "/"):
                    val = line[7:72] if line_len > 7 else ""
                    tok = CobolToken("COMMENT", val, self.file_path, line_num, 8, abs_offset + 7, abs_offset + min(line_len, 72))
                    self.tokens.append(tok)
                    abs_offset += line_len + 1
                    continue
                
                # Code content is columns 8-72
                code_segment = line[7:72] if line_len > 7 else ""
                code_start_col = 8
                code_offset = abs_offset + 7
                
                # Handle continuation indicator
                if indicator == "-":
                    # Check if last token was an unclosed or continued string literal
                    if self.tokens and self.tokens[-1].type == "LITERAL_STRING":
                        # Skip leading spaces to find opening quote
                        pos = 0
                        seg_len = len(code_segment)
                        while pos < seg_len and code_segment[pos].isspace():
                            pos += 1
                        
                        if pos < seg_len and code_segment[pos] in ('"', "'"):
                            quote = code_segment[pos]
                            pos += 1
                            val_chars = []
                            while pos < seg_len and code_segment[pos] != quote:
                                val_chars.append(code_segment[pos])
                                pos += 1
                            
                            self.tokens[-1].value += "".join(val_chars)
                            self.tokens[-1].end_offset = code_offset + pos
                            if pos < seg_len:
                                pos += 1  # consume closing quote
                            
                            # Tokenize the rest of the continuation line as normal
                            code_segment = code_segment[pos:]
                            code_offset += pos
                            code_start_col += pos
                        else:
                            # Standard string continuation without quote (fallback)
                            self.tokens[-1].value += code_segment.strip()
                            self.tokens[-1].end_offset = code_offset + len(code_segment)
                            abs_offset += line_len + 1
                            continue
                    
                    elif self.tokens and self.tokens[-1].type in ("IDENTIFIER", "KEYWORD"):
                        # Append to previous identifier
                        cleaned = code_segment.strip()
                        self.tokens[-1].value += cleaned
                        self.tokens[-1].end_offset = code_offset + len(code_segment)
                        # Re-classify keyword vs identifier
                        if self.tokens[-1].value.upper() in COBOL_KEYWORDS:
                            self.tokens[-1].type = "KEYWORD"
                        else:
                            self.tokens[-1].type = "IDENTIFIER"
                        
                        abs_offset += line_len + 1
                        continue

            else:
                # Free format line handling
                comment_idx = line.find("*>")
                if comment_idx != -1:
                    code_segment = line[:comment_idx]
                    comment_val = line[comment_idx+2:]
                else:
                    code_segment = line
                    comment_val = None
                code_start_col = 1
                code_offset = abs_offset

            # Tokenize code segment
            pos = 0
            seg_len = len(code_segment)
            
            while pos < seg_len:
                # Skip spaces first to align offsets
                while pos < seg_len and code_segment[pos].isspace():
                    pos += 1
                if pos >= seg_len:
                    break

                char_offset = code_offset + pos
                
                # Check if we hit the start of an SQL block
                sql_block_started = None
                for b in sql_blocks:
                    if b["start"] == char_offset:
                        sql_block_started = b
                        break
                
                if sql_block_started:
                    line, col = get_line_col(sql_block_started["start"])
                    tok = CobolToken(
                        "EXEC_SQL",
                        sql_block_started["content"],
                        self.file_path,
                        line,
                        col,
                        sql_block_started["start"],
                        sql_block_started["end"]
                    )
                    self.tokens.append(tok)
                    skip_len = sql_block_started["end"] - char_offset
                    pos += skip_len
                    continue

                # Check if we hit the start of a CICS block
                cics_block_started = None
                for b in cics_blocks:
                    if b["start"] == char_offset:
                        cics_block_started = b
                        break

                if cics_block_started:
                    line, col = get_line_col(cics_block_started["start"])
                    tok = CobolToken(
                        "EXEC_CICS",
                        cics_block_started["content"],
                        self.file_path,
                        line,
                        col,
                        cics_block_started["start"],
                        cics_block_started["end"]
                    )
                    self.tokens.append(tok)
                    skip_len = cics_block_started["end"] - char_offset
                    pos += skip_len
                    continue
                
                if is_in_sql_range(char_offset) or is_in_cics_range(char_offset):
                    pos += 1
                    continue
                
                char = code_segment[pos]
                tok_start_offset = code_offset + pos
                tok_col = code_start_col + pos
                
                # Check for string literal
                if char in ('"', "'"):
                    quote = char
                    val_chars = []
                    pos += 1
                    while pos < seg_len and code_segment[pos] != quote:
                        val_chars.append(code_segment[pos])
                        pos += 1
                    
                    if pos < seg_len:  # closing quote found
                        pos += 1
                        val = "".join(val_chars)
                        tok = CobolToken("LITERAL_STRING", val, self.file_path, line_num, tok_col, tok_start_offset, code_offset + pos)
                        self.tokens.append(tok)
                    else:
                        # unclosed string literal (might be continued on next line)
                        val = "".join(val_chars)
                        tok = CobolToken("LITERAL_STRING", val, self.file_path, line_num, tok_col, tok_start_offset, code_offset + pos)
                        self.tokens.append(tok)
                    continue

                # Check for operators / punctuation
                # Period must be a separate token if followed by space or end of segment
                if char == ".":
                    if pos + 1 >= seg_len or code_segment[pos+1].isspace():
                        tok = CobolToken("PUNCTUATION", ".", self.file_path, line_num, tok_col, tok_start_offset, tok_start_offset + 1)
                        self.tokens.append(tok)
                        pos += 1
                        continue

                # Exponentiation operator (**)
                if code_segment[pos:].startswith("**"):
                    tok = CobolToken("PUNCTUATION", "**", self.file_path, line_num, tok_col, tok_start_offset, tok_start_offset + 2)
                    self.tokens.append(tok)
                    pos += 2
                    continue

                # Comparison operators
                comp_match = re.match(r'^(<=|>=|<|>)', code_segment[pos:])
                if comp_match:
                    comp_val = comp_match.group(0)
                    tok = CobolToken("PUNCTUATION", comp_val, self.file_path, line_num, tok_col, tok_start_offset, tok_start_offset + len(comp_val))
                    self.tokens.append(tok)
                    pos += len(comp_val)
                    continue

                # Other punctuation
                is_signed_num = char in ("+", "-") and (pos + 1 < seg_len) and code_segment[pos+1].isdigit()
                if is_signed_num and self.tokens:
                    prev_type = self.tokens[-1].type
                    prev_val = self.tokens[-1].value
                    if prev_type in ("IDENTIFIER", "LITERAL_NUMBER") or (prev_type == "PUNCTUATION" and prev_val == ")"):
                        is_signed_num = False
                if not is_signed_num and char in (",", "(", ")", "+", "-", "=", "*", "/"):
                    tok = CobolToken("PUNCTUATION", char, self.file_path, line_num, tok_col, tok_start_offset, tok_start_offset + 1)
                    self.tokens.append(tok)
                    pos += 1
                    continue

                # Check for numeric literals
                num_match = re.match(r'^[+-]?\d+(\.\d+)?', code_segment[pos:])
                if num_match:
                    num_val = num_match.group(0)
                    # Exclude matching trailing period if it is a separator period (e.g. "100.")
                    if num_val.endswith(".") and (pos + len(num_val) >= seg_len or code_segment[pos + len(num_val)].isspace()):
                        num_val = num_val[:-1]
                    
                    tok = CobolToken("LITERAL_NUMBER", num_val, self.file_path, line_num, tok_col, tok_start_offset, tok_start_offset + len(num_val))
                    self.tokens.append(tok)
                    pos += len(num_val)
                    continue

                # Check for identifiers / keywords
                word_match = re.match(r'^[A-Za-z0-9\-]+', code_segment[pos:])
                if word_match:
                    word_val = word_match.group(0)
                    upper_word = word_val.upper()
                    if upper_word in COBOL_KEYWORDS:
                        tok = CobolToken("KEYWORD", word_val, self.file_path, line_num, tok_col, tok_start_offset, tok_start_offset + len(word_val))
                    else:
                        tok = CobolToken("IDENTIFIER", word_val, self.file_path, line_num, tok_col, tok_start_offset, tok_start_offset + len(word_val))
                    self.tokens.append(tok)
                    pos += len(word_val)
                    continue

                # Unrecognized character
                err_val = char
                tok = CobolToken("ERROR", err_val, self.file_path, line_num, tok_col, tok_start_offset, tok_start_offset + 1)
                self.tokens.append(tok)
                self.unsupported.append({
                    "char": err_val,
                    "line": line_num,
                    "col": tok_col,
                    "file": self.file_path
                })
                pos += 1

            # Emit line-end comments in free format if any
            if self.format_mode == "free" and comment_val is not None:
                tok = CobolToken("COMMENT", comment_val, self.file_path, line_num, code_start_col + comment_idx + 2, code_offset + comment_idx + 2, abs_offset + line_len)
                self.tokens.append(tok)

            abs_offset += line_len + 1

        return self.tokens

