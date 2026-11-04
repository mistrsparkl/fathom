"""Imagination: turns English-like scripts (*.imagine) into C++.

A script that starts with 'this is part of: <thing>' becomes part of that C++ class (e.g. Unreal code).
Any other script is a program of its own, which starts at its 'to start:' command.

Run a program:          py -3 imagination.py run <script.imagine>
Translate a folder:     py -3 imagination.py <scripts folder> <output folder>
The language itself is described in LANGUAGE.md.
"""
import difflib
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


LOGIC = Path("examples")  # set from the command line by main()
OUT = Path("generated")
HERE = Path(__file__).resolve().parent

NUMBER, YESNO, PLACE, FLAT, TEXT = "number", "yes or no", "place", "flat", "text"
# Kinds are strings: the five above, "list of <kind>", or "thing <name>" for a kind the script describes itself.
CPP_TYPE = {NUMBER: "double", YESNO: "bool", PLACE: "FVector", FLAT: "FVector2D", TEXT: "std::string"}
ZERO = {NUMBER: "0.0", YESNO: "false", PLACE: "FVector::ZeroVector", FLAT: "FVector2D::ZeroVector", TEXT: "std::string()"}
BASIC_WORDS = {"number": NUMBER, "numbers": NUMBER, "yes or no": YESNO, "place": PLACE, "places": PLACE,
               "flat place": FLAT, "flat places": FLAT, "text": TEXT, "texts": TEXT}
THINGS = {}  # name -> [(field words, kind)], for the script being translated

KEYWORDS = set("""set to if otherwise stop note and or not is more less than at least most plus minus times divided by
clamp between smaller larger of square root size flat direction angle from yes no move toward
say ask into repeat while with random for each in contains list empty new remove file write as""".split())


def is_list(kind):
    return kind.startswith("list of ")


def element(kind):
    return kind[len("list of "):]


def is_thing(kind):
    return kind.startswith("thing ")


def cpp_type(kind):
    if is_list(kind):
        return f"std::vector<{cpp_type(element(kind))}>"
    if is_thing(kind):
        return "".join(w.capitalize() for w in kind[6:].split())
    return CPP_TYPE[kind]


def param_type(kind):
    return cpp_type(kind) if kind in (NUMBER, YESNO) else f"const {cpp_type(kind)}&"


def zero(kind):
    return ZERO.get(kind) or f"{cpp_type(kind)}()"


def parse_kind(text):
    """'a number', 'a list of pets', 'some text' -> the kind, or None."""
    words = text.lower().split()
    if words[:1] in (["a"], ["an"], ["some"]):
        words = words[1:]
    phrase = " ".join(words)
    if phrase in BASIC_WORDS:
        return BASIC_WORDS[phrase]
    if words[:2] == ["list", "of"]:
        k = parse_kind(" ".join(words[2:]))
        return k and "list of " + k
    for name in (phrase, phrase[:-1] if phrase.endswith("s") else None):
        if name in THINGS:
            return "thing " + name
    return None


def kind_words():
    return ", ".join(["a number", "yes or no", "text", "a place", "a list of ..."] + [f"a {t}" for t in THINGS])
ITEM_NOT_INDEX = {None, ",", ")", "of", "is", "and", "or", "plus", "minus", "times", "divided", "by", "to",
                  "between", "+", "-", "*", "/", "contains"}
UNITS = set("degrees degree cm centimetres seconds second per squared percent metres metre m s".split())
TOKEN = r'"[^"]*"|\d+(?:\.\d+)?|[A-Za-z][A-Za-z\']*|[():,+\-*/]'


class ScriptError(Exception):
    def __init__(self, line, message):
        super().__init__(message)
        self.line = line
        self.message = message


def tokenize(text, line):
    tokens = re.findall(TOKEN + r"|\S", text)
    for t in tokens:
        if t == '"':
            raise ScriptError(line, 'This text has no closing ". Text goes between two quote marks, like "hello".')
        if not re.fullmatch(TOKEN, t):
            raise ScriptError(line, f"I don't understand the symbol '{t}'.")
    return [t.lower() if t[0].isalpha() else t for t in tokens]


def split_colon(text):
    """Splits 'head: rest' at the first colon that is not inside quote marks."""
    inside = False
    for k, c in enumerate(text):
        inside ^= c == '"'
        if c == ":" and not inside:
            return text[:k], ":", text[k + 1:]
    return text, "", ""


class Value:
    def __init__(self, cpp, kind, writable=False):
        self.cpp, self.kind, self.writable = cpp, kind, writable


class Names:
    """Every name a script can use: the class's words, settings, inputs and the script's own names."""

    def __init__(self):
        self.known = {}  # words tuple -> (cpp, kind, read_only)
        self.commands = {}  # words tuple -> (cpp name, [input kinds], kind given back or None); only programs call commands
        self.gives = None  # what the command being translated gives back

    def add(self, words, cpp, kind, read_only=False):
        self.known[tuple(words)] = (cpp, kind, read_only)

    def match(self, tokens, i):
        for n in range(min(8, len(tokens) - i), 0, -1):
            key = tuple(tokens[i:i + n])
            if key in self.known:
                return key, n
        return None, 0

    def unknown(self, tokens, i):
        """The best guess at what an unknown name at tokens[i] was meant to be, as an error message."""
        known = [" ".join(k) for k in self.known]
        best = (0.0, tokens[i], None)
        for n in range(1, min(5, len(tokens) - i) + 1):
            if not all(t[0].isalpha() for t in tokens[i:i + n]):
                break
            phrase = " ".join(tokens[i:i + n])
            for name in difflib.get_close_matches(phrase, known, n=1, cutoff=0.6):
                score = difflib.SequenceMatcher(None, phrase, name).ratio()
                if score > best[0]:
                    best = (score, phrase, name)
        return f"I don't know '{best[1]}'." + (f" Did you mean '{best[2]}'?" if best[2] else "")


CPP_RESERVED = set("""auto bool break case catch char check class const continue default delete do double else enum
explicit false float for friend goto if inline int long new operator private protected public return short signed
sizeof static struct switch template this throw true try typedef union unsigned using virtual void while""".split())


def snake(words):
    name = "_".join(re.sub(r"[^a-z0-9]", "", w) for w in words)
    return name + "_" if name in CPP_RESERVED else name


