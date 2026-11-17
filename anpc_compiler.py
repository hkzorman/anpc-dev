# anpc_compiler - a proper compiler for anpcscript
#
# Replaces the old anpcscript-interpreter.py. Design goals:
#   - compile(text) is a pure function: the CLI, the IDE and any future
#     service all call the same code path.
#   - Every line of source is either compiled or produces a hard diagnostic
#     with a line number. There is no such thing as a silently dropped line.
#   - Real expression precedence (comparison < arithmetic, and/or) and
#     parentheses.
#   - String/number/identifier rules come from the source: quoted stays
#     quoted (single set of quotes), bare numbers stay bare, bare
#     identifiers stay bare, true/false/nil stay bare.
#   - Every generated instruction carries a srcmap stamp (the line number in
#     the ORIGINAL anpcscript source) so the debugger can map N compiled
#     instructions back to 1 source line.
#   - The .anpcscript path is emitted as the third argument of
#     npc.proc.register_program by default, so the in-game debugger's source
#     view gets its input.
#
# Usage (CLI):
#   python anpc_compiler.py <input.anpcscript> <output.lua>
#
# Usage (API):
#   from anpc_compiler import compile
#   result = compile(text, source_path="...")
#   if not result.ok: print(result.diagnostics)
#   else: open("out.lua", "w").write(result.lua)

import os
import re
import sys

# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------

class Diagnostic:
    """One compile problem. line is 1-based (0 when unknown)."""
    def __init__(self, line, message):
        self.line = line
        self.message = message

    def __repr__(self):
        if self.line:
            return "line %d: %s" % (self.line, self.message)
        return self.message

    def __str__(self):
        return self.__repr__()


class CompileResult:
    def __init__(self):
        self.ok = False
        self.lua = None
        self.programs = []          # list of CompiledProgram
        self.diagnostics = []       # list of Diagnostic

    def error(self, line, message):
        self.diagnostics.append(Diagnostic(line, message))
        self.ok = False


class CompiledProgram:
    def __init__(self, name, define_line, end_line):
        self.name = name
        self.define_line = define_line
        self.end_line = end_line
        self.instructions = []      # list of record dicts


# ---------------------------------------------------------------------------
# Lua value tree (structured, for tests) + serializer (for output)
# ---------------------------------------------------------------------------

class Value:
    pass

class Num(Value):
    def __init__(self, value, line):
        self.value = value
        self.line = line

class Str(Value):
    def __init__(self, text, line):
        self.text = text          # exact source text, including quotes
        self.line = line

class Bool(Value):
    def __init__(self, value, line):
        self.value = value
        self.line = line

class Nil(Value):
    def __init__(self, line):
        self.line = line

class Var(Value):
    # Full variable reference text: @storage.name, @storage.name[key],
    # @storage.name.subkey. Quotes around bracket keys are stripped
    # (the engine's evaluate_argument expects @local.tbl[key]).
    def __init__(self, text, line):
        self.text = text
        self.line = line

class Ident(Value):
    def __init__(self, text, line):
        self.text = text
        self.line = line

class Raw(Value):
    # Raw Lua passthrough (from a lua: value)
    def __init__(self, text, line):
        self.text = text
        self.line = line

class Bin(Value):
    # Flat two-operand expression: {left = L, op = "OP", right = R}
    def __init__(self, op, left, right, line):
        self.op = op
        self.left = left
        self.right = right
        self.line = line

class Table(Value):
    def __init__(self, items, line):
        # items: list of (key_or_None, Value)
        self.items = items
        self.line = line


# Lua reserved words: argument keys that would break a table constructor
# are emitted as ["key"]. (Superset of the old compiler's list; quoting a
# key is always legal Lua.)
LUA_RESERVED = {
    "and", "break", "do", "else", "elseif", "end", "false", "for",
    "function", "goto", "if", "in", "local", "nil", "not", "or",
    "repeat", "return", "then", "true", "until", "while",
}


def lua_key(key):
    if key in LUA_RESERVED:
        return '["' + key + '"]'
    return key


def to_lua(value):
    """Serialize a Value node to a Lua expression string.

    Plain Python bool/int/float/str are accepted too (synthesized values:
    jump offsets, negation flags, pre-quoted strings).
    """
    if value is None:
        return "nil"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        if isinstance(value, float) and value == int(value):
            return str(int(value))
        return str(value)
    if isinstance(value, str):
        return value
    if isinstance(value, Num):
        v = value.value
        if isinstance(v, float) and v == int(v):
            return str(int(v))
        return str(v)
    if isinstance(value, (Str, Ident, Raw)):
        return value.text
    if isinstance(value, Bool):
        return "true" if value.value else "false"
    if isinstance(value, Nil):
        return "nil"
    if isinstance(value, Var):
        # Variable references travel as quoted DSL strings: "@local.x"
        return '"' + value.text + '"'
    if isinstance(value, Bin):
        return "{left = " + to_lua(value.left) \
            + ', op = "' + value.op + '", right = ' + to_lua(value.right) + "}"
    if isinstance(value, Table):
        parts = []
        for key, val in value.items:
            if key is None:
                parts.append(to_lua(val))
            else:
                parts.append(lua_key(key) + " = " + to_lua(val))
        return "{" + ", ".join(parts) + "}"
    raise TypeError("unknown value node: %r" % type(value))


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

