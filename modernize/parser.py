import re
from .lexer import CobolToken
from .semantic_ir import SemanticIR, SemanticIRNode

class ParserDiagnostic(Exception):
    def __init__(self, message: str, file: str, line: int, column: int, token_value: str, context: str):
        super().__init__(f"{message} at line {line}, col {column} (token: {token_value})")
        self.message = message
        self.file = file
        self.line = line
        self.column = column
        self.token_value = token_value
        self.context = context

    def to_dict(self) -> dict:
        return {
            "type": "PARSER_SYNTAX_ERROR",
            "message": self.message,
            "source_location": {
                "file": self.file,
                "line": self.line,
                "column": self.column
            },
            "offending_token": self.token_value,
            "context": self.context
        }


def parse_picture_clause(pic_str: str):
    pic = pic_str.upper()
    signed = pic.startswith("S") or "+" in pic or "-" in pic or "CR" in pic or "DB" in pic
    if pic.startswith("S"):
        pic = pic[1:]
    
    expanded = []
    i = 0
    while i < len(pic):
        char = pic[i]
        if i + 1 < len(pic) and pic[i+1] == "(":
            end = pic.find(")", i + 1)
            if end != -1:
                try:
                    count = int(pic[i+2:end])
                    expanded.append(char * count)
                except ValueError:
                    expanded.append(char)
                i = end + 1
                continue
        expanded.append(char)
        i += 1
    
    expanded_str = "".join(expanded)
    
    is_edited = any(c in expanded_str for c in ("$", "Z", "*", ",", "CR", "DB")) or (expanded_str.count("+") > 1) or (expanded_str.count("-") > 1)
    
    digit_chars = "9Z*"
    if "V" in expanded_str:
        parts = expanded_str.split("V")
        digits = sum(1 for c in parts[0] if c in digit_chars) + sum(1 for c in parts[1] if c in digit_chars)
        scale = sum(1 for c in parts[1] if c in digit_chars)
    elif "." in expanded_str:
        parts = expanded_str.split(".")
        digits = sum(1 for c in parts[0] if c in digit_chars) + sum(1 for c in parts[1] if c in digit_chars)
        scale = sum(1 for c in parts[1] if c in digit_chars)
    else:
        digits = sum(1 for c in expanded_str if c in digit_chars)
        scale = 0
        
    for sym in ("$", "+", "-"):
        c = expanded_str.count(sym)
        if c > 1:
            digits += (c - 1)
            
    return signed, digits, scale, is_edited


COBOL_KEYWORDS = {
    "IDENTIFICATION", "PROGRAM-ID", "ENVIRONMENT", "CONFIGURATION", "INPUT-OUTPUT", "FILE-CONTROL",
    "SELECT", "ASSIGN", "ORGANIZATION", "INDEXED", "ACCESS", "DYNAMIC", "RECORD", "KEY", "STATUS",
    "DATA", "FILE", "FD", "WORKING-STORAGE", "LINKAGE", "PROCEDURE", "DIVISION", "SECTION",
    "MOVE", "TO", "ADD", "SUBTRACT", "MULTIPLY", "DIVIDE", "COMPUTE", "IF", "ELSE", "PERFORM", "THRU", "UNTIL",
    "DISPLAY", "GOBACK", "EXIT", "INITIALIZE", "READ", "WRITE", "REWRITE", "OPEN", "CLOSE",
    "STOP", "RUN", "COPY", "PIC", "PICTURE", "USAGE", "COMP", "COMP-3", "DISPLAY", "BINARY", "PACKED-DECIMAL",
    "REDEFINES", "OCCURS", "JUSTIFIED", "JUST", "VALUE", "VALUES", "WHEN", "TRUE", "FALSE", "EVALUATE",
    "END-IF", "END-PERFORM", "END-READ", "END-WRITE", "END-EVALUATE", "END-ADD", "END-SUBTRACT", "END-MULTIPLY", "END-DIVIDE", "END-COMPUTE", "NOT", "EQUAL", "GREATER", "THAN", "LESS",
    "AND", "OR", "ON", "SIZE", "ERROR", "DECLARATIVES", "END-DECLARATIVES", "RETURN", "VARYING", "CALL", "USING",
    "GO", "CONTINUE", "NEXT", "SENTENCE", "INVALID", "RANDOM", "MODE", "IN", "OVERFLOW",
    "UNSTRING", "INSPECT", "TALLYING", "REPLACING", "CONVERTING", "POINTER", "CHARACTERS", "FIRST", "END-UNSTRING",
    "ALL", "LEADING", "WITH", "FOR", "GLOBAL", "PROGRAM", "END-PROGRAM", "SD", "SORT", "MERGE", "RELEASE", "ASCENDING", "DESCENDING", "SET", "ADDRESS", "OF",
    "REPORT", "REPORTS", "INITIATE", "GENERATE", "TERMINATE", "LINE", "COLUMN", "SOURCE", "SUM", "CONTROL", "RD"
}


STATEMENT_START_VERBS = {
    "MOVE", "COMPUTE", "ADD", "SUBTRACT", "MULTIPLY", "DIVIDE", "PERFORM", "CALL", "READ", "WRITE", 
    "REWRITE", "OPEN", "CLOSE", "STOP", "GOBACK", "IF", "ELSE", "END-IF", "THEN", "END-ADD", "END-SUBTRACT", "END-MULTIPLY", "END-DIVIDE", "END-COMPUTE",
    "EVALUATE", "WHEN", "END-EVALUATE", "STRING", "END-READ",
    "DISPLAY", "INITIALIZE", "EXIT", "END-PERFORM", "GO", "CONTINUE", "NEXT",
    "UNSTRING", "INSPECT", "END-UNSTRING", "SORT", "MERGE", "RELEASE", "RETURN", "SET", "INITIATE", "GENERATE", "TERMINATE",
    "DELETE", "START", "END-DELETE", "END-START"
}

def is_tok_statement_start(tok) -> bool:
    if tok.type in ("EXEC_SQL", "EXEC_CICS"):
        return True
    return tok.type == "KEYWORD" and tok.value.upper() in STATEMENT_START_VERBS


