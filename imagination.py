"""Imagination: a programming language written in plain English words.

Run a program:         py -3 imagination.py run <script.imagine>      (or: imagine <script.imagine>)
Build it as an .exe:   py -3 imagination.py build <script.imagine>    (needs Visual Studio's C++ compiler)
Unreal parts:          py -3 imagination.py <scripts folder> <output folder>

How it works: this file reads a script once, checks it, and turns every piece into two things at the same time:
a small Python function that does it (what 'run' uses) and the C++ that does it (what 'build' and Unreal use).
Both come from the same reading, so a script means the same thing either way. LANGUAGE.md describes the language.
"""
import copy
import json
import difflib
import math
import operator
import os
import random as pyrandom
import re
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path


LOGIC = Path("examples")  # where 'this is part of:' and 'use:' look first; set by main()
OUT = Path("generated")
HERE = Path(__file__).resolve().parent


class ScriptError(Exception):
    """A mistake in a script, found before it runs."""

    def __init__(self, line, message):
        super().__init__(message)
        self.line = line
        self.message = message


class RunError(Exception):
    """Something that went wrong while a program ran."""

    def __init__(self, line, message):
        super().__init__(message)
        self.line = line
        self.message = message


# ---------------------------------------------------------------- kinds of things

NUMBER, YESNO, PLACE, FLAT, TEXT = "number", "yes or no", "place", "flat", "text"
# Kinds are strings: the five above, "list of <kind>", or "thing <name>" for a kind the script describes itself.
CPP_TYPE = {NUMBER: "double", YESNO: "bool", PLACE: "FVector", FLAT: "FVector2D", TEXT: "std::string"}
ZERO = {NUMBER: "0.0", YESNO: "false", PLACE: "FVector::ZeroVector", FLAT: "FVector2D::ZeroVector", TEXT: "std::string()"}
BASIC_WORDS = {"number": NUMBER, "numbers": NUMBER, "yes or no": YESNO, "place": PLACE, "places": PLACE,
               "flat place": FLAT, "flat places": FLAT, "text": TEXT, "texts": TEXT}
THINGS = {}  # name -> [(field words, kind)], for the script being read (a new dict for each script)
FIELDS = {}  # field words tuple -> {thing kind: (member, kind)}

KEYWORDS = set("""touches exceeds falls echo cease gather banish inscribe conjure whisper wound horizontal vertical depth try set to if otherwise stop note and or not is more less than at least most plus minus times divided by
clamp between smaller larger of square root size flat direction angle from yes no move toward
scrawl ask into repeat while with random for each in contains list empty new remove file write as""".split())
ITEM_NOT_INDEX = {None, ",", ")", "of", "is", "and", "or", "plus", "minus", "times", "divided", "by", "to",
                  "between", "+", "-", "*", "/", "contains", "in", "from", "with"}
UNITS = set("degrees degree cm centimetres seconds second per squared percent metres metre m s".split())
TOKEN = r'"[^"]*"|\d+(?:\.\d+)?|[A-Za-z][A-Za-z\']*|[():,+\-*/]'


# Commands for a kind of thing ('to bounce, for a ball:'): their C++ name -> the kind.
OWNERS = {}

# The parts of a place, written after it: 'existence of horizontal'.
PLACE_PARTS = {("horizontal",): "X", ("vertical",): "Y", ("depth",): "Z"}


def reset_fields():
    """Forget the last script's kinds of things."""
    FIELDS.clear()


def is_list(kind):
    return kind.startswith("list of ")


def element(kind):
    return kind[len("list of "):]


def is_table(kind):
    return kind.startswith("table of ")


def entry_kind(kind):
    return kind[len("table of "):]


def is_thing(kind):
    return kind.startswith("thing ")


def cpp_type(kind):
    if is_list(kind):
        return f"std::vector<{cpp_type(element(kind))}>"
    if is_table(kind):
        return f"std::map<std::string, {cpp_type(entry_kind(kind))}>"
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
    if words[:2] in (["list", "of"], ["table", "of"], ["lists", "of"], ["tables", "of"]):
        k = parse_kind(" ".join(words[2:]))
        return k and f"{words[0].rstrip('s')} of " + k
    for name in (phrase, phrase[:-1] if phrase.endswith("s") else None):
        if name in THINGS:
            return "thing " + name
    return None


def kind_words():
    return ", ".join(["a number", "yes or no", "text", "a place", "a list of ...", "a table of ..."] + [f"a {t}" for t in THINGS])


def kind_name(kind):
    if is_list(kind):
        return "a list of " + plural(element(kind))
    if is_table(kind):
        return "a table of " + plural(entry_kind(kind))
    if is_thing(kind):
        return "a " + kind[6:]
    return {NUMBER: "a number", YESNO: "yes or no", PLACE: "a place", FLAT: "a flat place", TEXT: "text"}[kind]


def plural(kind):
    if is_list(kind):
        return "lists of " + plural(element(kind))
    if is_table(kind):
        return "tables of " + plural(entry_kind(kind))
    if is_thing(kind):
        return kind[6:] + "s"
    return {NUMBER: "numbers", YESNO: "yes or no", PLACE: "places", FLAT: "flat places", TEXT: "text"}[kind]


# ---------------------------------------------------------------- what running a program uses

class Thing:
    """One of a script's own kinds of things, while a program runs."""
    __slots__ = ("name", "spec", "fields")

    def __init__(self, name, things):
        self.name, self.spec = name, things[name]
        self.fields = {snake(w): py_zero(k, things) for w, k in self.spec}

    def __eq__(self, other):
        return isinstance(other, Thing) and self.name == other.name and self.fields == other.fields

    def __deepcopy__(self, memo):
        new = Thing.__new__(Thing)
        new.name, new.spec, new.fields = self.name, self.spec, {k: dup(x) for k, x in self.fields.items()}
        return new


class Place:
    """A place (x, y, z) or a flat place (x, y) while a program runs. Its parts are in .fields, like a Thing's."""
    __slots__ = ("fields",)

    def __init__(self, *parts):
        self.fields = {"X": float(parts[0]), "Y": float(parts[1])}
        if len(parts) > 2:
            self.fields["Z"] = float(parts[2])

    @staticmethod
    def made(fields):
        new = Place.__new__(Place)
        new.fields = fields
        return new

    def parts(self):
        return list(self.fields.values())  # always X, Y (, Z) in that order

    def __eq__(self, other):
        return isinstance(other, Place) and self.fields == other.fields

    def __add__(self, other):
        b = other.fields
        return Place.made({k: a + b[k] for k, a in self.fields.items()})

    def __sub__(self, other):
        b = other.fields
        return Place.made({k: a - b[k] for k, a in self.fields.items()})

    def __mul__(self, number):
        return Place.made({k: a * number for k, a in self.fields.items()})

    def __truediv__(self, number):
        return Place.made({k: div(a, number) for k, a in self.fields.items()})

    def __neg__(self):
        return Place.made({k: -a for k, a in self.fields.items()})

    def size(self):
        return math.sqrt(sum(a * a for a in self.fields.values()))


def py_zero(kind, things):
    if kind == NUMBER:
        return 0.0
    if kind == YESNO:
        return False
    if kind == TEXT:
        return ""
    if kind == PLACE:
        return Place(0, 0, 0)
    if kind == FLAT:
        return Place(0, 0)
    if is_list(kind):
        return []
    if is_table(kind):
        return {}
    if is_thing(kind):
        return Thing(kind[6:], things)
    return None


def dup(v):
    """Lists, tables, places and things are copied when they are stored, as they are in the C++.

    Made by hand rather than with copy.deepcopy: it is called on every 'set', so it must be quick."""
    t = type(v)
    if t is float or t is str or t is bool:
        return v
    if t is Place:
        new = Place.__new__(Place)
        new.fields = v.fields.copy()
        return new
    if t is Thing:
        new = Thing.__new__(Thing)
        new.name, new.spec = v.name, v.spec
        new.fields = {k: dup(x) for k, x in v.fields.items()}
        return new
    if t is list:
        return [dup(x) for x in v] if v and type(v[0]) in DEEP else v.copy()
    if t is dict:
        return {k: dup(x) for k, x in v.items()} if v and type(next(iter(v.values()))) in DEEP else v.copy()
    return v


DEEP = (list, dict, Thing, Place)  # values that hold other values, so copying them copies inside too


def part_text(v):
    """A list or table inside another one is shown in brackets, so its items stay together."""
    return f"({text(v)})" if isinstance(v, (list, dict)) and v else text(v)


def text(v):
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, (int, float)):
        if math.isnan(v):
            return "not a number"
        if math.isinf(v):
            return "infinity" if v > 0 else "-infinity"
        if math.isfinite(v) and math.floor(v) == v and abs(v) < 1e21:
            return "%.0f" % v if v else "0"
        return "%.15g" % v
    if isinstance(v, str):
        return v
    if isinstance(v, list):
        return ", ".join(part_text(x) for x in v) if v else "(nothing)"
    if isinstance(v, dict):
        return ", ".join(f"{k}: {part_text(v[k])}" for k in sorted(v)) if v else "(nothing)"
    if isinstance(v, Place):
        return " ".join(f"{text(x)} {w}" for x, w in zip(v.parts(), ("horizontal", "vertical", "depth")))
    if isinstance(v, Thing):
        return f"a {v.name} (" + ", ".join(f"{' '.join(w)}: {text(v.fields[snake(w)])}" for w, _ in v.spec) + ")"
    raise RunError(0, "this can't be shown as text when running directly.")


def divide(a, b):
    return a / b if isinstance(a, Place) else div(a, b)


def div(a, b):
    if b == 0:
        if a == 0 or a != a:
            return math.nan
        return math.copysign(math.inf, a) * math.copysign(1.0, b)
    return a / b


def unwind(a):
    a = math.fmod(a, 360.0)
    if a > 180.0:
        a -= 360.0
    if a < -180.0:
        a += 360.0
    return a


NUMBER_TEXT = re.compile(r"\s*[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?\s*")


def rounded(x, places, line):
    if math.floor(places) != places or not 0 <= places <= 15:
        raise RunError(line, f"I can round to 0 to 15 places, not {text(places)}.")
    if not math.isfinite(x):
        return x
    scale = 10.0 ** int(places)  # halves go away from zero, as taught at school (same steps as the C++)
    return math.copysign(math.floor(abs(x) * scale + 0.5) / scale, x)


def to_number(s, line):
    if NUMBER_TEXT.fullmatch(s):
        return float(s)
    raise RunError(line, f'"{s}" is not a number.')


def index_of(items, number, line):
    if math.floor(number) != number or number < 1 or number > len(items):
        raise RunError(line, f"there is no item {text(number)} in a list of {len(items)} item{'' if len(items) == 1 else 's'}."
                             " Items are counted from 1.")
    return int(number) - 1


def lines_of(s):
    if not s:
        return []
    parts = s.split("\n")
    if s.endswith("\n"):
        parts.pop()
    return [p[:-1] if p.endswith("\r") else p for p in parts]


def random_number(lo, hi, line):
    a, b = math.ceil(min(lo, hi)), math.floor(max(lo, hi))
    if a > b:
        raise RunError(line, f"there is no whole number from {text(lo)} to {text(hi)}.")
    return float(pyrandom.randint(a, b))


def ask_text(question):
    sys.stdout.write(question)
    sys.stdout.flush()
    line = sys.stdin.readline()
    if not line:
        raise SystemExit(0)  # nobody is left to answer (input closed)
    return line.rstrip("\n").rstrip("\r")


def ask_yes_no(question):
    while True:
        answer = ask_text(question).strip().translate(ASCII_DOWN)
        if answer in ("yes", "y"):
            return True
        if answer in ("no", "n"):
            return False
        print("Please type yes or no.")


def ask_number(question):
    while True:
        answer = ask_text(question)
        if NUMBER_TEXT.fullmatch(answer):
            return float(answer)
        print("Please type a number.")


def read_file(path, line):
    try:
        with open(path, "rb") as f:
            return f.read().decode("utf-8", errors="replace")
    except OSError:
        raise RunError(line, f'there is no file called "{path}" (or it can\'t be opened).')


def write_file(path, s, line, mode="wb"):
    try:
        with open(path, mode) as f:
            f.write(s.encode("utf-8"))
    except OSError:
        raise RunError(line, f'I couldn\'t {"write" if mode == "wb" else "add to"} the file "{path}".')


# ---------------------------------------------------------------- saving and loading (as JSON)

def saved_number(x, line):
    if not math.isfinite(x):
        raise RunError(line, "I can't save infinity or not a number.")
    if x == math.floor(x) and abs(x) < 1e16:
        return "%.0f" % (x if x else 0.0)
    return repr(x)


def saved(v, kind, line):
    """The value written out as JSON, exactly as the C++ writes it."""
    if kind == NUMBER:
        return saved_number(v, line)
    if kind == YESNO:
        return "true" if v else "false"
    if kind == TEXT:
        return json.dumps(v, ensure_ascii=False)
    if kind in (PLACE, FLAT):
        return "[" + ", ".join(saved_number(x, line) for x in v.parts()) + "]"
    if is_list(kind):
        return "[" + ", ".join(saved(x, element(kind), line) for x in v) + "]"
    if is_table(kind):
        return "{" + ", ".join(f"{json.dumps(k, ensure_ascii=False)}: {saved(v[k], entry_kind(kind), line)}" for k in sorted(v)) + "}"
    return "{" + ", ".join(f'"{" ".join(w)}": {saved(v.fields[snake(w)], k, line)}' for w, k in v.spec) + "}"