TK_NAME = "name"
TK_STRING = "string"
TK_NUMBER = "number"
TK_OP = "op"
TK_RAW = "raw"          # lua: raw span
TK_NEWLINE = "newline"
TK_EOF = "eof"

TWO_CHAR_OPS = ("==", "~=", "<=", ">=", "&&", "||")
ONE_CHAR_OPS = ("(", ")", "{", "}", "[", "]", ",", ";", "=", "<", ">",
                "+", "-", "*", "/", "%")

NAME_START = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                 "abcdefghijklmnopqrstuvwxyz_@")
NAME_CONT = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                "abcdefghijklmnopqrstuvwxyz"
                "0123456789_:.@")


class Token:
    __slots__ = ("kind", "value", "line", "start", "end")
    def __init__(self, kind, value, line, start, end):
        self.kind = kind
        self.value = value
        self.line = line
        self.start = start
        self.end = end


class TokenizerError(Diagnostic):
    pass


def tokenize(source):
    """Tokenize the whole source. Returns (tokens, diagnostics)."""
    tokens = []
    diags = []
    i = 0
    line = 1
    n = len(source)

    def err(msg, at_line):
        diags.append(Diagnostic(at_line, msg))

    while i < n:
        c = source[i]

        if c == "\n":
            tokens.append(Token(TK_NEWLINE, "\n", line, i, i + 1))
            i += 1
            line += 1
            continue

        if c in " \t\r":
            i += 1
            continue

        if source.startswith("--", i):
            # Comment: run to end of line
            while i < n and source[i] != "\n":
                i += 1
            continue

        if c == '"' or c == "'":
            quote = c
            start = i
            i += 1
            while i < n and source[i] != quote and source[i] != "\n":
                if source[i] == "\\":
                    i += 1
                i += 1
            if i >= n or source[i] == "\n":
                err("unterminated string", line)
                tokens.append(Token(TK_EOF, "", line, i, i))
                return tokens, diags
            i += 1  # closing quote
            tokens.append(Token(TK_STRING, source[start:i], line, start, i))
            continue

        if c.isdigit():
            start = i
            while i < n and source[i].isdigit():
                i += 1
            if i < n and source[i] == "." and i + 1 < n and source[i + 1].isdigit():
                i += 1
                while i < n and source[i].isdigit():
                    i += 1
                tokens.append(Token(TK_NUMBER, float(source[start:i]), line, start, i))
            else:
                tokens.append(Token(TK_NUMBER, int(source[start:i]), line, start, i))
            continue

        if c in NAME_START:
            # Special case: a `lua:` value is a raw Lua span, consumed up to
            # the end of the enclosing value (a depth-0 ), }, ], comma, or
            # end of line).
            if source.startswith("lua:", i):
                start = i
                j = i + 4
                depth = 0
                raw_ok = True
                while j < n and source[j] != "\n":
                    ch = source[j]
                    if ch == '"' or ch == "'":
                        # skip over the string literal inside the raw span
                        q = ch
                        j += 1
                        while j < n and source[j] != q and source[j] != "\n":
                            if source[j] == "\\":
                                j += 1
                            j += 1
                        if j >= n or source[j] == "\n":
                            raw_ok = False
                            break
                        j += 1
                        continue
                    if ch in "([{":
                        depth += 1
                    elif ch == ")":
                        if depth == 0:
                            break
                        depth -= 1
                    elif ch in "}]":
                        if depth == 0:
                            break
                        depth -= 1
                    elif ch == "," and depth == 0:
                        break
                    j += 1
                if not raw_ok:
                    err("unterminated lua: expression", line)
                    tokens.append(Token(TK_EOF, "", line, j, j))
                    return tokens, diags
                if j >= n or source[j] == "\n":
                    err("unterminated lua: expression", line)
                    tokens.append(Token(TK_EOF, "", line, j, j))
                    return tokens, diags
                tokens.append(Token(TK_RAW, source[i + 4:j].strip(), line, i, j))
                i = j
                continue

            start = i
            while i < n and source[i] in NAME_CONT:
                i += 1
            tokens.append(Token(TK_NAME, source[start:i], line, start, i))
            continue

        pair = source[i:i + 2]
        if pair in TWO_CHAR_OPS:
            tokens.append(Token(TK_OP, pair, line, i, i + 2))
            i += 2
            continue

        if c in ONE_CHAR_OPS:
            tokens.append(Token(TK_OP, c, line, i, i + 1))
            i += 1
            continue

        err("unexpected character %r" % c, line)
        i += 1

    tokens.append(Token(TK_EOF, "", line, i, i))
    return tokens, diags


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