class CobolParser:
    def __init__(self, tokens: list, file_path: str):
        self.tokens = [t for t in tokens if t.type != "COMMENT"]
        self.file_path = file_path
        self.current = 0
        self.diagnostics = []
        self.ir = SemanticIR()
        self.node_counter = 0
        self.block_stack = []
        self.active_programs = []
        self.current_program = None
        self.sentence_ended = False
        self.sentence_id = 0
        self.active_end_keywords = []

        # Intercept node addition to record sentence boundaries
        original_add_node = self.ir.add_node
        def custom_add_node(node):
            if node.kind == "STATEMENT" and "sentence_id" not in node.properties:
                node.properties["sentence_id"] = self.sentence_id
            if self.current_program and "program" not in node.properties:
                node.properties["program"] = self.current_program
            
            # Capability Matrix feature_id mapping
            if node.kind == "STATEMENT":
                stype = node.properties.get("statement_type", "").upper()
                feature_id = "UNKNOWN"
                if stype == "MOVE":
                    feature_id = "MOVE"
                elif stype == "IF":
                    feature_id = "COBOL.IF"
                elif stype == "EVALUATE":
                    feature_id = "COBOL.EVALUATE"
                elif stype == "PERFORM":
                    feature_id = "COBOL.PERFORM"
                elif stype == "CALL":
                    is_dyn = node.properties.get("call_type") == "dynamic"
                    feature_id = "COBOL.CALL_DYNAMIC" if is_dyn else "COBOL.CALL_STATIC"
                elif stype == "EXEC_SQL":
                    sql_props = node.properties.get("sql_props", {})
                    sql_type = sql_props.get("sql_type", "").upper()
                    if sql_type == "SELECT":
                        feature_id = "SQL.DB2.SELECT"
                    elif sql_type == "INSERT":
                        feature_id = "SQL.DB2.INSERT"
                    elif sql_type == "UPDATE":
                        feature_id = "SQL.DB2.UPDATE"
                    elif sql_type == "DELETE":
                        feature_id = "SQL.DB2.DELETE"
                    elif sql_type in ("DECLARE_CURSOR", "OPEN", "CLOSE", "FETCH"):
                        feature_id = "SQL.DB2.CURSOR"
                    elif sql_type in ("COMMIT", "ROLLBACK"):
                        feature_id = "SQL.DB2.TRANSACTION"
                    else:
                        feature_id = "SQL.DB2.SELECT"
                elif stype == "EXEC_CICS":
                    feature_id = "CICS." + node.properties.get("cics_command", "UNKNOWN").upper()
                else:
                    if stype in ("COMPUTE", "ADD", "SUBTRACT", "MULTIPLY", "DIVIDE"):
                        feature_id = "COBOL.COMP" if stype == "COMPUTE" else stype
                    elif stype in ("READ", "WRITE", "REWRITE", "DELETE", "START"):
                        feature_id = "FILE.SEQUENTIAL"
                    else:
                        feature_id = stype
                node.properties["feature_id"] = feature_id
            elif node.kind == "VARIABLE":
                props = node.properties
                if props.get("redefines"):
                    node.properties["feature_id"] = "COBOL.REDEFINES"
                elif props.get("occurs"):
                    node.properties["feature_id"] = "COBOL.OCCURS"
                elif "COMP-3" in str(props.get("usage", "")):
                    node.properties["feature_id"] = "COBOL.COMP_3"
                elif "COMP" in str(props.get("usage", "")):
                    node.properties["feature_id"] = "COBOL.COMP"
            original_add_node(node)
        self.ir.add_node = custom_add_node

    def is_active_end_keyword(self, val: str) -> bool:
        if not val:
            return False
        val_upper = val.upper()
        for kw_set in self.active_end_keywords:
            if val_upper in kw_set:
                return True
        return False

    def next_node_id(self) -> str:
        self.node_counter += 1
        return f"node_{self.node_counter:05d}"

    def peek(self, offset: int = 0) -> CobolToken:
        if self.current + offset >= len(self.tokens):
            return CobolToken("EOF", "", self.file_path, 0, 0, 0, 0)
        return self.tokens[self.current + offset]

    def is_at_end(self) -> bool:
        return self.current >= len(self.tokens) or self.peek().type == "EOF"

    def check(self, type_: str, value: str = None) -> bool:
        if self.is_at_end():
            return False
        tok = self.peek()
        if tok.type != type_:
            return False
        if value is not None and tok.value.upper() != value.upper():
            return False
        return True

    def match(self, type_: str, value: str = None) -> bool:
        if self.check(type_, value):
            self.current += 1
            return True
        return False

    def match_statement_period(self) -> bool:
        if self.match("PUNCTUATION", "."):
            self.sentence_ended = True
            return True
        return False

    def close_implicit_scopes(self, token):
        while self.block_stack:
            kind = self.block_stack.pop()
            end_type = f"END-{kind}"
            node = SemanticIRNode(
                node_id=self.next_node_id(),
                kind="STATEMENT",
                properties={"statement_type": end_type},
                source_file=self.file_path,
                source_line=token.line,
                source_column=token.column,
                start_offset=token.start_offset,
                end_offset=token.end_offset,
                status="PARSED"
            )
            self.ir.add_node(node)

    def consume(self, type_: str, value: str = None, message: str = "Expected token") -> CobolToken:
        if self.check(type_, value):
            tok = self.peek()
            self.current += 1
            return tok
        
        offending = self.peek()
        diag = ParserDiagnostic(
            message=message,
            file=self.file_path,
            line=offending.line,
            column=offending.column,
            token_value=offending.value,
            context=f"Parsing around token {offending.value}"
        )
        self.diagnostics.append(diag)
        raise diag

    def consume_val(self, message: str = "Expected identifier or literal") -> CobolToken:
        tok = self.peek()
        if tok.type in ("IDENTIFIER", "LITERAL_STRING", "LITERAL_NUMBER", "KEYWORD"):
            self.current += 1
            return tok
        
        diag = ParserDiagnostic(
            message=message,
            file=self.file_path,
            line=tok.line,
            column=tok.column,
            token_value=tok.value,
            context=f"Parsing value around {tok.value}"
        )
        self.diagnostics.append(diag)
        raise diag

    def consume_subscripted_identifier(self, message: str = "Expected identifier") -> str:
        tok = self.consume("IDENTIFIER", None, message)
        val = tok.value
        if self.match("PUNCTUATION", "("):
            parts = [val, "("]
            depth = 1
            while depth > 0 and not self.is_at_end():
                t = self.peek()
                self.current += 1
                parts.append(t.value)
                if t.type == "PUNCTUATION" and t.value == "(":
                    depth += 1
                elif t.type == "PUNCTUATION" and t.value == ")":
                    depth -= 1
            val = "".join(parts)
        return val

    def consume_val_or_subscript(self, message: str = "Expected identifier or literal"):
        class SubscriptValue:
            def __init__(self, value: str):
                self.value = value
        
        tok = self.peek()
        if tok.type == "KEYWORD" and tok.value.upper() == "FUNCTION":
            self.current += 1  # Consume FUNCTION
            func_name_tok = self.consume("IDENTIFIER", None, "Expected function name after FUNCTION")
            val = "FUNCTION " + func_name_tok.value
            if self.match("PUNCTUATION", "("):
                parts = [val, "("]
                depth = 1
                while depth > 0 and not self.is_at_end():
                    t = self.peek()
                    self.current += 1
                    parts.append(t.value)
                    if t.type == "PUNCTUATION" and t.value == "(":
                        depth += 1
                    elif t.type == "PUNCTUATION" and t.value == ")":
                        depth -= 1
                val = "".join(parts)
            return SubscriptValue(val)

        if tok.type in ("IDENTIFIER", "KEYWORD"):
            val = self.consume_subscripted_identifier()
            return SubscriptValue(val)
        else:
            return self.consume_val(message)


    def parse(self) -> SemanticIR:
        while not self.is_at_end():
            try:
                if self.check("KEYWORD", "END") and self.peek(1) and self.peek(1).value.upper() == "PROGRAM":
                    self.consume("KEYWORD", "END")
                    self.consume("KEYWORD", "PROGRAM")
                    if self.check("IDENTIFIER"):
                        prog_name_tok = self.consume("IDENTIFIER")
                    else:
                        prog_name_tok = self.consume("LITERAL_STRING")
                    self.consume("PUNCTUATION", ".")
                    if self.active_programs:
                        self.active_programs.pop()
                    self.current_program = self.active_programs[-1] if self.active_programs else None
                elif self.check("KEYWORD", "IDENTIFICATION") or self.check("KEYWORD", "ID"):
                    self.parse_identification_division()
                elif self.check("KEYWORD", "ENVIRONMENT"):
                    self.parse_environment_division()
                elif self.check("KEYWORD", "DATA"):
                    self.parse_data_division()
                elif self.check("KEYWORD", "PROCEDURE"):
                    self.parse_procedure_division()
                else:
                    self.current += 1
            except ParserDiagnostic as e:
                self.diagnostics.append(e)
                # Recover to next division
                while not self.is_at_end() and not self.check("KEYWORD", "ENVIRONMENT") and not self.check("KEYWORD", "DATA") and not self.check("KEYWORD", "PROCEDURE"):
                    self.current += 1
        return self.ir

    def parse_identification_division(self):
        start_tok = self.peek()
        if self.match("KEYWORD", "IDENTIFICATION") or self.match("KEYWORD", "ID"):
            self.consume("KEYWORD", "DIVISION", "Expected DIVISION keyword")
            self.consume("PUNCTUATION", ".", "Expected period after DIVISION")
        
        node = SemanticIRNode(
            node_id=self.next_node_id(),
            kind="DIVISION",
            properties={"name": "IDENTIFICATION"},
            source_file=self.file_path,
            source_line=start_tok.line,
            source_column=start_tok.column,
            start_offset=start_tok.start_offset,
            end_offset=self.peek().start_offset,
            status="PARSED"
        )
        self.ir.add_node(node)

        # Parse PROGRAM-ID
        if self.match("KEYWORD", "PROGRAM-ID"):
            self.consume("PUNCTUATION", ".", "Expected period after PROGRAM-ID")
            if self.check("IDENTIFIER"):
                prog_name_tok = self.consume("IDENTIFIER")
            else:
                prog_name_tok = self.consume("LITERAL_STRING", None, "Expected program name identifier")
            self.consume("PUNCTUATION", ".", "Expected period after program name")
            prog_name = prog_name_tok.value.strip('"').strip("'")
            
            self.active_programs.append(prog_name)
            self.current_program = prog_name
            
            p_node = SemanticIRNode(
                node_id=self.next_node_id(),
                kind="PROGRAM",
                properties={"name": prog_name},
                source_file=self.file_path,
                source_line=prog_name_tok.line,
                source_column=prog_name_tok.column,
                start_offset=prog_name_tok.start_offset,
                end_offset=self.peek().start_offset,
                status="PARSED"
            )
            self.ir.add_node(p_node)

    def parse_environment_division(self):
        start_tok = self.peek()
        self.consume("KEYWORD", "ENVIRONMENT", "Expected ENVIRONMENT")
        self.consume("KEYWORD", "DIVISION", "Expected DIVISION")
        self.consume("PUNCTUATION", ".", "Expected period")

        node = SemanticIRNode(
            node_id=self.next_node_id(),
            kind="DIVISION",
            properties={"name": "ENVIRONMENT"},
            source_file=self.file_path,
            source_line=start_tok.line,
            source_column=start_tok.column,
            start_offset=start_tok.start_offset,
            end_offset=self.peek().start_offset,
            status="PARSED"
        )
        self.ir.add_node(node)

        while not self.is_at_end() and not self.check("KEYWORD", "DATA") and not self.check("KEYWORD", "PROCEDURE"):
            if self.match("KEYWORD", "CONFIGURATION") or self.match("KEYWORD", "INPUT-OUTPUT"):
                name = self.peek(-1).value
                self.consume("KEYWORD", "SECTION", "Expected SECTION")
                self.consume("PUNCTUATION", ".", "Expected period")
                
                sec_node = SemanticIRNode(
                    node_id=self.next_node_id(),
                    kind="SECTION",
                    properties={"name": name},
                    source_file=self.file_path,
                    source_line=start_tok.line,
                    source_column=start_tok.column,
                    start_offset=start_tok.start_offset,
                    end_offset=self.peek().start_offset,
                    status="PARSED"
                )
                self.ir.add_node(sec_node)
                if name == "INPUT-OUTPUT":
                    self.parse_input_output_section()
            else:
                self.current += 1

    def parse_input_output_section(self):
        while not self.is_at_end() and not self.check("KEYWORD", "DATA") and not self.check("KEYWORD", "PROCEDURE") and not self.check("KEYWORD", "CONFIGURATION"):
            if self.match("KEYWORD", "FILE-CONTROL"):
                self.consume("PUNCTUATION", ".", "Expected period after FILE-CONTROL")
                self.parse_file_control()
            else:
                self.current += 1

    def parse_file_control(self):
        while not self.is_at_end() and self.check("KEYWORD", "SELECT"):
            self.parse_select_statement()

    def match_is_keyword(self) -> bool:
        if self.check("KEYWORD", "IS"):
            self.current += 1
            return True
        if self.check("IDENTIFIER") and self.peek().value.upper() == "IS":
            self.current += 1
            return True
        return False

    def parse_select_statement(self):
        start_tok = self.peek()
        self.consume("KEYWORD", "SELECT")
        file_name = self.consume("IDENTIFIER", None, "Expected file-name after SELECT").value
        
        assign_name = None
        status_var = None
        org_type = "SEQUENTIAL"
        access_mode = "SEQUENTIAL"
        record_key = None
        
        alternate_keys = []
        
        while not self.is_at_end() and not self.check("PUNCTUATION", "."):
            if self.match("KEYWORD", "ASSIGN"):
                self.match("KEYWORD", "TO")
                if self.check("IDENTIFIER") or self.check("LITERAL_STRING"):
                    assign_name = self.peek().value
                    self.current += 1
                else:
                    self.consume("IDENTIFIER", None, "Expected physical assignment after ASSIGN TO")
            elif self.match("KEYWORD", "ORGANIZATION"):
                self.match_is_keyword()
                if self.match("KEYWORD", "INDEXED") or self.match("IDENTIFIER", "INDEXED"):
                    org_type = "INDEXED"
                elif self.match("KEYWORD", "RELATIVE") or self.match("IDENTIFIER", "RELATIVE"):
                    org_type = "RELATIVE"
                elif self.match("KEYWORD", "LINE") or self.match("IDENTIFIER", "LINE"):
                    if not self.match("KEYWORD", "SEQUENTIAL") and not self.match("IDENTIFIER", "SEQUENTIAL"):
                        raise ParserDiagnostic("Expected SEQUENTIAL after LINE", self.file_path, self.peek().line, self.peek().column, self.peek().value, "")
                    org_type = "LINE SEQUENTIAL"
                elif self.match("KEYWORD", "SEQUENTIAL") or self.match("IDENTIFIER", "SEQUENTIAL"):
                    org_type = "SEQUENTIAL"
            elif self.match("KEYWORD", "ACCESS"):
                if self.check("KEYWORD", "MODE") or (self.check("IDENTIFIER") and self.peek().value.upper() == "MODE"):
                    self.current += 1
                self.match_is_keyword()
                if self.match("KEYWORD", "SEQUENTIAL") or self.match("IDENTIFIER", "SEQUENTIAL"):
                    access_mode = "SEQUENTIAL"
                elif self.match("KEYWORD", "RANDOM") or self.match("IDENTIFIER", "RANDOM"):
                    access_mode = "RANDOM"
                elif self.match("KEYWORD", "DYNAMIC") or self.match("IDENTIFIER", "DYNAMIC"):
                    access_mode = "DYNAMIC"
            elif self.match("KEYWORD", "RECORD"):
                self.consume("KEYWORD", "KEY")
                self.match_is_keyword()
                record_key = self.consume("IDENTIFIER", None, "Expected record key identifier").value
            elif self.match("KEYWORD", "ALTERNATE") or self.match("IDENTIFIER", "ALTERNATE"):
                if self.match("KEYWORD", "RECORD"):
                    self.match("KEYWORD", "KEY")
                elif self.match("KEYWORD", "KEY"):
                    pass
                self.match_is_keyword()
                alt_key_name = self.consume("IDENTIFIER", None, "Expected alternate record key identifier").value
                with_duplicates = False
                if self.match("KEYWORD", "WITH"):
                    if self.check("KEYWORD", "DUPLICATES") or self.check("IDENTIFIER", "DUPLICATES"):
                        self.current += 1
                        with_duplicates = True
                    else:
                        self.consume("KEYWORD", "DUPLICATES")
                elif self.match("KEYWORD", "DUPLICATES") or self.match("IDENTIFIER", "DUPLICATES"):
                    with_duplicates = True
                alternate_keys.append({
                    "name": alt_key_name,
                    "with_duplicates": with_duplicates
                })
            elif self.match("KEYWORD", "RELATIVE") or self.match("IDENTIFIER", "RELATIVE"):
                if self.check("KEYWORD", "KEY") or (self.check("IDENTIFIER") and self.peek().value.upper() == "KEY"):
                    self.current += 1
                self.match_is_keyword()
                record_key = self.consume("IDENTIFIER", None, "Expected relative key identifier").value
            elif self.match("KEYWORD", "FILE"):
                self.consume("KEYWORD", "STATUS")
                self.match_is_keyword()
                status_var = self.consume("IDENTIFIER", None, "Expected file status variable").value
            else:
                self.current += 1
                
        self.consume("PUNCTUATION", ".", "Expected period after SELECT statement")
        
        node = SemanticIRNode(
            node_id=self.next_node_id(),
            kind="FILE_CONTROL",
            properties={
                "file_name": file_name,
                "assign_name": assign_name,
                "organization": org_type,
                "access_mode": access_mode,
                "record_key": record_key,
                "alternate_keys": alternate_keys,
                "status_var": status_var
            },
            source_file=self.file_path,
            source_line=start_tok.line,
            source_column=start_tok.column,
            start_offset=start_tok.start_offset,
            end_offset=self.peek().start_offset,
            status="PARSED"
        )
        self.ir.add_node(node)

    def parse_data_division(self):
        start_tok = self.peek()
        self.consume("KEYWORD", "DATA", "Expected DATA")
        self.consume("KEYWORD", "DIVISION", "Expected DIVISION")
        self.consume("PUNCTUATION", ".", "Expected period")

        node = SemanticIRNode(
            node_id=self.next_node_id(),
            kind="DIVISION",
            properties={"name": "DATA"},
            source_file=self.file_path,
            source_line=start_tok.line,
            source_column=start_tok.column,
            start_offset=start_tok.start_offset,
            end_offset=self.peek().start_offset,
            status="PARSED"
        )
        self.ir.add_node(node)

        self.in_file_section = False
        self.current_fd = None
        while not self.is_at_end() and not self.check("KEYWORD", "PROCEDURE"):
            if self.check("KEYWORD", "FILE") or self.check("KEYWORD", "WORKING-STORAGE") or self.check("KEYWORD", "LINKAGE") or self.check("KEYWORD", "REPORT"):
                sec_tok = self.peek()
                self.current += 1
                sec_name = sec_tok.value
                self.consume("KEYWORD", "SECTION", "Expected SECTION")
                self.consume("PUNCTUATION", ".", "Expected period")
                
                self.in_file_section = (sec_name.upper() == "FILE")
                self.current_rd = None
                sec_node = SemanticIRNode(
                    node_id=self.next_node_id(),
                    kind="SECTION",
                    properties={"name": sec_name},
                    source_file=self.file_path,
                    source_line=sec_tok.line,
                    source_column=sec_tok.column,
                    start_offset=sec_tok.start_offset,
                    end_offset=self.peek().start_offset,
                    status="PARSED"
                )
                self.ir.add_node(sec_node)
                self.parse_data_items()
            else:
                self.current += 1

    def parse_data_items(self):
        while not self.is_at_end() and not self.check("KEYWORD", "PROCEDURE") and not self.check("KEYWORD", "FILE") and not self.check("KEYWORD", "WORKING-STORAGE") and not self.check("KEYWORD", "LINKAGE") and not self.check("KEYWORD", "REPORT"):
            if getattr(self, "in_file_section", False) and (self.match("KEYWORD", "FD") or self.match("KEYWORD", "SD")):
                fd_name_tok = self.consume("IDENTIFIER", None, "Expected FD name")
                self.current_fd = fd_name_tok.value.upper()
                while not self.is_at_end() and not self.match("PUNCTUATION", "."):
                    self.current += 1
                continue
                
            if self.match("KEYWORD", "RD"):
                rd_name_tok = self.consume("IDENTIFIER", None, "Expected RD name")
                self.current_rd = rd_name_tok.value.upper()
                node = SemanticIRNode(
                    node_id=self.next_node_id(),
                    kind="RD",
                    properties={"name": rd_name_tok.value.upper()},
                    source_file=self.file_path,
                    source_line=rd_name_tok.line,
                    source_column=rd_name_tok.column,
                    start_offset=rd_name_tok.start_offset,
                    end_offset=self.peek().start_offset,
                    status="PARSED"
                )
                self.ir.add_node(node)
                while not self.is_at_end() and not self.match("PUNCTUATION", "."):
                    self.current += 1
                continue
                
            if self.check("LITERAL_NUMBER"):
                lvl_tok = self.peek()
                lvl = int(lvl_tok.value)
                
                # Accept any valid COBOL level number (01-49, 66, 77, 78, 88)
                if lvl < 1 or (lvl > 49 and lvl not in (66, 77, 78, 88)):
                    self.current += 1
                    continue
                
                self.current += 1
                
                name_tok = self.peek()
                is_nameless = False
                if getattr(self, "current_rd", None) is not None:
                    if name_tok.value.upper() in ("TYPE", "LINE", "COLUMN", "SOURCE", "SUM"):
                        is_nameless = True
                
                if (self.check("IDENTIFIER") or self.check("KEYWORD")) and not is_nameless:
                    self.current += 1
                    name = name_tok.value
                else:
                    if getattr(self, "current_rd", None) is not None:
                        if not hasattr(self, "filler_rw_counter"):
                            self.filler_rw_counter = 0
                        self.filler_rw_counter += 1
                        name = f"FILLER_RW_{self.filler_rw_counter}"
                    else:
                        name = "FILLER"
                
                if name.upper() == "FILLER":
                    if not hasattr(self, "filler_counter"):
                        self.filler_counter = 0
                    self.filler_counter += 1
                    name = f"FILLER_{self.filler_counter}"
                
                props = {
                    "name": name,
                    "level": lvl,
                    "fd_name": self.current_fd if (lvl == 1 and getattr(self, "in_file_section", False)) else None,
                    "rd_name": getattr(self, "current_rd", None),
                    "picture": None,
                    "usage": None,
                    "value": None,
                    "redefines": None,
                    "occurs": None,
                    "occurs_min": None,
                    "occurs_max": None,
                    "depending_on": None,
                    "signed": False,
                    "digits": 0,
                    "scale": 0,
                    "is_group": True,
                    "condition_values": []
                }
                
                while not self.is_at_end() and not self.check("PUNCTUATION", "."):
                    if self.match("KEYWORD", "REDEFINES"):
                        ref_tok = self.consume("IDENTIFIER", None, "Expected identifier after REDEFINES")
                        props["redefines"] = ref_tok.value
                    
                    elif self.match("KEYWORD", "PIC") or self.match("KEYWORD", "PICTURE"):
                        self.match("KEYWORD", "IS")
                        
                        pic_parts = []
                        while not self.is_at_end() and not self.check("KEYWORD") and not self.check("PUNCTUATION", "."):
                            pic_parts.append(self.peek().value)
                            self.current += 1
                        
                        pic_str = "".join(pic_parts)
                        props["picture"] = pic_str
                        props["is_group"] = False
                        
                        signed, digits, scale, is_edited = parse_picture_clause(pic_str)
                        props["signed"] = signed
                        props["digits"] = digits
                        props["scale"] = scale
                        props["is_edited"] = is_edited
                        
                    elif self.match("KEYWORD", "GLOBAL"):
                        props["is_global"] = True
                        
                    elif self.match("KEYWORD", "USAGE"):
                        self.match("KEYWORD", "IS")
                        usage_tok = self.peek()
                        self.current += 1
                        props["usage"] = usage_tok.value.upper()
                        
                    elif self.match("KEYWORD", "POINTER"):
                        props["usage"] = "POINTER"
                        
                    elif self.match("KEYWORD", "COMP") or self.match("KEYWORD", "COMP-3") or self.match("KEYWORD", "BINARY") or self.match("KEYWORD", "DISPLAY"):
                        props["usage"] = self.peek(-1).value.upper()
                        
                    elif self.match("KEYWORD", "SIGN"):
                        self.match("KEYWORD", "IS")
                        pos = "TRAILING"
                        separate = False
                        if self.match("KEYWORD", "LEADING"):
                            pos = "LEADING"
                        elif self.match("KEYWORD", "TRAILING"):
                            pos = "TRAILING"
                        if self.match("KEYWORD", "SEPARATE"):
                            self.match("KEYWORD", "CHARACTER")
                            separate = True
                        props["sign_position"] = pos
                        props["sign_separate"] = separate
                        
                    elif self.match("KEYWORD", "VALUE") or self.match("KEYWORD", "VALUES"):
                        self.match("KEYWORD", "IS")
                        val_tok = self.peek()
                        self.current += 1
                        val_str = val_tok.value
                        if val_str in ("-", "+") and not self.is_at_end() and self.peek().type in ("NUMBER", "LITERAL_NUMBER"):
                            val_str += self.peek().value
                            self.current += 1
                        props["value"] = val_str
                        
                        if lvl == 88:
                            props["condition_values"].append(val_tok.value)
                            
                    elif self.match("KEYWORD", "TYPE") or self.match("IDENTIFIER", "TYPE"):
                        self.match("KEYWORD", "IS") or self.match("IDENTIFIER", "IS")
                        type_parts = []
                        while not self.is_at_end() and not self.check("PUNCTUATION", ".") and not self.check("KEYWORD", "LINE") and not self.check("KEYWORD", "COLUMN") and not self.check("KEYWORD", "SOURCE") and not self.check("IDENTIFIER", "LINE") and not self.check("IDENTIFIER", "COLUMN") and not self.check("IDENTIFIER", "SOURCE"):
                            type_parts.append(self.peek().value.upper())
                            self.current += 1
                        props["report_type"] = " ".join(type_parts)
                        
                    elif self.match("KEYWORD", "LINE") or self.match("IDENTIFIER", "LINE"):
                        self.match("KEYWORD", "NUMBER") or self.match("IDENTIFIER", "NUMBER")
                        self.match("KEYWORD", "IS") or self.match("IDENTIFIER", "IS")
                        if self.match("KEYWORD", "PLUS") or self.match("IDENTIFIER", "PLUS"):
                            props["line_number"] = "+" + self.consume("LITERAL_NUMBER").value
                        elif self.match("KEYWORD", "NEXT") or self.match("IDENTIFIER", "NEXT"):
                            self.match("KEYWORD", "PAGE") or self.match("IDENTIFIER", "PAGE")
                            props["line_number"] = "NEXT PAGE"
                        else:
                            props["line_number"] = self.consume("LITERAL_NUMBER").value
                            
                    elif self.match("KEYWORD", "COLUMN") or self.match("IDENTIFIER", "COLUMN"):
                        self.match("KEYWORD", "NUMBER") or self.match("IDENTIFIER", "NUMBER")
                        self.match("KEYWORD", "IS") or self.match("IDENTIFIER", "IS")
                        props["column_number"] = self.consume("LITERAL_NUMBER").value
                        
                    elif self.match("KEYWORD", "SOURCE") or self.match("IDENTIFIER", "SOURCE"):
                        self.match("KEYWORD", "IS") or self.match("IDENTIFIER", "IS")
                        props["source_expr"] = self.consume_subscripted_identifier("Expected source identifier")
                        
                    elif self.match("KEYWORD", "SUM") or self.match("IDENTIFIER", "SUM"):
                        props["sum_expr"] = self.consume("IDENTIFIER").value

                    elif self.match("KEYWORD", "OCCURS"):
                        first_tok = self.consume("LITERAL_NUMBER", None, "Expected count after OCCURS")
                        first_val = int(first_tok.value)
                        
                        min_val = first_val
                        max_val = first_val
                        
                        if self.match("KEYWORD", "TO"):
                            max_tok = self.consume("LITERAL_NUMBER", None, "Expected maximum count after TO")
                            max_val = int(max_tok.value)
                            
                        self.match("KEYWORD", "TIMES")
                        
                        props["occurs"] = max_val
                        props["occurs_min"] = min_val
                        props["occurs_max"] = max_val
                        
                        if self.match("KEYWORD", "DEPENDING"):
                            self.match("KEYWORD", "ON")
                            dep_tok = self.consume("IDENTIFIER", None, "Expected identifier after DEPENDING ON")
                            props["depending_on"] = dep_tok.value
                    else:
                        self.current += 1
                
                self.consume("PUNCTUATION", ".", "Expected period after data item definition")
                
                node = SemanticIRNode(
                    node_id=self.next_node_id(),
                    kind="DATA_ITEM",
                    properties=props,
                    source_file=self.file_path,
                    source_line=lvl_tok.line,
                    source_column=lvl_tok.column,
                    start_offset=lvl_tok.start_offset,
                    end_offset=self.peek().start_offset,
                    status="PARSED"
                )
                self.ir.add_node(node)
            else:
                self.current += 1

    def parse_procedure_division(self):
        start_tok = self.peek()
        self.consume("KEYWORD", "PROCEDURE", "Expected PROCEDURE")
        self.consume("KEYWORD", "DIVISION", "Expected DIVISION")
        using_args = []
        if self.match("KEYWORD", "USING"):
            while not self.is_at_end() and not self.check("PUNCTUATION", "."):
                tok = self.peek()
                if tok.type in ("IDENTIFIER", "KEYWORD"):
                    using_args.append(tok.value.upper())
                self.current += 1
        
        self.consume("PUNCTUATION", ".", "Expected period")

        node = SemanticIRNode(
            node_id=self.next_node_id(),
            kind="DIVISION",
            properties={"name": "PROCEDURE", "using_args": using_args},
            source_file=self.file_path,
            source_line=start_tok.line,
            source_column=start_tok.column,
            start_offset=start_tok.start_offset,
            end_offset=self.peek().start_offset,
            status="PARSED"
        )
        self.ir.add_node(node)

        while not self.is_at_end():
            if self.check("KEYWORD", "IDENTIFICATION") or self.check("KEYWORD", "ID"):
                break
            if self.check("KEYWORD", "END") and self.peek(1) and self.peek(1).value.upper() == "PROGRAM":
                break
            
            is_header = False
            is_section = False
            name_tok = self.peek()
            
            if self.check("IDENTIFIER"):
                if self.peek(1).type == "PUNCTUATION" and self.peek(1).value == ".":
                    is_header = True
                    is_section = False
                elif self.peek(1).type == "KEYWORD" and self.peek(1).value.upper() == "SECTION" and self.peek(2).type == "PUNCTUATION" and self.peek(2).value == ".":
                    is_header = True
                    is_section = True
                    
            if is_header:
                self.close_implicit_scopes(name_tok)
                self.current += 1 # Consume name_tok
                if is_section:
                    self.current += 2 # Consume SECTION and "."
                    kind = "SECTION"
                else:
                    self.current += 1 # Consume "."
                    kind = "PARAGRAPH"
                
                p_node = SemanticIRNode(
                    node_id=self.next_node_id(),
                    kind=kind,
                    properties={"name": name_tok.value},
                    source_file=self.file_path,
                    source_line=name_tok.line,
                    source_column=name_tok.column,
                    start_offset=name_tok.start_offset,
                    end_offset=self.peek().start_offset,
                    status="PARSED"
                )
                self.ir.add_node(p_node)
            else:
                self.parse_statement()

    def parse_nested_statement(self):
        before_keys = list(self.ir.nodes.keys())
        self._parse_statement_internal()
        after_keys = list(self.ir.nodes.keys())
        new_keys = [k for k in after_keys if k not in before_keys]
        if new_keys:
            main_node = self.ir.nodes[new_keys[0]]
            for k in new_keys:
                del self.ir.nodes[k]
            return main_node
        return None

    def parse_nested_statements_block(self, end_keywords, end_verbs=None):
        self.active_end_keywords.append(set(k.upper() for k in end_keywords))
        try:
            statements = []
            while not self.is_at_end() and not self.sentence_ended:
                peek_tok = self.peek()
                if peek_tok.type == "KEYWORD" and peek_tok.value.upper() in end_keywords:
                    break
                if end_verbs and peek_tok.type == "KEYWORD" and peek_tok.value.upper() in end_verbs:
                    break
                if peek_tok.type == "PUNCTUATION" and peek_tok.value == ".":
                    break
                stmt = self.parse_nested_statement()
                if stmt:
                    statements.append(stmt)
                    if self.sentence_ended:
                        break
                else:
                    self.current += 1
            return statements
        finally:
            self.active_end_keywords.pop()

    def parse_statement(self):
        try:
            self.sentence_ended = False
            self._parse_statement_internal()
            if self.sentence_ended:
                self.close_implicit_scopes(self.peek(-1))
                self.sentence_ended = False
                self.sentence_id += 1
        except ParserDiagnostic as e:
            self.diagnostics.append(e)
            while not self.is_at_end() and not self.check("PUNCTUATION", ".") and not self.check("KEYWORD", "MOVE") and not self.check("KEYWORD", "IF") and not self.check("KEYWORD", "PERFORM"):
                self.current += 1
            if self.match("PUNCTUATION", "."):
                self.close_implicit_scopes(self.peek(-1))
                self.sentence_id += 1

    def _parse_statement_internal(self):
        start_tok = self.peek()
        
        if self.match("KEYWORD", "MOVE"):
            is_corr = False
            if self.match("KEYWORD", "CORRESPONDING") or self.match("IDENTIFIER", "CORRESPONDING") or self.match("KEYWORD", "CORR") or self.match("IDENTIFIER", "CORR"):
                is_corr = True
            src_tok = self.consume_val_or_subscript("Expected source identifier or literal in MOVE")
            self.consume("KEYWORD", "TO", "Expected TO keyword")
            # Collect all targets (MOVE X TO A B C)
            targets = []
            while self.check("IDENTIFIER") or self.check("PUNCTUATION", ","):
                if self.match("PUNCTUATION", ","):
                    continue
                targets.append(self.consume_subscripted_identifier())
            if not targets:
                tgt_val = self.consume_subscripted_identifier("Expected target identifier")
                targets = [tgt_val]
            self.match_statement_period()
            
            node = SemanticIRNode(
                node_id=self.next_node_id(),
                kind="STATEMENT",
                properties={
                    "statement_type": "MOVE_CORRESPONDING" if is_corr else "MOVE",
                    "source": src_tok.value,
                    "targets": targets
                },
                source_file=self.file_path,
                source_line=start_tok.line,
                source_column=start_tok.column,
                start_offset=start_tok.start_offset,
                end_offset=self.peek().start_offset,
                status="PARSED"
            )
            self.ir.add_node(node)
            
        elif self.match("KEYWORD", "COMPUTE"):
            tgt_val = self.consume_subscripted_identifier("Expected target identifier")
            rounded = False
            if self.match("KEYWORD", "ROUNDED"):
                rounded = True
            self.consume("PUNCTUATION", "=", "Expected '=' in COMPUTE")
            
            expr_parts = []
            while not self.is_at_end() and not self.check("PUNCTUATION", ".") and not self.check("KEYWORD"):
                tok = self.peek()
                if tok.type in ("IDENTIFIER", "LITERAL_NUMBER", "PUNCTUATION"):
                    expr_parts.append(tok.value)
                    self.current += 1
                else:
                    break
            
            on_size_error_nodes = []
            not_on_size_error_nodes = []
            
            while not self.is_at_end() and not self.check("PUNCTUATION", ".") and not self.sentence_ended:
                if self.match("KEYWORD", "ON") or self.check("KEYWORD", "SIZE"):
                    if not self.match("KEYWORD", "SIZE"):
                        self.match("KEYWORD", "SIZE")
                    self.consume("KEYWORD", "ERROR", "Expected ERROR after SIZE")
                    on_size_error_nodes = self.parse_nested_statements_block(
                        ["NOT", "END-COMPUTE"]
                    )
                elif self.match("KEYWORD", "NOT"):
                    self.consume("KEYWORD", "ON", "Expected ON after NOT")
                    self.consume("KEYWORD", "SIZE", "Expected SIZE after ON")
                    self.consume("KEYWORD", "ERROR", "Expected ERROR after SIZE")
                    not_on_size_error_nodes = self.parse_nested_statements_block(
                        ["END-COMPUTE"]
                    )
                elif self.match("KEYWORD", "END-COMPUTE"):
                    break
                else:
                    break

            self.match_statement_period()
            
            node = SemanticIRNode(
                node_id=self.next_node_id(),
                kind="STATEMENT",
                properties={
                    "statement_type": "COMPUTE",
                    "target": tgt_val,
                    "rounded": rounded,
                    "expression": " ".join(expr_parts),
                    "on_size_error_nodes": on_size_error_nodes,
                    "not_on_size_error_nodes": not_on_size_error_nodes
                },
                source_file=self.file_path,
                source_line=start_tok.line,
                source_column=start_tok.column,
                start_offset=start_tok.start_offset,
                end_offset=self.peek().start_offset,
                status="PARSED"
            )
            self.ir.add_node(node)

        elif self.match("KEYWORD", "ADD") or self.match("KEYWORD", "SUBTRACT") or self.match("KEYWORD", "MULTIPLY") or self.match("KEYWORD", "DIVIDE"):
            op = self.peek(-1).value.upper()
            is_corr = False
            if op in ("ADD", "SUBTRACT"):
                if self.match("KEYWORD", "CORRESPONDING") or self.match("IDENTIFIER", "CORRESPONDING") or self.match("KEYWORD", "CORR") or self.match("IDENTIFIER", "CORR"):
                    is_corr = True
            val_tok = self.consume_val_or_subscript("Expected value to perform calculation")
            
            mid_kw = "TO"
            if op == "SUBTRACT":
                mid_kw = "FROM"
            elif op == "MULTIPLY":
                mid_kw = "BY"
            elif op == "DIVIDE":
                if self.check("KEYWORD", "INTO"):
                    mid_kw = "INTO"
                else:
                    mid_kw = "BY"
                
            self.consume("KEYWORD", mid_kw, f"Expected {mid_kw} keyword")
            
            to_idents = []
            end_verb = f"END-{op}"
            
            while True:
                if self.is_at_end() or self.check("PUNCTUATION", ".") or self.check("KEYWORD", "GIVING") or self.check("KEYWORD", "ON") or self.check("KEYWORD", "SIZE") or self.check("KEYWORD", "NOT") or self.check("KEYWORD", end_verb) or self.sentence_ended or is_tok_statement_start(self.peek()):
                    break
                ident_tok = self.consume_val_or_subscript("Expected identifier or literal value")
                ident = ident_tok.value
                rounded = False
                if self.match("KEYWORD", "ROUNDED"):
                    rounded = True
                to_idents.append({"name": ident, "rounded": rounded})
                if not self.check("IDENTIFIER") and not self.check("KEYWORD") and not self.check("NUMBER") and not self.check("LITERAL_NUMBER"):
                    break
            
            if not to_idents:
                raise self.error(self.peek(), "Expected target/value identifier")
            
            giving_targets = []
            remainder_tgt = None
            if self.match("KEYWORD", "GIVING"):
                while True:
                    if self.is_at_end() or self.check("PUNCTUATION", ".") or self.check("KEYWORD", "ON") or self.check("KEYWORD", "SIZE") or self.check("KEYWORD", "NOT") or self.check("KEYWORD", end_verb) or self.sentence_ended or is_tok_statement_start(self.peek()):
                        break
                    
                    if self.match("KEYWORD", "REMAINDER"):
                        remainder_tgt = self.consume_subscripted_identifier("Expected remainder target identifier")
                        break
                        
                    ident = self.consume_subscripted_identifier("Expected target identifier after GIVING")
                    rounded = False
                    if self.match("KEYWORD", "ROUNDED"):
                        rounded = True
                    giving_targets.append({"name": ident, "rounded": rounded})
                    if not self.check("IDENTIFIER") and not self.check("KEYWORD", "REMAINDER"):
                        break
                if not giving_targets and not remainder_tgt:
                    raise self.error(self.peek(), "Expected target identifier after GIVING")
                
            on_size_error_nodes = []
            not_on_size_error_nodes = []
            
            while not self.is_at_end() and not self.check("PUNCTUATION", ".") and not self.sentence_ended:
                if self.match("KEYWORD", "ON") or self.check("KEYWORD", "SIZE"):
                    if not self.match("KEYWORD", "SIZE"):
                        self.match("KEYWORD", "SIZE")
                    self.consume("KEYWORD", "ERROR", "Expected ERROR after SIZE")
                    on_size_error_nodes = self.parse_nested_statements_block(
                        ["NOT", end_verb]
                    )
                elif self.match("KEYWORD", "NOT"):
                    self.consume("KEYWORD", "ON", "Expected ON after NOT")
                    self.consume("KEYWORD", "SIZE", "Expected SIZE after ON")
                    self.consume("KEYWORD", "ERROR", "Expected ERROR after SIZE")
                    not_on_size_error_nodes = self.parse_nested_statements_block(
                        [end_verb]
                    )
                elif self.match("KEYWORD", end_verb):
                    break
                else:
                    break
                    
            self.match_statement_period()
            
            props = {
                "statement_type": f"{op}_CORRESPONDING" if is_corr else op,
                "value": val_tok.value,
                "on_size_error_nodes": on_size_error_nodes,
                "not_on_size_error_nodes": not_on_size_error_nodes
            }
            if giving_targets:
                props["giving"] = True
                props["operand2"] = to_idents[0]["name"]
                props["targets"] = giving_targets
            else:
                props["giving"] = False
                props["targets"] = to_idents
                
            if remainder_tgt:
                props["remainder"] = remainder_tgt
                
            node = SemanticIRNode(
                node_id=self.next_node_id(),
                kind="STATEMENT",
                properties=props,
                source_file=self.file_path,
                source_line=start_tok.line,
                source_column=start_tok.column,
                start_offset=start_tok.start_offset,
                end_offset=self.peek().start_offset,
                status="PARSED"
            )
            self.ir.add_node(node)

        elif self.match("KEYWORD", "IF"):
            cond_parts = []
            while not self.is_at_end() and not self.check("PUNCTUATION", "."):
                tok = self.peek()
                if is_tok_statement_start(tok):
                    break
                self.current += 1
                if tok.type == "LITERAL_STRING":
                    cond_parts.append(f'"{tok.value}"')
                else:
                    cond_parts.append(tok.value)
            
            self.match("KEYWORD", "THEN")
            self.block_stack.append("IF")
            
            node = SemanticIRNode(
                node_id=self.next_node_id(),
                kind="STATEMENT",
                properties={
                    "statement_type": "IF",
                    "condition": " ".join(cond_parts)
                },
                source_file=self.file_path,
                source_line=start_tok.line,
                source_column=start_tok.column,
                start_offset=start_tok.start_offset,
                end_offset=self.peek().start_offset,
                status="PARSED"
            )
            self.ir.add_node(node)

        elif self.match("KEYWORD", "ELSE"):
            node = SemanticIRNode(
                node_id=self.next_node_id(),
                kind="STATEMENT",
                properties={"statement_type": "ELSE"},
                source_file=self.file_path,
                source_line=start_tok.line,
                source_column=start_tok.column,
                start_offset=start_tok.start_offset,
                end_offset=self.peek().start_offset,
                status="PARSED"
            )
            self.ir.add_node(node)

        elif self.match("KEYWORD", "PERFORM"):
            is_times = False
            times_idx = -1
            for offset in range(1, 6):
                if self.peek(offset).value.upper() == "TIMES":
                    is_times = True
                    times_idx = offset
                    break
            
            if is_times:
                if times_idx == 1:
                    count_tok = self.consume_val_or_subscript("Expected repeat count in PERFORM TIMES")
                    if self.check("KEYWORD", "TIMES") or self.check("IDENTIFIER", "TIMES"):
                        self.current += 1
                    else:
                        self.consume("KEYWORD", "TIMES", "Expected TIMES keyword")
                    props = {
                        "statement_type": "PERFORM_TIMES",
                        "count": count_tok.value
                    }
                    self.block_stack.append("PERFORM")
                else:
                    target = self.consume("IDENTIFIER", None, "Expected paragraph/section target name").value
                    thru = None
                    if self.match("KEYWORD", "THRU"):
                        thru = self.consume("IDENTIFIER", None, "Expected THRU target name").value
                    count_tok = self.consume_val_or_subscript("Expected repeat count in PERFORM TIMES")
                    if self.check("KEYWORD", "TIMES") or self.check("IDENTIFIER", "TIMES"):
                        self.current += 1
                    else:
                        self.consume("KEYWORD", "TIMES", "Expected TIMES keyword")
                    props = {
                        "statement_type": "PERFORM_TIMES_OUT",
                        "target": target,
                        "thru": thru,
                        "count": count_tok.value
                    }
            elif self.match("KEYWORD", "VARYING"):
                # PERFORM VARYING idx FROM start BY step UNTIL cond
                idx_val = self.consume_subscripted_identifier("Expected index variable after VARYING")
                self.consume("KEYWORD", "FROM", "Expected FROM in PERFORM VARYING")
                from_tok = self.consume_val_or_subscript("Expected FROM value")
                self.consume("KEYWORD", "BY", "Expected BY in PERFORM VARYING")
                by_tok = self.consume_val_or_subscript("Expected BY value")
                self.consume("KEYWORD", "UNTIL", "Expected UNTIL in PERFORM VARYING")
                cond_parts = []
                while not self.is_at_end() and not self.check("PUNCTUATION", "."):
                    tok = self.peek()
                    if is_tok_statement_start(tok) or self.check("KEYWORD", "AFTER") or self.check("IDENTIFIER", "AFTER"):
                        break
                    self.current += 1
                    if tok.type == "LITERAL_STRING":
                        cond_parts.append(f'"{tok.value}"')
                    else:
                        cond_parts.append(tok.value)
                
                after_clauses = []
                while self.match("KEYWORD", "AFTER") or self.match("IDENTIFIER", "AFTER"):
                    after_idx = self.consume_subscripted_identifier("Expected index variable after AFTER")
                    self.consume("KEYWORD", "FROM", "Expected FROM in PERFORM AFTER")
                    after_from = self.consume_val_or_subscript("Expected FROM value")
                    self.consume("KEYWORD", "BY", "Expected BY in PERFORM AFTER")
                    after_by = self.consume_val_or_subscript("Expected BY value")
                    self.consume("KEYWORD", "UNTIL", "Expected UNTIL in PERFORM AFTER")
                    after_cond_parts = []
                    while not self.is_at_end() and not self.check("PUNCTUATION", "."):
                        tok = self.peek()
                        if is_tok_statement_start(tok) or self.check("KEYWORD", "AFTER") or self.check("IDENTIFIER", "AFTER"):
                            break
                        self.current += 1
                        if tok.type == "LITERAL_STRING":
                            after_cond_parts.append(f'"{tok.value}"')
                        else:
                            after_cond_parts.append(tok.value)
                    after_clauses.append({
                        "index": after_idx,
                        "from_value": after_from.value,
                        "by_value": after_by.value,
                        "condition": " ".join(after_cond_parts)
                    })
                
                props = {
                    "statement_type": "PERFORM_VARYING",
                    "index": idx_val,
                    "from_value": from_tok.value,
                    "by_value": by_tok.value,
                    "condition": " ".join(cond_parts),
                    "after_clauses": after_clauses
                }
                self.block_stack.append("PERFORM")
            elif self.match("KEYWORD", "UNTIL"):
                cond_parts = []
                while not self.is_at_end() and not self.check("PUNCTUATION", "."):
                    tok = self.peek()
                    if is_tok_statement_start(tok):
                        break
                    self.current += 1
                    if tok.type == "LITERAL_STRING":
                        cond_parts.append(f'"{tok.value}"')
                    else:
                        cond_parts.append(tok.value)
                props = {"statement_type": "PERFORM_UNTIL", "condition": " ".join(cond_parts)}
                self.block_stack.append("PERFORM")
            else:
                tgt_tok = self.consume("IDENTIFIER", None, "Expected paragraph name after PERFORM")
                props = {"statement_type": "PERFORM", "target": tgt_tok.value}
                if self.match("KEYWORD", "THRU"):
                    thru_tok = self.consume("IDENTIFIER", None, "Expected THRU paragraph name")
                    props["thru"] = thru_tok.value
 
                if self.match("KEYWORD", "VARYING"):
                    # PERFORM paragraph VARYING idx FROM start BY step UNTIL cond
                    idx_val = self.consume_subscripted_identifier("Expected index variable after VARYING")
                    self.consume("KEYWORD", "FROM", "Expected FROM in PERFORM VARYING")
                    from_tok = self.consume_val_or_subscript("Expected FROM value")
                    self.consume("KEYWORD", "BY", "Expected BY in PERFORM VARYING")
                    by_tok = self.consume_val_or_subscript("Expected BY value")
                    self.consume("KEYWORD", "UNTIL", "Expected UNTIL in PERFORM VARYING")
                    cond_parts = []
                    while not self.is_at_end() and not self.check("PUNCTUATION", "."):
                        tok = self.peek()
                        if is_tok_statement_start(tok) or self.check("KEYWORD", "AFTER") or self.check("IDENTIFIER", "AFTER"):
                            break
                        self.current += 1
                        if tok.type == "LITERAL_STRING":
                            cond_parts.append('"' + tok.value + '"')
                        else:
                            cond_parts.append(tok.value)
                    
                    after_clauses = []
                    while self.match("KEYWORD", "AFTER") or self.match("IDENTIFIER", "AFTER"):
                        after_idx = self.consume_subscripted_identifier("Expected index variable after AFTER")
                        self.consume("KEYWORD", "FROM", "Expected FROM in PERFORM AFTER")
                        after_from = self.consume_val_or_subscript("Expected FROM value")
                        self.consume("KEYWORD", "BY", "Expected BY in PERFORM AFTER")
                        after_by = self.consume_val_or_subscript("Expected BY value")
                        self.consume("KEYWORD", "UNTIL", "Expected UNTIL in PERFORM AFTER")
                        after_cond_parts = []
                        while not self.is_at_end() and not self.check("PUNCTUATION", "."):
                            tok = self.peek()
                            if is_tok_statement_start(tok) or self.check("KEYWORD", "AFTER") or self.check("IDENTIFIER", "AFTER"):
                                break
                            self.current += 1
                            if tok.type == "LITERAL_STRING":
                                after_cond_parts.append('"' + tok.value + '"')
                            else:
                                after_cond_parts.append(tok.value)
                        after_clauses.append({
                            "index": after_idx,
                            "from_value": after_from.value,
                            "by_value": after_by.value,
                            "condition": " ".join(after_cond_parts)
                        })
                    
                    props["statement_type"] = "PERFORM_VARYING_OUT"
                    props["index"] = idx_val
                    props["from_value"] = from_tok.value
                    props["by_value"] = by_tok.value
                    props["condition"] = " ".join(cond_parts)
                    props["after_clauses"] = after_clauses
                elif self.match("KEYWORD", "UNTIL"):
                    cond_parts = []
                    while not self.is_at_end() and not self.check("PUNCTUATION", "."):
                        tok = self.peek()
                        if is_tok_statement_start(tok):
                            break
                        self.current += 1
                        if tok.type == "LITERAL_STRING":
                            cond_parts.append('"' + tok.value + '"')
                        else:
                            cond_parts.append(tok.value)
                    props["statement_type"] = "PERFORM_UNTIL_OUT"
                    props["condition"] = " ".join(cond_parts)

            self.match_statement_period()
            
            node = SemanticIRNode(
                node_id=self.next_node_id(),
                kind="STATEMENT",
                properties=props,
                source_file=self.file_path,
                source_line=start_tok.line,
                source_column=start_tok.column,
                start_offset=start_tok.start_offset,
                end_offset=self.peek().start_offset,
                status="PARSED"
            )
            self.ir.add_node(node)

        elif self.match("KEYWORD", "DISPLAY"):
            operands = []
            while not self.is_at_end() and not self.check("PUNCTUATION", "."):
                tok = self.peek()
                if is_tok_statement_start(tok):
                    break
                if tok.type == "KEYWORD" and self.is_active_end_keyword(tok.value):
                    break
                if tok.type == "LITERAL_STRING":
                    self.current += 1
                    operands.append({"type": "literal", "value": tok.value})
                elif tok.type == "LITERAL_NUMBER":
                    self.current += 1
                    operands.append({"type": "literal", "value": tok.value})
                elif tok.type in ("IDENTIFIER", "KEYWORD"):
                    val = self.consume_subscripted_identifier()
                    operands.append({"type": "variable", "value": val})
                else:
                    self.current += 1
            
            self.match_statement_period()
            
            node = SemanticIRNode(
                node_id=self.next_node_id(),
                kind="STATEMENT",
                properties={
                    "statement_type": "DISPLAY",
                    "operands": operands
                },
                source_file=self.file_path,
                source_line=start_tok.line,
                source_column=start_tok.column,
                start_offset=start_tok.start_offset,
                end_offset=self.peek().start_offset,
                status="PARSED"
            )
            self.ir.add_node(node)

        elif self.match("KEYWORD", "STRING"):
            parts = []
            while not self.is_at_end() and not self.check("KEYWORD", "INTO"):
                val_tok = self.consume_val("Expected value in STRING")
                delim_val = "SIZE"
                delim_type = "keyword"
                if self.match("KEYWORD", "DELIMITED"):
                    self.match("KEYWORD", "BY")
                    delim_tok = self.consume_val("Expected delimiter in STRING")
                    delim_val = delim_tok.value
                    delim_type = "literal" if delim_tok.type == "LITERAL_STRING" else "variable"
                parts.append({
                    "value": val_tok.value,
                    "type": "literal" if val_tok.type == "LITERAL_STRING" else "variable",
                    "delimited_by": delim_val,
                    "delimited_by_type": delim_type
                })
            
            self.consume("KEYWORD", "INTO", "Expected INTO keyword in STRING")
            tgt_tok = self.consume("IDENTIFIER", None, "Expected target identifier in STRING")
            self.match("PUNCTUATION", ".")
            
            node = SemanticIRNode(
                node_id=self.next_node_id(),
                kind="STATEMENT",
                properties={
                    "statement_type": "STRING",
                    "parts": parts,
                    "target": tgt_tok.value
                },
                source_file=self.file_path,
                source_line=start_tok.line,
                source_column=start_tok.column,
                start_offset=start_tok.start_offset,
                end_offset=self.peek().start_offset,
                status="PARSED"
            )
            self.ir.add_node(node)

        elif self.match("KEYWORD", "UNSTRING"):
            source_tok = self.consume_val("Expected source identifier or literal in UNSTRING")
            
            delimited_by = None
            if self.match("KEYWORD", "DELIMITED"):
                self.match("KEYWORD", "BY")
                delim_tok = self.consume_val("Expected delimiter in UNSTRING")
                delimited_by = delim_tok.value
                
            self.consume("KEYWORD", "INTO", "Expected INTO keyword in UNSTRING")
            targets = []
            while not self.is_at_end() and not self.check("PUNCTUATION", "."):
                peek_tok = self.peek()
                if peek_tok.type == "KEYWORD" and peek_tok.value.upper() in ("WITH", "POINTER", "TALLYING", "ON", "NOT", "END-UNSTRING"):
                    break
                if is_tok_statement_start(peek_tok):
                    break
                if self.match("PUNCTUATION", ","):
                    continue
                tgt_tok = self.consume("IDENTIFIER", None, "Expected target identifier in UNSTRING")
                targets.append(tgt_tok.value)
                
            pointer_var = None
            tally_var = None
            on_overflow_nodes = []
            not_on_overflow_nodes = []
            
            while not self.is_at_end() and not self.check("PUNCTUATION", ".") and not self.sentence_ended:
                if self.match("KEYWORD", "WITH") or self.check("KEYWORD", "POINTER"):
                    if not self.match("KEYWORD", "POINTER"):
                        self.match("KEYWORD", "POINTER")
                    pointer_tok = self.consume("IDENTIFIER", None, "Expected POINTER variable")
                    pointer_var = pointer_tok.value
                elif self.match("KEYWORD", "TALLYING"):
                    if self.match("KEYWORD", "IN"):
                        pass
                    tally_tok = self.consume("IDENTIFIER", None, "Expected TALLYING variable")
                    tally_var = tally_tok.value
                elif self.match("KEYWORD", "ON") or self.check("KEYWORD", "OVERFLOW"):
                    if self.peek(-1).value.upper() == "ON" and self.match("KEYWORD", "OVERFLOW"):
                        pass
                    elif self.match("KEYWORD", "OVERFLOW"):
                        pass
                    on_overflow_nodes = self.parse_nested_statements_block(
                        ["NOT", "END-UNSTRING"]
                    )
                elif self.match("KEYWORD", "NOT"):
                    self.consume("KEYWORD", "ON", "Expected ON after NOT")
                    self.consume("KEYWORD", "OVERFLOW", "Expected OVERFLOW after ON")
                    not_on_overflow_nodes = self.parse_nested_statements_block(
                        ["END-UNSTRING"]
                    )
                elif self.match("KEYWORD", "END-UNSTRING"):
                    break
                else:
                    break
                    
            self.match_statement_period()
            
            node = SemanticIRNode(
                node_id=self.next_node_id(),
                kind="STATEMENT",
                properties={
                    "statement_type": "UNSTRING",
                    "source": source_tok.value,
                    "delimited_by": delimited_by,
                    "targets": targets,
                    "pointer": pointer_var,
                    "tallying": tally_var,
                    "on_overflow_nodes": on_overflow_nodes,
                    "not_on_overflow_nodes": not_on_overflow_nodes
                },
                source_file=self.file_path,
                source_line=start_tok.line,
                source_column=start_tok.column,
                start_offset=start_tok.start_offset,
                end_offset=self.peek().start_offset,
                status="PARSED"
            )
            self.ir.add_node(node)

        elif self.match("KEYWORD", "INSPECT"):
            target_tok = self.consume("IDENTIFIER", None, "Expected target identifier in INSPECT")
            
            inspect_type = None
            tally_var = None
            tally_type = None
            tally_search = None
            replacements = []
            converting_from = None
            converting_to = None
            
            if self.match("KEYWORD", "TALLYING"):
                inspect_type = "TALLYING"
                tally_var = self.consume("IDENTIFIER", None, "Expected tally variable").value
                self.consume("KEYWORD", "FOR", "Expected FOR in INSPECT TALLYING")
                
                if self.match("KEYWORD", "CHARACTERS"):
                    tally_type = "CHARACTERS"
                elif self.match("KEYWORD", "ALL"):
                    tally_type = "ALL"
                    search_tok = self.consume_val("Expected search value after ALL")
                    tally_search = search_tok.value
                elif self.match("KEYWORD", "LEADING"):
                    tally_type = "LEADING"
                    search_tok = self.consume_val("Expected search value after LEADING")
                    tally_search = search_tok.value
                else:
                    raise ParserDiagnostic("Expected CHARACTERS, ALL, or LEADING in INSPECT TALLYING", self.file_path, self.peek().line, self.peek().column, self.peek().value, "")
                    
            elif self.match("KEYWORD", "REPLACING"):
                inspect_type = "REPLACING"
                while not self.is_at_end() and not self.check("PUNCTUATION", "."):
                    peek_tok = self.peek()
                    if peek_tok.type != "KEYWORD" or peek_tok.value.upper() not in ("CHARACTERS", "ALL", "LEADING", "FIRST"):
                        break
                        
                    rep_type = None
                    search_val = None
                    
                    if self.match("KEYWORD", "CHARACTERS"):
                        rep_type = "CHARACTERS"
                        self.consume("KEYWORD", "BY", "Expected BY after CHARACTERS")
                        rep_val = self.consume_val("Expected replacement value").value
                    elif self.match("KEYWORD", "ALL"):
                        rep_type = "ALL"
                        search_val = self.consume_val("Expected search value").value
                        self.consume("KEYWORD", "BY", "Expected BY after search value")
                        rep_val = self.consume_val("Expected replacement value").value
                    elif self.match("KEYWORD", "LEADING"):
                        rep_type = "LEADING"
                        search_val = self.consume_val("Expected search value").value
                        self.consume("KEYWORD", "BY", "Expected BY after search value")
                        rep_val = self.consume_val("Expected replacement value").value
                    elif self.match("KEYWORD", "FIRST"):
                        rep_type = "FIRST"
                        search_val = self.consume_val("Expected search value").value
                        self.consume("KEYWORD", "BY", "Expected BY after search value")
                        rep_val = self.consume_val("Expected replacement value").value
                    else:
                        break
                    replacements.append({
                        "type": rep_type,
                        "search": search_val,
                        "replace": rep_val
                    })
                    
            elif self.match("KEYWORD", "CONVERTING"):
                inspect_type = "CONVERTING"
                from_tok = self.consume_val("Expected source characters in CONVERTING")
                self.consume("KEYWORD", "TO", "Expected TO in CONVERTING")
                to_tok = self.consume_val("Expected destination characters in CONVERTING")
                converting_from = from_tok.value
                converting_to = to_tok.value
            else:
                raise ParserDiagnostic("Expected TALLYING, REPLACING, or CONVERTING in INSPECT", self.file_path, self.peek().line, self.peek().column, self.peek().value, "")
                
            self.match_statement_period()
            
            node = SemanticIRNode(
                node_id=self.next_node_id(),
                kind="STATEMENT",
                properties={
                    "statement_type": "INSPECT",
                    "target": target_tok.value,
                    "inspect_type": inspect_type,
                    "tally_var": tally_var,
                    "tally_type": tally_type,
                    "tally_search": tally_search,
                    "replacements": replacements,
                    "converting_from": converting_from,
                    "converting_to": converting_to
                },
                source_file=self.file_path,
                source_line=start_tok.line,
                source_column=start_tok.column,
                start_offset=start_tok.start_offset,
                end_offset=self.peek().start_offset,
                status="PARSED"
            )
            self.ir.add_node(node)

        elif self.match("KEYWORD", "CALL"):
            tgt_tok = self.consume_val("Expected subprogram target name")
            
            args = []
            args_info = []
            if self.match("KEYWORD", "USING"):
                current_mode = "REFERENCE"
                while not self.is_at_end() and not self.check("PUNCTUATION", ".") and not (self.check("KEYWORD") and self.peek().value.upper() in ("RETURNING", "GIVING")) and not is_tok_statement_start(self.peek()):
                    if self.match("KEYWORD", "BY"):
                        next_val = self.peek().value.upper()
                        if next_val == "REFERENCE":
                            self.current += 1
                            current_mode = "REFERENCE"
                            continue
                        elif next_val == "CONTENT":
                            self.current += 1
                            current_mode = "CONTENT"
                            continue
                        elif next_val == "VALUE":
                            self.current += 1
                            current_mode = "VALUE"
                            continue
                        else:
                            raise ParserDiagnostic("Expected REFERENCE, CONTENT, or VALUE after BY", self.file_path, self.peek().line, self.peek().column, self.peek().value, "")
                    
                    tok = self.consume_val("Expected USING argument name")
                    args.append(tok.value)
                    args_info.append({
                        "value": tok.value,
                        "mode": current_mode
                    })
            
            returning_val = None
            if self.match("KEYWORD", "RETURNING") or self.match("KEYWORD", "GIVING"):
                ret_tok = self.consume_val("Expected returning identifier")
                returning_val = ret_tok.value
            
            self.match("PUNCTUATION", ".")
            
            node = SemanticIRNode(
                node_id=self.next_node_id(),
                kind="STATEMENT",
                properties={
                    "statement_type": "CALL",
                    "target": tgt_tok.value,
                    "arguments": args,
                    "arguments_info": args_info,
                    "returning": returning_val
                },
                source_file=self.file_path,
                source_line=start_tok.line,
                source_column=start_tok.column,
                start_offset=start_tok.start_offset,
                end_offset=self.peek().start_offset,
                status="PARSED"
            )
            self.ir.add_node(node)

        elif self.match("KEYWORD", "READ") or self.match("KEYWORD", "WRITE") or self.match("KEYWORD", "REWRITE") or self.match("KEYWORD", "DELETE") or self.match("KEYWORD", "START"):
            op = self.peek(-1).value.upper()
            file_tok = self.consume("IDENTIFIER", None, f"Expected file identifier after {op}")
            
            from_source = None
            into_target = None
            at_end_nodes = []
            not_at_end_nodes = []
            invalid_key_nodes = []
            not_invalid_key_nodes = []
            key_operator = None
            key_name = None
            is_next = False
            
            if op in ("WRITE", "REWRITE") and self.match("KEYWORD", "FROM"):
                from_tok = self.consume_val("Expected source identifier/literal after FROM")
                # Preserve literal-ness: string literals are re-quoted so the
                # generator can distinguish them from data identifiers.
                if from_tok.type == "LITERAL_STRING":
                    from_source = f'"{from_tok.value}"'
                elif from_tok.type == "NUMBER":
                    from_source = str(from_tok.value)
                else:
                    from_source = from_tok.value
            elif op == "READ":
                if self.match("KEYWORD", "NEXT"):
                    is_next = True
                if self.match("KEYWORD", "RECORD"):
                    pass
                if self.match("KEYWORD", "INTO"):
                    into_tok = self.consume("IDENTIFIER", None, "Expected target identifier after INTO")
                    into_target = into_tok.value
                if self.match("KEYWORD", "NEXT"):
                    is_next = True
                if self.match("KEYWORD", "KEY"):
                    self.match("KEYWORD", "IS")
                    key_tok = self.consume("IDENTIFIER", None, "Expected key variable identifier in READ statement")
                    key_name = key_tok.value
            elif op == "DELETE":
                self.match("KEYWORD", "RECORD")
            elif op == "START":
                if self.match("KEYWORD", "KEY"):
                    self.match("KEYWORD", "IS")
                    if self.match("KEYWORD", "EQUAL"):
                        self.match("KEYWORD", "TO")
                        key_operator = "="
                    elif self.match("PUNCTUATION", "="):
                        key_operator = "="
                    elif self.match("KEYWORD", "GREATER"):
                        self.match("KEYWORD", "THAN")
                        key_operator = ">"
                    elif self.match("PUNCTUATION", ">"):
                        key_operator = ">"
                    elif self.match("KEYWORD", "NOT"):
                        self.consume("KEYWORD", "LESS")
                        self.match("KEYWORD", "THAN")
                        key_operator = ">="
                    elif self.match("PUNCTUATION", ">="):
                        key_operator = ">="
                    else:
                        raise ParserDiagnostic("Expected relation operator in START KEY clause", self.file_path, self.peek().line, self.peek().column, self.peek().value, "START statement")
                    
                    key_tok = self.consume("IDENTIFIER", None, "Expected key variable identifier in START statement")
                    key_name = key_tok.value
                    
            # Parse clauses for all READ/WRITE/REWRITE/DELETE/START
            in_at_end = False
            in_not_at_end = False
            in_invalid_key = False
            in_not_invalid_key = False
            
            while not self.is_at_end():
                if self.check("KEYWORD", "AT") and not self.is_at_end():
                    self.current += 1
                    if self.match("KEYWORD", "END"):
                        in_at_end = True
                        in_not_at_end = False
                        in_invalid_key = False
                        in_not_invalid_key = False
                        continue
                    self.current -= 1
                    break
                elif self.check("KEYWORD", "INVALID") and not self.is_at_end():
                    self.current += 1
                    if self.match("KEYWORD", "KEY"):
                        in_invalid_key = True
                        in_not_invalid_key = False
                        in_at_end = False
                        in_not_at_end = False
                        continue
                    self.current -= 1
                    break
                elif self.check("KEYWORD", "NOT") and not self.is_at_end():
                    self.current += 1
                    if self.check("KEYWORD", "AT"):
                        self.current += 1
                        if self.match("KEYWORD", "END"):
                            in_not_at_end = True
                            in_at_end = False
                            in_invalid_key = False
                            in_not_invalid_key = False
                            continue
                        self.current -= 1
                    elif self.check("KEYWORD", "INVALID"):
                        self.current += 1
                        if self.match("KEYWORD", "KEY"):
                            in_not_invalid_key = True
                            in_invalid_key = False
                            in_at_end = False
                            in_not_at_end = False
                            continue
                        self.current -= 1
                    self.current -= 1
                    break
                elif self.check("KEYWORD", f"END-{op}"):
                    self.current += 1
                    break
                elif in_at_end or in_not_at_end or in_invalid_key or in_not_invalid_key:
                    tok = self.peek()
                    if is_tok_statement_start(tok) and tok.value.upper() not in ("AT", "NOT", f"END-{op}", "INVALID"):
                        stmt_node = None
                        if self.match("KEYWORD", "MOVE"):
                            src_tok = self.consume_val("Expected source in MOVE")
                            self.consume("KEYWORD", "TO", "Expected TO")
                            in_targets = []
                            while self.check("IDENTIFIER"):
                                in_targets.append(self.peek().value)
                                self.current += 1
                            if not in_targets:
                                in_t = self.consume("IDENTIFIER", None, "Expected target")
                                in_targets = [in_t.value]
                            stmt_node = SemanticIRNode(
                                node_id=self.next_node_id(),
                                kind="STATEMENT",
                                properties={"statement_type": "MOVE", "source": src_tok.value, "targets": in_targets},
                                source_file=self.file_path,
                                source_line=tok.line,
                                source_column=tok.column,
                                start_offset=tok.start_offset,
                                end_offset=self.peek().start_offset,
                                status="PARSED"
                            )
                        elif self.match("KEYWORD", "WRITE") or self.match("KEYWORD", "REWRITE"):
                            w_op = self.peek(-1).value.upper()
                            file_tok2 = self.consume("IDENTIFIER", None, f"Expected file/record after {w_op}")
                            from_src = None
                            if self.match("KEYWORD", "FROM"):
                                from_tok2 = self.consume_val("Expected source after FROM")
                                from_src = from_tok2.value
                            stmt_node = SemanticIRNode(
                                node_id=self.next_node_id(),
                                kind="STATEMENT",
                                properties={"statement_type": w_op, "target": file_tok2.value, "from_source": from_src, "into_target": None, "at_end_nodes": [], "not_at_end_nodes": []},
                                source_file=self.file_path,
                                source_line=tok.line,
                                source_column=tok.column,
                                start_offset=tok.start_offset,
                                end_offset=self.peek().start_offset,
                                status="PARSED"
                            )
                        elif self.match("KEYWORD", "PERFORM"):
                            tgt_tok = self.consume("IDENTIFIER", None, "Expected paragraph name after PERFORM")
                            props = {"statement_type": "PERFORM", "target": tgt_tok.value}
                            if self.match("KEYWORD", "THRU"):
                                thru_tok = self.consume("IDENTIFIER", None, "Expected THRU paragraph name")
                                props["thru"] = thru_tok.value
                            if self.match("KEYWORD", "UNTIL"):
                                cond_parts = []
                                while not self.is_at_end() and not self.check("PUNCTUATION", "."):
                                    tok = self.peek()
                                    if is_tok_statement_start(tok):
                                        break
                                    self.current += 1
                                    if tok.type == "LITERAL_STRING":
                                        cond_parts.append(f'"{tok.value}"')
                                    else:
                                        cond_parts.append(tok.value)
                                props["statement_type"] = "PERFORM_UNTIL_OUT"
                                props["condition"] = " ".join(cond_parts)
                            stmt_node = SemanticIRNode(
                                node_id=self.next_node_id(),
                                kind="STATEMENT",
                                properties=props,
                                source_file=self.file_path,
                                source_line=tok.line,
                                source_column=tok.column,
                                start_offset=tok.start_offset,
                                end_offset=self.peek().start_offset,
                                status="PARSED"
                            )
                        elif self.match("KEYWORD", "DISPLAY"):
                            operands = []
                            while not self.is_at_end() and not self.check("PUNCTUATION", "."):
                                tok2 = self.peek()
                                if is_tok_statement_start(tok2) or tok2.value.upper() in ("AT", "NOT", "INVALID", f"END-{op}"):
                                    break
                                val_tok = self.consume_val("Expected display operand")
                                operands.append({
                                    "type": "literal" if val_tok.type == "LITERAL_STRING" else "variable",
                                    "value": val_tok.value
                                })
                            stmt_node = SemanticIRNode(
                                node_id=self.next_node_id(),
                                kind="STATEMENT",
                                properties={"statement_type": "DISPLAY", "operands": operands},
                                source_file=self.file_path,
                                source_line=tok.line,
                                source_column=tok.column,
                                start_offset=tok.start_offset,
                                end_offset=self.peek().start_offset,
                                status="PARSED"
                            )
                        elif self.match("KEYWORD", "STOP"):
                            self.consume("KEYWORD", "RUN")
                            stmt_node = SemanticIRNode(
                                node_id=self.next_node_id(),
                                kind="STATEMENT",
                                properties={"statement_type": "STOP RUN"},
                                source_file=self.file_path,
                                source_line=tok.line,
                                source_column=tok.column,
                                start_offset=tok.start_offset,
                                end_offset=self.peek().start_offset,
                                status="PARSED"
                            )
                        elif self.match("KEYWORD", "GOBACK"):
                            stmt_node = SemanticIRNode(
                                node_id=self.next_node_id(),
                                kind="STATEMENT",
                                properties={"statement_type": "GOBACK"},
                                source_file=self.file_path,
                                source_line=tok.line,
                                source_column=tok.column,
                                start_offset=tok.start_offset,
                                end_offset=self.peek().start_offset,
                                status="PARSED"
                            )
                        elif self.match("KEYWORD", "CONTINUE"):
                            stmt_node = SemanticIRNode(
                                node_id=self.next_node_id(),
                                kind="STATEMENT",
                                properties={"statement_type": "CONTINUE"},
                                source_file=self.file_path,
                                source_line=tok.line,
                                source_column=tok.column,
                                start_offset=tok.start_offset,
                                end_offset=self.peek().start_offset,
                                status="PARSED"
                            )
                        elif self.match("KEYWORD", "ADD"):
                            # ADD <value> TO <target> [GIVING <target>]
                            operands = []
                            while not self.is_at_end() and not self.check("KEYWORD", "TO"):
                                tk = self.peek()
                                if is_tok_statement_start(tk):
                                    break
                                operands.append(self.consume_val("Expected ADD operand").value)
                            targets = []
                            if self.match("KEYWORD", "TO"):
                                while not self.is_at_end():
                                    tk2 = self.peek()
                                    if is_tok_statement_start(tk2) or tk2.value.upper() in ("GIVING",):
                                        break
                                    if tk2.type not in ("IDENTIFIER", "NUMBER"):
                                        break
                                    targets.append(self.consume_val("Expected ADD target").value)
                            giving = None
                            if self.match("KEYWORD", "GIVING"):
                                giving = self.consume_val("Expected GIVING target").value
                            stmt_node = SemanticIRNode(
                                node_id=self.next_node_id(),
                                kind="STATEMENT",
                                properties={"statement_type": "ADD", "operands": operands, "targets": targets, "giving": giving},
                                source_file=self.file_path,
                                source_line=tok.line,
                                source_column=tok.column,
                                start_offset=tok.start_offset,
                                end_offset=self.peek().start_offset,
                                status="PARSED"
                            )
                        elif self.match("KEYWORD", "SUBTRACT"):
                            # SUBTRACT <value> FROM <target>
                            operands = []
                            while not self.is_at_end() and not self.check("KEYWORD", "FROM"):
                                tk = self.peek()
                                if is_tok_statement_start(tk):
                                    break
                                operands.append(self.consume_val("Expected SUBTRACT operand").value)
                            targets = []
                            if self.match("KEYWORD", "FROM"):
                                while not self.is_at_end():
                                    tk2 = self.peek()
                                    if is_tok_statement_start(tk2):
                                        break
                                    if tk2.type not in ("IDENTIFIER", "NUMBER"):
                                        break
                                    targets.append(self.consume_val("Expected SUBTRACT target").value)
                            stmt_node = SemanticIRNode(
                                node_id=self.next_node_id(),
                                kind="STATEMENT",
                                properties={"statement_type": "SUBTRACT", "operands": operands, "targets": targets},
                                source_file=self.file_path,
                                source_line=tok.line,
                                source_column=tok.column,
                                start_offset=tok.start_offset,
                                end_offset=self.peek().start_offset,
                                status="PARSED"
                            )
                        elif self.match("KEYWORD", "IF"):
                            # Parse IF <condition> <body> END-IF inside an AT-END block.
                            # Collect condition tokens until we hit a STATEMENT_START_VERB.
                            cond_toks = []
                            while not self.is_at_end():
                                tk2 = self.peek()
                                if is_tok_statement_start(tk2) and tk2.value.upper() not in ("THEN",):
                                    break
                                if tk2.type == "KEYWORD" and tk2.value.upper() in ("END-IF",):
                                    break
                                self.current += 1
                                if tk2.type == "LITERAL_STRING":
                                    cond_toks.append(f'"{tk2.value}"')
                                else:
                                    cond_toks.append(tk2.value)
                            cond_str = " ".join(cond_toks)
                            # Emit IF node
                            stmt_node = SemanticIRNode(
                                node_id=self.next_node_id(),
                                kind="STATEMENT",
                                properties={"statement_type": "IF", "condition": cond_str},
                                source_file=self.file_path,
                                source_line=tok.line,
                                source_column=tok.column,
                                start_offset=tok.start_offset,
                                end_offset=self.peek().start_offset,
                                status="PARSED"
                            )
                            if in_at_end:
                                at_end_nodes.append(stmt_node)
                            elif in_not_at_end:
                                not_at_end_nodes.append(stmt_node)
                            stmt_node = None  # Will be added by the body loop below
                            # Parse body statements until END-IF
                            while not self.is_at_end():
                                bk = self.peek()
                                if bk.type == "KEYWORD" and bk.value.upper() == "END-IF":
                                    self.current += 1
                                    break
                                body_stmt = None
                                if self.match("KEYWORD", "ADD"):
                                    b_ops = []
                                    while not self.is_at_end() and not self.check("KEYWORD", "TO"):
                                        bk2 = self.peek()
                                        if is_tok_statement_start(bk2):
                                            break
                                        b_ops.append(self.consume_val("Expected ADD operand").value)
                                    b_tgts = []
                                    if self.match("KEYWORD", "TO"):
                                        while not self.is_at_end():
                                            bk3 = self.peek()
                                            if is_tok_statement_start(bk3):
                                                break
                                            if bk3.type not in ("IDENTIFIER", "NUMBER"):
                                                break
                                            b_tgts.append(self.consume_val("Expected ADD target").value)
                                    body_stmt = SemanticIRNode(
                                        node_id=self.next_node_id(),
                                        kind="STATEMENT",
                                        properties={"statement_type": "ADD", "operands": b_ops, "targets": b_tgts},
                                        source_file=self.file_path,
                                        source_line=bk.line,
                                        source_column=bk.column,
                                        start_offset=bk.start_offset,
                                        end_offset=self.peek().start_offset,
                                        status="PARSED"
                                    )
                                elif self.match("KEYWORD", "MOVE"):
                                    src_tok2 = self.consume_val("Expected source in MOVE")
                                    self.consume("KEYWORD", "TO", "Expected TO")
                                    b_tgts = []
                                    while self.check("IDENTIFIER"):
                                        b_tgts.append(self.peek().value)
                                        self.current += 1
                                    if not b_tgts:
                                        b_t = self.consume("IDENTIFIER", None, "Expected target")
                                        b_tgts = [b_t.value]
                                    body_stmt = SemanticIRNode(
                                        node_id=self.next_node_id(),
                                        kind="STATEMENT",
                                        properties={"statement_type": "MOVE", "source": src_tok2.value, "targets": b_tgts},
                                        source_file=self.file_path,
                                        source_line=bk.line,
                                        source_column=bk.column,
                                        start_offset=bk.start_offset,
                                        end_offset=self.peek().start_offset,
                                        status="PARSED"
                                    )
                                else:
                                    # Skip unknown token inside IF body
                                    self.current += 1
                                if body_stmt:
                                    if in_at_end:
                                        at_end_nodes.append(body_stmt)
                                    elif in_not_at_end:
                                        not_at_end_nodes.append(body_stmt)
                            # Emit END-IF node
                            end_if_node = SemanticIRNode(
                                node_id=self.next_node_id(),
                                kind="STATEMENT",
                                properties={"statement_type": "END-IF"},
                                source_file=self.file_path,
                                source_line=tok.line,
                                source_column=tok.column,
                                start_offset=tok.start_offset,
                                end_offset=self.peek().start_offset,
                                status="PARSED"
                            )
                            if in_at_end:
                                at_end_nodes.append(end_if_node)
                            elif in_not_at_end:
                                not_at_end_nodes.append(end_if_node)
                            continue
                        
                        if stmt_node:
                            if in_at_end:
                                at_end_nodes.append(stmt_node)
                            elif in_not_at_end:
                                not_at_end_nodes.append(stmt_node)
                            elif in_invalid_key:
                                invalid_key_nodes.append(stmt_node)
                            elif in_not_invalid_key:
                                not_invalid_key_nodes.append(stmt_node)
                        else:
                            break
                    else:
                        break
                else:
                    break
            
            self.match_statement_period()
            
            node = SemanticIRNode(
                node_id=self.next_node_id(),
                kind="STATEMENT",
                properties={
                    "statement_type": op,
                    "target": file_tok.value,
                    "from_source": from_source,
                    "into_target": into_target,
                    "at_end_nodes": at_end_nodes,
                    "not_at_end_nodes": not_at_end_nodes,
                    "invalid_key_nodes": invalid_key_nodes,
                    "not_invalid_key_nodes": not_invalid_key_nodes,
                    "key_operator": key_operator,
                    "key_name": key_name,
                    "is_next": is_next
                },
                source_file=self.file_path,
                source_line=start_tok.line,
                source_column=start_tok.column,
                start_offset=start_tok.start_offset,
                end_offset=self.peek().start_offset,
                status="PARSED"
            )
            self.ir.add_node(node)

        elif self.match("KEYWORD", "OPEN") or self.match("KEYWORD", "CLOSE"):
            op = self.peek(-1).value.upper()
            targets = []
            if op == "OPEN":
                # Support: OPEN INPUT F1 F2 OUTPUT F3 F4
                while not self.is_at_end() and not self.check("PUNCTUATION", ".") and not is_tok_statement_start(self.peek()):
                    if self.check("KEYWORD") and self.peek().value.upper() in ("INPUT", "OUTPUT", "I-O", "EXTEND"):
                        mode_kw = self.peek().value.upper()
                        self.current += 1
                        targets.append(mode_kw)
                    file_tok = self.consume("IDENTIFIER", None, "Expected file identifier after OPEN mode")
                    targets.append(file_tok.value)
            else:
                while not self.is_at_end() and not self.check("PUNCTUATION", ".") and not is_tok_statement_start(self.peek()):
                    file_tok = self.consume("IDENTIFIER", None, "Expected file identifier after CLOSE")
                    targets.append(file_tok.value)
                
            self.match_statement_period()
            
            node = SemanticIRNode(
                node_id=self.next_node_id(),
                kind="STATEMENT",
                properties={
                    "statement_type": op,
                    "targets": targets
                },
                source_file=self.file_path,
                source_line=start_tok.line,
                source_column=start_tok.column,
                start_offset=start_tok.start_offset,
                end_offset=self.peek().start_offset,
                status="PARSED"
            )
            self.ir.add_node(node)

        elif self.match("KEYWORD", "EVALUATE"):
            subjects = []
            subjects.append(self.consume_val("Expected subject after EVALUATE").value)
            while self.match("KEYWORD", "ALSO") or self.match("IDENTIFIER", "ALSO"):
                subjects.append(self.consume_val("Expected subject after ALSO").value)
            self.match_statement_period()
            self.block_stack.append("EVALUATE")
            
            node = SemanticIRNode(
                node_id=self.next_node_id(),
                kind="STATEMENT",
                properties={
                    "statement_type": "EVALUATE",
                    "subject": subjects[0],
                    "subjects": subjects
                },
                source_file=self.file_path,
                source_line=start_tok.line,
                source_column=start_tok.column,
                start_offset=start_tok.start_offset,
                end_offset=self.peek().start_offset,
                status="PARSED"
            )
            self.ir.add_node(node)

        elif self.match("KEYWORD", "WHEN"):
            cond_parts = []
            while not self.is_at_end() and not self.check("PUNCTUATION", "."):
                tok = self.peek()
                if is_tok_statement_start(tok):
                    break
                self.current += 1
                if tok.type == "LITERAL_STRING":
                    cond_parts.append(f'"{tok.value}"')
                else:
                    cond_parts.append(tok.value)
            
            cond_str = " ".join(cond_parts)
            self.match_statement_period()
            
            node = SemanticIRNode(
                node_id=self.next_node_id(),
                kind="STATEMENT",
                properties={
                    "statement_type": "WHEN",
                    "condition": cond_str
                },
                source_file=self.file_path,
                source_line=start_tok.line,
                source_column=start_tok.column,
                start_offset=start_tok.start_offset,
                end_offset=self.peek().start_offset,
                status="PARSED"
            )
            self.ir.add_node(node)

        elif self.match("KEYWORD", "STOP") or self.match("KEYWORD", "GOBACK"):
            val = self.peek(-1).value.upper()
            if val == "STOP":
                self.consume("KEYWORD", "RUN", "Expected RUN after STOP")
                val = "STOP RUN"
            self.match_statement_period()
            
            node = SemanticIRNode(
                node_id=self.next_node_id(),
                kind="STATEMENT",
                properties={
                    "statement_type": val
                },
                source_file=self.file_path,
                source_line=start_tok.line,
                source_column=start_tok.column,
                start_offset=start_tok.start_offset,
                end_offset=self.peek().start_offset,
                status="PARSED"
            )
            self.ir.add_node(node)
        elif self.match("KEYWORD", "GO"):
            self.consume("KEYWORD", "TO", "Expected TO after GO")
            tgt_tok = self.consume("IDENTIFIER", None, "Expected paragraph/section name after GO TO")
            self.match_statement_period()
            
            node = SemanticIRNode(
                node_id=self.next_node_id(),
                kind="STATEMENT",
                properties={
                    "statement_type": "GO TO",
                    "target": tgt_tok.value
                },
                source_file=self.file_path,
                source_line=start_tok.line,
                source_column=start_tok.column,
                start_offset=start_tok.start_offset,
                end_offset=self.peek().start_offset,
                status="PARSED"
            )
            self.ir.add_node(node)
        elif self.match("KEYWORD", "NEXT"):
            if self.match("KEYWORD", "SENTENCE") or self.match("IDENTIFIER", "SENTENCE"):
                self.match_statement_period()
                node = SemanticIRNode(
                    node_id=self.next_node_id(),
                    kind="STATEMENT",
                    properties={
                        "statement_type": "NEXT SENTENCE"
                    },
                    source_file=self.file_path,
                    source_line=start_tok.line,
                    source_column=start_tok.column,
                    start_offset=start_tok.start_offset,
                    end_offset=self.peek().start_offset,
                    status="PARSED"
                )
                self.ir.add_node(node)

        elif self.match("KEYWORD", "CONTINUE"):
            self.match_statement_period()
            node = SemanticIRNode(
                node_id=self.next_node_id(),
                kind="STATEMENT",
                properties={
                    "statement_type": "CONTINUE"
                },
                source_file=self.file_path,
                source_line=start_tok.line,
                source_column=start_tok.column,
                start_offset=start_tok.start_offset,
                end_offset=self.peek().start_offset,
                status="PARSED"
            )
            self.ir.add_node(node)

        elif self.match("KEYWORD", "EXIT"):
            exit_type = "EXIT"
            if self.match("KEYWORD", "PERFORM") or self.match("IDENTIFIER", "PERFORM"):
                exit_type = "EXIT PERFORM"
            elif self.match("KEYWORD", "PARAGRAPH") or self.match("IDENTIFIER", "PARAGRAPH"):
                exit_type = "EXIT PARAGRAPH"
            elif self.match("KEYWORD", "PROGRAM") or self.match("IDENTIFIER", "PROGRAM"):
                exit_type = "EXIT_PROGRAM"
            elif self.match("KEYWORD", "SECTION") or self.match("IDENTIFIER", "SECTION"):
                exit_type = "EXIT SECTION"
            
            self.match_statement_period()
            
            node = SemanticIRNode(
                node_id=self.next_node_id(),
                kind="STATEMENT",
                properties={
                    "statement_type": exit_type
                },
                source_file=self.file_path,
                source_line=start_tok.line,
                source_column=start_tok.column,
                start_offset=start_tok.start_offset,
                end_offset=self.peek().start_offset,
                status="PARSED"
            )
            self.ir.add_node(node)

        elif self.match("KEYWORD", "END-IF") or self.match("KEYWORD", "END-PERFORM") or self.match("KEYWORD", "END-READ") or self.match("KEYWORD", "END-WRITE") or self.match("KEYWORD", "END-EVALUATE"):
            val = self.peek(-1).value.upper()
            block_type = val[4:]  # IF, PERFORM, EVALUATE, READ, WRITE
            if self.block_stack and self.block_stack[-1] == block_type:
                self.block_stack.pop()
            self.match_statement_period()
            
            node = SemanticIRNode(
                node_id=self.next_node_id(),
                kind="STATEMENT",
                properties={
                    "statement_type": val
                },
                source_file=self.file_path,
                source_line=start_tok.line,
                source_column=start_tok.column,
                start_offset=start_tok.start_offset,
                end_offset=self.peek().start_offset,
                status="PARSED"
            )
            self.ir.add_node(node)

        elif self.check("EXEC_SQL"):
            tok = self.peek()
            self.current += 1
            self.parse_exec_sql(tok)

        elif self.check("EXEC_CICS"):
            tok = self.peek()
            self.current += 1
            self.parse_exec_cics(tok)

        elif self.match("KEYWORD", "SORT") or self.match("KEYWORD", "MERGE"):
            verb = self.peek(-1).value.upper()
            work_file = self.consume("IDENTIFIER", None, "Expected work file name").value
            
            # Keys parsing
            keys = []
            while self.match("KEYWORD", "ON"):
                order = "ASCENDING"
                if self.match("KEYWORD", "ASCENDING") or self.match("KEYWORD", "DESCENDING"):
                    order = self.peek(-1).value.upper()
                self.match("KEYWORD", "KEY") # Optional KEY keyword
                while self.check("IDENTIFIER"):
                    k_name = self.consume("IDENTIFIER").value
                    keys.append({"name": k_name, "order": order})
            
            # Input clause
            using_files = []
            input_procedure = None
            if self.match("KEYWORD", "USING"):
                while self.check("IDENTIFIER"):
                    using_files.append(self.consume("IDENTIFIER").value)
            elif self.match("KEYWORD", "INPUT"):
                self.consume("KEYWORD", "PROCEDURE")
                if self.match("KEYWORD", "IS"): pass
                input_procedure = self.consume("IDENTIFIER").value
                if self.match("KEYWORD", "THRU") or self.match("KEYWORD", "THROUGH"):
                    thru_para = self.consume("IDENTIFIER").value
                    input_procedure = f"{input_procedure} THRU {thru_para}"
                    
            # Output clause
            giving_files = []
            output_procedure = None
            if self.match("KEYWORD", "GIVING"):
                while self.check("IDENTIFIER"):
                    giving_files.append(self.consume("IDENTIFIER").value)
            elif self.match("KEYWORD", "OUTPUT"):
                self.consume("KEYWORD", "PROCEDURE")
                if self.match("KEYWORD", "IS"): pass
                output_procedure = self.consume("IDENTIFIER").value
                if self.match("KEYWORD", "THRU") or self.match("KEYWORD", "THROUGH"):
                    thru_para = self.consume("IDENTIFIER").value
                    output_procedure = f"{output_procedure} THRU {thru_para}"
                    
            self.match_statement_period()
            
            node = SemanticIRNode(
                node_id=self.next_node_id(),
                kind="STATEMENT",
                properties={
                    "statement_type": verb,
                    "work_file": work_file,
                    "keys": keys,
                    "using_files": using_files,
                    "giving_files": giving_files,
                    "input_procedure": input_procedure,
                    "output_procedure": output_procedure
                },
                source_file=self.file_path,
                source_line=start_tok.line,
                source_column=start_tok.column,
                start_offset=start_tok.start_offset,
                end_offset=self.peek().start_offset,
                status="PARSED"
            )
            self.ir.add_node(node)

        elif self.match("KEYWORD", "RELEASE"):
            rec_name = self.consume("IDENTIFIER", None, "Expected record name in RELEASE").value
            from_val = None
            if self.match("KEYWORD", "FROM"):
                from_val = self.consume_val_or_subscript().value
            
            self.match_statement_period()
            
            node = SemanticIRNode(
                node_id=self.next_node_id(),
                kind="STATEMENT",
                properties={
                    "statement_type": "RELEASE",
                    "record_name": rec_name,
                    "from_val": from_val
                },
                source_file=self.file_path,
                source_line=start_tok.line,
                source_column=start_tok.column,
                start_offset=start_tok.start_offset,
                end_offset=self.peek().start_offset,
                status="PARSED"
            )
            self.ir.add_node(node)

        elif self.match("KEYWORD", "RETURN"):
            work_file = self.consume("IDENTIFIER", None, "Expected work file name in RETURN").value
            self.match("KEYWORD", "RECORD") # Optional
            into_val = None
            if self.match("KEYWORD", "INTO"):
                into_val = self.consume_subscripted_identifier().value
            
            at_end_action = None
            if self.match("KEYWORD", "AT") or self.match("KEYWORD", "END"):
                if self.peek(-1).value.upper() == "AT":
                    self.consume("KEYWORD", "END")
                
                # Check for MOVE or SET statements directly inline
                if self.check("KEYWORD", "MOVE"):
                    self.consume("KEYWORD", "MOVE")
                    src = self.consume_val().value
                    self.consume("KEYWORD", "TO")
                    tgt = self.consume_subscripted_identifier().value
                    at_end_action = f"MOVE {src} TO {tgt}"
                elif self.check("KEYWORD", "SET"):
                    self.consume("KEYWORD", "SET")
                    tgt = self.consume_subscripted_identifier().value
                    self.consume("KEYWORD", "TO")
                    src = self.consume_val().value
                    at_end_action = f"SET {tgt} TO {src}"
            
            if self.match("KEYWORD", "END-RETURN"):
                pass
            self.match_statement_period()
            
            node = SemanticIRNode(
                node_id=self.next_node_id(),
                kind="STATEMENT",
                properties={
                    "statement_type": "RETURN",
                    "work_file": work_file,
                    "into_val": into_val,
                    "at_end_action": at_end_action
                },
                source_file=self.file_path,
                source_line=start_tok.line,
                source_column=start_tok.column,
                start_offset=start_tok.start_offset,
                end_offset=self.peek().start_offset,
                status="PARSED"
            )
            self.ir.add_node(node)

        elif self.match("KEYWORD", "SET"):
            is_address_of_target = False
            target_var = None
            
            if self.match("KEYWORD", "ADDRESS"):
                self.consume("KEYWORD", "OF")
                target_var = self.consume("IDENTIFIER", None, "Expected identifier after ADDRESS OF").value
                is_address_of_target = True
            else:
                target_var = self.consume_subscripted_identifier("Expected target in SET")
                
            self.consume("KEYWORD", "TO", "Expected TO keyword in SET")
            
            is_address_of_source = False
            source_var = None
            
            if self.match("KEYWORD", "ADDRESS"):
                self.consume("KEYWORD", "OF")
                source_var = self.consume("IDENTIFIER", None, "Expected identifier after ADDRESS OF").value
                is_address_of_source = True
            elif self.match("KEYWORD", "TRUE"):
                source_var = "TRUE"
            elif self.match("KEYWORD", "FALSE"):
                source_var = "FALSE"
            else:
                source_var = self.consume_val_or_subscript("Expected source in SET").value
                
            self.match_statement_period()
            
            node = SemanticIRNode(
                node_id=self.next_node_id(),
                kind="STATEMENT",
                properties={
                    "statement_type": "SET",
                    "is_address_of_target": is_address_of_target,
                    "target_var": target_var,
                    "is_address_of_source": is_address_of_source,
                    "source_var": source_var
                },
                source_file=self.file_path,
                source_line=start_tok.line,
                source_column=start_tok.column,
                start_offset=start_tok.start_offset,
                end_offset=self.peek().start_offset,
                status="PARSED"
            )
            self.ir.add_node(node)

        elif self.match("KEYWORD", "INITIATE"):
            target_report = self.consume("IDENTIFIER", None, "Expected report name after INITIATE").value
            self.match_statement_period()
            node = SemanticIRNode(
                node_id=self.next_node_id(),
                kind="STATEMENT",
                properties={
                    "statement_type": "INITIATE",
                    "report_name": target_report
                },
                source_file=self.file_path,
                source_line=start_tok.line,
                source_column=start_tok.column,
                start_offset=start_tok.start_offset,
                end_offset=self.peek().start_offset,
                status="PARSED"
            )
            self.ir.add_node(node)
            
        elif self.match("KEYWORD", "GENERATE"):
            target = self.consume("IDENTIFIER", None, "Expected target after GENERATE").value
            self.match_statement_period()
            node = SemanticIRNode(
                node_id=self.next_node_id(),
                kind="STATEMENT",
                properties={
                    "statement_type": "GENERATE",
                    "target": target
                },
                source_file=self.file_path,
                source_line=start_tok.line,
                source_column=start_tok.column,
                start_offset=start_tok.start_offset,
                end_offset=self.peek().start_offset,
                status="PARSED"
            )
            self.ir.add_node(node)
            
        elif self.match("KEYWORD", "TERMINATE"):
            target_report = self.consume("IDENTIFIER", None, "Expected report name after TERMINATE").value
            self.match_statement_period()
            node = SemanticIRNode(
                node_id=self.next_node_id(),
                kind="STATEMENT",
                properties={
                    "statement_type": "TERMINATE",
                    "report_name": target_report
                },
                source_file=self.file_path,
                source_line=start_tok.line,
                source_column=start_tok.column,
                start_offset=start_tok.start_offset,
                end_offset=self.peek().start_offset,
                status="PARSED"
            )
            self.ir.add_node(node)

        elif self.match("KEYWORD", "INITIALIZE"):
            targets = []
            while self.check("IDENTIFIER"):
                targets.append(self.consume_subscripted_identifier())
                self.match("PUNCTUATION", ",")
            self.match_statement_period()
            node = SemanticIRNode(
                node_id=self.next_node_id(),
                kind="STATEMENT",
                properties={
                    "statement_type": "INITIALIZE",
                    "targets": targets
                },
                source_file=self.file_path,
                source_line=start_tok.line,
                source_column=start_tok.column,
                start_offset=start_tok.start_offset,
                end_offset=self.peek().start_offset,
                status="PARSED"
            )
            self.ir.add_node(node)


        elif self.match("KEYWORD", "SEARCH"):
            is_all = self.match("KEYWORD", "ALL")
            while not self.is_at_end() and not self.check("PUNCTUATION", "."):
                self.current += 1
            self.match_statement_period()
            node = SemanticIRNode(
                node_id=self.next_node_id(),
                kind="STATEMENT",
                properties={
                    "statement_type": "SEARCH_ALL" if is_all else "SEARCH",
                    "reason": "SEARCH statement is not supported natively; refactor manually."
                },
                source_file=self.file_path,
                source_line=start_tok.line,
                source_column=start_tok.column,
                start_offset=start_tok.start_offset,
                end_offset=self.peek().start_offset,
                status="UNSUPPORTED"
            )
            self.ir.add_node(node)

        elif self.match("KEYWORD", "ENTRY"):
            entry_name = self.consume_val("Expected entry name in ENTRY").value
            while not self.is_at_end() and not self.check("PUNCTUATION", "."):
                self.current += 1
            self.match_statement_period()
            node = SemanticIRNode(
                node_id=self.next_node_id(),
                kind="STATEMENT",
                properties={
                    "statement_type": "ENTRY",
                    "entry_name": entry_name,
                    "reason": "Alternate entry points are not supported in JVM."
                },
                source_file=self.file_path,
                source_line=start_tok.line,
                source_column=start_tok.column,
                start_offset=start_tok.start_offset,
                end_offset=self.peek().start_offset,
                status="UNSUPPORTED"
            )
            self.ir.add_node(node)

        elif self.match("KEYWORD", "CANCEL"):
            prog_name = self.consume_val("Expected program target in CANCEL").value
            self.match_statement_period()
            node = SemanticIRNode(
                node_id=self.next_node_id(),
                kind="STATEMENT",
                properties={
                    "statement_type": "CANCEL",
                    "program_name": prog_name,
                    "reason": "CANCEL subprogram unloading is not supported in JVM."
                },
                source_file=self.file_path,
                source_line=start_tok.line,
                source_column=start_tok.column,
                start_offset=start_tok.start_offset,
                end_offset=self.peek().start_offset,
                status="UNSUPPORTED"
            )
            self.ir.add_node(node)

        else:
            tok = self.peek()
            self.current += 1
            
            # Skip until period or statement boundary to prevent cascade UNKNOWNs
            while not self.is_at_end() and not self.check("PUNCTUATION", "."):
                peek_tok = self.peek()
                if is_tok_statement_start(peek_tok):
                    break
                self.current += 1
            
            self.match_statement_period()
            
            node = SemanticIRNode(
                node_id=self.next_node_id(),
                kind="STATEMENT",
                properties={
                    "statement_type": "UNKNOWN",
                    "offending_token": tok.value
                },
                source_file=self.file_path,
                source_line=start_tok.line,
                source_column=start_tok.column,
                start_offset=start_tok.start_offset,
                end_offset=self.peek().start_offset,
                status="UNSUPPORTED"
            )
            self.ir.add_node(node)

    def parse_exec_sql(self, tok):
        sql_text = tok.value
        
        # Dialect warnings for unsupported DB2 constructs
        sql_upper = sql_text.upper()
        unsupported_constructs = []
        if "WITH UR" in sql_upper:
            unsupported_constructs.append("WITH UR (Isolation Level)")
        if "FOR UPDATE" in sql_upper:
            unsupported_constructs.append("FOR UPDATE OF clause")
        if "FETCH FIRST" in sql_upper and "ONLY" in sql_upper:
            unsupported_constructs.append("FETCH FIRST N ROWS ONLY clause")
            
        for construct in unsupported_constructs:
            diag = ParserDiagnostic(
                message=f"DB2_UNSUPPORTED_CONSTRUCT: {construct} is not supported natively in H2/standard JDBC mapping",
                file=self.file_path,
                line=tok.line,
                column=tok.column,
                token_value=tok.value,
                context="SQL Dialect Validation"
            )
            self.diagnostics.append(diag)
            
        sql_tokens = tokenize_sql(sql_text)
        try:
            sql_props = parse_sql_tokens(sql_tokens)
        except Exception as e:
            raise ParserDiagnostic(f"Malformed EXEC SQL statement: {e}", self.file_path, tok.line, tok.column, tok.value, "")
        
        # Resolve host variables
        host_vars = extract_host_variables(sql_props)
        for hv in host_vars:
            var_found = False
            for node in self.ir.nodes.values():
                if node.kind in ("VARIABLE", "DATA_ITEM") and node.properties.get("name", "").upper() == hv:
                    var_found = True
                    break
            
            # Allow SQLCA variables (e.g. SQLCODE, SQLSTATE, SQLERRMC)
            if hv in ("SQLCODE", "SQLSTATE", "SQLERRMC"):
                var_found = True
                
            if not var_found:
                raise ParserDiagnostic(f"SQL_HOST_VARIABLE_NOT_FOUND: Host variable {hv} not declared in WORKING-STORAGE or LINKAGE", self.file_path, tok.line, tok.column, tok.value, "")
        
        node = SemanticIRNode(
            node_id=self.next_node_id(),
            kind="STATEMENT",
            properties={
                "statement_type": "EXEC_SQL",
                "sql_props": sql_props,
                "host_variables": host_vars,
                "original_sql": sql_text
            },
            source_file=self.file_path,
            source_line=tok.line,
            source_column=tok.column,
            start_offset=tok.start_offset,
            end_offset=tok.end_offset,
            status="PARSED"
        )
        self.ir.add_node(node)

    def parse_exec_cics(self, tok):
        cics_text = tok.value
        cics_tokens = tokenize_cics(cics_text)
        try:
            cics_props = parse_cics_tokens(cics_tokens)
        except Exception as e:
            raise ParserDiagnostic(f"Malformed EXEC CICS statement: {e}", self.file_path, tok.line, tok.column, tok.value, "")
        
        # Verify CICS supported command constraints
        cics_type = cics_props.get("cics_type", "EMPTY").upper()
        supported_types = ("SEND", "RECEIVE", "LINK", "XCTL", "RETURN", "GET", "PUT", "DELETE", "ABEND", "ASKTIME", "FORMATTIME")
        if cics_type not in supported_types:
            raise ParserDiagnostic(f"CICS_UNSUPPORTED_COMMAND: Unsupported CICS command '{cics_type}'", self.file_path, tok.line, tok.column, tok.value, "")
            
        if cics_type in ("LINK", "XCTL") and not cics_props.get("program"):
            raise ParserDiagnostic("CICS_INVALID_PROGRAM: Program target is missing or invalid", self.file_path, tok.line, tok.column, tok.value, "")
            
        if cics_type in ("GET", "PUT", "DELETE") and "container" not in cics_props:
            raise ParserDiagnostic(f"CICS_INVALID_CONTAINER: Container parameter is missing for EXEC CICS {cics_type}", self.file_path, tok.line, tok.column, tok.value, "")

        # Resolve variables in cics_props against the Working-Storage/Linkage semantic model
        cics_vars = []
        for key in ("from", "into", "commarea", "resp", "resp2", "abstime", "yyyymmdd", "time"):
            if key in cics_props and not cics_props.get(key + "_is_literal", False):
                val = cics_props[key]
                if isinstance(val, str) and not val.startswith("'") and not val.startswith('"') and not val.isdigit():
                    cics_vars.append(val)
                
        for cv in cics_vars:
            var_found = False
            for node in self.ir.nodes.values():
                if node.kind in ("VARIABLE", "DATA_ITEM") and node.properties.get("name", "").upper() == cv.upper():
                    var_found = True
                    break
            
            # Allow CICS special registers
            if cv.upper() in ("EIBRESP", "EIBRESP2", "EIBTRNID", "EIBAID", "EIBCALEN", "EIBCPOSN", "DFHCOMMAREA"):
                var_found = True
                
            if not var_found:
                raise ParserDiagnostic(f"CICS_HOST_VARIABLE_NOT_FOUND: Host variable {cv} not declared in WORKING-STORAGE or LINKAGE", self.file_path, tok.line, tok.column, tok.value, "")
                
        # Resolve variable size if length is explicitly provided
        if "commarea" in cics_props and "length" in cics_props:
            cv = cics_props["commarea"]
            try:
                length_limit = int(cics_props["length"])
                # Find variable node
                for node in self.ir.nodes.values():
                    if node.kind in ("VARIABLE", "DATA_ITEM") and node.properties.get("name", "").upper() == cv.upper():
                        # Calculate size
                        pic = node.properties.get("picture", "")
                        digits = node.properties.get("digits", 0)
                        size = digits if digits > 0 else len(pic)
                        # Extract length from standard forms like X(20) -> 20
                        if pic:
                            m = re.match(r'[A-Z]\((\d+)\)', pic, re.IGNORECASE)
                            if m:
                                size = int(m.group(1))
                        
                        if size != length_limit:
                            raise ParserDiagnostic(f"CICS_COMMAREA_MISMATCH: COMMAREA variable {cv} size {size} does not match specified length {length_limit}", self.file_path, tok.line, tok.column, tok.value, "")
            except ValueError:
                pass
                
        node = SemanticIRNode(
            node_id=self.next_node_id(),
            kind="STATEMENT",
            properties={
                "statement_type": "EXEC_CICS",
                "cics_props": cics_props,
                "original_cics": cics_text
            },
            source_file=self.file_path,
            source_line=tok.line,
            source_column=tok.column,
            start_offset=tok.start_offset,
            end_offset=tok.end_offset,
            status="PARSED"
        )
        self.ir.add_node(node)