class NotSaved(Exception):
    pass


def from_saved(d, kind, things):
    """JSON data back into a value of this kind; a part a thing's file doesn't have stays empty."""
    if kind == NUMBER and isinstance(d, float):
        return d
    if kind == YESNO and isinstance(d, bool):
        return d
    if kind == TEXT and isinstance(d, str):
        return d
    if kind in (PLACE, FLAT) and isinstance(d, list) and len(d) == (3 if kind == PLACE else 2) \
            and all(isinstance(x, float) for x in d):
        return Place(*d)
    if is_list(kind) and isinstance(d, list):
        return [from_saved(x, element(kind), things) for x in d]
    if is_table(kind) and isinstance(d, dict):
        return {k: from_saved(x, entry_kind(kind), things) for k, x in d.items()}
    if is_thing(kind) and isinstance(d, dict):
        t = Thing(kind[6:], things)
        for w, k in t.spec:
            if " ".join(w) in d:
                t.fields[snake(w)] = from_saved(d[" ".join(w)], k, things)
        return t
    raise NotSaved()


def no_constant(name):
    raise NotSaved()


def load_saved(path, kind, things, line):
    data = read_file(path, line)
    try:
        return from_saved(json.loads(data, parse_int=float, parse_constant=no_constant), kind, things)
    except (NotSaved, ValueError, RecursionError):
        raise RunError(line, f'the file "{path}" doesn\'t hold {kind_name(kind)}.')


def letters(s):
    return float(len(s))


ASCII_UP = str.maketrans("abcdefghijklmnopqrstuvwxyz", "ABCDEFGHIJKLMNOPQRSTUVWXYZ")
ASCII_DOWN = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")


def letter(s, number, line):
    if math.floor(number) != number or number < 1 or number > len(s):
        raise RunError(line, f"there is no letter {text(number)} in text of {len(s)} letters.")
    return s[int(number) - 1]


def letters_from(s, first, last, line):
    if math.floor(first) != first or math.floor(last) != last or first < 1 or last > len(s) or first > last + 1:
        raise RunError(line, f"there are no letters {text(first)} to {text(last)} in text of {len(s)} letters.")
    return s[int(first) - 1:int(last)]


def replace_all(s, old, new, line):
    if not old:
        raise RunError(line, "I can't replace empty text.")
    return s.replace(old, new)


def split(s, by, line):
    if not by:
        raise RunError(line, "I can't split text by empty text.")
    return s.split(by)


def entry_of(table, key, line):
    if key not in table:
        raise RunError(line, f'there is no entry "{key}" in the table.')
    return table[key]


def remove_entry(table, key, line):
    if key not in table:
        raise RunError(line, f'there is no entry "{key}" in the table to remove.')
    del table[key]


def list_stat(stat, items, line):
    if stat == "sum":
        total = 0.0
        for x in items:  # one at a time, in order, as the C++ does
            total += x
        return total
    if not items:
        raise RunError(line, f"the list is empty, so it has no {stat}.")
    if stat == "average":
        return list_stat("sum", items, line) / len(items)
    return max(items) if stat == "biggest" else min(items)


def last(items, line):
    if not items:
        raise RunError(line, "the list is empty, so it has no last item.")
    return items[-1]


class Flow(Exception):
    """Leaving a command or a loop early (not an error)."""


class Stop(Flow):
    pass


class GiveBack(Flow):
    def __init__(self, value):
        self.value = value


class LeaveLoop(Flow):
    pass


class NextRound(Flow):
    pass


def looped(then):
    """One round of a loop. Returns False when the loop should end ('stop the loop')."""
    def step(env):
        try:
            then(env)
        except LeaveLoop:
            return False
        except NextRound:
            pass
        return True
    return step


def not_here(line, what):
    """For words that only mean something in C++ (Unreal, or a library word without a 'runs:' line)."""
    def run(env):
        raise RunError(line, f"{what} only works when the script is built into C++, not when it runs directly.")
    return run


# ---------------------------------------------------------------- reading

def tokenize(text, line):
    tokens = re.findall(TOKEN + r"|\S", text)
    for t in tokens:
        if t == '"':
            raise ScriptError(line, 'This text has no closing ". Text goes between two quote marks, like "hello".')
        if not re.fullmatch(TOKEN, t):
            raise ScriptError(line, f"I don't understand the symbol '{t}'.")
    return [t.lower() if t[0].isalpha() else t for t in tokens]


# The language's words, and the words they replaced. A script line's words are turned into the
# older inner words before it is read; the older words themselves are not allowed in scripts.
OLD_WORDS = [  # (old words, how to say it now) - checked anywhere in a line, outside quote marks
    (r"\bis more than\b", "exceeds"), (r"\bis less than\b", "falls below"),
    (r"\bthe problem\b", "the wound"), (r"\ban? new\b", "conjure a"),
    (r"\bopen a window\b", "open a world"), (r"\bthe window is open\b", "the world lives"),
    (r"\bclose the window\b", "end the world"), (r"\bshow the frame\b", "reveal the frame"),
]
OLD_STARTS = [  # (old first words, how to say it now) - checked at the start of a line
    (r"while\b", "as long as"), (r"repeat\b", "echo"), (r"stop the loop$", "break free"),
    (r"skip to the next( one)?$", "move on"), (r"stop$", "cease"), (r"add\b", "gather ... into"),
    (r"remove\b", "banish ... from"), (r"write\b", "inscribe ... into"),
]
NEW_WORDS = [  # (new words, the inner words they become) - anywhere outside quote marks
    (r"\bexceeds\b", "is more than"), (r"\bfalls below\b", "is less than"), (r"\bthe wound\b", "the problem"),
    (r"\bconjure (an?) ", "a new "),
]
NEW_STARTS = [  # at the start of a line
    (r"as long as\b", "while"), (r"echo\b", "repeat"), (r"break free$", "stop the loop"),
    (r"move on$", "skip to the next one"), (r"cease$", "stop"),
]


def outside_quotes(text, change):
    """Applies change to the parts of text that are not between quote marks."""
    parts = re.split(r'("[^"]*")', text)
    return "".join(part if k % 2 else change(part, k == 0) for k, part in enumerate(parts))


def surface(text, line):
    """A script line in the language's words, turned into the inner words (old words are a mistake).

    'if done: cease' is two parts; each is turned on its own."""
    head, colon, rest = split_colon(text)
    out = surface_part(head, line)
    if colon:
        out += ":" + (" " + surface(rest.strip(), line) if rest.strip() else "")
    return out