# AST node types

class PProgram:
    def __init__(self, name, define_line, body, end_line):
        self.name = name
        self.define_line = define_line
        self.body = body
        self.end_line = end_line

class PVarSet:
    def __init__(self, var, storage, key, value, line):
        self.var = var              # full @storage.name[...] text
        self.storage = storage      # "local" | "global" | ...
        self.key = key              # name (with [subkey] if present)
        self.value = value          # Value tree
        self.line = line

class PInstr:
    def __init__(self, name, args, line):
        # args: list of (key, Value)
        self.name = name
        self.args = args
        self.line = line

class PBreak:
    def __init__(self, line):
        self.line = line

class PExit:
    def __init__(self, line):
        self.line = line

class PIf:
    def __init__(self, cond, true_body, else_body, line, else_line):
        self.cond = cond
        self.true_body = true_body
        self.else_body = else_body  # None when no else
        self.line = line
        self.else_line = else_line  # 0 when no else

class PWhile:
    def __init__(self, cond, body, line):
        self.cond = cond
        self.body = body
        self.line = line

class PFor:
    def __init__(self, init, cond, step, body, line):
        self.init = init
        self.cond = cond
        self.step = step
        self.body = body
        self.line = line


PROGRAM_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?::[A-Za-z_][A-Za-z0-9_]*)*$")
INSTR_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?::[A-Za-z0-9_]+)*$")