class Expr:
    """Reads one expression from a token list (recursive descent, lowest precedence first)."""

    def __init__(self, tokens, names, line):
        self.t, self.i, self.names, self.line = tokens, 0, names, line

    def peek(self, k=0):
        return self.t[self.i + k] if self.i + k < len(self.t) else None

    def at(self, *words):
        return list(self.t[self.i:self.i + len(words)]) == list(words)

    def take(self, *words):
        if not self.at(*words):
            got = self.peek() or "the end of the line"
            raise ScriptError(self.line, f"I expected '{' '.join(words)}' but found '{got}'.")
        self.i += len(words)

    def need(self, value, kind, what):
        if value.kind != kind:
            raise ScriptError(self.line, f"{what} needs {kind_name(kind)}, but this is {kind_name(value.kind)}.")
        return value

    def full(self):
        return self.logic_or()

    def logic_or(self):
        v = self.logic_and()
        while self.at("or"):
            self.i += 1
            r = self.logic_and()
            v = Value(f"({self.need(v, YESNO, 'or').cpp} || {self.need(r, YESNO, 'or').cpp})", YESNO)
        return v

    def logic_and(self):
        v = self.logic_not()
        while self.at("and"):
            self.i += 1
            r = self.logic_not()
            v = Value(f"({self.need(v, YESNO, 'and').cpp} && {self.need(r, YESNO, 'and').cpp})", YESNO)
        return v

    def logic_not(self):
        if self.at("not"):
            self.i += 1
            return Value(f"!{self.need(self.logic_not(), YESNO, 'not').cpp}", YESNO)
        return self.compare()

    COMPARE = [(("is", "more", "than"), ">"), (("is", "less", "than"), "<"), (("is", "at", "least"), ">="),
               (("is", "at", "most"), "<="), (("is", "not"), "!="), (("is",), "==")]

    def made(self):
        """A new value: 'a list of numbers', 'an empty list of text', 'a list of (1, 2, 3)', 'a new pet'."""
        start = self.i
        for lead in (("a", "new"), ("an", "new"), ("new",)):
            if self.at(*lead):
                self.i += len(lead)
                for n in range(min(5, len(self.t) - self.i), 0, -1):
                    name = " ".join(self.t[self.i:self.i + n])
                    if name in THINGS:
                        self.i += n
                        return Value(f"{cpp_type('thing ' + name)}{{}}", "thing " + name)
                raise ScriptError(self.line, f"There is no kind of thing called '{' '.join(self.t[self.i:self.i + 2])}'."
                                  + (f" Kinds of things: {', '.join(THINGS)}." if THINGS else ""))
        for lead in (("a", "list", "of"), ("an", "empty", "list", "of"), ("list", "of"), ("empty", "list", "of")):
            if self.at(*lead):
                self.i += len(lead)
                if "empty" not in lead and self.at("("):
                    self.i += 1
                    items = [self.full()]
                    while self.at(","):
                        self.i += 1
                        items.append(self.full())
                    self.take(")")
                    for v in items:
                        if v.kind != items[0].kind:
                            raise ScriptError(self.line, f"A list holds one kind of thing, but this mixes {kind_name(items[0].kind)} and {kind_name(v.kind)}.")
                    kind = "list of " + items[0].kind
                    return Value(f"{cpp_type(kind)}{{{', '.join(strip_parens(v.cpp) for v in items)}}}", kind)
                for n in range(min(6, len(self.t) - self.i), 0, -1):
                    k = parse_kind(" ".join(self.t[self.i:self.i + n]))
                    if k:
                        self.i += n
                        return Value(f"{cpp_type('list of ' + k)}()", "list of " + k)
                raise ScriptError(self.line, f"Say what the list holds, like 'a list of numbers'. Kinds are: {kind_words()}.")
        self.i = start
        return None

    def compare(self):
        v = self.sum()
        if self.at("contains"):
            self.i += 1
            r = self.sum()
            if not (v.kind == r.kind == TEXT or (is_list(v.kind) and element(v.kind) == r.kind)):
                raise ScriptError(self.line, f"I can't look for {kind_name(r.kind)} in {kind_name(v.kind)}.")
            return Value(f"imagine::contains({v.cpp}, {r.cpp})", YESNO)
        for words, op in self.COMPARE:
            if self.at(*words):
                self.i += len(words)
                r = self.sum()
                if op in ("==", "!=") and v.kind == r.kind and v.kind not in (PLACE, FLAT):
                    return Value(f"({v.cpp} {op} {r.cpp})", YESNO)
                return Value(f"({self.need(v, NUMBER, 'Comparing').cpp} {op} {self.need(r, NUMBER, 'Comparing').cpp})", YESNO)
        return v

    def sum(self):
        v = self.product()
        while self.peek() in ("plus", "+", "minus", "-"):
            op = "+" if self.peek() in ("plus", "+") else "-"
            self.i += 1
            r = self.product()
            if v.kind == TEXT and op == "+":
                v = Value(f"(imagine::text({v.cpp}) + imagine::text({r.cpp}))", TEXT)
                continue
            if v.kind != r.kind or v.kind in (YESNO, TEXT):
                raise ScriptError(self.line, f"I can't {'add' if op == '+' else 'subtract'} {kind_name(r.kind)} {'to' if op == '+' else 'from'} {kind_name(v.kind)}.")
            v = Value(f"({v.cpp} {op} {r.cpp})", v.kind)
        return v

    def product(self):
        v = self.unary()
        while self.peek() in ("times", "*", "/") or self.at("divided", "by"):
            op = "/" if self.peek() in ("/", "divided") else "*"
            self.i += 2 if self.at("divided", "by") else 1
            r = self.unary()
            if r.kind != NUMBER or v.kind in (YESNO, TEXT):
                raise ScriptError(self.line, f"I can only multiply or divide by a number, not {kind_name(r.kind)}.")
            v = Value(f"({v.cpp} {op} {r.cpp})", v.kind)
        return v

    def unary(self):
        if self.peek() in ("-", "minus"):
            self.i += 1
            v = self.unary()
            if v.kind in (YESNO, TEXT):
                raise ScriptError(self.line, f"I can't make {kind_name(v.kind)} negative.")
            return Value(f"(-{v.cpp})", v.kind)
        v = self.primary()
        if self.at("as", "a", "number") or self.at("as", "number"):
            self.i += 3 if self.at("as", "a") else 2
            if v.kind != TEXT:
                raise ScriptError(self.line, f"'as a number' turns text into a number, but this is {kind_name(v.kind)}.")
            return Value(f"imagine::to_number({v.cpp}, {self.line})", NUMBER)
        if self.at("as", "text"):
            self.i += 2
            return Value(f"imagine::text({v.cpp})", TEXT)
        return v

    def primary(self):
        tok = self.peek()
        if tok is None:
            raise ScriptError(self.line, "This line ends too early: something is missing.")
        if re.fullmatch(r"\d+(?:\.\d+)?", tok):
            self.i += 1
            while self.peek() in UNITS:
                self.i += 1
            return Value(tok if "." in tok else tok + ".0", NUMBER)
        if tok.startswith('"'):
            self.i += 1
            return Value(cpp_text(tok), TEXT)
        if self.at("random", "number", "from"):
            self.i += 3
            lo = self.need(self.sum(), NUMBER, "random number")
            self.take("to")
            hi = self.need(self.sum(), NUMBER, "random number")
            return Value(f"imagine::random({lo.cpp}, {hi.cpp})", NUMBER)
        if tok == "(":
            self.i += 1
            v = self.full()
            self.take(")")
            return v
        for n in range(min(6, len(self.t) - self.i), 0, -1):
            key = tuple(self.t[self.i:self.i + n])
            if key in FIELDS and self.peek(n) == "of":
                self.i += n + 1
                owner = self.unary()
                if owner.kind not in FIELDS[key]:
                    raise ScriptError(self.line, f"{kind_name(owner.kind).capitalize()} has no '{' '.join(key)}'.")
                member, kind = FIELDS[key][owner.kind]
                return Value(f"({owner.cpp}).{member}", kind, owner.writable)
        if tok == "item" and self.peek(1) not in ITEM_NOT_INDEX:
            self.i += 1
            index = self.need(self.sum(), NUMBER, "item")
            self.take("of")
            seq = self.unary()
            if not is_list(seq.kind):
                raise ScriptError(self.line, f"'item ... of' needs a list, but this is {kind_name(seq.kind)}.")
            return Value(f"imagine::at({seq.cpp}, {strip_parens(index.cpp)}, {self.line})", element(seq.kind), seq.writable)
        key, n = self.names.match(self.t, self.i)
        if key:
            self.i += n
            cpp, kind, read_only = self.names.known[key]
            return Value(cpp, kind, not read_only)
        key, n = match_command(self.names, self.t[self.i:])
        if key:
            self.i += n
            needs = len(self.names.commands[key][1])
            if self.at("with"):
                self.i += 1
            args = []
            if needs == 1:
                args = [self.unary()]
            elif needs > 1:
                if not self.at("("):
                    raise ScriptError(self.line, f"'{' '.join(key)}' needs {needs} inputs. Put them in brackets here, like: {' '.join(key)} with (1, 2)")
                self.i += 1
                args = [self.full()]
                while self.at(","):
                    self.i += 1
                    args.append(self.full())
                self.take(")")
            gives = self.names.commands[key][2]
            if not gives:
                raise ScriptError(self.line, f"'{' '.join(key)}' doesn't give back anything, so it can't be used as a value.")
            return Value(call(key, args, self.names, self.line), gives)
        made = self.made()
        if made:
            return made
        if tok in ("yes", "no"):
            self.i += 1
            return Value("true" if tok == "yes" else "false", YESNO)
        if self.at("clamp"):
            self.i += 1
            v = self.need(self.sum(), NUMBER, "clamp")
            self.take("between")
            lo = self.need(self.sum(), NUMBER, "clamp")
            self.take("and")
            hi = self.need(self.sum(), NUMBER, "clamp")
            return Value(f"FMath::Clamp({v.cpp}, {lo.cpp}, {hi.cpp})", NUMBER)
        for word, fn in (("smaller", "Min"), ("larger", "Max")):
            if self.at(word, "of"):
                self.i += 2
                a = self.need(self.sum(), NUMBER, f"{word} of")
                self.take("and")
                b = self.need(self.sum(), NUMBER, f"{word} of")
                return Value(f"FMath::{fn}({a.cpp}, {b.cpp})", NUMBER)
        for words, fn, kind, what in ((("contents", "of", "file"), "read_file", TEXT, "text"),
                                      (("lines", "of", "file"), "read_lines", "list of text", "lines"),
                                      (("file",), "file_exists", YESNO, "exists")):
            if self.at(*words):
                self.i += len(words)
                where = self.need(self.unary(), TEXT, "file")
                if fn == "file_exists":
                    self.take("exists")
                    return Value(f"imagine::file_exists({where.cpp})", YESNO)
                return Value(f"imagine::{fn}({where.cpp}, {self.line})", kind)
        for words, fn in ((("lines", "of"), "lines_of"), (("words", "of"), "words_of")):
            if self.at(*words):
                self.i += 2
                return Value(f"imagine::{fn}({self.need(self.unary(), TEXT, ' '.join(words)).cpp})", "list of text")
        if self.at("square", "root", "of"):
            self.i += 3
            return Value(f"FMath::Sqrt({self.need(self.sum(), NUMBER, 'square root').cpp})", NUMBER)
        if self.at("size", "of"):
            self.i += 2
            v = self.sum()
            if v.kind == NUMBER:
                return Value(f"FMath::Abs({v.cpp})", NUMBER)
            if v.kind in (PLACE, FLAT):
                return Value(f"({v.cpp}).Size()", NUMBER)
            if v.kind == TEXT or is_list(v.kind):
                return Value(f"double(({v.cpp}).size())", NUMBER)
            raise ScriptError(self.line, "yes or no has no size.")
        if self.at("flat"):
            self.i += 1
            return Value(f"FVector2D({self.need(self.unary(), PLACE, 'flat').cpp})", FLAT)
        if self.at("direction", "of"):
            self.i += 2
            v = self.need(self.sum(), FLAT, "direction of")
            return Value(f"FMath::RadiansToDegrees(FMath::Atan2(({v.cpp}).Y, ({v.cpp}).X))", NUMBER)
        if self.at("angle", "from"):
            self.i += 2
            a = self.need(self.sum(), NUMBER, "angle from")
            self.take("to")
            b = self.need(self.sum(), NUMBER, "angle from")
            return Value(f"FMath::UnwindDegrees({b.cpp} - {a.cpp})", NUMBER)
        if tok in KEYWORDS:
            raise ScriptError(self.line, f"'{tok}' can't go here.")
        raise ScriptError(self.line, self.names.unknown(self.t, self.i))