def tokenize_sql(sql_text):
    tokens = []
    pattern = re.compile(r'(?i):[a-z0-9_-]+|[a-z0-9_-]+\.[a-z0-9_-]+|[a-z0-9_-]+|\'[^\']*\'|"[^"]*"|<=|>=|<>|!=|=|<|>|\(|\)|,|\.|\*|\+|\/')
    for m in pattern.finditer(sql_text):
        tokens.append(m.group(0))
    return tokens

def parse_sql_where(tokens, i):
    predicates = []
    if i < len(tokens) and tokens[i].upper() == "WHERE":
        i += 1
        while i < len(tokens):
            t_upper = tokens[i].upper()
            if t_upper in ("WITH", "FOR", "ORDER", "GROUP"):
                break
            if t_upper in ("AND", "OR", "NOT", "(", ")"):
                predicates.append({"logical": t_upper})
                i += 1
                continue
            
            if i >= len(tokens):
                break
            col = tokens[i]
            i += 1
            if i >= len(tokens):
                raise ValueError("Unexpected end of WHERE clause")
            
            op = tokens[i].upper()
            i += 1
            
            if op == "IS":
                if i < len(tokens) and tokens[i].upper() == "NOT":
                    i += 1
                    if i < len(tokens) and tokens[i].upper() == "NULL":
                        i += 1
                        predicates.append({"column": col, "op": "IS NOT NULL"})
                        continue
                    else:
                        raise ValueError("Expected NULL after IS NOT")
                elif i < len(tokens) and tokens[i].upper() == "NULL":
                    i += 1
                    predicates.append({"column": col, "op": "IS NULL"})
                    continue
                else:
                    raise ValueError("Expected NOT or NULL after IS")
            
            if op == "BETWEEN":
                if i >= len(tokens):
                    raise ValueError("Expected value after BETWEEN")
                val1 = tokens[i]
                i += 1
                if i < len(tokens) and tokens[i].upper() == "AND":
                    i += 1
                    if i >= len(tokens):
                        raise ValueError("Expected value after AND")
                    val2 = tokens[i]
                    i += 1
                    predicates.append({"column": col, "op": "BETWEEN", "value": val1, "value2": val2})
                    continue
                else:
                    raise ValueError("Expected AND in BETWEEN clause")
            
            if op == "IN":
                if i < len(tokens) and tokens[i] == "(":
                    i += 1
                    vals = []
                    while i < len(tokens) and tokens[i] != ")":
                        if tokens[i] != ",":
                            vals.append(tokens[i])
                        i += 1
                    if i < len(tokens) and tokens[i] == ")":
                        i += 1
                    predicates.append({"column": col, "op": "IN", "values": vals})
                    continue
                else:
                    raise ValueError("Expected ( after IN")
            
            if i >= len(tokens):
                raise ValueError(f"Expected value after operator {op}")
            val = tokens[i]
            i += 1
            predicates.append({"column": col, "op": op, "value": val})
            
    return predicates, i