class Parser:
    def __init__(self, tokens, result):
        self.toks = tokens
        self.pos = 0
        self.result = result

    # -- token helpers -------------------------------------------------
    def peek(self):
        return self.toks[self.pos]

    def next(self):
        tok = self.toks[self.pos]
        if tok.kind != TK_EOF:
            self.pos += 1
        return tok

    def at_name(self, text):
        tok = self.peek()
        return tok.kind == TK_NAME and tok.value == text

    def expect_name(self, text, what):
        if self.at_name(text):
            return self.next()
        tok = self.peek()
        self.result.error(tok.line, "expected %s, got %r" % (what, tok.value))
        return None

    def expect_op(self, op, what):
        tok = self.peek()
        if tok.kind == TK_OP and tok.value == op:
            return self.next()
        self.result.error(tok.line, "expected %s (%r), got %r"
                          % (what, op, tok.value if tok.kind != TK_EOF else "end of file"))
        return None

    def skip_newlines(self):
        while self.peek().kind == TK_NEWLINE:
            self.next()

    # -- top level ------------------------------------------------------
    def parse(self):
        programs = []
        seen = set()
        while True:
            self.skip_newlines()
            if self.peek().kind == TK_EOF:
                break
            if not self.at_name("define"):
                tok = self.peek()
                self.result.error(tok.line,
                    "expected 'define program', got %r" % tok.value)
                break
            self.next()
            if not self.at_name("program"):
                tok = self.peek()
                self.result.error(tok.line,
                    "expected 'program' after 'define', got %r" % tok.value)
                self.skip_newlines()
                continue
            self.next()
            name_tok = self.peek()
            if name_tok.kind != TK_NAME or name_tok.value.startswith("@"):
                self.result.error(name_tok.line,
                    "expected program name, got %r" % name_tok.value)
                self.skip_newlines()
                continue
            self.next()
            if not PROGRAM_NAME_RE.match(name_tok.value):
                self.result.error(name_tok.line,
                    "invalid program name %r" % name_tok.value)
            elif name_tok.value in seen:
                self.result.error(name_tok.line,
                    'program "%s" is already defined' % name_tok.value)
            else:
                seen.add(name_tok.value)
            self.skip_newlines()
            body, end_tok = self.parse_block(name_tok.value)
            if end_tok is None:
                continue
            programs.append(PProgram(name_tok.value, name_tok.line, body,
                                     end_tok.line))
            self.skip_newlines()
        return programs

    def parse_block(self, owner):
        """Parse statements until the matching 'end'. Consumes the 'end'."""
        body = []
        while True:
            self.skip_newlines()
            tok = self.peek()
            if tok.kind == TK_EOF:
                self.result.error(0,
                    "program %r: expected 'end' before end of file" % owner)
                return body, None
            if tok.kind == TK_NAME and tok.value == "end":
                self.next()
                return body, tok
            ndiag = len(self.result.diagnostics)
            stmt = self.parse_statement()
            if stmt is not None:
                body.append(stmt)
            # A statement ends at the newline; consume it.
            if self.peek().kind == TK_NEWLINE:
                self.next()
            elif self.peek().kind != TK_EOF:
                # A control statement may leave its 'end' (or an 'else')
                # right here - the loop top (or the caller) handles it.
                if self.at_name("end") or self.at_name("else"):
                    continue
                # The parser is sitting on unexpected tokens: report where
                # the statement went wrong (unless the statement parser
                # already said so).
                t = self.peek()
                if len(self.result.diagnostics) == ndiag:
                    self.result.error(t.line,
                        "unexpected %r after statement" % t.value)
                # recover: skip to next line
                while self.peek().kind not in (TK_NEWLINE, TK_EOF):
                    self.next()

    # -- statements ------------------------------------------------------
    def parse_statement(self):
        tok = self.peek()
        if tok.kind == TK_NAME:
            t = tok.value
            if t.startswith("@"):
                return self.parse_var_assignment()
            if t == "if":
                return self.parse_if()
            if t == "while":
                return self.parse_while()
            if t == "for":
                return self.parse_for()
            if t == "break":
                self.next()
                return PBreak(tok.line)
            if t == "exit":
                self.next()
                return PExit(tok.line)
            return self.parse_instruction()
        if tok.kind == TK_OP:
            self.result.error(tok.line, "expected a statement, got %r" % tok.value)
            self.next()
        return None

    def parse_var_assignment(self):
        var_tok = self.next()
        # Optional bracket index: @storage.name[key]
        var_text = var_tok.value
        if self.peek().kind == TK_OP and self.peek().value == "[":
            self.next()
            idx = self.peek()
            if idx.kind == TK_STRING:
                inner = idx.value[1:-1]      # strip the quotes
            elif idx.kind in (TK_NUMBER, TK_NAME):
                inner = str(idx.value)
            else:
                self.result.error(idx.line,
                    "invalid table index in variable, expected number, "
                    "string or @variable")
                self.next()
                inner = ""
            self.next()
            if not self.expect_op("]", "']' after variable index"):
                return None
            var_text = var_text + "[" + inner + "]"

        if not self.expect_op("=", "'=' after variable"):
            return None

        value = self.parse_expression()
        if value is None:
            return None

        # Split @storage.name into storage + key
        rest_part = var_text[1:]
        if "." not in rest_part:
            self.result.error(var_tok.line,
                "cannot assign to %r: expected @storage.name form" % var_text)
            return None
        storage = rest_part.split(".", 1)[0]
        key = rest_part.split(".", 1)[1]
        return PVarSet(var_text, storage, key, value, var_tok.line)

    def parse_instruction(self):
        name_tok = self.next()
        name = name_tok.value
        if not INSTR_NAME_RE.match(name):
            self.result.error(name_tok.line,
                "invalid instruction name %r" % name)
            # still consume any arg list so we can recover
            if self.peek().kind == TK_OP and self.peek().value == "(":
                self.skip_balanced()
            return None
        args = []
        if self.peek().kind == TK_OP and self.peek().value == "(":
            self.next()
            args = self.parse_arg_list()
            if self.peek().kind != TK_EOF:
                self.expect_op(")", "')' after instruction arguments")
        return PInstr(name, args, name_tok.line)

    def parse_arg_list(self):
        """Parse a (comma-separated) list of key = value arguments."""
        args = []
        if self.peek().kind == TK_OP and self.peek().value == ")":
            return args
        while True:
            key_tok = self.peek()
            if key_tok.kind != TK_NAME:
                self.result.error(key_tok.line,
                    "expected argument name, got %r" % key_tok.value)
                return args
            key = key_tok.value
            self.next()
            if not self.expect_op("=", "'=' after argument name %r" % key):
                return args
            value = self.parse_expression()
            if value is None:
                return args
            args.append((key, value))
            tok = self.peek()
            if tok.kind == TK_OP and tok.value == ",":
                self.next()
                continue
            if tok.kind == TK_OP and tok.value == ")":
                break
            self.result.error(tok.line,
                "expected ',' or ')' in argument list, got %r" % tok.value)
            return args
        return args

    # -- control structures ----------------------------------------------
    def parse_condition(self, opener):
        """Parse '(' expression ')' for if/while/for conditions."""
        if not self.expect_op("(", "'(' starting condition"):
            return None
        expr = self.parse_expression()
        if expr is None:
            return None
        if not self.expect_op(")", "')' closing condition"):
            return None
        return expr

    def parse_if(self):
        line = self.next().line          # 'if'
        cond = self.parse_condition("if")
        if cond is None:
            return None
        if not self.at_name("then"):
            tok = self.peek()
            self.result.error(tok.line, "expected 'then', got %r" % tok.value)
            return None
        self.next()
        true_body = self.parse_inner_block("if")
        if true_body is None:
            return None
        else_body = None
        else_line = 0
        if self.at_name("else"):
            else_line = self.next().line
            else_body = self.parse_inner_block("if", allow_end=True)
            if else_body is None:
                return None
        elif not self.expect_name("end", "'end' closing if"):
            return None
        return PIf(cond, true_body, else_body, line, else_line)

    def parse_while(self):
        line = self.next().line          # 'while'
        cond = self.parse_condition("while")
        if cond is None:
            return None
        if not self.at_name("do"):
            tok = self.peek()
            self.result.error(tok.line, "expected 'do', got %r" % tok.value)
            return None
        self.next()
        body = self.parse_inner_block("while", allow_end=True)
        if body is None:
            return None
        return PWhile(cond, body, line)

    def parse_for(self):
        line = self.next().line          # 'for'
        if not self.expect_op("(", "'(' starting for-header"):
            return None
        init = self.parse_expression()
        if init is None:
            return None
        if not self.expect_op(";", "';' in for-header"):
            return None
        cond = self.parse_expression()
        if cond is None:
            return None
        step = Num(1, line)
        if self.peek().kind == TK_OP and self.peek().value == ";":
            self.next()
            step = self.parse_expression()
            if step is None:
                return None
        if not self.expect_op(")", "')' closing for-header"):
            return None
        if not self.at_name("do"):
            tok = self.peek()
            self.result.error(tok.line, "expected 'do', got %r" % tok.value)
            return None
        self.next()
        body = self.parse_inner_block("for", allow_end=True)
        if body is None:
            return None
        return PFor(init, cond, step, body, line)

    def parse_inner_block(self, owner, allow_end=False):
        """Parse a control-structure body.

        For 'if' we stop at 'else' or 'end' (the 'end' is left unconsumed so
        the caller decides). For while/for we consume the matching 'end'.
        Returns the statement list, or None on error.
        """
        body = []
        while True:
            self.skip_newlines()
            tok = self.peek()
            if tok.kind == TK_EOF:
                self.result.error(0,
                    "expected 'end' closing %s before end of file" % owner)
                return None
            if tok.kind == TK_NAME:
                if tok.value == "end":
                    if allow_end:
                        self.next()
                    return body
                if owner == "if" and tok.value == "else":
                    return body
            ndiag = len(self.result.diagnostics)
            stmt = self.parse_statement()
            if stmt is not None:
                body.append(stmt)
            if self.peek().kind == TK_NEWLINE:
                self.next()
            elif self.peek().kind != TK_EOF:
                if self.at_name("end") or self.at_name("else"):
                    continue
                t = self.peek()
                if len(self.result.diagnostics) == ndiag:
                    self.result.error(t.line,
                        "unexpected %r after statement" % t.value)
                while self.peek().kind not in (TK_NEWLINE, TK_EOF):
                    self.next()

    # -- expressions (precedence climbing) --------------------------------
    def parse_expression(self):
        return self.parse_or()

    def parse_or(self):
        left = self.parse_and()
        if left is None:
            return None
        while self.peek().kind == TK_OP and self.peek().value == "||":
            self.next()
            right = self.parse_and()
            if right is None:
                return None
            left = Bin("||", left, right, left.line)
        return left

    def parse_and(self):
        left = self.parse_cmp()
        if left is None:
            return None
        while self.peek().kind == TK_OP and self.peek().value == "&&":
            self.next()
            right = self.parse_cmp()
            if right is None:
                return None
            left = Bin("&&", left, right, left.line)
        return left

    def parse_cmp(self):
        left = self.parse_add()
        if left is None:
            return None
        tok = self.peek()
        if tok.kind == TK_OP and tok.value in ("==", "~=", "<", ">", "<=", ">="):
            self.next()
            right = self.parse_add()
            if right is None:
                return None
            return Bin(tok.value, left, right, left.line)
        return left

    def parse_add(self):
        left = self.parse_mul()
        if left is None:
            return None
        tok = self.peek()
        while tok.kind == TK_OP and tok.value in ("+", "-"):
            self.next()
            right = self.parse_mul()
            if right is None:
                return None
            left = Bin(tok.value, left, right, left.line)
            tok = self.peek()
        return left

    def parse_mul(self):
        left = self.parse_unary()
        if left is None:
            return None
        tok = self.peek()
        while tok.kind == TK_OP and tok.value in ("*", "/", "%"):
            self.next()
            right = self.parse_unary()
            if right is None:
                return None
            left = Bin(tok.value, left, right, left.line)
            tok = self.peek()
        return left

    def parse_unary(self):
        tok = self.peek()
        if tok.kind == TK_OP and tok.value in ("+", "-"):
            self.next()
            operand = self.parse_unary()
            if operand is None:
                return None
            if tok.value == "-":
                if isinstance(operand, Num):
                    return Num(-operand.value, tok.line)
                # No unary operator in the DSL: -x == 0 - x
                return Bin("-", Num(0, tok.line), operand, tok.line)
            return operand
        return self.parse_primary()

    def parse_primary(self):
        tok = self.peek()

        if tok.kind == TK_NUMBER:
            self.next()
            return Num(tok.value, tok.line)

        if tok.kind == TK_STRING:
            self.next()
            return Str(tok.value, tok.line)

        if tok.kind == TK_RAW:
            self.next()
            return Raw(tok.value, tok.line)

        if tok.kind == TK_OP and tok.value == "(":
            self.next()
            expr = self.parse_expression()
            if expr is None:
                return None
            if not self.expect_op(")", "')' closing parenthesis"):
                return None
            return expr

        if tok.kind == TK_OP and tok.value == "{":
            return self.parse_table()

        if tok.kind != TK_NAME:
            self.result.error(tok.line, "expected a value, got %r"
                              % (tok.value if tok.value else "end of file"))
            self.next()
            return None

        self.next()
        t = tok.value

        if t == "true" or t == "false":
            return Bool(t == "true", tok.line)
        if t == "nil":
            return Nil(tok.line)

        if t.startswith("@"):
            # Variable reference, with an optional [index] part.
            var_text = t
            if self.peek().kind == TK_OP and self.peek().value == "[":
                self.next()
                idx = self.peek()
                if idx.kind == TK_STRING:
                    inner = idx.value[1:-1]
                elif idx.kind in (TK_NUMBER, TK_NAME):
                    inner = str(idx.value)
                else:
                    self.result.error(idx.line,
                        "invalid table index, expected number, string or "
                        "@variable")
                    self.next()
                    inner = ""
                self.next()
                if not self.expect_op("]", "']' after index"):
                    return None
                var_text = var_text + "[" + inner + "]"
            return Var(var_text, tok.line)

        # An instruction call as an expression operand: npc:random(...)
        if ":" in t and not t.startswith("lua:"):
            if self.peek().kind == TK_OP and self.peek().value == "(":
                self.next()
                args = self.parse_arg_list()
                if self.peek().kind != TK_EOF:
                    self.expect_op(")", "')' after arguments of %s" % t)
                return Call(t, args, tok.line)
            self.result.error(tok.line,
                "instruction name %r not followed by '('" % t)
            return None

        return Ident(t, tok.line)

    def parse_table(self):
        t = self.peek()
        if t.kind != TK_OP or t.value != "{":
            self.result.error(t.line,
                "expected '{' starting table, got %r" % t.value)
            return None
        line = t.line
        self.next()
        items = []
        if self.peek().kind == TK_OP and self.peek().value == "}":
            self.next()
            return Table(items, line)
        while True:
            # key = value  |  value
            tok = self.peek()
            key = None
            if tok.kind == TK_NAME and not tok.value.startswith("@") \
                    and not tok.value.startswith("lua:"):
                save = self.pos
                self.next()
                if self.peek().kind == TK_OP and self.peek().value == "=":
                    key = tok.value
                    self.next()
                else:
                    self.pos = save   # not a key=value pair
            if key is None:
                value = self.parse_expression()
            else:
                value = self.parse_expression()
            if value is None:
                return None
            items.append((key, value))
            t2 = self.peek()
            if t2.kind == TK_OP and t2.value == ",":
                self.next()
                if self.peek().kind == TK_NEWLINE:
                    self.result.error(self.peek().line,
                        "multi-line tables are not supported; keep the "
                        "table on one line")
                    return None
                continue
            if t2.kind == TK_OP and t2.value == "}":
                self.next()
                return Table(items, line)
            self.result.error(t2.line, "expected ',' or '}' in table, got %r"
                              % t2.value)
            return None

    def skip_balanced(self):
        """Skip a ( ... ) group (error recovery)."""
        depth = 0
        while self.peek().kind != TK_EOF:
            tok = self.next()
            if tok.kind == TK_OP and tok.value == "(":
                depth += 1
            elif tok.kind == TK_OP and tok.value == ")":
                depth -= 1
                if depth == 0:
                    return
            elif tok.kind == TK_NEWLINE:
                return