def kind_name(kind):
    if is_list(kind):
        return "a list of " + plural(element(kind))
    if is_thing(kind):
        return "a " + kind[6:]
    return {NUMBER: "a number", YESNO: "yes or no", PLACE: "a place", FLAT: "a flat place", TEXT: "text"}[kind]


def plural(kind):
    if is_list(kind):
        return "lists of " + plural(element(kind))
    if is_thing(kind):
        return kind[6:] + "s"
    return {NUMBER: "numbers", YESNO: "yes or no", PLACE: "places", FLAT: "flat places", TEXT: "text"}[kind]


def load_words(name, line):
    path = LOGIC / f"{name}.words"
    if not path.exists():
        raise ScriptError(line, f"There is no '{name}' to be part of (no {name}.words next to the script).")
    names, info = Names(), {}
    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        text = raw.strip()
        if not text or text.startswith("note:"):
            continue
        if text.startswith("class:") or text.startswith("header:"):
            key, value = text.split(":", 1)
            info[key] = value.strip()
            continue
        english, _, rest = text.partition("=")
        parts = [p.strip() for p in rest.rsplit(",", 2)]
        read_only = parts[-1] == "read only"
        if read_only:
            parts = parts[:-1]
        cpp, kind = ", ".join(parts[:-1]), parts[-1]
        if kind not in CPP_TYPE:
            raise ScriptError(n, f"{path.name}: unknown type '{kind}'.")
        names.add(english.strip().lower().split(), cpp, kind, read_only)
    return names, info