def surface_part(text, line):
    def check(part, first):
        low = part.lower()
        for old, now in OLD_WORDS:
            m = re.search(old, low)
            if m:
                raise ScriptError(line, f"'{m.group(0)}' is now '{now}'.")
        if first:
            head = split_colon(low)[0].strip()
            for old, now in OLD_STARTS:
                m = re.match(old, head)
                if m:
                    raise ScriptError(line, f"'{m.group(0).strip()}' is now '{now}'.")
        return part
    outside_quotes(text, check)

    def change(part, first):
        for new, inner in NEW_WORDS:
            part = re.sub(new, inner, part, flags=re.IGNORECASE)
        if first:
            lead = len(part) - len(part.lstrip())
            body = part[lead:]
            for new, inner in NEW_STARTS:
                body = re.sub("^" + new, inner, body, flags=re.IGNORECASE)
            m = re.match(r"(gather|banish|inscribe)\b", body, re.IGNORECASE)
            if m:  # gather x into y -> add x to y; banish x from y -> remove x from y; inscribe x into file -> write x to file
                verb = m.group(1).lower()
                body = {"gather": "add", "banish": "remove", "inscribe": "write"}[verb] + body[m.end():]
                if verb != "banish":
                    k = body.lower().rfind(" into ")
                    if k < 0:
                        raise ScriptError(line, f"'{verb}' looks like '{verb} {'5 into scores' if verb == 'gather' else chr(34) + 'hello' + chr(34) + ' into file ' + chr(34) + 'notes.txt' + chr(34)}'.")
                    body = body[:k] + " to " + body[k + 6:]
            part = part[:lead] + body
        return part
    # 'into' may sit after a quoted part, so turn the whole line, then put the quoted parts back unchanged
    pieces = re.split(r'("[^"]*")', text)
    marks = [pieces[k] for k in range(1, len(pieces), 2)]
    joined = "".join(f"\x00{k}\x00" if i % 2 else piece for i, piece in enumerate(pieces) for k in [i // 2])
    joined = change(joined, True)
    return re.sub(r"\x00(\d+)\x00", lambda m: marks[int(m.group(1))], joined)


def split_colon(text):
    """Splits 'head: rest' at the first colon that is not inside quote marks."""
    inside = False
    for k, c in enumerate(text):
        inside ^= c == '"'
        if c == ":" and not inside:
            return text[:k], ":", text[k + 1:]
    return text, "", ""


class Value:
    """A piece of an expression: its C++, its kind, and run(env) which works it out.

    store(env, x) changes it, for values that can be changed (a name, a part of a thing, an item of a list)."""

    def __init__(self, cpp, kind, run, store=None):
        self.cpp, self.kind, self.run, self.store = cpp, kind, run, store

    @property
    def writable(self):
        return self.store is not None


class Command:
    """A command a program can call: one of the script's own, or a word from a library."""

    def __init__(self, cpp, kinds, gives, inputs=None, runner=None):
        self.cpp, self.kinds, self.gives = cpp, kinds, gives
        self.inputs = inputs  # library words: the input names their C++ uses as {name}
        self.runner = runner  # called with the inputs' values when running directly


class Names:
    """Every name a script can use: the class's words, settings, inputs and the script's own names."""

    def __init__(self):
        self.known = {}  # words tuple -> (cpp, kind, read_only, run or None for a name kept in env)
        self.commands = {}  # words tuple -> Command
        self.gives = None  # what the command being read gives back
        self.loops = 0  # how many loops the line being read is inside

    def add(self, words, cpp, kind, read_only=False, run=None):
        self.known[tuple(words)] = (cpp, kind, read_only, run)

    def match(self, tokens, i):
        for n in range(min(8, len(tokens) - i), 0, -1):
            key = tuple(tokens[i:i + n])
            if key in self.known:
                return key, n
        return None, 0

    def unknown(self, tokens, i):
        """The best guess at what an unknown name at tokens[i] was meant to be, as an error message."""
        known = [" ".join(k) for k in self.known] + [" ".join(k) for k in self.commands]
        best = (0.0, tokens[i], None)
        for n in range(1, min(5, len(tokens) - i) + 1):
            if not all(t[0].isalpha() for t in tokens[i:i + n]):
                break
            phrase = " ".join(tokens[i:i + n])
            for name in difflib.get_close_matches(phrase, known, n=1, cutoff=0.6):
                score = difflib.SequenceMatcher(None, phrase, name).ratio()
                if score > best[0]:
                    best = (score, phrase, name)
        hint = library_hint(tokens[i:])
        if hint:
            return f"I don't know '{best[1]}'." + hint
        return f"I don't know '{best[1]}'." + (f" Did you mean '{best[2]}'?" if best[2] else "")

    def value(self, key):
        cpp, kind, read_only, run = self.known[key]
        if isinstance(run, tuple):  # (get, put): a part of the thing a command is for
            return Value(cpp, kind, run[0], None if read_only else run[1])
        if run is not None:  # a setting, an Unreal word or a library word
            return Value(cpp, kind, run, None if read_only else (lambda env, x: run(env)))
        get = lambda env: env[cpp]

        def put(env, x):
            env[cpp] = dup(x)
        return Value(cpp, kind, get, None if read_only else put)


CPP_RESERVED = set("""auto bool break case catch char check class const continue default delete do double else enum
explicit false float for friend goto if inline int long new operator private protected public return short signed
sizeof static struct switch template this throw true try typedef union unsigned using virtual void while""".split())


def snake(words):
    name = "_".join(re.sub(r"[^a-z0-9]", "", w) for w in words)
    return name + "_" if name in CPP_RESERVED else name


def cpp_text(token):
    """A quoted text token as a C++ string."""
    return "std::string(" + token.replace("\\", "\\\\") + ")"


COMPARE_RUN = {">": operator.gt, "<": operator.lt, ">=": operator.ge, "<=": operator.le, "!=": operator.ne, "==": operator.eq}


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
            a, b = self.need(v, YESNO, "or").run, self.need(r, YESNO, "or").run
            v = Value(f"({v.cpp} || {r.cpp})", YESNO, lambda env, a=a, b=b: a(env) or b(env))
        return v

    def logic_and(self):
        v = self.logic_not()
        while self.at("and"):
            self.i += 1
            r = self.logic_not()
            a, b = self.need(v, YESNO, "and").run, self.need(r, YESNO, "and").run
            v = Value(f"({v.cpp} && {r.cpp})", YESNO, lambda env, a=a, b=b: a(env) and b(env))
        return v

    def logic_not(self):
        if self.at("not"):
            self.i += 1
            v = self.need(self.logic_not(), YESNO, "not")
            a = v.run
            return Value(f"!{v.cpp}", YESNO, lambda env: not a(env))
        return self.compare()

    COMPARE = [(("is", "more", "than"), ">"), (("is", "less", "than"), "<"), (("is", "at", "least"), ">="),
               (("is", "at", "most"), "<="), (("is", "not"), "!="), (("is",), "==")]

    def compare(self):
        v = self.sum()
        if self.at("contains"):
            self.i += 1
            r = self.sum()
            if not (v.kind == r.kind == TEXT or (is_list(v.kind) and element(v.kind) == r.kind)
                    or (is_table(v.kind) and r.kind == TEXT)):
                raise ScriptError(self.line, f"I can't look for {kind_name(r.kind)} in {kind_name(v.kind)}.")
            a, b = v.run, r.run
            return Value(f"imagine::contains({v.cpp}, {r.cpp})", YESNO, lambda env: b(env) in a(env))
        for words, part, size in ((("touches", "a", "side"), "horizontal", "width"),
                                  (("touches", "the", "top", "or", "bottom"), "vertical", "height")):
            if self.at(*words):  # 'existence touches a side': within radius of the world's edge (or past it)
                self.i += len(words)
                if v.kind not in (PLACE, FLAT):
                    raise ScriptError(self.line, f"'{' '.join(words)}' needs a place, like 'existence {' '.join(words)}', not {kind_name(v.kind)}.")
                if ("radius",) not in self.names.known or self.names.known[("radius",)][1] != NUMBER:
                    raise ScriptError(self.line, f"'{' '.join(words)}' needs to know how big the thing is: set radius first, like 'set radius to 20'.")
                edge = (size, "of", "the", "world")
                if edge not in self.names.known:
                    raise ScriptError(self.line, f"I don't know '{' '.join(words)}'." + library_hint(list(edge)))
                at = part_of(v, (part,))
                r = self.names.value(("radius",))
                far = self.names.value(edge)
                a, b, c = at.run, r.run, far.run
                return Value(f"({at.cpp} <= {r.cpp} || {at.cpp} >= {far.cpp} - {r.cpp})", YESNO,
                             lambda env: a(env) <= b(env) or a(env) >= c(env) - b(env))
        if self.at("is", "within"):  # 'existence is within 30 of coin': close enough to touch
            self.i += 2
            reach = self.need(self.sum(), NUMBER, "within")
            self.take("of")
            r = self.sum()
            if v.kind != r.kind or v.kind not in (NUMBER, PLACE, FLAT):
                raise ScriptError(self.line, f"'within' compares two numbers or two places, not {kind_name(v.kind)} and {kind_name(r.kind)}.")
            a, b, c = v.run, r.run, reach.run
            gap = (lambda x, y: abs(x - y)) if v.kind == NUMBER else (lambda x, y: (x - y).size())
            return Value(f"imagine::within({v.cpp}, {r.cpp}, {reach.cpp})", YESNO, lambda env: gap(a(env), b(env)) <= c(env))
        for words, op in self.COMPARE:
            if self.at(*words):
                self.i += len(words)
                r = self.sum()
                if not (op in ("==", "!=") and v.kind == r.kind and v.kind not in (PLACE, FLAT)):
                    self.need(v, NUMBER, "Comparing")
                    self.need(r, NUMBER, "Comparing")
                a, b, f = v.run, r.run, COMPARE_RUN[op]
                return Value(f"({v.cpp} {op} {r.cpp})", YESNO, lambda env: f(a(env), b(env)))
        return v

    def sum(self):
        v = self.product()
        while self.peek() in ("plus", "+", "minus", "-"):
            op = "+" if self.peek() in ("plus", "+") else "-"
            self.i += 1
            r = self.product()
            a, b = v.run, r.run
            if v.kind == TEXT and op == "+":
                v = Value(f"(imagine::text({v.cpp}) + imagine::text({r.cpp}))", TEXT,
                          lambda env, a=a, b=b: text(a(env)) + text(b(env)))
                continue
            if v.kind != r.kind or v.kind not in (NUMBER, PLACE, FLAT):
                raise ScriptError(self.line, f"I can't {'add' if op == '+' else 'subtract'} {kind_name(r.kind)} {'to' if op == '+' else 'from'} {kind_name(v.kind)}.")
            f = operator.add if op == "+" else operator.sub
            run = lambda env, a=a, b=b, f=f: f(a(env), b(env))
            v = Value(f"({v.cpp} {op} {r.cpp})", v.kind, run)
        return v

    def product(self):
        v = self.unary()
        while self.peek() in ("times", "*", "/") or self.at("divided", "by"):
            op = "/" if self.peek() in ("/", "divided") else "*"
            self.i += 2 if self.at("divided", "by") else 1
            r = self.unary()
            if r.kind != NUMBER or v.kind not in (NUMBER, PLACE, FLAT):
                raise ScriptError(self.line, f"I can only multiply or divide a number or a place by a number, not {kind_name(v.kind)} by {kind_name(r.kind)}.")
            a, b = v.run, r.run
            f = divide if op == "/" else operator.mul
            run = lambda env, a=a, b=b, f=f: f(a(env), b(env))
            v = Value(f"({v.cpp} {op} {r.cpp})", v.kind, run)
        return v

    def unary(self):
        v = self.single()
        if v.kind != NUMBER or not self.at("horizontal"):
            return v
        self.i += 1  # 300 horizontal 200 vertical (5 depth): a place
        parts = [v, self.need(self.single(), NUMBER, "a place")]
        self.take("vertical")
        start = self.i
        if self.peek() not in (None, ",", ")") and self.peek() not in ITEM_NOT_INDEX:
            third = self.single()
            if third.kind == NUMBER and self.at("depth"):
                self.i += 1
                parts.append(third)
            else:
                self.i = start
        runs = [x.run for x in parts]
        cpp = "FVector" if len(parts) == 3 else "FVector2D"
        return Value(f"{cpp}({', '.join(strip_parens(x.cpp) for x in parts)})", PLACE if len(parts) == 3 else FLAT,
                     lambda env: Place(*[f(env) for f in runs]))

    def single(self):
        if self.peek() in ("-", "minus"):
            self.i += 1
            v = self.single()
            if v.kind not in (NUMBER, PLACE, FLAT):
                raise ScriptError(self.line, f"I can't make {kind_name(v.kind)} negative.")
            a = v.run
            return Value(f"(-{v.cpp})", v.kind, lambda env: -a(env))
        v = self.primary()
        while self.at("of"):  # 'existence of horizontal': a part named after the place or thing
            key = next((tuple(self.t[self.i + 1:self.i + 1 + n]) for n in range(min(6, len(self.t) - self.i - 1), 0, -1)
                        if v.kind in FIELDS.get(tuple(self.t[self.i + 1:self.i + 1 + n]), {})
                        or place_part(v.kind, tuple(self.t[self.i + 1:self.i + 1 + n]))), None)
            if not key:
                break
            self.i += 1 + len(key)
            v = part_of(v, key)
        if self.at("as", "a", "number") or self.at("as", "number"):
            self.i += 3 if self.at("as", "a") else 2
            if v.kind != TEXT:
                raise ScriptError(self.line, f"'as a number' turns text into a number, but this is {kind_name(v.kind)}.")
            a, line = v.run, self.line
            return Value(f"imagine::to_number({v.cpp}, {line})", NUMBER, lambda env: to_number(a(env), line))
        if self.at("as", "text"):
            self.i += 2
            a = v.run
            return Value(f"imagine::text({v.cpp})", TEXT, lambda env: text(a(env)))
        if self.at("rounded", "to"):
            self.i += 2
            self.need(v, NUMBER, "rounded to")
            places = self.need(self.primary(), NUMBER, "rounded to")
            if self.peek() in ("places", "place", "decimal"):
                self.i += 1
                if self.at("places") or self.at("place"):
                    self.i += 1
            a, b, line = v.run, places.run, self.line
            return Value(f"imagine::rounded({v.cpp}, {places.cpp}, {line})", NUMBER, lambda env: rounded(a(env), b(env), line))
        if self.at("split", "by"):
            self.i += 2
            self.need(v, TEXT, "split by")
            by = self.need(self.primary(), TEXT, "split by")
            a, b, line = v.run, by.run, self.line
            return Value(f"imagine::split({v.cpp}, {by.cpp}, {line})", "list of text", lambda env: split(a(env), b(env), line))
        return v

    def primary(self):
        tok, line = self.peek(), self.line
        if tok is None:
            raise ScriptError(line, "This line ends too early: something is missing.")
        if re.fullmatch(r"\d+(?:\.\d+)?", tok):
            self.i += 1
            while self.peek() in UNITS:
                self.i += 1
            number = float(tok)
            return Value(tok if "." in tok else tok + ".0", NUMBER, lambda env: number)
        for words, mark, cpp in ((("quote", "mark"), '"', '"\\""'), (("new", "line"), "\n", '"\\n"')):
            if self.at(*words):  # text can't hold these between its own quote marks
                self.i += 2
                return Value(f"std::string({cpp})", TEXT, lambda env, mark=mark: mark)
        if tok.startswith('"'):
            self.i += 1
            s = tok[1:-1]
            return Value(cpp_text(tok), TEXT, lambda env: s)
        if self.at("random", "item", "of") or self.at("a", "random", "item", "of"):
            self.i += 4 if tok == "a" else 3
            v = self.unary()
            if not is_list(v.kind):
                raise ScriptError(line, f"'random item of' needs a list, but this is {kind_name(v.kind)}.")
            a = v.run

            def pick(env):
                items = a(env)
                if not items:
                    raise RunError(line, "the list is empty, so I can't pick a random item.")
                return pyrandom.choice(items)
            return Value(f"imagine::random_item({v.cpp}, {line})", element(v.kind), pick)
        if self.at("random", "number", "from"):
            self.i += 3
            lo = self.need(self.sum(), NUMBER, "random number")
            self.take("to")
            hi = self.need(self.sum(), NUMBER, "random number")
            a, b = lo.run, hi.run
            return Value(f"imagine::random({lo.cpp}, {hi.cpp}, {line})", NUMBER, lambda env: random_number(a(env), b(env), line))
        if tok == "(":
            self.i += 1
            v = self.full()
            if self.at(","):
                raise ScriptError(line, "A place is written like 300 horizontal 200 vertical (and 5 depth, for a place with depth).")
            self.take(")")
            return v
        for n in range(min(6, len(self.t) - self.i), 0, -1):
            key = tuple(self.t[self.i:self.i + n])
            if key in FIELDS and self.peek(n) == "of" and not (
                    key in self.names.known and (self.names.known[key][1] in FIELDS.get((self.peek(n + 1),), {})
                                                 or place_part(self.names.known[key][1], (self.peek(n + 1),)))):
                # 'existence of x' is x of the name existence, when there is one, not the existence of x
                self.i += n + 1
                owner = self.unary()
                if owner.kind not in FIELDS[key]:
                    raise ScriptError(line, f"{kind_name(owner.kind).capitalize()} has no '{' '.join(key)}'.")
                return part_of(owner, key)
        if tok == "item" and self.peek(1) not in ITEM_NOT_INDEX:
            self.i += 1
            index = self.need(self.sum(), NUMBER, "item")
            self.take("of")
            seq = self.unary()
            if not is_list(seq.kind):
                raise ScriptError(line, f"'item ... of' needs a list, but this is {kind_name(seq.kind)}.")
            get, at = seq.run, index.run

            def item(env):
                items = get(env)
                return items[index_of(items, at(env), line)]

            def put(env, x):
                items = get(env)
                items[index_of(items, at(env), line)] = dup(x)
            return Value(f"imagine::at({seq.cpp}, {strip_parens(index.cpp)}, {line})", element(seq.kind), item,
                         put if seq.writable else None)
        made = self.made()  # before names, so a name like 'a' doesn't hide 'a list of'
        if made:
            return made
        if tok == "entry" and self.peek(1) not in ITEM_NOT_INDEX:
            self.i += 1
            name = self.need(self.sum(), TEXT, "entry")
            self.take("of")
            table = self.unary()
            if not is_table(table.kind):
                raise ScriptError(line, f"'entry ... of' needs a table, but this is {kind_name(table.kind)}.")
            get, at = table.run, name.run

            def put(env, x):
                get(env)[at(env)] = dup(x)
            v = Value(f"imagine::entry({table.cpp}, {strip_parens(name.cpp)}, {line})", entry_kind(table.kind),
                      lambda env: entry_of(get(env), at(env), line), put if table.writable else None)
            v.cpp_assign = f"({table.cpp})[{strip_parens(name.cpp)}] = "  # setting an entry may make a new one
            return v
        for stat in ("sum", "average", "biggest", "smallest"):
            if self.at(stat, "of") and not match_command(self.names, self.t[self.i:])[0]:  # a command called 'sum of' still wins
                self.i += 2
                v = self.unary()
                if v.kind != "list of number":
                    raise ScriptError(line, f"'{stat} of' needs a list of numbers, but this is {kind_name(v.kind)}.")
                a = v.run
                return Value(f"imagine::{stat}_of({v.cpp}, {line})", NUMBER, lambda env, stat=stat: list_stat(stat, a(env), line))
        if self.at("keys", "of"):
            self.i += 2
            table = self.unary()
            if not is_table(table.kind):
                raise ScriptError(line, f"'keys of' needs a table, but this is {kind_name(table.kind)}.")
            get = table.run
            return Value(f"imagine::keys({table.cpp})", "list of text", lambda env: sorted(get(env)))
        key, n = self.names.match(self.t, self.i)
        command_key, command_n = match_command(self.names, self.t[self.i:])
        if key and n >= command_n:  # the longer match wins: 'balls moved down' is a command even when 'balls' is a name
            self.i += n
            return self.names.value(key)
        key, n = command_key, command_n
        if key:
            self.i += n
            command = self.names.commands[key]
            needs = len(command.kinds)
            if self.at("with"):
                self.i += 1
            args = []
            if needs == 1:
                args = [self.unary()]
            elif needs > 1:
                if not self.at("("):
                    raise ScriptError(line, f"'{' '.join(key)}' needs {needs} inputs. Put them in brackets here, like: {' '.join(key)} with (1, 2)")
                self.i += 1
                args = [self.full()]
                while self.at(","):
                    self.i += 1
                    args.append(self.full())
                self.take(")")
            if not command.gives:
                raise ScriptError(line, f"'{' '.join(key)}' doesn't give back anything, so it can't be used as a value.")
            cpp, run = call(key, args, self.names, line)
            return Value(cpp, command.gives, run)
        if tok in ("yes", "no"):
            self.i += 1
            b = tok == "yes"
            return Value("true" if b else "false", YESNO, lambda env: b)
        if self.at("clamp"):
            self.i += 1
            v = self.need(self.sum(), NUMBER, "clamp")
            self.take("between")
            lo = self.need(self.sum(), NUMBER, "clamp")
            self.take("and")
            hi = self.need(self.sum(), NUMBER, "clamp")
            x, a, b = v.run, lo.run, hi.run
            return Value(f"FMath::Clamp({v.cpp}, {lo.cpp}, {hi.cpp})", NUMBER, lambda env: min(max(x(env), a(env)), b(env)))
        for word, fn, f in (("smaller", "Min", min), ("larger", "Max", max)):
            if self.at(word, "of"):
                self.i += 2
                a = self.need(self.sum(), NUMBER, f"{word} of")
                self.take("and")
                b = self.need(self.sum(), NUMBER, f"{word} of")
                x, y = a.run, b.run
                return Value(f"FMath::{fn}({a.cpp}, {b.cpp})", NUMBER, lambda env, f=f: f(x(env), y(env)))
        if self.at("contents", "of", "file") or self.at("lines", "of", "file"):
            whole = self.at("contents")
            self.i += 3
            where = self.need(self.unary(), TEXT, "file")
            w = where.run
            if whole:
                return Value(f"imagine::read_file({where.cpp}, {line})", TEXT, lambda env: read_file(w(env), line))
            return Value(f"imagine::read_lines({where.cpp}, {line})", "list of text", lambda env: lines_of(read_file(w(env), line)))
        if self.at("file"):
            self.i += 1
            where = self.need(self.unary(), TEXT, "file")
            self.take("exists")
            w = where.run
            return Value(f"imagine::file_exists({where.cpp})", YESNO, lambda env: os.path.isfile(w(env)))
        for words, fn, f in ((("lines", "of"), "lines_of", lines_of), (("words", "of"), "words_of", str.split)):
            if self.at(*words):
                self.i += 2
                v = self.need(self.unary(), TEXT, " ".join(words))
                a = v.run
                return Value(f"imagine::{fn}({v.cpp})", "list of text", lambda env, f=f: f(a(env)))
        if tok in ("letter", "letters") and self.peek(1) not in ITEM_NOT_INDEX:
            self.i += 1
            first = self.need(self.sum(), NUMBER, tok)
            last_ = None
            if tok == "letters":
                self.take("to")
                last_ = self.need(self.sum(), NUMBER, "letters ... to")
            self.take("of")
            v = self.need(self.unary(), TEXT, f"'{tok} ... of'")
            a, f = v.run, first.run
            if last_ is None:
                return Value(f"imagine::letter({v.cpp}, {strip_parens(first.cpp)}, {line})", TEXT, lambda env: letter(a(env), f(env), line))
            b = last_.run
            return Value(f"imagine::letters_from({v.cpp}, {strip_parens(first.cpp)}, {strip_parens(last_.cpp)}, {line})", TEXT,
                         lambda env: letters_from(a(env), f(env), b(env), line))
        for words, fn, table in ((("upper", "case", "of"), "upper", ASCII_UP), (("lower", "case", "of"), "lower", ASCII_DOWN)):
            if self.at(*words):
                self.i += 3
                v = self.need(self.unary(), TEXT, " ".join(words))
                a = v.run
                return Value(f"imagine::{fn}({v.cpp})", TEXT, lambda env, table=table: a(env).translate(table))
        if self.at("position", "of"):
            self.i += 2
            part = self.need(self.sum(), TEXT, "position of")
            self.take("in")
            v = self.need(self.unary(), TEXT, "position of ... in")
            a, b = v.run, part.run
            return Value(f"imagine::position({v.cpp}, {part.cpp})", NUMBER, lambda env: float(a(env).find(b(env)) + 1))
        if self.at("replace"):
            self.i += 1
            old = self.need(self.sum(), TEXT, "replace")
            self.take("with")
            new = self.need(self.sum(), TEXT, "replace ... with")
            self.take("in")
            v = self.need(self.unary(), TEXT, "replace ... in")
            a, o, w = v.run, old.run, new.run
            return Value(f"imagine::replace_all({v.cpp}, {old.cpp}, {new.cpp}, {line})", TEXT,
                         lambda env: replace_all(a(env), o(env), w(env), line))
        if self.at("join"):
            self.i += 1
            v = self.unary()
            if not is_list(v.kind):
                raise ScriptError(line, f"'join' needs a list, but this is {kind_name(v.kind)}.")
            self.take("with")
            between = self.need(self.unary(), TEXT, "join ... with")
            a, b = v.run, between.run
            return Value(f"imagine::join({v.cpp}, {between.cpp})", TEXT, lambda env: b(env).join(text(x) for x in a(env)))
        if self.at("sorted"):
            start = self.i
            self.i += 1
            v = self.unary()
            if self.at("by") and is_list(v.kind) and is_thing(element(v.kind)):
                self.i += 1
                thing = element(v.kind)
                for n in range(min(6, len(self.t) - self.i), 0, -1):
                    key = tuple(self.t[self.i:self.i + n])
                    if key in FIELDS and thing in FIELDS[key]:
                        self.i += n
                        member, kind = FIELDS[key][thing]
                        if kind not in (NUMBER, TEXT):
                            raise ScriptError(line, f"'sorted ... by' needs a part that is a number or text, but '{' '.join(key)}' is {kind_name(kind)}.")
                        a = v.run
                        return Value(f"imagine::sorted_by({v.cpp}, [](const auto& t) {{ return t.{member}; }})", v.kind,
                                     lambda env: [dup(x) for x in sorted(a(env), key=lambda t: t.fields[member])])
                raise ScriptError(line, f"{kind_name(thing).capitalize()} has no part called '{' '.join(self.t[self.i:self.i + 2])}'.")
            self.i = start
        for word in ("sorted", "reversed"):
            if self.at(word):
                self.i += 1
                v = self.unary()
                if not is_list(v.kind) or (word == "sorted" and element(v.kind) not in (NUMBER, TEXT)):
                    need = " of numbers or text" if word == "sorted" else ""
                    raise ScriptError(line, f"'{word}' needs a list{need}, but this is {kind_name(v.kind)}.")
                a = v.run
                run = (lambda env: sorted(a(env))) if word == "sorted" else (lambda env: [dup(x) for x in reversed(a(env))])
                return Value(f"imagine::{word}({v.cpp})", v.kind, run)
        if self.at("last", "item", "of"):
            self.i += 3
            v = self.unary()
            if not is_list(v.kind):
                raise ScriptError(line, f"'last item of' needs a list, but this is {kind_name(v.kind)}.")
            a = v.run
            return Value(f"imagine::last({v.cpp}, {line})", element(v.kind), lambda env: last(a(env), line))
        if self.at("square", "root", "of"):
            self.i += 3
            v = self.need(self.sum(), NUMBER, "square root")
            a = v.run
            return Value(f"FMath::Sqrt({v.cpp})", NUMBER, lambda env: math.sqrt(x) if (x := a(env)) >= 0 else math.nan)
        if self.at("size", "of"):
            self.i += 2
            v = self.sum()
            a = v.run
            if v.kind == NUMBER:
                return Value(f"FMath::Abs({v.cpp})", NUMBER, lambda env: abs(a(env)))
            if v.kind in (PLACE, FLAT):
                return Value(f"({v.cpp}).Size()", NUMBER, lambda env: a(env).size())
            if v.kind == TEXT:
                return Value(f"imagine::letters({v.cpp})", NUMBER, lambda env: letters(a(env)))
            if is_list(v.kind) or is_table(v.kind):
                return Value(f"double(({v.cpp}).size())", NUMBER, lambda env: float(len(a(env))))
            raise ScriptError(line, f"{kind_name(v.kind)} has no size.")
        if self.at("flat"):
            self.i += 1
            v = self.need(self.unary(), PLACE, "flat")
            a = v.run
            return Value(f"FVector2D({v.cpp})", FLAT, lambda env: Place(*a(env).parts()[:2]))
        if self.at("direction", "of"):
            self.i += 2
            v = self.need(self.sum(), FLAT, "direction of")
            a = v.run
            return Value(f"FMath::RadiansToDegrees(FMath::Atan2(({v.cpp}).Y, ({v.cpp}).X))", NUMBER,
                         lambda env: (lambda q: math.atan2(q.fields["Y"], q.fields["X"]) * 180.0 / 3.14159265358979323846)(a(env)))
        if self.at("angle", "from"):
            self.i += 2
            a = self.need(self.sum(), NUMBER, "angle from")
            self.take("to")
            b = self.need(self.sum(), NUMBER, "angle from")
            x, y = a.run, b.run
            return Value(f"FMath::UnwindDegrees({b.cpp} - {a.cpp})", NUMBER, lambda env: unwind(y(env) - x(env)))
        if tok in KEYWORDS:
            raise ScriptError(line, f"'{tok}' can't go here.")
        raise ScriptError(line, self.names.unknown(self.t, self.i))

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
                        things = THINGS
                        return Value(f"{cpp_type('thing ' + name)}{{}}", "thing " + name, lambda env: Thing(name, things))
                raise ScriptError(self.line, f"There is no kind of thing called '{' '.join(self.t[self.i:self.i + 2])}'."
                                  + (f" Kinds of things: {', '.join(THINGS)}." if THINGS else ""))
        for lead in (("a", "table", "of"), ("an", "empty", "table", "of"), ("table", "of"), ("empty", "table", "of")):
            if self.at(*lead):
                self.i += len(lead)
                for n in range(min(6, len(self.t) - self.i), 0, -1):
                    k = parse_kind(" ".join(self.t[self.i:self.i + n]))
                    if k:
                        self.i += n
                        return Value(f"{cpp_type('table of ' + k)}()", "table of " + k, lambda env: {})
                raise ScriptError(self.line, f"Say what the table holds, like 'a table of numbers'. Kinds are: {kind_words()}.")
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
                    runs = [v.run for v in items]
                    return Value(f"{cpp_type(kind)}{{{', '.join(strip_parens(v.cpp) for v in items)}}}", kind,
                                 lambda env: [dup(f(env)) for f in runs])
                for n in range(min(6, len(self.t) - self.i), 0, -1):
                    k = parse_kind(" ".join(self.t[self.i:self.i + n]))
                    if k:
                        self.i += n
                        return Value(f"{cpp_type('list of ' + k)}()", "list of " + k, lambda env: [])
                raise ScriptError(self.line, f"Say what the list holds, like 'a list of numbers'. Kinds are: {kind_words()}.")
        self.i = start
        return None


# ---------------------------------------------------------------- words files and libraries

def load_words(name, line):
    path = LOGIC / f"{name}.words"
    if not path.exists():
        raise ScriptError(line, f"There is no '{name}' to be part of (no {name}.words next to the script).")
    names, info = Names(), {}
    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        text_ = raw.strip()
        if not text_ or text_.startswith("note:"):
            continue
        if text_.startswith("class:") or text_.startswith("header:"):
            key, value = text_.split(":", 1)
            info[key] = value.strip()
            continue
        english, _, rest = text_.partition("=")
        parts = [p.strip() for p in rest.rsplit(",", 2)]
        read_only = parts[-1] == "read only"
        if read_only:
            parts = parts[:-1]
        cpp, kind = ", ".join(parts[:-1]), parts[-1]
        if kind not in CPP_TYPE:
            raise ScriptError(n, f"{path.name}: unknown type '{kind}'.")
        names.add(english.strip().lower().split(), cpp, kind, read_only, not_here(line, f"'{english.strip()}'"))
    return names, info


LIBRARY_HELP = """A library is <name>.words, next to the script or in Imagination's libraries folder. Its lines:
  include: <cmath>                    a C++ header to include
  link: shell32                       a system library to link with
  code:                               C++ lines (indented below) the words can use
  python:                             Python lines (indented below) the 'runs:' lines can use
  pi = 3.14159, number, read only     a word for a value
  to wait, given seconds (a number) = std::this_thread::sleep_for(std::chrono::duration<double>({seconds}))
                                      a word for a command; {input name} stands for each input
    runs: time.sleep({seconds})       (indented under a word) what it does when the program runs directly"""


def place_part(kind, key):
    """True if a place of this kind has this part ('depth' only for places with depth)."""
    return kind in (PLACE, FLAT) and key in PLACE_PARTS and not (kind == FLAT and key == ("depth",))


def part_of(owner, key):
    """One part of a thing ('name of rex') or of a place ('existence of horizontal')."""
    member, kind = (PLACE_PARTS[key], NUMBER) if place_part(owner.kind, key) else FIELDS[key][owner.kind]
    get = owner.run

    def put(env, x):
        get(env).fields[member] = dup(x)
    v = Value(f"({owner.cpp}).{member}", kind, lambda env: get(env).fields[member], put if owner.writable else None)
    if key == ("birth",) and is_thing(owner.kind) and owner.kind in FIELDS.get(("existence",), {}) and owner.writable:
        def born(env, x):
            fields = get(env).fields
            fields["birth"], fields["existence"] = dup(x), dup(x)
        v.store = born
        v.cpp_assign, v.cpp_close = f"imagine::born(({owner.cpp}).birth, ({owner.cpp}).existence, ", ")"
    return v


def library_hint(tokens):
    """If the words at the start of tokens belong to a library the script doesn't use, says which one."""
    best = None  # the longest matching word wins: 'open a window' over 'open'
    for path in sorted((HERE / "libraries").glob("*.words")):
        for row in path.read_text(encoding="utf-8").splitlines():
            m = re.match(r"(?:to )?([a-z][a-z ]*?)\s*(?:,|=)", row)
            if m and tokens[:len(m.group(1).split())] == m.group(1).split() and (not best or len(m.group(1)) > len(best[0])):
                best = (m.group(1), path.stem)
    if not best:
        return ""
    return f" '{best[0]}' is a word from the {best[1]} library: put the line 'use: {best[1]}' at the top of the script."


def similar_words(tokens, names):
    """' Words that start with 'etch': ...' when a line starts like known words but goes on differently."""
    found = sorted({" ".join(k) for k in names.commands if k[0] == tokens[0]})
    if not found:
        return ""
    return f" Words that start with '{tokens[0]}': " + ", ".join(found) + "."


def load_library(name, line, names):
    """Reads the words a 'use:' line asks for into names; returns the C++ the library needs at the top of the file."""
    path = next((p for p in (LOGIC / f"{name}.words", HERE / "libraries" / f"{name}.words") if p.exists()), None)
    if not path:
        have = sorted(p.stem for p in (HERE / "libraries").glob("*.words"))
        raise ScriptError(line, f"There is no library called '{name}'." + (f" Libraries: {', '.join(have)}." if have else ""))
    out = [f"// From the library '{name}'"]
    space = {"math": math, "time": time, "os": os, "sys": sys, "subprocess": subprocess, "random": pyrandom,
             "text": text, "RunError": RunError}
    rows = path.read_text(encoding="utf-8").splitlines()
    pending = None  # the word whose 'runs:' line may come next: (where, input names, set run)
    k = 0
    while k < len(rows):
        raw = rows[k]
        stripped = raw.strip()
        n = k + 1
        k += 1
        where = f"In the library '{name}' ({path.name} line {n}): "
        if not stripped or stripped.startswith("note:"):
            continue
        if raw[:1].isspace() and stripped.startswith("runs:"):
            if not pending:
                raise ScriptError(line, where + "'runs:' goes indented under the word it is for.")
            src, (word_where, inputs, set_run) = stripped[5:].strip(), pending
            for idx, in_name in enumerate(inputs):
                src = src.replace("{" + in_name + "}", f"_{idx}")
            try:
                fn = eval(f"lambda {', '.join(f'_{idx}' for idx in range(len(inputs)))}: ({src})", space)
            except SyntaxError as err:
                raise ScriptError(line, where + f"the 'runs:' line isn't valid Python: {err.msg}.")
            set_run(fn)
            pending = None
            continue
        pending = None
        if stripped.startswith("include:"):
            out.append(f"#include {stripped[8:].strip()}")
        elif stripped.startswith("link:"):
            out.append(f'#pragma comment(lib, "{stripped[5:].strip()}")')
        elif stripped in ("code:", "python:"):
            block = []
            while k < len(rows) and (not rows[k].strip() or rows[k][:1].isspace()):
                block.append(rows[k][2:] if rows[k].startswith("  ") else rows[k].lstrip())
                k += 1
            if stripped == "code:":
                out += block
            else:
                exec("\n".join(block), space)
        elif stripped.startswith("to ") and " = " in stripped:
            head, _, cpp = stripped.partition(" = ")
            try:
                words, _, inputs, gives = command_head(head + ":", line)
            except ScriptError as err:
                raise ScriptError(line, where + err.message)
            in_names = [" ".join(w) for w, _ in inputs]
            for in_name in in_names:
                if "{" + in_name + "}" not in cpp:
                    raise ScriptError(line, where + f"the C++ doesn't use the input '{in_name}' (write it as {{{in_name}}}).")
            command = Command(cpp.strip(), [kd for _, kd in inputs], gives, in_names)
            word = " ".join(words)

            def missing(*args, word=word):
                raise RunError(0, f"'{word}' (from the library '{name}') only works when the program is built into C++.")
            command.runner = missing
            names.commands[tuple(words)] = command
            pending = (where, in_names, lambda fn, command=command: setattr(command, "runner", fn))
        elif "=" in stripped:
            english, _, rest = stripped.partition("=")
            parts = [p.strip() for p in rest.rsplit(",", 2)]
            read_only = parts[-1] == "read only"
            if read_only:
                parts = parts[:-1]
            kind = parse_kind(parts[-1])
            if not kind or len(parts) < 2:
                raise ScriptError(line, where + f"a word looks like 'pi = 3.14159, number, read only'. Kinds are: {kind_words()}.")
            words = english.strip().lower().split()
            holder = {"run": not_here(line, f"'{english.strip()}' (from the library '{name}')")}
            names.add(words, ", ".join(parts[:-1]), kind, True, lambda env, holder=holder: holder["run"](env))
            if not read_only:
                raise ScriptError(line, where + "library words for values must be 'read only' for now.")

            def set_value(fn, holder=holder):
                holder["run"] = lambda env: fn()
            pending = (where, [], set_value)
        else:
            raise ScriptError(line, where + f"I don't understand '{stripped}'.\n{LIBRARY_HELP}")
    return out + [""]


# ---------------------------------------------------------------- a whole script

CLOSING = "and the universe said i love you"


def is_closing(line):
    """The line every command must end with."""
    return line.strip().lower().rstrip(".") == CLOSING


class Program:
    """A script read for running directly: start() runs it."""

    def __init__(self, commands):
        self.commands = commands

    def start(self):
        self.commands[("start",)].runner()


def translate(path):
    """Returns the C++ text for one .imagine file, or raises ScriptError."""
    return read_script(path)[0]


FILES = []  # the script, then each script it uses ('use: shapes.imagine'), in the order they were read
PER_FILE = 100000  # a line number n in FILES[k] is kept as k * PER_FILE + n


def where(line):
    """'guess.imagine line 3' for a kept line number."""
    k, n = divmod(line, PER_FILE)
    return f"{FILES[k] if k < len(FILES) else '?'} line {n}"


def run_where(line):
    """How an error while running names its line: 'Line 3' in the program itself, 'shapes.imagine line 3' in a used script."""
    return f"Line {line}" if line < PER_FILE else where(line)


def gather(path, from_line=None, seen=None):
    """The lines of a script with every 'use: other.imagine' line replaced by that script's lines.

    Returns (lines, numbers): numbers[i] is the kept line number of lines[i]."""
    seen = set() if seen is None else seen
    seen.add(path.resolve())
    k = len(FILES)
    FILES.append(path.name)
    own = path.read_text(encoding="utf-8").splitlines()
    if len(own) >= PER_FILE:
        raise ScriptError(k * PER_FILE + 1, f"A script can have at most {PER_FILE - 1} lines.")
    lines, numbers = [], []
    for n, raw in enumerate(own, 1):
        if raw.strip().lower().startswith("note:"):
            raise ScriptError(k * PER_FILE + n, "'note:' is now 'whisper:'.")
        if raw.strip().lower().startswith("whisper:"):  # read as an inner 'note:' line
            raw = raw[:len(raw) - len(raw.lstrip())] + "note:" + raw.strip()[8:]
        m = re.fullmatch(r"\s*use:\s*(.+\.imagine)\s*", raw, re.IGNORECASE)
        if m and not raw[:1].isspace():
            other = path.parent / m.group(1).strip()
            if not other.exists():
                raise ScriptError(k * PER_FILE + n, f"There is no script called '{m.group(1).strip()}' next to {path.name}.")
            if other.resolve() not in seen:  # a script used twice (or by itself) is read once
                more, more_numbers = gather(other, k * PER_FILE + n, seen)
                lines += more
                numbers += more_numbers
            continue
        lines.append(raw)
        numbers.append(k * PER_FILE + n)
    return lines, numbers


def read_script(path):
    """Reads one .imagine file. Returns (C++ text, Program or None), or raises ScriptError.

    A program that uses a library's words without 'use:' gets that library by itself."""
    auto = []
    while True:
        try:
            return read_one(path, auto)
        except ScriptError as err:
            m = re.search(r"put the line 'use: (\w+)' at the top", err.message)
            if not m or m.group(1) in auto or len(auto) > 20:
                raise
            auto.append(m.group(1))


def read_one(path, auto):
    global THINGS
    FILES.clear()
    lines, numbers = gather(path)
    main_lines = sum(1 for x in numbers if x < PER_FILE)
    names, info, settings, out = None, {}, [], []
    commands = []  # (header text, line, body)
    things = []  # (name, line, [(line, field text)])
    libs, used = [], set()  # C++ that 'use:' libraries need, and their names
    THINGS = {}
    OWNERS.clear()
    reset_fields()
    first = next((t.strip() for t in lines if t.strip() and not t.strip().startswith("note:")), "")
    if not first.startswith("this is part of:"):
        names, info = Names(), None  # a program of its own
        for lib in auto:
            used.add(lib)
            libs += load_library(lib, 1, names)
    i = 0
    while i < len(lines):
        raw = lines[i]
        text_ = raw.strip()
        n = numbers[i]
        i += 1
        if not text_:
            continue
        if text_.startswith("note:"):
            if not raw[0].isspace():
                out.append(f"// {text_[5:].strip()}")
            continue
        if text_.startswith("this is part of:"):
            if text_ != first or (names and names.known):
                raise ScriptError(n, "'this is part of:' must be the first line of the script (after notes).")
            names, info = load_words(text_.split(":", 1)[1].strip().lower(), n)
            continue
        if text_ == "settings:":
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
                    raise ScriptError(numbers[i - 1], "A setting looks like 'name: number', e.g. 'look limit: 30 degrees'.")
                words = m.group(1).split()
                cpp = f"Imagine_{snake(path.stem.split())}::{snake(words)}"
                number = float(m.group(2))
                names.add(words, cpp, NUMBER, True, lambda env, number=number: number)
                value = m.group(2) if "." in m.group(2) else m.group(2) + ".0"
                settings.append(f"\tconstexpr double {snake(words)} = {value};{'  // ' + m.group(3) if m.group(3) else ''}")
            continue
        if text_.lower() == "to start:":
            raise ScriptError(n, "'to start:' is now 'genesis:'.")
        if text_.lower() == "genesis:":
            text_ = "to start:"
        if text_.startswith("to ") and text_.endswith(":"):
            body = []
            while i < len(lines) and (not lines[i].strip() or lines[i][:1].isspace()):
                body.append((numbers[i], lines[i]))
                i += 1
            if not (n >= PER_FILE and text_.lower() == "to start:"):  # a used script's own start is left out
                commands.append((text_, n, body))
            if i >= len(lines) or not is_closing(lines[i]):
                raise ScriptError(numbers[i] if i < len(lines) else numbers[-1],
                                  f"The command '{text_[:-1]}' must end with the line '{CLOSING}', unindented, after its last indented line.")
            i += 1
            continue
        if text_.lower().startswith("use:"):  # a library ('use: x.imagine' lines were already replaced by gather)
            lib = " ".join(text_[4:].split()).lower()
            if lib in auto:
                continue
            if lib in used:
                raise ScriptError(n, f"The library '{lib}' is already used above.")
            used.add(lib)
            libs += load_library(lib, n, names)
            continue
        m = re.fullmatch(r"an? ([a-z][a-z ]*?) has:", text_.lower())
        if m:
            fields = []
            while i < len(lines) and (not lines[i].strip() or lines[i][:1].isspace()):
                if lines[i].strip() and not lines[i].strip().startswith("note:"):
                    fields.append((numbers[i], lines[i].strip()))
                i += 1
            if i >= len(lines) or not is_closing(lines[i]):
                raise ScriptError(numbers[i] if i < len(lines) else numbers[-1],
                                  f"The description of '{m.group(1)}' must end with the line '{CLOSING}', unindented.")
            i += 1
            name = " ".join(m.group(1).split())
            if name in THINGS or name in BASIC_WORDS:
                raise ScriptError(n, f"There is already a kind of thing called '{name}'.")
            THINGS[name] = []
            things.append((name, n, fields))
            continue
        if is_closing(text_):
            raise ScriptError(n, f"'{CLOSING}' closes a command, so it goes right after the command's last indented line.")
        raise ScriptError(n, f"I don't know what to do with '{text_}'. Top-level lines are notes, 'use:', 'settings:', 'a ... has:' or 'to ...:'.")
    if names is None:
        raise ScriptError(1, "The script is empty.")
    program = info is None
    if things and not program:
        raise ScriptError(things[0][1], "New kinds of things can only be described in programs for now.")
    structs = describe_things(things)
    heads = [command_head(text_, n) for text_, n, _ in commands]
    for (words, cpp, inputs, gives), (_, n, _) in zip(heads, commands):
        if tuple(words) in names.commands:
            raise ScriptError(n, f"There are two commands called '{' '.join(words)}'.")
        names.commands[tuple(words)] = Command(cpp, [kind for _, kind in inputs], gives)
    if program:
        if ("start",) not in names.commands:
            raise ScriptError(main_lines or 1, "A program needs a 'genesis:' command: that is where it begins.")
        if names.commands[("start",)].kinds or names.commands[("start",)].gives:
            raise ScriptError(next(n for (w, *_), (_, n, _) in zip(heads, commands) if w == ["start"]),
                              "'genesis:' has no inputs and gives nothing back.")
    functions = [function(head, n, body, names, info) for head, (_, n, body) in zip(heads, commands)]
    if program:
        protos = [f"{cpp_type(gives) if gives else 'void'} {cpp}({params(cpp, inputs)});"
                  for _, cpp, inputs, gives in heads]
        head = [f"// Generated from {path.name} by imagination.py. Edit the .imagine file, not this one.",
                '#include "imagination.h"', ""] + libs + structs + protos + [""]
        files = ", ".join('"' + f.replace("\\", "\\\\").replace('"', '\\"') + '"' for f in FILES)
        functions.append(f"int main()\n{{\n\timagine::begin({{{files}}});\n\ttry\n\t{{\n\t\tStart();\n\t}}\n"
                         f"\tcatch (const imagine::Problem& problem)\n\t{{\n\t\timagine::report(problem);\n\t\treturn 1;\n\t}}\n\treturn 0;\n}}\n")
    else:
        # The class's header must declare each command, so they can call each other (C++ needs that).
        wanted = [f"//   {cpp_type(gives) if gives else 'void'} {cpp}({params(cpp, inputs)});"
                  for _, cpp, inputs, gives in heads]
        head = [f"// Generated from {path.name} by imagination.py. Edit the .imagine file, not this one.",
                f"// {info['header']} declares these in {info['class']}:"] + wanted + [
                f'#include "{info["header"]}"', ""] + libs
    ns = [f"namespace Imagine_{snake(path.stem.split())}", "{"] + settings + ["}", ""] if settings else []
    return "\n".join(head + ns + out + [""] + functions) + "\n", Program(names.commands) if program else None


def describe_things(things):
    """Reads 'a pet has:' descriptions; returns the C++ structs."""
    described = set()
    for name, n, fields in things:
        if not fields:
            raise ScriptError(n, f"Say what a {name} has, one thing per indented line, like: name (text)")
        for fn, text_ in fields:
            m = re.fullmatch(r"([a-z][a-z ]*?)\s*\(([a-z ]+)\)", text_.lower())
            kind = m and parse_kind(m.group(2))
            if not kind:
                raise ScriptError(fn, f"Each thing a {name} has looks like 'name (text)'. Kinds are: {kind_words()}.")
            if kind == "thing " + name:
                raise ScriptError(fn, f"A {name} can't hold a whole {name} inside itself, but it can hold a list of {name}s.")
            if is_thing(kind) and kind[6:] not in described:
                raise ScriptError(fn, f"Describe what a {kind[6:]} has above the {name}, or hold a list of {kind[6:]}s.")
            words = m.group(1).split()
            if any(w in KEYWORDS for w in words):
                raise ScriptError(fn, f"'{' '.join(words)}' can't be a name: it uses the language's own words.")
            THINGS[name].append((words, kind))
            FIELDS.setdefault(tuple(words), {})["thing " + name] = (snake(words), kind)
        if any(w == ["birth"] for w, _ in THINGS[name]) and not any(w == ["existence"] for w, _ in THINGS[name]):
            kind = next(k for w, k in THINGS[name] if w == ["birth"])  # where it is now, next to where it started
            THINGS[name].insert(next(i for i, (w, _) in enumerate(THINGS[name]) if w == ["birth"]) + 1, (["existence"], kind))
            FIELDS.setdefault(("existence",), {})["thing " + name] = ("existence", kind)
        described.add(name)
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
        for name, _, _ in things:
            cpp = cpp_type("thing " + name)
            out.append(f"\tinline void save(std::string& out, const {cpp}& v, int line);\n\tinline bool load(const SavedData& d, {cpp}& v);")
        for name, _, _ in things:
            cpp = cpp_type("thing " + name)
            parts = ' out += ", ";'.join(f' out += "\\"{" ".join(w)}\\": "; save(out, v.{snake(w)}, line);' for w, k in THINGS[name])
            out.append(f'\tinline void save(std::string& out, const {cpp}& v, int line) {{ out += "{{";{parts} out += "}}"; }}')
            loads = "".join(f' if (auto p = d.part("{" ".join(w)}"); p && !load(*p, v.{snake(w)})) return false;' for w, k in THINGS[name])
            out.append(f"\tinline bool load(const SavedData& d, {cpp}& v) {{ if (d.type != SavedData::Table) return false; v = {cpp}{{}};{loads} return true; }}")
        out.append("}")
        out += [f"using imagine::{cpp_type('thing ' + name)};" for name, _, _ in things]
        out.append("")
    return out


def command_head(header, line):
    """'to greet, given name (text):' -> (['greet'], 'Greet', [(['name'], TEXT)], None)."""
    m = re.fullmatch(r"to ([a-z ]+?)(?:, for an? ([a-z ]+?))?(?:, given (.+?))?(?:, giving back (.+))?:", header.lower())
    if not m:
        raise ScriptError(line, "A command starts like 'to steer toward, given goal (a place) and running (yes or no):'.")
    inputs = []
    words = m.group(1).split()
    if m.group(2):  # a command for a kind of thing: it gets that thing and can change it
        owner = " ".join(m.group(2).split())
        if owner not in THINGS:
            raise ScriptError(line, f"There is no kind of thing called '{owner}'." + (f" Kinds of things: {', '.join(THINGS)}." if THINGS else ""))
        inputs.append((owner.split(), "thing " + owner))
        OWNERS["".join(w.capitalize() for w in words)] = "thing " + owner
    if m.group(3):
        for part in re.split(r"\s+and\s+(?=[a-z ]+\()", m.group(3)):
            pm = re.fullmatch(r"([a-z ]+?)\s*\(([a-z ]+)\)", part.strip())
            kind = pm and parse_kind(pm.group(2))
            if not kind:
                raise ScriptError(line, f"An input looks like 'goal (a place)'. Kinds are: {kind_words()}.")
            inputs.append((pm.group(1).split(), kind))
    gives = None
    if m.group(4):
        gives = parse_kind(m.group(4))
        if not gives:
            raise ScriptError(line, f"'giving back' needs a kind, like 'giving back a number'. Kinds are: {kind_words()}.")
    return words, "".join(w.capitalize() for w in words), inputs, gives


def params(cpp, inputs):
    """The C++ inputs of a command; the thing a command is for is passed so the command can change it."""
    return ", ".join((f"{cpp_type(k)}& " if i == 0 and cpp in OWNERS else param_type(k) + " ") + snake(w)
                     for i, (w, k) in enumerate(inputs))


def function(head, line, body, names, info):
    words, name, inputs, gives = head
    local = Names()
    local.known = dict(names.known)
    local.commands = names.commands
    local.gives = gives
    if any(cpp_type("thing " + t) == name for t in THINGS):
        raise ScriptError(line, f"The command '{' '.join(words)}' has the same name as a kind of thing. Give one of them another name.")
    for k, (in_words, kind) in enumerate(inputs):
        if k == 0 and name in OWNERS:
            own = snake(in_words)

            def put_all(env, x, own=own):
                env[own].fields = dup(x).fields  # change the caller's thing itself, not a copy
            local.add(in_words, own, kind, False, (lambda env, own=own: env[own], put_all))
            for part_words, part_kind in THINGS[kind[6:]]:
                member = snake(part_words)

                def get(env, own=own, member=member):
                    return env[own].fields[member]

                def put(env, x, own=own, member=member):
                    env[own].fields[member] = dup(x)
                local.add(part_words, f"{own}.{member}", part_kind, False, (get, put))
        else:
            local.add(in_words, snake(in_words), kind, read_only=True)
    declared = {}
    code, run = statements(body, local, declared, 1)
    hoisted = [f"\t{cpp_type(k)} {c} = {zero(k)};" for c, k in declared.values()]
    owner = f"{info['class']}::" if info else ""
    end = [f"\treturn {zero(gives)};"] if gives else []
    if not info:
        param_names = [snake(w) for w, _ in inputs]
        things = THINGS

        def runner(*args):
            env = {c: py_zero(k, things) for c, k in declared.values()}
            env.update(zip(param_names, args))
            try:
                run(env)
            except Stop:
                return None
            except GiveBack as g:
                return g.value
            return py_zero(gives, things) if gives else None
        names.commands[tuple(words)].runner = runner
    return "\n".join([f"{cpp_type(gives) if gives else 'void'} {owner}{name}({params(name, inputs)})", "{"]
                     + hoisted + code + end + ["}"]) + "\n"


# ---------------------------------------------------------------- lines inside a command

def statements(body, names, declared, depth):
    """Reads an indented block. body: list of (line number, raw text). Returns (C++ lines, run)."""
    out, runs = [], []
    rows = [(n, r) for n, r in body if r.strip()]
    indent = len(rows[0][1].expandtabs(4)) - len(rows[0][1].expandtabs(4).lstrip()) if rows else 0
    chain = None  # the if / otherwise if / otherwise choices being collected
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
        if raw.strip().lower() == "try:":
            handler = None
            if k < len(rows) and rows[k][1].strip().lower() == "if that went wrong:" \
                    and len(rows[k][1].expandtabs(4)) - len(rows[k][1].expandtabs(4).lstrip()) == indent:
                hn = rows[k][0]
                k += 1
                handler = []
                while k < len(rows) and len(rows[k][1].expandtabs(4)) - len(rows[k][1].expandtabs(4).lstrip()) > indent:
                    handler.append(rows[k])
                    k += 1
            if handler is None:
                raise ScriptError(n, "'try:' needs an 'if that went wrong:' line after its indented lines, at the same indent.")
            if not inner or not handler:
                raise ScriptError(n if not inner else hn, "Say what to do on the indented lines below the ':'.")
            lines, run = attempt(n, inner, handler, names, declared, depth)
            out += lines
            chain = None
            runs.append(run)
            continue
        if raw.strip().lower() == "if that went wrong:":
            raise ScriptError(n, "'if that went wrong:' goes right after the indented lines of a 'try:'.")
        lines, run, branch = statement(n, surface(raw.strip(), n), inner, names, declared, depth)
        out += lines
        if branch:
            which, cond = branch
            if which == "if":
                chain = [(cond, run)]
                runs.append(choose(chain))
            elif chain is None:
                raise ScriptError(n, f"'{raw.strip().split(':')[0]}' needs an 'if' line just above it, at the same indent.")
            else:
                chain.append((cond, run))
            if which == "otherwise":
                chain = None
            continue
        if run is not None:
            chain = None
            runs.append(guard(run, n))
    return out, block(runs)


def attempt(n, tried, handler, names, declared, depth):
    """try: ... if that went wrong: ...  Inside the second part, 'the problem' is what went wrong, as text."""
    tab = "\t" * depth
    try_lines, try_run = statements(tried, names, declared, depth + 1)
    key = ("the", "problem")
    if key in names.known:
        raise ScriptError(n, "There is a 'try:' inside the 'if that went wrong:' of another one. Put it in a command of its own.")
    cpp = f"the_problem_{n}"
    names.add(key, cpp, TEXT, read_only=True)
    try:
        fix_lines, fix_run = statements(handler, names, declared, depth + 1)
    finally:
        del names.known[key]

    def run(env):
        try:
            try_run(env)
        except RunError as err:
            env[cpp] = err.message
            fix_run(env)
    caught = f"imagine_problem_{n}"
    return ([f"{tab}try", tab + "{"] + try_lines + [tab + "}", f"{tab}catch (const imagine::Problem& {caught})", tab + "{",
             f"{tab}\tconst std::string {cpp} = {caught}.message;"] + fix_lines + [tab + "}"]), run


def choose(chain):
    def run(env):
        for cond, then in chain:
            if cond is None or cond(env):
                then(env)
                return
    return run


def block(runs):
    runs = tuple(runs)

    def run(env):
        for f in runs:
            f(env)
    return run


def guard(run, n):
    """Turns a surprise inside Imagination into a plain message with the line it happened on."""
    def guarded(env):
        try:
            run(env)
        except (RunError, Flow, SystemExit, KeyboardInterrupt):
            raise
        except RecursionError:
            raise RunError(n, "commands called each other too many times in a row (they may never stop).")
        except Exception as err:
            raise RunError(n, f"something went wrong inside Imagination: {err}")
    return guarded


def statement(n, text_, inner, names, declared, depth):
    """One line (with its indented lines). Returns (C++ lines, run, branch); branch is set for if/otherwise lines."""
    tab = "\t" * depth
    if text_.startswith("note:"):
        return [f"{tab}// {text_[5:].strip()}"], None, None
    head, colon, rest = split_colon(text_)

    def body(loop=False):
        if loop:
            names.loops += 1
            try:
                lines, run = body()
            finally:
                names.loops -= 1
            return lines, looped(run)
        if rest.strip():
            lines, run, branch = statement(n, rest.strip(), [], names, declared, depth + 1)
            if branch:
                raise ScriptError(n, "Put 'if' and 'otherwise' on their own lines when they are inside another line.")
            return lines, run or (lambda env: None)
        lines, run = statements(inner, names, declared, depth + 1)
        if not lines:
            raise ScriptError(n, "Say what to do after the ':' (on the same line or indented below).")
        return lines, run

    if colon and re.match(r"for each ", text_.lower()):
        return for_each(n, head, body, names, declared, depth)
    if colon and re.match(r"(repeat |while )", text_.lower()):
        tokens = tokenize(head, n)
        if tokens[0] == "while":
            v = expr_to_end(tokens, 1, names, n)
            if v.kind != YESNO:
                raise ScriptError(n, f"'as long as' needs something that is yes or no, but this is {kind_name(v.kind)}.")
            lines, then = body(loop=True)
            cond = v.run

            def run(env):
                while cond(env):
                    if not then(env):
                        break
            return [f"{tab}while ({strip_parens(v.cpp)})", tab + "{"] + lines + [tab + "}"], run, None
        if tokens[-1:] != ["times"]:
            raise ScriptError(n, "'echo' looks like 'echo 10 times:'.")
        count = expr_to_end(tokens[:-1], 1, names, n)
        if count.kind != NUMBER:
            raise ScriptError(n, f"'echo' needs a number of times, but this is {kind_name(count.kind)}.")
        lines, then = body(loop=True)
        k = f"imagine_count_{depth}_{n}"
        times = count.run

        def run(env):
            c = times(env)
            for _ in range(int(c) if math.isfinite(c) else 0):
                if not then(env):
                    break
        return [f"{tab}for (long long {k} = 0; {k} < (long long)({strip_parens(count.cpp)}); ++{k})", tab + "{"] + lines + [tab + "}"], run, None
    if colon and re.match(r"(if |otherwise\b)", text_):
        tokens = tokenize(head, n)
        if tokens[:2] == ["otherwise", "if"]:
            cond, prefix, which = tokens[2:], "else if", "otherwise if"
        elif tokens == ["otherwise"]:
            cond, prefix, which = None, "else", "otherwise"
        elif tokens[0] == "if":
            cond, prefix, which = tokens[1:], "if", "if"
        else:
            raise ScriptError(n, "Use 'if ...:', 'otherwise if ...:' or 'otherwise:'.")
        line = f"{tab}{prefix}"
        test = None
        if cond is not None:
            v = expr_to_end(cond, 0, names, n)
            if v.kind != YESNO:
                raise ScriptError(n, f"'if' needs something that is yes or no, but this is {kind_name(v.kind)}.")
            line += f" ({strip_parens(v.cpp)})"
            test = v.run
        lines, then = body()
        return [line, tab + "{"] + lines + [tab + "}"], guard(then, n), (which, test)
    if inner:
        raise ScriptError(inner[0][0], "Only 'if', 'otherwise', 'echo', 'as long as', 'for each' and 'try' lines can have indented lines under them.")
    tokens = tokenize(text_, n)
    if tokens in (["stop", "the", "loop"], ["skip", "to", "the", "next", "one"], ["skip", "to", "the", "next"]):
        if not names.loops:
            said = "break free" if tokens[0] == "stop" else "move on"
            raise ScriptError(n, f"'{said}' only works inside 'echo', 'as long as' or 'for each'.")
        leave = tokens[0] == "stop"

        def run(env):
            raise LeaveLoop() if leave else NextRound()
        return [f"{tab}{'break' if leave else 'continue'};"], run, None
    if tokens == ["stop"]:
        if names.gives:
            raise ScriptError(n, f"This command gives back {kind_name(names.gives)}, so leave it with 'give back ...' instead of 'cease'.")

        def run(env):
            raise Stop()
        return [f"{tab}return;"], run, None
    if tokens[:2] == ["give", "back"]:
        if not names.gives:
            raise ScriptError(n, "'give back' only works in a command that says what it gives back, like 'to double, given x (a number), giving back a number:'.")
        v = expr_to_end(tokens, 2, names, n)
        if v.kind != names.gives:
            raise ScriptError(n, f"This command gives back {kind_name(names.gives)}, not {kind_name(v.kind)}.")
        get = v.run

        def run(env):
            raise GiveBack(get(env))
        return [f"{tab}return {strip_parens(v.cpp)};"], run, None
    if tokens[0] in ("add", "write") and "to" in tokens and tokens[len(tokens) - tokens[::-1].index("to"):][:1] == ["file"]:
        cut = len(tokens) - 1 - tokens[::-1].index("to")
        where = expr_to_end(tokens, cut + 2, names, n)
        v = expr_to_end(tokens[:cut], 1, names, n)
        if where.kind != TEXT:
            raise ScriptError(n, f"A file is named with text, like file \"notes.txt\", but this is {kind_name(where.kind)}.")
        fn = "add_line" if tokens[0] == "add" else "write_file"
        w, get, adding = where.run, v.run, tokens[0] == "add"

        def run(env):
            s = text(get(env))
            write_file(w(env), s + "\n" if adding else s, n, "ab" if adding else "wb")
        return [f"{tab}imagine::{fn}({strip_parens(where.cpp)}, imagine::text({strip_parens(v.cpp)}), {n});"], run, None
    if tokens[0] == "add" and "to" in tokens:
        cut = len(tokens) - 1 - tokens[::-1].index("to")
        target = writable_list(tokens[cut + 1:], names, n, "add to")
        v = expr_to_end(tokens[:cut], 1, names, n)
        if v.kind != element(target.kind):
            raise ScriptError(n, f"This list holds {plural(element(target.kind))}, so I can't add {kind_name(v.kind)} to it.")
        seq, get = target.run, v.run
        return [f"{tab}({target.cpp}).push_back({strip_parens(v.cpp)});"], lambda env: seq(env).append(dup(get(env))), None
    if tokens[:2] == ["remove", "entry"] and "from" in tokens:
        cut = len(tokens) - 1 - tokens[::-1].index("from")
        table = expr_to_end(tokens, cut + 1, names, n)
        if not is_table(table.kind) or not table.writable:
            raise ScriptError(n, f"'banish entry ... from' needs a table that can be changed, but this is {kind_name(table.kind)}.")
        key = expr_to_end(tokens[:cut], 2, names, n)
        if key.kind != TEXT:
            raise ScriptError(n, f"A table's entries are named with text, but this is {kind_name(key.kind)}.")
        get, at = table.run, key.run
        return ([f"{tab}imagine::remove_entry({table.cpp}, {strip_parens(key.cpp)}, {n});"],
                lambda env: remove_entry(get(env), at(env), n), None)
    if tokens[0] == "remove" and "from" in tokens:
        cut = len(tokens) - 1 - tokens[::-1].index("from")
        target = writable_list(tokens[cut + 1:], names, n, "remove from")
        seq = target.run
        if tokens[1] == "item":
            index = expr_to_end(tokens[:cut], 2, names, n)
            if index.kind != NUMBER:
                raise ScriptError(n, f"'banish item' needs a number, but this is {kind_name(index.kind)}.")
            at = index.run

            def run(env):
                items = seq(env)
                items.pop(index_of(items, at(env), n))
            return [f"{tab}imagine::remove_item({target.cpp}, {strip_parens(index.cpp)}, {n});"], run, None
        v = expr_to_end(tokens[:cut], 1, names, n)
        if v.kind != element(target.kind):
            raise ScriptError(n, f"This list holds {plural(element(target.kind))}, so it has no {kind_name(v.kind)} to remove.")
        get = v.run

        def run(env):
            items, x = seq(env), get(env)
            if x in items:
                items.remove(x)
        return [f"{tab}imagine::remove_value({target.cpp}, {strip_parens(v.cpp)});"], run, None
    if tokens[0] == "draw":
        raise ScriptError(n, "'draw' is now 'etch', like: etch a circle with 100, 100, 20, \"orange\".")
    if tokens[0] == "say":
        raise ScriptError(n, "'say' is now 'scrawl', like: scrawl \"hello\".")
    if tokens[0] == "scrawl":
        parts = expr_list(tokens, 1, names, n)
        if not parts:
            raise ScriptError(n, f"'{tokens[0]}' needs something to show, like: {tokens[0]} \"hello\".")
        gets = [p.run for p in parts]

        def run(env):
            print("".join(text(g(env)) for g in gets))
        return [f"{tab}imagine::say({{{', '.join('imagine::text(' + strip_parens(p.cpp) + ')' for p in parts)}}});"], run, None
    if tokens[0] == "ask":
        return ask(tokens, names, declared, n, tab)
    for verb, joint in (("save", "to"), ("load", "from")):
        if tokens[0] == verb and joint in tokens and tokens[len(tokens) - tokens[::-1].index(joint):][:1] == ["file"]:
            cut = len(tokens) - 1 - tokens[::-1].index(joint)
            where = expr_to_end(tokens, cut + 2, names, n)
            if where.kind != TEXT:
                raise ScriptError(n, f"A file is named with text, like file \"scores.txt\", but this is {kind_name(where.kind)}.")
            if cut == 1:
                raise ScriptError(n, f"Say what to {verb}, like '{verb} scores {joint} file \"scores.txt\"'.")
            w = where.run
            if verb == "save":
                v = expr_to_end(tokens[:cut], 1, names, n)
                get, kind = v.run, v.kind
                return ([f"{tab}imagine::save_file({strip_parens(v.cpp)}, {strip_parens(where.cpp)}, {n});"],
                        lambda env: write_file(w(env), saved(get(env), kind, n) + "\n", n), None)
            e = Expr(tokens[1:cut], names, n)
            target = e.full()
            if e.i != len(e.t) or not target.writable or getattr(target, "cpp_assign", None):
                raise ScriptError(n, f"'{' '.join(tokens[1:cut])}' can't be changed, so I can't load into it.")
            put, kind, things = target.store, target.kind, THINGS
            return ([f"{tab}imagine::load_file({strip_parens(target.cpp)}, {strip_parens(where.cpp)}, {cpp_text(chr(34) + kind_name(target.kind) + chr(34))}, {n});"],
                    lambda env: put(env, load_saved(w(env), kind, things, n)), None)
    key, size = match_command(names, tokens)
    if key:
        start = size + (tokens[size:size + 1] == ["with"])
        rest = tokens[start:]
        if rest[:1] == ["("] and rest[-1:] == [")"] and closing_bracket(rest, 0) == len(rest) - 1 and "," in rest:
            rest = rest[1:-1]  # 'move along with (b, 2)': the inputs may be in brackets here too
        args = expr_list(rest, 0, names, n)
        cpp, run = call(key, args, names, n)
        return [f"{tab}{cpp};"], run, None
    if tokens[0] == "set" and "to" in tokens and ("of" in tokens[1:tokens.index("to")] or tokens[1:2] in (["item"], ["entry"])):
        cut = tokens.index("to")
        e = Expr(tokens[1:cut], names, n)
        target = e.full()
        if e.i != len(e.t) or not target.writable:
            raise ScriptError(n, f"'{' '.join(tokens[1:cut])}' can't be changed.")
        v = expr_to_end(tokens, cut + 1, names, n)
        if v.kind != target.kind:
            raise ScriptError(n, f"'{' '.join(tokens[1:cut])}' holds {kind_name(target.kind)}, not {kind_name(v.kind)}.")
        put, get = target.store, v.run
        assign = getattr(target, "cpp_assign", None) or f"{strip_parens(target.cpp)} = "
        return [f"{tab}{assign}{strip_parens(v.cpp)}{getattr(target, 'cpp_close', '')};"], lambda env: put(env, get(env)), None
    if tokens[0] == "set":
        key, size = names.match(tokens, 1)
        if key and tokens[1 + size:2 + size] == ["to"]:
            cpp, kind, read_only, _ = names.known[key]
            if read_only:
                raise ScriptError(n, f"'{' '.join(key)}' can't be changed by a script.")
            v = expr_to_end(tokens, 2 + size, names, n)
            if v.kind != kind:
                raise ScriptError(n, f"'{' '.join(key)}' holds {kind_name(kind)}, not {kind_name(v.kind)}.")
            put, get = names.value(key).store, v.run
            if key == ("birth",) and names.known.get(("existence",), (None, None))[1] == kind:
                there = names.value(("existence",)).store

                def run(env):
                    x = get(env)
                    put(env, x)
                    there(env, dup(x))
                return [f"{tab}{cpp} = {strip_parens(v.cpp)};", f"{tab}{names.known[('existence',)][0]} = {cpp};"], run, None
            return [f"{tab}{cpp} = {strip_parens(v.cpp)};"], lambda env: put(env, get(env)), None
        hint = library_hint(tokens)
        if hint:
            raise ScriptError(n, f"I don't know '{' '.join(tokens[:tokens.index('to') + 1] if 'to' in tokens else tokens)}'." + hint)
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
        get = v.run
        if words == ["birth"] and ("existence",) not in names.known:
            # birth is where something starts; existence is where it is now, and it starts at its birth
            declared[("existence",)] = ("existence", v.kind)
            names.add(["existence"], "existence", v.kind)

            def run(env):
                env[cpp] = dup(get(env))
                env["existence"] = dup(env[cpp])
            return [f"{tab}{cpp} = {strip_parens(v.cpp)};", f"{tab}existence = {cpp};"], run, None

        def run(env):
            env[cpp] = dup(get(env))
        return [f"{tab}{cpp} = {strip_parens(v.cpp)};"], run, None
    if tokens[0] == "move":
        key, size = names.match(tokens, 1)
        if not key or tokens[1 + size:2 + size] != ["toward"]:
            raise ScriptError(n, "'move' looks like 'move turn rate toward 20 by at most 5'.")
        cpp, kind, read_only, _ = names.known[key]
        if read_only or kind != NUMBER:
            raise ScriptError(n, f"'{' '.join(key)}' can't be moved: it must be a number a script may change.")
        e = Expr(tokens[2 + size:], names, n)
        goal = e.need(e.sum(), NUMBER, "move")
        e.take("by", "at", "most")
        step = e.need(e.sum(), NUMBER, "move")
        if e.i != len(e.t):
            raise ScriptError(n, f"I don't understand '{' '.join(e.t[e.i:])}' here.")
        s = f"imagine_step_{depth}_{n}"
        target = names.value(key)
        now, put, g, st = target.run, target.store, goal.run, step.run

        def run(env):
            x, by = now(env), st(env)
            put(env, min(max(g(env), x - by), x + by))
        return [f"{tab}const double {s} = {strip_parens(step.cpp)};",
                f"{tab}{cpp} = FMath::Clamp({strip_parens(goal.cpp)}, {cpp} - {s}, {cpp} + {s});"], run, None
    hint = library_hint(tokens)
    if hint:
        raise ScriptError(n, f"I don't know how to start a line with '{tokens[0]}'." + hint)
    near = similar_words(tokens, names)
    if near:
        raise ScriptError(n, f"I don't know '{' '.join(tokens[:4])}'." + near)
    raise ScriptError(n, f"I don't know how to start a line with '{tokens[0]}'. Lines start with set, move, scrawl, ask, gather, banish, inscribe, if, otherwise, echo, as long as, for each, try, give back, cease, whisper or the name of a command.")


def for_each(n, head, body, names, declared, depth):
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
        get = seq.run
        simple = kind in (NUMBER, YESNO, TEXT)

        def items(env):
            return list(get(env)) if simple else copy.deepcopy(get(env))
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
        a, b = lo.run, hi.run

        def items(env):
            x, last = a(env), b(env)
            while x <= last:
                yield x
                x += 1
    names.add(words, cpp, kind, read_only=True)
    lines, then = body(loop=True)
    del names.known[tuple(words)]

    def run(env):
        for x in items(env):
            env[cpp] = x
            if not then(env):
                break
    return [line, tab + "{"] + lines + [tab + "}"], run, None


def call(key, args, names, n):
    """Calling a command, after checking its inputs. Returns (C++, run)."""
    command = names.commands[key]
    kinds = command.kinds
    if len(args) != len(kinds):
        raise ScriptError(n, f"'{' '.join(key)}' needs {len(kinds)} input{'s' if len(kinds) != 1 else ''}, but this gives it {len(args)}.")
    for k, (a, kind) in enumerate(zip(args, kinds), 1):
        if a.kind != kind:
            raise ScriptError(n, f"Input {k} of '{' '.join(key)}' must be {kind_name(kind)}, not {kind_name(a.kind)}.")
    if command.cpp in OWNERS and not args[0].writable:
        raise ScriptError(n, f"'{' '.join(key)}' changes the {kind_name(kinds[0])[2:]} it is given, so give it a name "
                             f"that holds one, like '{' '.join(key)} {kind_name(kinds[0])[2:]}'.")
    gets = [a.run for a in args]

    def run(env):
        try:
            return command.runner(*[g(env) for g in gets])
        except RunError as err:
            if not err.line:  # from a library word: point at the line that used it
                err.line = n
            raise
    cpp = command.cpp
    if command.inputs is not None:  # a library word: put each input into its {input name} place
        given = {"{" + in_name + "}": f"({strip_parens(a.cpp)})" for in_name, a in zip(command.inputs, args)}
        given["{line}"] = str(n)  # so the library's C++ can say which line went wrong
        # all at once, so an input's own text is never replaced again
        cpp = re.sub("|".join(re.escape(g) for g in given), lambda m: given[m.group(0)], cpp)
        return f"({cpp})", run
    return f"{cpp}({', '.join(strip_parens(a.cpp) for a in args)})", run


def writable_list(tokens, names, n, what):
    v = expr_to_end(tokens, 0, names, n)
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
    if not (len(tokens) >= 4 and tokens[1].startswith('"') and tokens[2] == "into"):
        raise ScriptError(n, "'ask' looks like: ask \"What's your name? \" into name (text)")
    rest = tokens[3:]
    kind = TEXT
    if rest[-1:] == [")"] and "(" in rest:
        cut = rest.index("(")
        kind = parse_kind(" ".join(rest[cut + 1:-1]))
        if kind not in (TEXT, NUMBER, YESNO):
            raise ScriptError(n, "'ask' can keep a number, text or yes or no, like: into age (a number)")
        rest = rest[:cut]
    key, size = names.match(rest, 0)
    if key and size == len(rest):
        cpp, have, read_only, _ = names.known[key]
        if read_only or have not in (TEXT, NUMBER, YESNO):
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
    question = tokens[1][1:-1]
    reader = {NUMBER: ask_number, YESNO: ask_yes_no, TEXT: ask_text}[kind]

    def run(env):
        env[cpp] = reader(question)
    cpp_reader = {NUMBER: "imagine::ask_number", YESNO: "imagine::ask_yes_no", TEXT: "imagine::ask_text"}[kind]
    return [f"{tab}{cpp} = {cpp_reader}({cpp_text(tokens[1])});"], run, None


def closing_bracket(tokens, i):
    """Where the bracket opened at tokens[i] closes, or -1."""
    depth = 0
    for k in range(i, len(tokens)):
        depth += {"(": 1, ")": -1}.get(tokens[k], 0)
        if depth == 0:
            return k
    return -1


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


# ---------------------------------------------------------------- running and building

def run_program(script):
    """Runs a program directly. Returns the exit code (0 when it finished, 1 when it stopped with an error)."""
    global LOGIC
    LOGIC = script.parent
    try:
        _, program = read_script(script)
    except ScriptError as err:
        print(f"{where(err.line)}: {err.message}")
        return 1
    if program is None:
        print(f"{script.name} is part of something else ('this is part of:'), so it can't run on its own.")
        return 1
    result = {"code": 0}
    # Text is UTF-8 everywhere, as in built programs (Windows would otherwise use its old code page when piped).
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")

    def go():
        try:
            program.start()
        except RunError as err:
            sys.stdout.flush()
            print(f"{run_where(err.line)}: {err.message}", file=sys.stderr)
            result["code"] = 1
        except SystemExit as done:
            result["code"] = done.code or 0
        except KeyboardInterrupt:
            result["code"] = 130
        sys.stdout.flush()
    # Deep chains of commands need a deeper stack than Python's default.
    sys.setrecursionlimit(100000)
    threading.stack_size(255 * 1024 * 1024)  # the most Windows allows here
    worker = threading.Thread(target=go)
    worker.start()
    worker.join()
    return result["code"]


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
    """Reads a program script and compiles it into exe. Returns an error message, or None."""
    global LOGIC
    LOGIC = script.parent
    try:
        cpp_out, program = read_script(script)
    except ScriptError as err:
        return f"{where(err.line)}: {err.message}"
    if program is None:
        return f"{script.name} is part of something else ('this is part of:'), so it can't run on its own."
    vcvars = find_vcvars()
    if not vcvars:
        return "I can't find the C++ compiler. Install Visual Studio with 'Desktop development with C++'."
    work = Path(tempfile.mkdtemp(prefix="imagine_"))
    cpp = work / f"{script.stem}.imagine.cpp"
    cpp.write_text(cpp_out, encoding="utf-8")
    bat = work / "build.bat"
    bat.write_text(f'@call "{vcvars}" >nul 2>&1\r\n@cl /nologo /utf-8 /EHsc /std:c++20 /O2 /W0 /I"{HERE / "runtime"}" '
                   f'"{cpp}" /Fe"{exe}" /Fo"{work}\\\\" >"{work / "compile.log"}" 2>&1\r\n', encoding="utf-8")
    result = subprocess.run(["cmd", "/c", str(bat)])
    if result.returncode != 0:
        log = (work / "compile.log").read_text(errors="replace")
        return f"Imagination wrote C++ the compiler didn't accept. That is a bug in Imagination (or a library), not in your script.\n{log}"
    return None


TRY_HELLO = """Imagination: type a line and press Enter to see what it does. For example:
  set name to "Sam"
  scrawl "Hello, " plus name
  5 plus 3 times 2
A line ending in ':' (like 'repeat 3 times:') takes the indented lines after it; finish them with an empty line.
'use: maths' brings in a library. Type 'bye' to finish."""


def try_it(read=input, show=print):
    """Lines typed one at a time, each done straight away (names are kept from line to line)."""
    global LOGIC, THINGS
    LOGIC = Path.cwd()
    THINGS = {}
    reset_fields()
    FILES[:] = ["(typed)"]
    names, declared, env = Names(), {}, {}
    names.loops = 0
    show(TRY_HELLO)
    n = 0
    while True:
        try:
            line = read("> ")
        except (EOFError, KeyboardInterrupt):
            return 0
        n += 1
        if line.strip().lower() in ("bye", "quit", "exit"):
            return 0
        if not line.strip():
            continue
        rows = [(n, "  " + line)]
        if split_colon(line)[1] and not split_colon(line)[2].strip():
            while True:  # the indented lines of a block, until an empty line
                try:
                    more = read("... ")
                except (EOFError, KeyboardInterrupt):
                    more = ""
                n += 1
                if not more.strip():
                    break
                rows.append((n, "  " + (more if more[:1].isspace() else "  " + more)))
        try:
            if line.strip().lower().startswith("use:"):
                load_library(" ".join(line.strip()[4:].split()).lower(), n, names)
                show(f"(the words of '{line.strip()[4:].strip()}' can be used now)")
                continue
            v = None
            if len(rows) == 1:
                try:  # a value on its own (like '5 plus 3' or 'round 2.6') is shown
                    v = expr_to_end(tokenize(line.strip(), n), 0, names, n)
                except ScriptError:
                    v = None
            if v is not None:
                run = lambda env, get=v.run: show(text(get(env)))
            else:
                _, run = statements(rows, names, declared, 1)
            for cpp, kind in declared.values():
                env.setdefault(cpp, py_zero(kind, THINGS))
            run(env)
        except ScriptError as err:
            show(err.message)
        except RunError as err:
            show(err.message[:1].upper() + err.message[1:])
        except (Stop, GiveBack):
            pass
        except Flow:
            show("That only works inside a loop.")


USAGE = """Use:
  imagine <script.imagine>                     run a program
  imagine run <script.imagine>                 the same
  imagine build <script.imagine>               make it into an .exe (needs Visual Studio's C++ compiler)
  imagine check <script.imagine>               look for mistakes without running it
  imagine                                      try lines out, one at a time
  imagine <scripts folder> <output folder>     turn 'this is part of:' scripts into C++ (for Unreal)
(imagine is short for: py -3 imagination.py)"""


def main(argv):
    global LOGIC, OUT
    args = argv[1:]
    if not args:
        return try_it()
    if len(args) == 1 and args[0].lower().endswith(".imagine"):
        args = ["run", args[0]]
    if len(args) == 2 and args[0] == "check":
        LOGIC = Path(args[1]).parent
        try:
            read_script(Path(args[1]))
        except FileNotFoundError:
            print(f"There is no script called {args[1]}.")
            return 2
        except ScriptError as err:
            print(f"{where(err.line)}: {err.message}")
            return 1
        print(f"{Path(args[1]).name}: no mistakes found.")
        return 0
    if len(args) == 2 and args[0] in ("run", "build"):
        script = Path(args[1])
        if not script.exists():
            print(f"There is no script called {script}.")
            return 2
        if args[0] == "run":
            code = run_program(script)
            sys.stdout.flush()
            sys.stderr.flush()
            # Exit straight away: a library's leftovers (like a closed window) must not be tidied up from the wrong thread.
            os._exit(code)
        exe = script.with_suffix(".exe")
        problem = build(script, exe)
        if problem:
            print(problem)
            return 1
        print(f"Built {exe}")
        return 0
    if len(args) != 2:
        print(USAGE)
        return 2
    LOGIC, OUT = Path(args[0]), Path(args[1])
    OUT.mkdir(parents=True, exist_ok=True)
    failed = False
    wanted = set()
    for path in sorted(LOGIC.glob("*.imagine")):
        target = OUT / f"{path.stem}.imagine.cpp"
        wanted.add(target.name)
        try:
            cpp_out = translate(path)
        except ScriptError as err:
            print(f"{where(err.line)}: {err.message}")
            failed = True
            continue
        if not target.exists() or target.read_text(encoding="utf-8") != cpp_out:
            target.write_text(cpp_out, encoding="utf-8")
    for old in OUT.glob("*.imagine.cpp"):
        if old.name not in wanted:
            old.unlink()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