def parse_sql_tokens(tokens):
    if not tokens:
        return {"sql_type": "EMPTY"}
    
    first = tokens[0].upper()
    if first == "COMMIT":
        return {"sql_type": "COMMIT"}
    elif first == "ROLLBACK":
        return {"sql_type": "ROLLBACK"}
        
    elif first == "DECLARE":
        cursor_name = tokens[1]
        if tokens[2].upper() != "CURSOR" or tokens[3].upper() != "FOR":
            raise ValueError("Expected CURSOR FOR after declare cursor name")
        subquery_props = parse_sql_tokens(tokens[4:])
        subquery_props["original_sql"] = " ".join(tokens[4:])
        return {
            "sql_type": "DECLARE_CURSOR",
            "cursor_name": cursor_name,
            "cursor_query": subquery_props
        }
        
    elif first == "OPEN":
        return {
            "sql_type": "OPEN",
            "cursor_name": tokens[1]
        }
        
    elif first == "CLOSE":
        return {
            "sql_type": "CLOSE",
            "cursor_name": tokens[1]
        }
        
    elif first == "FETCH":
        cursor_name = tokens[1]
        into_vars = []
        into_inds = []
        if len(tokens) > 2 and tokens[2].upper() == "INTO":
            i = 3
            while i < len(tokens):
                t = tokens[i]
                if t == ",":
                    i += 1
                    continue
                var_name = t[1:] if t.startswith(":") else t
                ind_name = None
                if i + 1 < len(tokens):
                    next_t = tokens[i+1]
                    if next_t != "," and (next_t.startswith(":") or next_t.upper().endswith("-IND") or next_t.upper() == "INDICATOR"):
                        if next_t.upper() == "INDICATOR" and i + 2 < len(tokens):
                            ind_t = tokens[i+2]
                            ind_name = ind_t[1:] if ind_t.startswith(":") else ind_t
                            i += 2
                        else:
                            ind_name = next_t[1:] if next_t.startswith(":") else next_t
                            i += 1
                into_vars.append(var_name)
                into_inds.append(ind_name)
                i += 1
        return {
            "sql_type": "FETCH",
            "cursor_name": cursor_name,
            "into_variables": into_vars,
            "into_indicators": into_inds
        }
        
    elif first == "SELECT":
        i = 1
        cols = []
        while i < len(tokens) and tokens[i].upper() not in ("INTO", "FROM"):
            t = tokens[i]
            if t != ",":
                cols.append(t)
            i += 1
            
        into_vars = []
        into_inds = []
        if i < len(tokens) and tokens[i].upper() == "INTO":
            i += 1
            while i < len(tokens) and tokens[i].upper() != "FROM":
                t = tokens[i]
                if t == ",":
                    i += 1
                    continue
                var_name = t[1:] if t.startswith(":") else t
                ind_name = None
                if i + 1 < len(tokens) and tokens[i+1].upper() != "FROM":
                    next_t = tokens[i+1]
                    if next_t != "," and (next_t.startswith(":") or next_t.upper().endswith("-IND") or next_t.upper() == "INDICATOR"):
                        if next_t.upper() == "INDICATOR" and i + 2 < len(tokens) and tokens[i+2].upper() != "FROM":
                            ind_t = tokens[i+2]
                            ind_name = ind_t[1:] if ind_t.startswith(":") else ind_t
                            i += 2
                        else:
                            ind_name = next_t[1:] if next_t.startswith(":") else next_t
                            i += 1
                into_vars.append(var_name)
                into_inds.append(ind_name)
                i += 1
                
        if i >= len(tokens) or tokens[i].upper() != "FROM":
            raise ValueError("Expected FROM keyword in SELECT")
        i += 1
        
        from_tokens = []
        while i < len(tokens) and tokens[i].upper() != "WHERE":
            from_tokens.append(tokens[i])
            i += 1
            
        alias_map = {}
        tables = []
        def is_alias_candidate(tok):
            t_u = tok.upper()
            return t_u not in ("INNER", "LEFT", "RIGHT", "JOIN", "ON", "WHERE", "AND", "OR", ",", ".", "=", "<", ">", "<=", ">=", "<>", "!=")
            
        if from_tokens:
            first_table = from_tokens[0].upper()
            tables.append(first_table)
            if len(from_tokens) > 1 and is_alias_candidate(from_tokens[1]):
                alias_map[from_tokens[1].upper()] = first_table
            
            k = 1
            while k < len(from_tokens):
                t_upper = from_tokens[k].upper()
                if t_upper == "JOIN" and k + 1 < len(from_tokens):
                    tbl = from_tokens[k+1].upper()
                    tables.append(tbl)
                    if k + 2 < len(from_tokens) and is_alias_candidate(from_tokens[k+2]):
                        alias_map[from_tokens[k+2].upper()] = tbl
                        k += 3
                    else:
                        k += 2
                else:
                    k += 1
                    
        predicates, i = parse_sql_where(tokens, i)
                
        return {
            "sql_type": "SELECT",
            "columns": cols,
            "into_variables": into_vars,
            "into_indicators": into_inds,
            "table": tables[0] if tables else None,
            "tables": tables,
            "alias_map": alias_map,
            "predicates": predicates
        }
        
    elif first == "INSERT":
        if tokens[1].upper() != "INTO":
            raise ValueError("Expected INTO after INSERT")
        table = tokens[2]
        i = 3
        cols = []
        if tokens[i] == "(":
            i += 1
            while i < len(tokens) and tokens[i] != ")":
                if tokens[i] != ",":
                    cols.append(tokens[i])
                i += 1
            i += 1
            
        if tokens[i].upper() != "VALUES":
            raise ValueError("Expected VALUES in INSERT")
        i += 1
        vals = []
        if tokens[i] == "(":
            i += 1
            while i < len(tokens) and tokens[i] != ")":
                if tokens[i] != ",":
                    val = tokens[i]
                    if val.startswith(":"):
                        val = val[1:]
                    vals.append(val)
                i += 1
                
        return {
            "sql_type": "INSERT",
            "table": table,
            "columns": cols,
            "values": vals
        }
        
    elif first == "UPDATE":
        table = tokens[1]
        if tokens[2].upper() != "SET":
            raise ValueError("Expected SET in UPDATE")
        i = 3
        sets = []
        while i < len(tokens) and tokens[i].upper() != "WHERE":
            col = tokens[i]
            if tokens[i+1] != "=":
                raise ValueError("Expected = in UPDATE SET")
            val = tokens[i+2]
            if val.startswith(":"):
                val = val[1:]
            sets.append({"column": col, "value": val})
            i += 3
            if i < len(tokens) and tokens[i] == ",":
                i += 1
                
        predicates, i = parse_sql_where(tokens, i)
                
        return {
            "sql_type": "UPDATE",
            "table": table,
            "sets": sets,
            "predicates": predicates
        }
        
    elif first == "DELETE":
        if tokens[1].upper() != "FROM":
            raise ValueError("Expected FROM in DELETE")
        table = tokens[2]
        i = 3
        predicates, i = parse_sql_where(tokens, i)
        return {
            "sql_type": "DELETE",
            "table": table,
            "predicates": predicates
        }
        
    else:
        raise ValueError(f"Unsupported SQL statement type: {first}")