CLOSING = "and the universe said i love you"


def is_closing(line):
    """The line every command must end with."""
    return line.strip().lower().rstrip(".") == CLOSING


def translate(path):
    """Returns the C++ text for one .imagine file, or raises ScriptError."""
    lines = path.read_text(encoding="utf-8").splitlines()
    names, info, settings, out = None, {}, [], []
    commands = []  # (header text, line, body)
    things = []  # (name, line, [(line, field text)])
    THINGS.clear()
    FIELDS.clear()
    first = next((t.strip() for t in lines if t.strip() and not t.strip().startswith("note:")), "")
    if not first.startswith("this is part of:"):
        names, info = Names(), None  # a program of its own
    i = 0
    while i < len(lines):
        raw = lines[i]
        text = raw.strip()
        n = i + 1
        i += 1
        if not text:
            continue
        if text.startswith("note:"):
            if not raw[0].isspace():
                out.append(f"// {text[5:].strip()}")
            continue
        if text.startswith("this is part of:"):
            if text != first or (names and names.known):
                raise ScriptError(n, "'this is part of:' must be the first line of the script (after notes).")
            names, info = load_words(text.split(":", 1)[1].strip().lower(), n)
            continue
        if text == "settings:":
            while i < len(lines) and (not lines[i].strip() or lines[i][:1].isspace()):
                s = lines[i].strip()
                i += 1
                if not s:
                    continue
                if s.startswith("note:"):
                    settings.append(f"	// {s[5:].strip()}")
                    continue
                m = re.fullmatch(r"([a-z][a-z' ]*):\s*(-?\d+(?:\.\d+)?)\s*(.*)", s.lower())
                if not m:
                    raise ScriptError(i, "A setting looks like 'name: number', e.g. 'look limit: 30 degrees'.")
                words = m.group(1).split()
                cpp = f"Imagine_{snake(path.stem.split())}::{snake(words)}"
                names.add(words, cpp, NUMBER, read_only=True)
                value = m.group(2) if "." in m.group(2) else m.group(2) + ".0"
                settings.append(f"\tconstexpr double {snake(words)} = {value};{'  // ' + m.group(3) if m.group(3) else ''}")
            continue
        if text.startswith("to ") and text.endswith(":"):
            body = []
            while i < len(lines) and (not lines[i].strip() or lines[i][:1].isspace()):
                body.append((i + 1, lines[i]))
                i += 1
            commands.append((text, n, body))
            if i >= len(lines) or not is_closing(lines[i]):
                raise ScriptError(i + 1 if i < len(lines) else len(lines),
                                  f"The command '{text[:-1]}' must end with the line '{CLOSING}', unindented, after its last indented line.")
            i += 1
            continue
        m = re.fullmatch(r"an? ([a-z][a-z ]*?) has:", text.lower())
        if m:
            fields = []
            while i < len(lines) and (not lines[i].strip() or lines[i][:1].isspace()):
                if lines[i].strip() and not lines[i].strip().startswith("note:"):
                    fields.append((i + 1, lines[i].strip()))
                i += 1
            if i >= len(lines) or not is_closing(lines[i]):
                raise ScriptError(i + 1 if i < len(lines) else len(lines),
                                  f"The description of '{m.group(1)}' must end with the line '{CLOSING}', unindented.")
            i += 1
            name = " ".join(m.group(1).split())
            if name in THINGS or name in BASIC_WORDS:
                raise ScriptError(n, f"There is already a kind of thing called '{name}'.")
            THINGS[name] = []
            things.append((name, n, fields))
            continue
        if is_closing(text):
            raise ScriptError(n, f"'{CLOSING}' closes a command, so it goes right after the command's last indented line.")
        raise ScriptError(n, f"I don't know what to do with '{text}'. Top-level lines are notes, 'settings:', 'a ... has:' or 'to ...:'.")
    if names is None:
        raise ScriptError(1, "The script is empty.")
    program = info is None
    if things and not program:
        raise ScriptError(things[0][1], "New kinds of things can only be described in programs for now.")
    structs = describe_things(things)
    heads = [command_head(text, n) for text, n, _ in commands]
    if program:
        for words, cpp, inputs, gives in heads:
            if tuple(words) in names.commands:
                raise ScriptError(next(n for t, n, _ in commands if command_head(t, n)[0] == words),
                                  f"There are two commands called '{' '.join(words)}'.")
            names.commands[tuple(words)] = (cpp, [kind for _, kind in inputs], gives)
        if ("start",) not in names.commands:
            raise ScriptError(len(lines) or 1, "A program needs a 'to start:' command: that is where it begins.")
    functions = [function(head, n, body, names, info) for head, (_, n, body) in zip(heads, commands)]
    if program:
        protos = [f"{cpp_type(gives) if gives else 'void'} {cpp}({', '.join(param_type(k) + ' ' + snake(w) for w, k in inputs)});"
                  for _, cpp, inputs, gives in heads]
        head = [f"// Generated from {path.name} by imagination.py. Edit the .imagine file, not this one.",
                '#include "imagination.h"', ""] + structs + protos + [""]
        functions.append("int main()\n{\n\tStart();\n\treturn 0;\n}\n")
    else:
        head = [f"// Generated from {path.name} by imagination.py. Edit the .imagine file, not this one.",
                f'#include "{info["header"]}"', ""]
    ns = [f"namespace Imagine_{snake(path.stem.split())}", "{"] + settings + ["}", ""] if settings else []
    return "\n".join(head + ns + out + [""] + functions) + "\n"