class Call:
    """An inline instruction call used as a value. Hoisted at codegen time
    into a standalone instruction whose result is referenced by a
    @local._inline_<name><n> variable."""
    def __init__(self, name, args, line):
        self.name = name
        self.args = args            # list of (key, Value)
        self.line = line


# ---------------------------------------------------------------------------
# Code generator
# ---------------------------------------------------------------------------

WAIT_EXPANSION_NOTE = "npc:wait expansion matches the engine's proc-interval mechanism"


class GenContext:
    def __init__(self):
        self.inlines = []           # hoisted instruction records
        self.inline_counter = 0     # per-statement, matches old naming


class CodeGen:
    def __init__(self, program, result):
        self.program = program
        self.result = result

    def generate(self):
        recs = []
        for stmt in self.program.body:
            r = self.stmt_records(stmt)
            if r is None:
                return None
            recs.extend(r)
        return recs

    def block_records(self, body):
        out = []
        for stmt in body:
            r = self.stmt_records(stmt)
            if r is None:
                return None
            out.extend(r)
        return out

    # -- hoisting ----------------------------------------------------------
    def hoist(self, value, ctx):
        """Rewrite inline calls in the value tree into variable references.

        A call used as a plain value becomes a standalone instruction that
        stores its result in @local._inline_<name><n> (counter is per
        statement, as in the old compiler), followed by a Var reference.
        Nested calls are hoisted first (post-order) so the records execute
        inner-before-outer. Returns the (possibly replaced) node.
        """
        if isinstance(value, Call):
            # Hoist nested calls first (post-order) so their records
            # execute before this one; numbering follows execution order.
            value.args = [(k, self.hoist(v, ctx)) for k, v in value.args]
            key = "@local._inline_%s%d" % (value.name, ctx.inline_counter)
            ctx.inline_counter += 1
            ctx.inlines.append({
                "key": key,
                "name": value.name,
                "args": self.args_dict(value.args),
                "srcmap": value.line,
            })
            return Var(key, value.line)
        if isinstance(value, Bin):
            value.left = self.hoist(value.left, ctx)
            value.right = self.hoist(value.right, ctx)
            return value
        if isinstance(value, Table):
            value.items = [(k, self.hoist(v, ctx)) for k, v in value.items]
            return value
        return value

    # -- per-statement record building ---------------------------------------
    def stmt_records(self, stmt):
        if isinstance(stmt, PBreak):
            return [{"name": "npc:break", "srcmap": stmt.line}]
        if isinstance(stmt, PExit):
            return [{"name": "npc:exit", "srcmap": stmt.line}]

        if isinstance(stmt, PInstr):
            ctx = GenContext()
            args = [(k, self.hoist(v, ctx)) for k, v in stmt.args]
            if stmt.name == "npc:wait":
                r = self.wait_records(stmt)
                if r is None:
                    return None
                return list(ctx.inlines) + r
            rec = {
                "name": stmt.name,
                "args": self.args_dict(args),
                "srcmap": stmt.line,
            }
            return list(ctx.inlines) + [rec]

        if isinstance(stmt, PVarSet):
            ctx = GenContext()
            value = stmt.value
            if isinstance(value, Call):
                # @var = instr(...) : the call IS the instruction record
                # (its result is stored into @var). Nested calls in its
                # arguments are hoisted first.
                value.args = [(k, self.hoist(v, ctx)) for k, v in value.args]
                rec = {
                    "key": stmt.var,
                    "name": value.name,
                    "args": self.args_dict(value.args),
                    "srcmap": stmt.line,
                }
                return list(ctx.inlines) + [rec]
            stmt.value = self.hoist(value, ctx)
            rec = {
                "name": "npc:var:set",
                "args": {
                    "key": '"%s"' % stmt.key,
                    "value": stmt.value,
                    "storage_type": '"%s"' % stmt.storage,
                },
                "srcmap": stmt.line,
            }
            return list(ctx.inlines) + [rec]

        if isinstance(stmt, PIf):
            ctx = GenContext()
            stmt.cond = self.hoist(stmt.cond, ctx)
            T = self.block_records(stmt.true_body)
            if T is None:
                return None
            F = None
            if stmt.else_body is not None:
                F = self.block_records(stmt.else_body)
                if F is None:
                    return None
            recs = list(ctx.inlines) + [{
                "name": "npc:jump_if",
                "args": {
                    "expr": stmt.cond,
                    "offset": True,
                    "negate": True,
                    "pos": len(T) + (1 if F is not None else 0),
                },
                "srcmap": stmt.line,
            }]
            recs.extend(T)
            if F is not None:
                recs.append({
                    "name": "npc:jump",
                    "args": {"offset": True, "pos": len(F)},
                    "srcmap": stmt.else_line,
                })
                recs.extend(F)
            return recs

        if isinstance(stmt, PWhile):
            ctx = GenContext()
            stmt.cond = self.hoist(stmt.cond, ctx)
            B = self.block_records(stmt.body)
            if B is None:
                return None
            recs = list(ctx.inlines) + B
            recs.append({
                "name": "npc:jump_if",
                "args": {
                    "expr": stmt.cond,
                    "offset": True,
                    "negate": False,
                    "pos": -(len(B) + 1),
                },
                "loop_end": True,
                "srcmap": stmt.line,
            })
            return recs

        if isinstance(stmt, PFor):
            ctx = GenContext()
            stmt.init = self.hoist(stmt.init, ctx)
            stmt.cond = self.hoist(stmt.cond, ctx)
            stmt.step = self.hoist(stmt.step, ctx)
            B = self.block_records(stmt.body)
            if B is None:
                return None
            recs = list(ctx.inlines) + [{
                "name": "npc:var:set",
                "args": {
                    "key": '"for_index"',
                    "value": stmt.init,
                    "storage_type": '"local"',
                },
                "srcmap": stmt.line,
            }]
            recs.extend(B)
            recs.append({
                "name": "npc:var:set",
                "args": {
                    "key": '"for_index"',
                    "value": Bin("+", Var("@local.for_index", stmt.line),
                                 stmt.step, stmt.line),
                    "storage_type": '"local"',
                },
                "srcmap": stmt.line,
            })
            recs.append({
                "name": "npc:jump_if",
                "args": {
                    "expr": stmt.cond,
                    "offset": True,
                    "negate": False,
                    "pos": -(len(B) + 2),
                },
                "loop_end": True,
                "srcmap": stmt.line,
            })
            return recs

        raise TypeError("unknown statement %r" % type(stmt))

    def wait_records(self, stmt):
        """npc:wait(time = N) -> the engine's proc-interval expansion.

        Exact shape of the historically working output (no srcmap, the
        first record has no args field).
        """
        if len(stmt.args) != 1 or stmt.args[0][0] != "time":
            self.result.error(stmt.line,
                "npc:wait expects exactly one argument: time")
            return None
        n = stmt.args[0][1]
        return [
            {"key": "_prev_proc_int", "name": "npc:get_proc_interval"},
            {"name": "npc:set_proc_interval", "args": {
                "wait_time": n,
                "value": Bin("-", n, Var("@local._prev_proc_int", stmt.line),
                             stmt.line),
            }},
            {"name": "npc:set_proc_interval", "args": {
                "value": Var("@local._prev_proc_int", stmt.line),
            }},
        ]

    def args_dict(self, args):
        """Structured args table (insertion-ordered dict of Value nodes)."""
        table = {}
        for key, value in args:
            table[key] = value
        return table