def extract_host_variables(props):
    vars = []
    for v in props.get("into_variables", []):
        vars.append(v)
    for v in props.get("into_indicators", []):
        if v:
            vars.append(v)
    for p in props.get("predicates", []):
        if "value" in p:
            val = p["value"]
            if val and isinstance(val, str) and (val.startswith(":") or val.upper() in ("WS-", "LK-") or "-" in val):
                cleaned = val[1:] if val.startswith(":") else val
                vars.append(cleaned)
        if "value2" in p:
            val = p["value2"]
            if val and isinstance(val, str) and (val.startswith(":") or val.upper() in ("WS-", "LK-") or "-" in val):
                cleaned = val[1:] if val.startswith(":") else val
                vars.append(cleaned)
        if "values" in p:
            for val in p["values"]:
                if val and isinstance(val, str) and (val.startswith(":") or val.upper() in ("WS-", "LK-") or "-" in val):
                    cleaned = val[1:] if val.startswith(":") else val
                    vars.append(cleaned)
    for v in props.get("values", []):
        if isinstance(v, str):
            vars.append(v)
    for s in props.get("sets", []):
        val = s.get("value")
        if val:
            vars.append(val)
    if "cursor_query" in props:
        vars.extend(extract_host_variables(props["cursor_query"]))
    
    res = []
    for v in vars:
        if v and not v.startswith("'") and not v.startswith('"') and not v.replace(".", "").isdigit():
            res.append(v.upper())
    return list(set(res))