FIELDS = {}  # field words tuple -> {thing kind: (cpp member, kind)}


def describe_things(things):
    """Reads 'a pet has:' descriptions; returns the C++ structs."""
    for name, n, fields in things:
        if not fields:
            raise ScriptError(n, f"Say what a {name} has, one thing per indented line, like: name (text)")
        for fn, text in fields:
            m = re.fullmatch(r"([a-z][a-z ]*?)\s*\(([a-z ]+)\)", text.lower())
            kind = m and parse_kind(m.group(2))
            if not kind:
                raise ScriptError(fn, f"Each thing a {name} has looks like 'name (text)'. Kinds are: {kind_words()}.")
            if kind == "thing " + name:
                raise ScriptError(fn, f"A {name} can't hold a whole {name} inside itself, but it can hold a list of {name}s.")
            words = m.group(1).split()
            if any(w in KEYWORDS for w in words):
                raise ScriptError(fn, f"'{' '.join(words)}' can't be a name: it uses the language's own words.")
            THINGS[name].append((words, kind))
            FIELDS.setdefault(tuple(words), {})["thing " + name] = (snake(words), kind)
    out = []
    if things:
        out.append("namespace imagine\n{")
        out += [f"\tstruct {cpp_type('thing ' + name)};" for name, _, _ in things]
        for name, _, _ in things:
            cpp = cpp_type("thing " + name)
            out.append(f"\tstruct {cpp}\n\t{{")
            out += [f"\t\t{cpp_type(k)} {snake(w)} = {zero(k)};" for w, k in THINGS[name]]
            out.append(f"\t\tbool operator==(const {cpp}&) const = default;\n\t}};")
        for name, _, _ in things:
            cpp = cpp_type("thing " + name)
            shown = ' + ", " + '.join(f'"{" ".join(w)}: " + text(v.{snake(w)})' for w, k in THINGS[name])
            out.append(f'\tinline std::string text(const {cpp}& v) {{ return std::string("a {name} (") + {shown} + ")"; }}')
        out.append("}")
        out += [f"using imagine::{cpp_type('thing ' + name)};" for name, _, _ in things]
        out.append("")
    return out


def command_head(header, line):
    """'to greet, given name (text):' -> (['greet'], 'Greet', [(['name'], TEXT)], None)."""
    m = re.fullmatch(r"to ([a-z ]+?)(?:, given (.+?))?(?:, giving back (.+))?:", header.lower())
    if not m:
        raise ScriptError(line, "A command starts like 'to steer toward, given goal (a place) and running (yes or no):'.")
    inputs = []
    if m.group(2):
        for part in re.split(r"\s+and\s+(?=[a-z ]+\()", m.group(2)):
            pm = re.fullmatch(r"([a-z ]+?)\s*\(([a-z ]+)\)", part.strip())
            kind = pm and parse_kind(pm.group(2))
            if not kind:
                raise ScriptError(line, f"An input looks like 'goal (a place)'. Kinds are: {kind_words()}.")
            inputs.append((pm.group(1).split(), kind))
    gives = None
    if m.group(3):
        gives = parse_kind(m.group(3))
        if not gives:
            raise ScriptError(line, f"'giving back' needs a kind, like 'giving back a number'. Kinds are: {kind_words()}.")
    words = m.group(1).split()
    return words, "".join(w.capitalize() for w in words), inputs, gives


def function(head, line, body, names, info):
    words, name, inputs, gives = head
    local = Names()
    local.known = dict(names.known)
    local.commands = names.commands
    local.gives = gives
    if any(cpp_type("thing " + t) == name for t in THINGS):
        raise ScriptError(line, f"The command '{' '.join(words)}' has the same name as a kind of thing. Give one of them another name.")
    params = []
    for in_words, kind in inputs:
        params.append(f"{param_type(kind)} {snake(in_words)}")
        local.add(in_words, snake(in_words), kind, read_only=True)
    declared = {}
    code = statements(body, local, declared, 1)
    hoisted = [f"\t{cpp_type(k)} {c} = {zero(k)};" for c, k in declared.values()]
    owner = f"{info['class']}::" if info else ""
    end = [f"\treturn {zero(gives)};"] if gives else []
    return "\n".join([f"{cpp_type(gives) if gives else 'void'} {owner}{name}({', '.join(params)})", "{"]
                     + hoisted + code + end + ["}"]) + "\n"


def statements(body, names, declared, depth):
    """Translates an indented block. body: list of (line number, raw text)."""
    out = []
    rows = [(n, r) for n, r in body if r.strip()]
    if not rows:
        return out
    indent = len(rows[0][1].expandtabs(4)) - len(rows[0][1].expandtabs(4).lstrip())
    k = 0
    while k < len(rows):
        n, raw = rows[k]
        width = len(raw.expandtabs(4)) - len(raw.expandtabs(4).lstrip())
        if width != indent:
            raise ScriptError(n, "This line is indented differently from the lines around it.")
        k += 1
        inner = []
        while k < len(rows) and len(rows[k][1].expandtabs(4)) - len(rows[k][1].expandtabs(4).lstrip()) > indent:
            inner.append(rows[k])
            k += 1
        out += statement(n, raw.strip(), inner, names, declared, depth)
    return out