# ---------------------------------------------------------------------------
# Output serializer
# ---------------------------------------------------------------------------

def lua_escape_path(path):
    return path.replace("\\", "\\\\").replace('"', '\\"')


def format_args(args):
    """Serialize an instruction's args (dict of Value nodes)."""
    if args is None:
        return None
    parts = []
    for key, value in args.items():
        parts.append(lua_key(key) + " = " + to_lua(value))
    return "{" + ", ".join(parts) + "}"


def format_instruction(rec):
    pieces = []
    if "key" in rec and rec["key"]:
        pieces.append('key = "%s"' % rec["key"])
    pieces.append('name = "%s"' % rec["name"])
    if rec.get("args") is not None:
        pieces.append("args = " + format_args(rec["args"]))
    if rec.get("loop_end"):
        pieces.append("loop_end = true")
    if rec.get("srcmap") is not None:
        pieces.append("srcmap = %d" % rec["srcmap"])
    return "{" + ", ".join(pieces) + "}"


def render_program(program):
    lines = ['npc.proc.register_program("%s", {' % program.name]
    recs = program.instructions
    for i, rec in enumerate(recs):
        if isinstance(rec, list):
            # npc:wait expansion: three records from one line
            for sub in rec:
                lines.append("\t" + format_instruction(sub))
            lines[-1] = lines[-1] + ("," if i < len(recs) - 1 else "")
        else:
            lines.append("\t" + format_instruction(rec)
                         + ("," if i < len(recs) - 1 else ""))
    if program.source_file:
        lines.append('}, "%s")' % lua_escape_path(program.source_file))
    else:
        lines.append("})")
    return "\n".join(lines)