def tokenize_cics(cics_text):
    tokens = []
    # Match keywords, values, parentheses:
    pattern = re.compile(r'[A-Za-z0-9_-]+|\'[^\']*\'|"[^"]*"|\(|\)|\=|\,')
    for m in pattern.finditer(cics_text):
        tokens.append(m.group(0))
    return tokens

def parse_cics_tokens(tokens):
    if not tokens:
        return {"cics_type": "EMPTY"}
    
    # Locate first command token (CICS command name, skip EXEC CICS prefix if present)
    start_idx = 0
    if tokens[0].upper() == "EXEC":
        start_idx = 1
        if len(tokens) > 1 and tokens[1].upper() == "CICS":
            start_idx = 2
            
    if start_idx >= len(tokens):
        return {"cics_type": "EMPTY"}
        
    first = tokens[start_idx].upper()
    props = {"cics_type": first}
    
    i = start_idx + 1
    while i < len(tokens):
        key = tokens[i].upper()
        # Parse key(value) structures
        if i + 1 < len(tokens) and tokens[i+1] == "(":
            val_tokens = []
            depth = 1
            j = i + 2
            while j < len(tokens):
                t = tokens[j]
                if t == "(":
                    depth += 1
                elif t == ")":
                    depth -= 1
                    if depth == 0:
                        break
                val_tokens.append(t)
                j += 1
            
            is_quoted = len(val_tokens) > 0 and (val_tokens[0].startswith("'") or val_tokens[0].startswith('"'))
            val = "".join(val_tokens).strip("'\"")
            props[key.lower()] = val
            if is_quoted:
                props[key.lower() + "_is_literal"] = True
            i = j + 1
        else:
            props[key.lower()] = True
            i += 1
            
    return props