def statement(n, text, inner, names, declared, depth):
    tab = "\t" * depth
    if text.startswith("note:"):
        return [f"{tab}// {text[5:].strip()}"]
    head, colon, rest = split_colon(text)
    if colon and re.match(r"for each ", text.lower()):
        return for_each(n, head, rest, inner, names, declared, depth)
    if colon and re.match(r"(repeat |while )", text.lower()):
        tokens = tokenize(head, n)
        if tokens[0] == "while":
            v = expr_to_end(tokens, 1, names, n)
            if v.kind != YESNO:
                raise ScriptError(n, f"'while' needs something that is yes or no, but this is {kind_name(v.kind)}.")
            line = [f"{tab}while ({strip_parens(v.cpp)})"]
        else:
            if tokens[-1:] != ["times"]:
                raise ScriptError(n, "'repeat' looks like 'repeat 10 times:'.")
            count = expr_to_end(tokens[:-1], 1, names, n)
            if count.kind != NUMBER:
                raise ScriptError(n, f"'repeat' needs a number of times, but this is {kind_name(count.kind)}.")
            k = f"imagine_count_{depth}_{n}"
            line = [f"{tab}for (long long {k} = 0; {k} < (long long)({strip_parens(count.cpp)}); ++{k})"]
        block = statement(n, rest.strip(), [], names, declared, depth + 1) if rest.strip() else statements(inner, names, declared, depth + 1)
        if not block:
            raise ScriptError(n, "Say what to repeat after the ':' (on the same line or indented below).")
        return line + [tab + "{"] + block + [tab + "}"]
    if colon and re.match(r"(if |otherwise\b)", text):
        tokens = tokenize(head, n)
        if tokens[:2] == ["otherwise", "if"]:
            cond, prefix = tokens[2:], "else if"
        elif tokens == ["otherwise"]:
            cond, prefix = None, "else"
        elif tokens[0] == "if":
            cond, prefix = tokens[1:], "if"
        else:
            raise ScriptError(n, "Use 'if ...:', 'otherwise if ...:' or 'otherwise:'.")
        line = f"{tab}{prefix}"
        if cond is not None:
            e = Expr(cond, names, n)
            v = e.full()
            if e.i != len(cond):
                raise ScriptError(n, f"I don't understand '{' '.join(cond[e.i:])}' here.")
            if v.kind != YESNO:
                raise ScriptError(n, f"'if' needs something that is yes or no, but this is {kind_name(v.kind)}.")
            line += f" ({strip_parens(v.cpp)})"
        block = statement(n, rest.strip(), [], names, declared, depth + 1) if rest.strip() else statements(inner, names, declared, depth + 1)
        if not block:
            raise ScriptError(n, "Say what to do after the ':' (on the same line or indented below).")
        return [line, tab + "{"] + block + [tab + "}"]
    if inner:
        raise ScriptError(inner[0][0], "Only 'if', 'otherwise', 'repeat' and 'while' lines can have indented lines under them.")
    tokens = tokenize(text, n)
    if tokens == ["stop"]:
        if names.gives:
            raise ScriptError(n, f"This command gives back {kind_name(names.gives)}, so leave it with 'give back ...' instead of 'stop'.")
        return [f"{tab}return;"]
    if tokens[:2] == ["give", "back"]:
        if not names.gives:
            raise ScriptError(n, "'give back' only works in a command that says what it gives back, like 'to double, given x (a number), giving back a number:'.")
        v = expr_to_end(tokens, 2, names, n)
        if v.kind != names.gives:
            raise ScriptError(n, f"This command gives back {kind_name(names.gives)}, not {kind_name(v.kind)}.")
        return [f"{tab}return {strip_parens(v.cpp)};"]
    if tokens[0] in ("add", "write") and "to" in tokens and tokens[len(tokens) - tokens[::-1].index("to"):][:1] == ["file"]:
        cut = len(tokens) - 1 - tokens[::-1].index("to")
        where = expr_to_end(tokens, cut + 2, names, n)
        v = expr_to_end(tokens[:cut], 1, names, n)
        if where.kind != TEXT:
            raise ScriptError(n, f"A file is named with text, like file \"notes.txt\", but this is {kind_name(where.kind)}.")
        fn = "add_line" if tokens[0] == "add" else "write_file"
        return [f"{tab}imagine::{fn}({strip_parens(where.cpp)}, imagine::text({strip_parens(v.cpp)}), {n});"]
    if tokens[0] == "add" and "to" in tokens:
        cut = len(tokens) - 1 - tokens[::-1].index("to")
        target = writable_list(tokens[cut + 1:], names, n, "add to")
        v = expr_to_end(tokens[:cut], 1, names, n)
        if v.kind != element(target.kind):
            raise ScriptError(n, f"This list holds {plural(element(target.kind))}, so I can't add {kind_name(v.kind)} to it.")
        return [f"{tab}({target.cpp}).push_back({strip_parens(v.cpp)});"]
    if tokens[0] == "remove" and "from" in tokens:
        cut = len(tokens) - 1 - tokens[::-1].index("from")
        target = writable_list(tokens[cut + 1:], names, n, "remove from")
        if tokens[1] == "item":
            index = expr_to_end(tokens[:cut], 2, names, n)
            if index.kind != NUMBER:
                raise ScriptError(n, f"'remove item' needs a number, but this is {kind_name(index.kind)}.")
            return [f"{tab}imagine::remove_item({target.cpp}, {strip_parens(index.cpp)}, {n});"]
        v = expr_to_end(tokens[:cut], 1, names, n)
        if v.kind != element(target.kind):
            raise ScriptError(n, f"This list holds {plural(element(target.kind))}, so it has no {kind_name(v.kind)} to remove.")
        return [f"{tab}imagine::remove_value({target.cpp}, {strip_parens(v.cpp)});"]
    if tokens[0] == "say":
        parts = expr_list(tokens, 1, names, n)
        if not parts:
            raise ScriptError(n, "'say' needs something to say, like: say \"hello\".")
        return [f"{tab}imagine::say({{{', '.join('imagine::text(' + strip_parens(p.cpp) + ')' for p in parts)}}});"]
    if tokens[0] == "ask":
        return ask(tokens, names, declared, n, tab)
    key, size = match_command(names, tokens)
    if key:
        args = expr_list(tokens, size + (tokens[size:size + 1] == ["with"]), names, n)
        return [f"{tab}{call(key, args, names, n)};"]
    if tokens[0] == "set" and "to" in tokens and ("of" in tokens[1:tokens.index("to")] or tokens[1:2] == ["item"]):
        cut = tokens.index("to")
        e = Expr(tokens[1:cut], names, n)
        target = e.full()
        if e.i != len(e.t) or not target.writable:
            raise ScriptError(n, f"'{' '.join(tokens[1:cut])}' can't be changed.")
        v = expr_to_end(tokens, cut + 1, names, n)
        if v.kind != target.kind:
            raise ScriptError(n, f"'{' '.join(tokens[1:cut])}' holds {kind_name(target.kind)}, not {kind_name(v.kind)}.")
        return [f"{tab}{strip_parens(target.cpp)} = {strip_parens(v.cpp)};"]
    if tokens[0] == "set":
        key, size = names.match(tokens, 1)
        if key and tokens[1 + size:2 + size] == ["to"]:
            cpp, kind, read_only = names.known[key]
            if read_only:
                raise ScriptError(n, f"'{' '.join(key)}' can't be changed by a script.")
            v = expr_to_end(tokens, 2 + size, names, n)
            if v.kind != kind:
                raise ScriptError(n, f"'{' '.join(key)}' holds {kind_name(kind)}, not {kind_name(v.kind)}.")
            return [f"{tab}{cpp} = {strip_parens(v.cpp)};"]
        if "to" not in tokens:
            raise ScriptError(n, "'set' looks like 'set speed to 5'.")
        words = tokens[1:tokens.index("to")]
        if not words or any(w in KEYWORDS or not w[0].isalpha() for w in words):
            raise ScriptError(n, f"'{' '.join(words)}' can't be a name: names can't use the words {', '.join(sorted(set(words) & KEYWORDS)) or 'symbols'}.")
        v = expr_to_end(tokens, tokens.index("to") + 1, names, n)
        cpp = snake(words)
        if tuple(words) in declared and declared[tuple(words)][1] != v.kind:
            raise ScriptError(n, f"'{' '.join(words)}' already holds {kind_name(declared[tuple(words)][1])}, so it can't hold {kind_name(v.kind)}.")
        declared[tuple(words)] = (cpp, v.kind)
        names.add(words, cpp, v.kind)
        return [f"{tab}{cpp} = {strip_parens(v.cpp)};"]
    if tokens[0] == "move":
        key, size = names.match(tokens, 1)
        if not key or tokens[1 + size:2 + size] != ["toward"]:
            raise ScriptError(n, "'move' looks like 'move turn rate toward 20 by at most 5'.")
        cpp, kind, read_only = names.known[key]
        if read_only or kind != NUMBER:
            raise ScriptError(n, f"'{' '.join(key)}' can't be moved: it must be a number a script may change.")
        e = Expr(tokens[2 + size:], names, n)
        goal = e.need(e.sum(), NUMBER, "move")
        e.take("by", "at", "most")
        step = e.need(e.sum(), NUMBER, "move")
        if e.i != len(e.t):
            raise ScriptError(n, f"I don't understand '{' '.join(e.t[e.i:])}' here.")
        s = f"imagine_step_{depth}_{n}"
        return [f"{tab}const double {s} = {strip_parens(step.cpp)};",
                f"{tab}{cpp} = FMath::Clamp({strip_parens(goal.cpp)}, {cpp} - {s}, {cpp} + {s});"]
    raise ScriptError(n, f"I don't know how to start a line with '{tokens[0]}'. Lines start with set, move, say, ask, if, otherwise, repeat, while, stop, note or the name of a command.")