def render(programs):
    return "\n\n".join(render_program(p) for p in programs) + "\n"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compile(text, source_path=""):
    """Compile anpcscript source text.

    Returns a CompileResult. On success: .lua is the full generated source
    and .programs is the structured program list. On failure: .diagnostics
    holds the problems (always at least one).
    """
    result = CompileResult()

    diags = []
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    tokens, tdiags = tokenize(text)
    diags.extend(tdiags)
    if diags:
        result.diagnostics = diags
        return result

    parser = Parser(tokens, result)
    programs_ast = parser.parse()
    if result.diagnostics:
        return result

    for prog in programs_ast:
        cp = CompiledProgram(prog.name, prog.define_line, prog.end_line)
        cp.source_file = source_path
        gen = CodeGen(prog, result)
        records = gen.generate()
        if result.diagnostics:
            return result
        cp.instructions = records
        result.programs.append(cp)

    result.ok = True
    result.lua = render(result.programs)
    return result


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) < 2:
        print("anpc_compiler.py - compile anpcscript into anpc Lua programs")
        print('Usage: python anpc_compiler.py <input.anpcscript> <output.lua>')
        return 0

    input_name, output_name = argv[0], argv[1]
    try:
        with open(input_name, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        print("error: cannot read %s: %s" % (input_name, e), file=sys.stderr)
        return 1

    result = compile(text, source_path=os.path.abspath(input_name))
    if not result.ok:
        for d in result.diagnostics:
            print(str(d), file=sys.stderr)
        print("error: %d problem(s) found in %s"
              % (len(result.diagnostics), input_name), file=sys.stderr)
        return 1

    with open(output_name, "w", encoding="utf-8", newline="\n") as f:
        f.write(result.lua)
    n_instr = sum(len(p.instructions) for p in result.programs)
    print("compiled %s: %d program(s), %d instruction(s) -> %s"
          % (os.path.basename(input_name), len(result.programs),
             n_instr, output_name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