def for_each(n, head, rest, inner, names, declared, depth):
    """for each score in scores:  /  for each n from 1 to 10:"""
    tab = "\t" * depth
    tokens = tokenize(head, n)
    cut = next((k for k, t in enumerate(tokens) if t in ("in", "from")), None)
    words = tokens[2:cut] if cut else []
    if not words or any(w in KEYWORDS or not w[0].isalpha() for w in words):
        raise ScriptError(n, "'for each' looks like 'for each score in scores:' or 'for each n from 1 to 10:'.")
    if tuple(words) in names.known:
        raise ScriptError(n, f"'{' '.join(words)}' already means something here, so pick another name for each item.")
    cpp = snake(words) + f"_{n}"
    if tokens[cut] == "in":
        seq = expr_to_end(tokens, cut + 1, names, n)
        if not is_list(seq.kind):
            raise ScriptError(n, f"'for each ... in' needs a list, but this is {kind_name(seq.kind)}.")
        kind = element(seq.kind)
        line = f"{tab}for (const {cpp_type(kind)} {cpp} : imagine::copy({strip_parens(seq.cpp)}))"
    else:
        e = Expr(tokens[cut + 1:], names, n)
        lo = e.need(e.sum(), NUMBER, "for each ... from")
        e.take("to")
        hi = e.need(e.sum(), NUMBER, "for each ... from")
        if e.i != len(e.t):
            raise ScriptError(n, f"I don't understand '{' '.join(e.t[e.i:])}' here.")
        kind = NUMBER
        end = f"imagine_end_{n}"
        line = f"{tab}for (double {cpp} = {strip_parens(lo.cpp)}, {end} = {strip_parens(hi.cpp)}; {cpp} <= {end}; {cpp} += 1)"
    names.add(words, cpp, kind, read_only=True)
    block = statement(n, rest.strip(), [], names, declared, depth + 1) if rest.strip() else statements(inner, names, declared, depth + 1)
    del names.known[tuple(words)]
    if not block:
        raise ScriptError(n, "Say what to do for each one after the ':' (on the same line or indented below).")
    return [line, tab + "{"] + block + [tab + "}"]


def call(key, args, names, n):
    """C++ for calling a command, after checking its inputs."""
    cpp, kinds, _ = names.commands[key]
    if len(args) != len(kinds):
        raise ScriptError(n, f"'{' '.join(key)}' needs {len(kinds)} input{'s' if len(kinds) != 1 else ''}, but this gives it {len(args)}.")
    for k, (a, kind) in enumerate(zip(args, kinds), 1):
        if a.kind != kind:
            raise ScriptError(n, f"Input {k} of '{' '.join(key)}' must be {kind_name(kind)}, not {kind_name(a.kind)}.")
    return f"{cpp}({', '.join(strip_parens(a.cpp) for a in args)})"


def writable_list(tokens, names, n, what):
    e = Expr(tokens, names, n)
    v = e.full()
    if e.i != len(e.t):
        raise ScriptError(n, f"I don't understand '{' '.join(e.t[e.i:])}' here.")
    if not is_list(v.kind):
        raise ScriptError(n, f"'{what}' needs a list, but this is {kind_name(v.kind)}.")
    if not v.writable:
        raise ScriptError(n, f"'{' '.join(tokens)}' can't be changed.")
    return v


def match_command(names, tokens):
    for size in range(len(tokens), 0, -1):
        if tuple(tokens[:size]) in names.commands:
            return tuple(tokens[:size]), size
    return None, 0


def ask(tokens, names, declared, n, tab):
    """ask "question" into name (kind) -- shows the question and keeps what the person types."""
    m = len(tokens) >= 4 and tokens[1].startswith('"') and tokens[2] == "into"
    if not m:
        raise ScriptError(n, "'ask' looks like: ask \"What's your name? \" into name (text)")
    rest = tokens[3:]
    kind = TEXT
    if rest[-1:] == [")"] and "(" in rest:
        cut = rest.index("(")
        kind = parse_kind(" ".join(rest[cut + 1:-1]))
        if kind not in (TEXT, NUMBER):
            raise ScriptError(n, "'ask' can keep a number or text, like: into age (a number)")
        rest = rest[:cut]
    key, size = names.match(rest, 0)
    if key and size == len(rest):
        cpp, have, read_only = names.known[key]
        if read_only or have not in (TEXT, NUMBER):
            raise ScriptError(n, f"'{' '.join(key)}' can't hold an answer.")
        if "(" in tokens and have != kind:
            raise ScriptError(n, f"'{' '.join(key)}' already holds {kind_name(have)}, so it can't hold {kind_name(kind)}.")
        kind = have
    else:
        if not rest or any(w in KEYWORDS or not w[0].isalpha() for w in rest):
            raise ScriptError(n, f"'{' '.join(rest)}' can't be a name.")
        cpp = snake(rest)
        declared[tuple(rest)] = (cpp, kind)
        names.add(rest, cpp, kind)
    reader = "imagine::ask_number" if kind == NUMBER else "imagine::ask_text"
    return [f"{tab}{cpp} = {reader}({cpp_text(tokens[1])});"]


def cpp_text(token):
    """A quoted text token as a C++ string."""
    return "std::string(" + token.replace("\\", "\\\\") + ")"


def expr_list(tokens, start, names, n):
    """Reads 'a, b, c' up to the end of the line."""
    e = Expr(tokens[start:], names, n)
    parts = []
    while e.i < len(e.t):
        parts.append(e.full())
        if e.i < len(e.t):
            e.take(",")
    return parts


def expr_to_end(tokens, start, names, n):
    e = Expr(tokens[start:], names, n)
    v = e.full()
    if e.i != len(e.t):
        raise ScriptError(n, f"I don't understand '{' '.join(e.t[e.i:])}' here.")
    return v


def strip_parens(cpp):
    if cpp.startswith("(") and cpp.endswith(")"):
        depth = 0
        for k, c in enumerate(cpp):
            depth += c == "("
            depth -= c == ")"
            if depth == 0 and k < len(cpp) - 1:
                return cpp
        return cpp[1:-1]
    return cpp


def find_vcvars():
    """The Visual Studio script that sets up the C++ compiler, or None."""
    vswhere = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
    if not vswhere.exists():
        return None
    found = subprocess.run([str(vswhere), "-latest", "-products", "*", "-property", "installationPath"],
                           capture_output=True, text=True).stdout.strip()
    bat = Path(found) / "VC" / "Auxiliary" / "Build" / "vcvars64.bat" if found else None
    return bat if bat and bat.exists() else None


def build(script, exe):
    """Translates a program script and compiles it into exe. Returns an error message, or None."""
    global LOGIC
    LOGIC = script.parent
    try:
        cpp_text_out = translate(script)
    except ScriptError as err:
        return f"{script.name} line {err.line}: {err.message}"
    if "int main()" not in cpp_text_out:
        return f"{script.name} is part of something else ('this is part of:'), so it can't run on its own."
    vcvars = find_vcvars()
    if not vcvars:
        return "I can't find the C++ compiler. Install Visual Studio with 'Desktop development with C++'."
    work = Path(tempfile.mkdtemp(prefix="imagine_"))
    cpp = work / f"{script.stem}.imagine.cpp"
    cpp.write_text(cpp_text_out, encoding="utf-8")
    bat = work / "build.bat"
    bat.write_text(f'@call "{vcvars}" >nul 2>&1\r\n@cl /nologo /utf-8 /EHsc /std:c++20 /O2 /W0 /I"{HERE / "runtime"}" '
                   f'"{cpp}" /Fe"{exe}" /Fo"{work}\\\\" >"{work / "compile.log"}" 2>&1\r\n', encoding="utf-8")
    result = subprocess.run(["cmd", "/c", str(bat)])
    if result.returncode != 0:
        log = (work / "compile.log").read_text(errors="replace")
        return f"Imagination wrote C++ the compiler didn't accept. That is a bug in Imagination, not in your script.\n{log}"
    return None


def main(argv):
    global LOGIC, OUT
    if len(argv) == 3 and argv[1] == "run":
        script = Path(argv[2])
        if not script.exists():
            print(f"There is no script called {script}.")
            return 2
        exe = script.with_suffix(".exe")
        problem = build(script, exe)
        if problem:
            print(problem)
            return 1
        return subprocess.run([str(exe.resolve())]).returncode
    if len(argv) != 3:
        print("Use: py -3 imagination.py run <script.imagine>")
        print("  or py -3 imagination.py <scripts folder> <output folder>")
        return 2
    LOGIC, OUT = Path(argv[1]), Path(argv[2])
    OUT.mkdir(parents=True, exist_ok=True)
    failed = False
    wanted = set()
    for path in sorted(LOGIC.glob("*.imagine")):
        target = OUT / f"{path.stem}.imagine.cpp"
        wanted.add(target.name)
        try:
            text = translate(path)
        except ScriptError as err:
            print(f"{path.name} line {err.line}: {err.message}")
            failed = True
            continue
        if not target.exists() or target.read_text(encoding="utf-8") != text:
            target.write_text(text, encoding="utf-8")
    for old in OUT.glob("*.imagine.cpp"):
        if old.name not in wanted:
            old.unlink()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
