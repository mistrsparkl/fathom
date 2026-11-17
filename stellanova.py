"""Stellanova: a programming language written in plain English words.

Run a program:         py -3 stellanova.py run <script.stella>      (or: stellanova <script.stella>)
Build it as an .exe:   py -3 stellanova.py build <script.stella>    (needs LLVM: winget install LLVM.LLVM)
Unreal parts:          py -3 stellanova.py <scripts folder> <output folder>

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
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import machine


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
    """Something that went wrong while a program ran (kind: a kind of problem of the program's own, or "")."""

    def __init__(self, line, message, kind=""):
        super().__init__(message)
        self.line = line
        self.message = message
        self.kind = kind


# ---------------------------------------------------------------- kinds of things

NUMBER, YESNO, PLACE, FLAT, TEXT = "number", "yes or no", "place", "flat", "text"
# Kinds are strings: the five above, "list of <kind>", or "thing <name>" for a kind the script describes itself.
CPP_TYPE = {NUMBER: "double", YESNO: "bool", PLACE: "FVector", FLAT: "FVector2D", TEXT: "std::string"}
ZERO = {NUMBER: "0.0", YESNO: "false", PLACE: "FVector::ZeroVector", FLAT: "FVector2D::ZeroVector", TEXT: "std::string()"}
BASIC_WORDS = {"number": NUMBER, "numbers": NUMBER, "yes or no": YESNO, "place": PLACE, "places": PLACE,
               "flat place": FLAT, "flat places": FLAT, "text": TEXT, "texts": TEXT, "text values": TEXT}
UNREAL = False  # set by 'stellanova unreal': libraries/unreal/ words win, and the program starts from StellanovaMain()
# Set by 'stellanova web': the script is read into JavaScript instead. Every piece's .cpp then holds JavaScript; most of it
# is written the same way in both (calls, operators, if, while), and the places where they differ check JS.
JS = False
JS_RESERVED = set("""function let var yield await async in of typeof instanceof void delete new this class extends super import
export default null undefined true false arguments eval with enum implements interface package private protected public
static stellanova""".split())
MAKING_CPP = False  # yes while a program is being made into C++ (build, unreal, translate)
PLUGIN = False  # yes while a program is being made into a plugin for a game engine
UNUSABLE = "\x00"  # a library word's C++ starts with this when this way of running can't use it; the message follows
ARGUMENTS = []  # the words typed after the script's name, for 'the words given'
THINGS = {}  # name -> [(field words, kind)], for the script being read (a new dict for each script)
FIELDS = {}  # field words tuple -> {thing kind: (member, kind)}
SECRET_PARTS = {}  # (thing kind, field words tuple) -> the kind that hid it: only its commands (and its kinds' commands) use it
OWNER_NOW = [None]  # the kind of thing the command being read is for

KEYWORDS = set("""changed kept meanwhile invoke shatter trimmed begins ends touches exceeds falls echo cease gather banish inscribe conjure whisper wound return returning raise whether horizontal vertical depth try set to if otherwise stop note and or not is more less than at least most plus minus times divided by
clamp between smaller larger of square root size flat direction angle from yes no move toward
scrawl ask into repeat while with random for each in contains list empty new remove file write as""".split())
# Words that shape a line, so no name may hold them. A name of two or more words may hold the other keywords.
STRUCTURE = set("""to and or is of in with as by from into plus minus times divided than not if otherwise set at between contains
toward exceeds falls each for""".split())


def bad_name(words):
    """True if these words can't be a name."""
    if len(words) == 1:
        return words[0] in KEYWORDS
    return any(w in STRUCTURE for w in words)


ITEM_NOT_INDEX = {None, ",", ")", "of", "is", "and", "or", "plus", "minus", "times", "divided", "by", "to",
                  "between", "+", "-", "*", "/", "contains", "in", "from", "with"}
UNITS = set("degrees degree cm centimetres seconds second per squared percent metres metre m s".split())
TOKEN = r'"[^"]*"|\d+(?:\.\d+)?|[A-Za-z][A-Za-z\']*|[():,+\-*/]'


OWNER_KINDS = {}  # the same, -> the kind of thing (machine code finds its parts with it)
OWNER_PARAMS = set()  # the C++ names of the things commands are for ('to bounce, for a ball:' gets 'ball')
# Commands for a kind of thing ('to bounce, for a ball:'): their C++ name -> the kind.
OWNERS = {}
PARENTS = {}  # kind of thing -> the kind it is a kind of ('a dog is a kind of pet')
ABLE = {}  # 'a speaker is anything that can speak': 'speaker' -> [('speak',)], the commands every one of them has
NAMES_NOW = [None]  # the Names of the script being read (fit() asks which kinds can do an ability's commands)

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


SIGNATURES = {}  # a command kind -> (input kinds, the kind it gives back or None)


def command_kind(inputs, gives):
    """The kind of a command that takes these inputs and gives this back: 'command(number;text)>number'."""
    kind = "command(" + ";".join(inputs) + ")>" + (gives or "")
    SIGNATURES[kind] = (list(inputs), gives)
    return kind


def is_command(kind):
    return kind.startswith("command(")


def holds_command(kind):
    """Is it a command, or a list or table with commands in it? (They can't be compared or saved.)"""
    if is_list(kind):
        return holds_command(element(kind))
    if is_table(kind):
        return holds_command(entry_kind(kind))
    return is_command(kind)


def command_words(kind, word="command"):
    ins, gives = SIGNATURES[kind]
    return word + (" given " + " and ".join(kind_name(k) for k in ins) if ins else "") + \
        (" returning " + kind_name(gives) if gives else "")


def cpp_type(kind):
    if is_command(kind):
        ins, gives = SIGNATURES[kind]
        return f"std::function<{cpp_type(gives) if gives else 'void'}({', '.join(cpp_type(k) for k in ins)})>"
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
    if JS:
        return js_zero(kind)
    return ZERO.get(kind) or f"{cpp_type(kind)}()"


def js_class(kind):
    """A kind of thing's JavaScript class: 'thing pet' -> Kind_Pet (a prefix, so it can't meet a browser's own names)."""
    return "Kind_" + "".join(w.capitalize() for w in kind[6:].split())


def js_zero(kind):
    if is_list(kind):
        return "[]"
    if is_table(kind):
        return "stellanova::table()"
    if is_thing(kind) and kind[6:] in ABLE:
        return "undefined"
    if is_thing(kind):
        return f"new {js_class(kind)}()"
    if is_command(kind):
        return "null"
    return {NUMBER: "0", YESNO: "false", TEXT: '""', PLACE: "FVector(0, 0, 0)", FLAT: "FVector2D(0, 0)"}[kind]


def is_deep(kind):
    """Values that hold other values: they are copied when stored (C++ copies them by itself)."""
    return kind in (PLACE, FLAT) or is_list(kind) or is_table(kind) or is_thing(kind)


def js_copy(cpp, kind):
    """In JavaScript a stored list, table, place or thing must be copied by hand, as C++ and Python do."""
    return f"stellanova::dup({strip_parens(cpp)})" if JS and is_deep(kind) else strip_parens(cpp)


def js_set(target):
    """The start of putting a value into target, in JavaScript: 'x = ', or a runtime call that the close bracket ends."""
    return getattr(target, "cpp_assign", None) or f"{strip_parens(target.cpp)} = "


def js_dots(code):
    """C++'s 'stellanova::text' is JavaScript's 'stellanova.text': turn every '::' outside text into '.'."""
    out, k, n = [], 0, len(code)
    while k < n:
        c = code[k]
        if c == '"':
            end = k + 1
            while end < n and code[end] != '"':
                end += 2 if code[end] == "\\" else 1
            out.append(code[k:end + 1])
            k = end + 1
        elif code.startswith("::", k):
            out.append(".")
            k += 2
        else:
            out.append(c)
            k += 1
    return "".join(out)


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
    if words[:1] in (["command"], ["commands"]):  # 'a command given a number and text returning yes or no'
        m = re.fullmatch(r"(?:given (.+?))?\s*(?:returning (.+))?", " ".join(words[1:]))
        if not m:
            return None
        ins = [parse_kind(part) for part in re.split(r"\s+and\s+", m.group(1))] if m.group(1) else []
        gives = parse_kind(m.group(2)) if m.group(2) else None
        if None in ins or (m.group(2) and not gives):
            return None
        return command_kind(ins, gives)
    first_plural = " ".join([words[0][:-1]] + words[1:]) if words and words[0].endswith("s") else None  # 'stacks of numbers'
    singular = [phrase[:-3] + "y"] if phrase.endswith("ies") else []  # 'bodies', 'boxes'
    singular += [phrase[:-2]] if phrase.endswith("es") else []
    for name in (phrase, phrase[:-1] if phrase.endswith("s") else None, *singular, first_plural):
        if name in THINGS:
            return "thing " + name
    return None


def kind_words():
    return ", ".join(["a number", "yes or no", "text", "a place", "a list of ...", "a table of ...",
                      "a command given ... returning ..."] + [f"a {t}" for t in THINGS])


def kind_name(kind):
    if is_command(kind):
        return "a " + command_words(kind)
    if is_list(kind):
        return "a list of " + plural(element(kind))
    if is_table(kind):
        return "a table of " + plural(entry_kind(kind))
    if is_thing(kind):
        return "a " + kind[6:]
    return {NUMBER: "a number", YESNO: "yes or no", PLACE: "a place", FLAT: "a flat place", TEXT: "text"}[kind]


def plural_word(name):
    """'pet' -> 'pets', 'body' -> 'bodies', 'box' -> 'boxes' (the last word of a name of several)"""
    if re.search(r"[^aeiou]y$", name):
        return name[:-1] + "ies"
    if re.search(r"(s|x|z|ch|sh)$", name):
        return name + "es"
    return name + "s"


def plural(kind):
    if is_command(kind):
        return command_words(kind, "commands")
    if is_list(kind):
        return "lists of " + plural(element(kind))
    if is_table(kind):
        return "tables of " + plural(entry_kind(kind))
    if is_thing(kind):
        return plural_word(kind[6:])
    return {NUMBER: "numbers", YESNO: "yes or no", PLACE: "places", FLAT: "flat places", TEXT: "text"}[kind]


# ---------------------------------------------------------------- what running a program uses

PART_NAMES = {}  # a kind's name -> (its parts as described, [(each part's inner name, kind)])


class Thing:
    """One of a script's own kinds of things, while a program runs."""
    __slots__ = ("name", "spec", "fields")

    def __init__(self, name, things):
        self.name, self.spec = name, things[name]
        if PLAIN_KINDS.get(name) is self.spec:  # (every part plain: the same new parts each time)
            self.fields = PLAIN_ZEROS[name].copy()
            return
        known = PART_NAMES.get(name)
        if known is None or known[0] is not self.spec:  # each part's inner name, worked out once for each kind
            known = PART_NAMES[name] = (self.spec, [(snake(w), k) for w, k in self.spec])
            if all(k in (NUMBER, YESNO, TEXT) for _, k in self.spec):
                PLAIN_KINDS[name] = self.spec
                PLAIN_ZEROS[name] = {part: py_zero(k, things) for part, k in known[1]}
        self.fields = {part: py_zero(k, things) for part, k in known[1]}

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
    if is_thing(kind) and kind[6:] in ABLE:
        return None
    if is_thing(kind):
        return Thing(kind[6:], things)
    if is_command(kind):
        return no_command
    return None


OTHERS = []  # commands running alongside the rest ('meanwhile ...'), as threads
OTHERS_LOCK = threading.Lock()
NAMED_LOCKS = {}  # 'holding the lock "total":' -> its lock (one command at a time holds each)


def named_lock(name):
    with OTHERS_LOCK:
        return NAMED_LOCKS.setdefault(name, threading.RLock())


def meanwhile(run, env):
    """Starts run going on its own, with a copy of every name as it is now (as the C++ copies them)."""
    snapshot = {k: dup(v) for k, v in env.items()}

    def go():
        try:
            run(snapshot)
        except RunError as err:
            sys.stdout.flush()
            print(f"{run_where(err.line)}: {err.message}", file=sys.stderr)
            sys.stderr.flush()
            os._exit(1)
        except Flow:
            pass
    worker = threading.Thread(target=go)
    with OTHERS_LOCK:
        OTHERS.append(worker)
    worker.start()


def wait_for_others():
    """Waits until every command started with 'meanwhile' (except the one waiting) has finished."""
    me = threading.current_thread()
    while True:
        with OTHERS_LOCK:
            other = next((t for t in OTHERS if t is not me), None)
            if other is None:
                return
            OTHERS.remove(other)
        other.join()


def no_command(*args):
    raise RunError(0, "there is no command in it yet: set it to one first, like 'set f to the command double'.")


def invoke_value(f, args, line):
    try:
        return f(*args)
    except RunError as err:
        if not err.line:
            err.line = line
        raise


PLAIN = (float, str, bool, type(None))  # never changed in place, so never copied


def dup_thing(v):
    new = Thing.__new__(Thing)
    new.name, new.spec = v.name, v.spec
    if PLAIN_KINDS.get(v.name) is v.spec:  # only numbers, yes/no and text: a plain copy is enough
        new.fields = v.fields.copy()
    else:
        new.fields = {k: x if type(x) in PLAIN else dup(x) for k, x in v.fields.items()}
    return new


_new_thing = Thing.__new__
PLAIN_KINDS = {}  # a kind's name -> its parts as described, when every part is a number, yes/no or text
PLAIN_ZEROS = {}  # such a kind's name -> a new one's parts


def dup(v):
    """Lists, tables, places and things are copied when they are stored, as they are in the C++.

    Made by hand rather than with copy.deepcopy: it is called on every 'set', so it must be quick."""
    t = type(v)
    if t is Thing:  # (most often: py_copy leaves out numbers, yes/no and text it knows about)
        new = _new_thing(Thing)
        new.name, new.spec = v.name, v.spec
        new.fields = v.fields.copy() if PLAIN_KINDS.get(v.name) is v.spec else             {k: x if type(x) in PLAIN else dup(x) for k, x in v.fields.items()}
        return new
    if t is float or t is str or t is bool:
        return v
    if t is Place:
        new = Place.__new__(Place)
        new.fields = v.fields.copy()
        return new
    if t is Thing:
        return dup_thing(v)
    if t is list:
        if not v or type(v[0]) not in DEEP:
            return v.copy()
        return [dup_thing(x) if type(x) is Thing else dup(x) for x in v]
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
    if v is None:
        return "nothing"
    if isinstance(v, Thing):
        return f"a {v.name} (" + ", ".join(f"{' '.join(w)}: {text(v.fields[snake(w)])}" for w, _ in v.spec) + ")"
    if callable(v):
        return "a command"
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


def insert_at(items, number, x, line):
    """'insert x at 3 in xs': any place from the first to just after the last"""
    if number == len(items) + 1:
        items.append(x)
    else:
        items.insert(index_of(items, number, line), x)


def power(a, b, line):
    """'2 to the power 10'"""
    try:
        out = math.pow(a, b)
    except (OverflowError, ValueError):
        out = None
    if out is None or math.isinf(out) or math.isnan(out):
        raise RunError(line, f"{text(a)} to the power {text(b)} can't be worked out (it is too big, or not a real number).")
    return out


BIT_LIMIT = 2 ** 53  # whole numbers this big (either way) are exact: bits work on them


def bits(op, a, b, line):
    """'12 bitwise and 10', 'bitwise or', 'bitwise exclusive or', '1 shifted left by 4', 'shifted right by'"""
    for x in (a, b):
        if x != math.floor(x) or abs(x) >= BIT_LIMIT:
            raise RunError(line, f"bits need whole numbers smaller than 9007199254740992, not {text(x)}.")
    a, b = int(a), int(b)
    if op in (3, 4) and not 0 <= b <= 63:
        raise RunError(line, f"I can shift by 0 to 63 places, not {b}.")
    out = (a & b, a | b, a ^ b, a << b if op == 3 else 0, a >> b if op == 4 else 0)[op]
    if abs(out) >= BIT_LIMIT:
        raise RunError(line, f"that makes a number too big for bits ({out}).")
    return float(out)


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
    if is_command(kind):
        raise RunError(line, "I can't save a command in a file.")
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
    if v is None:
        return "null"
    parts = [f'"{" ".join(w)}": {saved(v.fields[snake(w)], k, line)}' for w, k in v.spec]
    if kind[6:] in ABLE:  # a speaker: which kind of thing it is, so loading can make one again
        parts.insert(0, f'"is a": {json.dumps(v.name, ensure_ascii=False)}')
    return "{" + ", ".join(parts) + "}"


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
    if is_thing(kind) and d is None:
        return None
    if is_thing(kind) and kind[6:] in ABLE:
        if isinstance(d, dict) and isinstance(d.get("is a"), str) and d["is a"] in things and can("thing " + d["is a"], kind[6:]):
            return from_saved(d, "thing " + d["is a"], things)
        raise NotSaved()
    if is_thing(kind) and isinstance(d, dict):
        t = Thing(kind[6:], things)
        loose = {loose_key(key): x for key, x in d.items()}  # a web service's "windSpeed" or "wind_speed" is 'wind speed'
        for w, k in t.spec:
            x = d[" ".join(w)] if " ".join(w) in d else loose.get(loose_key(" ".join(w)))
            if x is not None:  # missing, or null: the part stays empty
                t.fields[snake(w)] = from_saved(x, k, things)
        return t
    raise NotSaved()


def loose_key(key):
    return re.sub(r"[ _-]", "", key).translate(ASCII_DOWN)


def something(thing, kind, part, line):
    """A thing whose part is wanted: an error if it is nothing."""
    if thing is None:
        raise RunError(line, f"this {kind[6:]} is nothing, so it has no {part}.")
    return thing


def no_nothing(items, line):
    if None in items:
        raise RunError(line, "a list sorted by a part can't hold nothing.")
    return items


def no_constant(name):
    raise NotSaved()


def load_text(data, kind, things, line):
    """'load scores from the text reply': JSON text (from 'as saved text', a file or the web) back into a value."""
    try:
        return from_saved(json.loads(data, parse_int=float, parse_constant=no_constant), kind, things)
    except (NotSaved, ValueError, RecursionError):
        raise RunError(line, f"the text doesn't hold {kind_name(kind)}.")


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
# small and capital letters in every alphabet, in pairs (the same list is in stellanova.h and stellanova.js)
CASE_PAIRS = "aAbBcCdDeEfFgGhHiIjJkKlLmMnNoOpPqQrRsStTuUvVwWxXyYzZàÀáÁâÂãÃäÄåÅæÆçÇèÈéÉêÊëËìÌíÍîÎïÏðÐñÑòÒóÓôÔõÕöÖøØùÙúÚûÛüÜýÝþÞÿŸāĀăĂąĄćĆĉĈċĊčČďĎđĐēĒĕĔėĖęĘěĚĝĜğĞġĠģĢĥĤħĦĩĨīĪĭĬįĮĳĲĵĴķĶĺĹļĻľĽŀĿłŁńŃņŅňŇŋŊōŌŏŎőŐœŒŕŔŗŖřŘśŚŝŜşŞšŠţŢťŤŧŦũŨūŪŭŬůŮűŰųŲŵŴŷŶźŹżŻžŽƀɃƃƂƅƄƈƇƌƋƒƑƕǶƙƘƚȽƞȠơƠƣƢƥƤƨƧƭƬưƯƴƳƶƵƹƸƽƼƿǷǆǄǉǇǌǊǎǍǐǏǒǑǔǓǖǕǘǗǚǙǜǛǝƎǟǞǡǠǣǢǥǤǧǦǩǨǫǪǭǬǯǮǳǱǵǴǹǸǻǺǽǼǿǾȁȀȃȂȅȄȇȆȉȈȋȊȍȌȏȎȑȐȓȒȕȔȗȖșȘțȚȝȜȟȞȣȢȥȤȧȦȩȨȫȪȭȬȯȮȱȰȳȲȼȻȿⱾɀⱿɂɁɇɆɉɈɋɊɍɌɏɎɐⱯɑⱭɒⱰɓƁɔƆɖƉɗƊəƏɛƐɜꞫɠƓɡꞬɣƔɥꞍɦꞪɨƗɩƖɪꞮɫⱢɬꞭɯƜɱⱮɲƝɵƟɽⱤʀƦʂꟅʃƩʇꞱʈƮʉɄʊƱʋƲʌɅʒƷʝꞲʞꞰͱͰͳͲͷͶͻϽͼϾͽϿάΆέΈήΉίΊαΑβΒγΓδΔεΕζΖηΗθΘιΙκΚλΛμΜνΝξΞοΟπΠρΡσΣτΤυΥφΦχΧψΨωΩϊΪϋΫόΌύΎώΏϗϏϙϘϛϚϝϜϟϞϡϠϣϢϥϤϧϦϩϨϫϪϭϬϯϮϲϹϳͿϸϷϻϺаАбБвВгГдДеЕжЖзЗиИйЙкКлЛмМнНоОпПрРсСтТуУфФхХцЦчЧшШщЩъЪыЫьЬэЭюЮяЯѐЀёЁђЂѓЃєЄѕЅіІїЇјЈљЉњЊћЋќЌѝЍўЎџЏѡѠѣѢѥѤѧѦѩѨѫѪѭѬѯѮѱѰѳѲѵѴѷѶѹѸѻѺѽѼѿѾҁҀҋҊҍҌҏҎґҐғҒҕҔҗҖҙҘқҚҝҜҟҞҡҠңҢҥҤҧҦҩҨҫҪҭҬүҮұҰҳҲҵҴҷҶҹҸһҺҽҼҿҾӂӁӄӃӆӅӈӇӊӉӌӋӎӍӏӀӑӐӓӒӕӔӗӖәӘӛӚӝӜӟӞӡӠӣӢӥӤӧӦөӨӫӪӭӬӯӮӱӰӳӲӵӴӷӶӹӸӻӺӽӼӿӾԁԀԃԂԅԄԇԆԉԈԋԊԍԌԏԎԑԐԓԒԕԔԗԖԙԘԛԚԝԜԟԞԡԠԣԢԥԤԧԦԩԨԫԪԭԬԯԮաԱբԲգԳդԴեԵզԶէԷըԸթԹժԺիԻլԼխԽծԾկԿհՀձՁղՂճՃմՄյՅնՆշՇոՈչՉպՊջՋռՌսՍվՎտՏրՐցՑւՒփՓքՔօՕֆՖაᲐბᲑგᲒდᲓეᲔვᲕზᲖთᲗიᲘკᲙლᲚმᲛნᲜოᲝპᲞჟᲟრᲠსᲡტᲢუᲣფᲤქᲥღᲦყᲧშᲨჩᲩცᲪძᲫწᲬჭᲭხᲮჯᲯჰᲰჱᲱჲᲲჳᲳჴᲴჵᲵჶᲶჷᲷჸᲸჹᲹჺᲺჽᲽჾᲾჿᲿᏸᏰᏹᏱᏺᏲᏻᏳᏼᏴᏽᏵᵹꝽᵽⱣᶎꟆḁḀḃḂḅḄḇḆḉḈḋḊḍḌḏḎḑḐḓḒḕḔḗḖḙḘḛḚḝḜḟḞḡḠḣḢḥḤḧḦḩḨḫḪḭḬḯḮḱḰḳḲḵḴḷḶḹḸḻḺḽḼḿḾṁṀṃṂṅṄṇṆṉṈṋṊṍṌṏṎṑṐṓṒṕṔṗṖṙṘṛṚṝṜṟṞṡṠṣṢṥṤṧṦṩṨṫṪṭṬṯṮṱṰṳṲṵṴṷṶṹṸṻṺṽṼṿṾẁẀẃẂẅẄẇẆẉẈẋẊẍẌẏẎẑẐẓẒẕẔạẠảẢấẤầẦẩẨẫẪậẬắẮằẰẳẲẵẴặẶẹẸẻẺẽẼếẾềỀểỂễỄệỆỉỈịỊọỌỏỎốỐồỒổỔỗỖộỘớỚờỜởỞỡỠợỢụỤủỦứỨừỪửỬữỮựỰỳỲỵỴỷỶỹỸỻỺỽỼỿỾἀἈἁἉἂἊἃἋἄἌἅἍἆἎἇἏἐἘἑἙἒἚἓἛἔἜἕἝἠἨἡἩἢἪἣἫἤἬἥἭἦἮἧἯἰἸἱἹἲἺἳἻἴἼἵἽἶἾἷἿὀὈὁὉὂὊὃὋὄὌὅὍὑὙὓὛὕὝὗὟὠὨὡὩὢὪὣὫὤὬὥὭὦὮὧὯὰᾺάΆὲῈέΈὴῊήΉὶῚίΊὸῸόΌὺῪύΎὼῺώΏᾰᾸᾱᾹῐῘῑῙῠῨῡῩῥῬⅎℲⅰⅠⅱⅡⅲⅢⅳⅣⅴⅤⅵⅥⅶⅦⅷⅧⅸⅨⅹⅩⅺⅪⅻⅫⅼⅬⅽⅭⅾⅮⅿⅯↄↃⓐⒶⓑⒷⓒⒸⓓⒹⓔⒺⓕⒻⓖⒼⓗⒽⓘⒾⓙⒿⓚⓀⓛⓁⓜⓂⓝⓃⓞⓄⓟⓅⓠⓆⓡⓇⓢⓈⓣⓉⓤⓊⓥⓋⓦⓌⓧⓍⓨⓎⓩⓏⰰⰀⰱⰁⰲⰂⰳⰃⰴⰄⰵⰅⰶⰆⰷⰇⰸⰈⰹⰉⰺⰊⰻⰋⰼⰌⰽⰍⰾⰎⰿⰏⱀⰐⱁⰑⱂⰒⱃⰓⱄⰔⱅⰕⱆⰖⱇⰗⱈⰘⱉⰙⱊⰚⱋⰛⱌⰜⱍⰝⱎⰞⱏⰟⱐⰠⱑⰡⱒⰢⱓⰣⱔⰤⱕⰥⱖⰦⱗⰧⱘⰨⱙⰩⱚⰪⱛⰫⱜⰬⱝⰭⱞⰮⱟⰯⱡⱠⱥȺⱦȾⱨⱧⱪⱩⱬⱫⱳⱲⱶⱵⲁⲀⲃⲂⲅⲄⲇⲆⲉⲈⲋⲊⲍⲌⲏⲎⲑⲐⲓⲒⲕⲔⲗⲖⲙⲘⲛⲚⲝⲜⲟⲞⲡⲠⲣⲢⲥⲤⲧⲦⲩⲨⲫⲪⲭⲬⲯⲮⲱⲰⲳⲲⲵⲴⲷⲶⲹⲸⲻⲺⲽⲼⲿⲾⳁⳀⳃⳂⳅⳄⳇⳆⳉⳈⳋⳊⳍⳌⳏⳎⳑⳐⳓⳒⳕⳔⳗⳖⳙⳘⳛⳚⳝⳜⳟⳞⳡⳠⳣⳢⳬⳫⳮⳭⳳⳲⴀႠⴁႡⴂႢⴃႣⴄႤⴅႥⴆႦⴇႧⴈႨⴉႩⴊႪⴋႫⴌႬⴍႭⴎႮⴏႯⴐႰⴑႱⴒႲⴓႳⴔႴⴕႵⴖႶⴗႷⴘႸⴙႹⴚႺⴛႻⴜႼⴝႽⴞႾⴟႿⴠჀⴡჁⴢჂⴣჃⴤჄⴥჅⴧჇⴭჍꙁꙀꙃꙂꙅꙄꙇꙆꙉꙈꙋꙊꙍꙌꙏꙎꙑꙐꙓꙒꙕꙔꙗꙖꙙꙘꙛꙚꙝꙜꙟꙞꙡꙠꙣꙢꙥꙤꙧꙦꙩꙨꙫꙪꙭꙬꚁꚀꚃꚂꚅꚄꚇꚆꚉꚈꚋꚊꚍꚌꚏꚎꚑꚐꚓꚒꚕꚔꚗꚖꚙꚘꚛꚚꜣꜢꜥꜤꜧꜦꜩꜨꜫꜪꜭꜬꜯꜮꜳꜲꜵꜴꜷꜶꜹꜸꜻꜺꜽꜼꜿꜾꝁꝀꝃꝂꝅꝄꝇꝆꝉꝈꝋꝊꝍꝌꝏꝎꝑꝐꝓꝒꝕꝔꝗꝖꝙꝘꝛꝚꝝꝜꝟꝞꝡꝠꝣꝢꝥꝤꝧꝦꝩꝨꝫꝪꝭꝬꝯꝮꝺꝹꝼꝻꝿꝾꞁꞀꞃꞂꞅꞄꞇꞆꞌꞋꞑꞐꞓꞒꞔꟄꞗꞖꞙꞘꞛꞚꞝꞜꞟꞞꞡꞠꞣꞢꞥꞤꞧꞦꞩꞨꞵꞴꞷꞶꞹꞸꞻꞺꞽꞼꞿꞾꟁꟀꟃꟂꟈꟇꟊꟉꟑꟐꟗꟖꟙꟘꟶꟵꭓꞳꭰᎠꭱᎡꭲᎢꭳᎣꭴᎤꭵᎥꭶᎦꭷᎧꭸᎨꭹᎩꭺᎪꭻᎫꭼᎬꭽᎭꭾᎮꭿᎯꮀᎰꮁᎱꮂᎲꮃᎳꮄᎴꮅᎵꮆᎶꮇᎷꮈᎸꮉᎹꮊᎺꮋᎻꮌᎼꮍᎽꮎᎾꮏᎿꮐᏀꮑᏁꮒᏂꮓᏃꮔᏄꮕᏅꮖᏆꮗᏇꮘᏈꮙᏉꮚᏊꮛᏋꮜᏌꮝᏍꮞᏎꮟᏏꮠᏐꮡᏑꮢᏒꮣᏓꮤᏔꮥᏕꮦᏖꮧᏗꮨᏘꮩᏙꮪᏚꮫᏛꮬᏜꮭᏝꮮᏞꮯᏟꮰᏠꮱᏡꮲᏢꮳᏣꮴᏤꮵᏥꮶᏦꮷᏧꮸᏨꮹᏩꮺᏪꮻᏫꮼᏬꮽᏭꮾᏮꮿᏯａＡｂＢｃＣｄＤｅＥｆＦｇＧｈＨｉＩｊＪｋＫｌＬｍＭｎＮｏＯｐＰｑＱｒＲｓＳｔＴｕＵｖＶｗＷｘＸｙＹｚＺ𐐨𐐀𐐩𐐁𐐪𐐂𐐫𐐃𐐬𐐄𐐭𐐅𐐮𐐆𐐯𐐇𐐰𐐈𐐱𐐉𐐲𐐊𐐳𐐋𐐴𐐌𐐵𐐍𐐶𐐎𐐷𐐏𐐸𐐐𐐹𐐑𐐺𐐒𐐻𐐓𐐼𐐔𐐽𐐕𐐾𐐖𐐿𐐗𐑀𐐘𐑁𐐙𐑂𐐚𐑃𐐛𐑄𐐜𐑅𐐝𐑆𐐞𐑇𐐟𐑈𐐠𐑉𐐡𐑊𐐢𐑋𐐣𐑌𐐤𐑍𐐥𐑎𐐦𐑏𐐧𐓘𐒰𐓙𐒱𐓚𐒲𐓛𐒳𐓜𐒴𐓝𐒵𐓞𐒶𐓟𐒷𐓠𐒸𐓡𐒹𐓢𐒺𐓣𐒻𐓤𐒼𐓥𐒽𐓦𐒾𐓧𐒿𐓨𐓀𐓩𐓁𐓪𐓂𐓫𐓃𐓬𐓄𐓭𐓅𐓮𐓆𐓯𐓇𐓰𐓈𐓱𐓉𐓲𐓊𐓳𐓋𐓴𐓌𐓵𐓍𐓶𐓎𐓷𐓏𐓸𐓐𐓹𐓑𐓺𐓒𐓻𐓓𐖗𐕰𐖘𐕱𐖙𐕲𐖚𐕳𐖛𐕴𐖜𐕵𐖝𐕶𐖞𐕷𐖟𐕸𐖠𐕹𐖡𐕺𐖣𐕼𐖤𐕽𐖥𐕾𐖦𐕿𐖧𐖀𐖨𐖁𐖩𐖂𐖪𐖃𐖫𐖄𐖬𐖅𐖭𐖆𐖮𐖇𐖯𐖈𐖰𐖉𐖱𐖊𐖳𐖌𐖴𐖍𐖵𐖎𐖶𐖏𐖷𐖐𐖸𐖑𐖹𐖒𐖻𐖔𐖼𐖕𐳀𐲀𐳁𐲁𐳂𐲂𐳃𐲃𐳄𐲄𐳅𐲅𐳆𐲆𐳇𐲇𐳈𐲈𐳉𐲉𐳊𐲊𐳋𐲋𐳌𐲌𐳍𐲍𐳎𐲎𐳏𐲏𐳐𐲐𐳑𐲑𐳒𐲒𐳓𐲓𐳔𐲔𐳕𐲕𐳖𐲖𐳗𐲗𐳘𐲘𐳙𐲙𐳚𐲚𐳛𐲛𐳜𐲜𐳝𐲝𐳞𐲞𐳟𐲟𐳠𐲠𐳡𐲡𐳢𐲢𐳣𐲣𐳤𐲤𐳥𐲥𐳦𐲦𐳧𐲧𐳨𐲨𐳩𐲩𐳪𐲪𐳫𐲫𐳬𐲬𐳭𐲭𐳮𐲮𐳯𐲯𐳰𐲰𐳱𐲱𐳲𐲲𑣀𑢠𑣁𑢡𑣂𑢢𑣃𑢣𑣄𑢤𑣅𑢥𑣆𑢦𑣇𑢧𑣈𑢨𑣉𑢩𑣊𑢪𑣋𑢫𑣌𑢬𑣍𑢭𑣎𑢮𑣏𑢯𑣐𑢰𑣑𑢱𑣒𑢲𑣓𑢳𑣔𑢴𑣕𑢵𑣖𑢶𑣗𑢷𑣘𑢸𑣙𑢹𑣚𑢺𑣛𑢻𑣜𑢼𑣝𑢽𑣞𑢾𑣟𑢿𖹠𖹀𖹡𖹁𖹢𖹂𖹣𖹃𖹤𖹄𖹥𖹅𖹦𖹆𖹧𖹇𖹨𖹈𖹩𖹉𖹪𖹊𖹫𖹋𖹬𖹌𖹭𖹍𖹮𖹎𖹯𖹏𖹰𖹐𖹱𖹑𖹲𖹒𖹳𖹓𖹴𖹔𖹵𖹕𖹶𖹖𖹷𖹗𖹸𖹘𖹹𖹙𖹺𖹚𖹻𖹛𖹼𖹜𖹽𖹝𖹾𖹞𖹿𖹟𞤢𞤀𞤣𞤁𞤤𞤂𞤥𞤃𞤦𞤄𞤧𞤅𞤨𞤆𞤩𞤇𞤪𞤈𞤫𞤉𞤬𞤊𞤭𞤋𞤮𞤌𞤯𞤍𞤰𞤎𞤱𞤏𞤲𞤐𞤳𞤑𞤴𞤒𞤵𞤓𞤶𞤔𞤷𞤕𞤸𞤖𞤹𞤗𞤺𞤘𞤻𞤙𞤼𞤚𞤽𞤛𞤾𞤜𞤿𞤝𞥀𞤞𞥁𞤟𞥂𞤠𞥃𞤡"
CASE_UP = str.maketrans(CASE_PAIRS[0::2], CASE_PAIRS[1::2])
CASE_DOWN = str.maketrans(CASE_PAIRS[1::2], CASE_PAIRS[0::2])


def letter(s, number, line):
    if math.floor(number) != number or number < 1 or number > len(s):
        raise RunError(line, f"there is no letter {text(number)} in text of {len(s)} letters.")
    return s[int(number) - 1]


def letters_from(s, first, last, line):
    if math.floor(first) != first or math.floor(last) != last or first < 1 or last > len(s) or first > last + 1:
        raise RunError(line, f"there are no letters {text(first)} to {text(last)} in text of {len(s)} letters.")
    return s[int(first) - 1:int(last)]


def items_from(items, first, last, line):
    if math.floor(first) != first or math.floor(last) != last or first < 1 or last > len(items) or first > last + 1:
        raise RunError(line, f"there are no items {text(first)} to {text(last)} in a list of {len(items)} items.")
    return [dup(x) for x in items[int(first) - 1:int(last)]]


def first_of(items, count, line, end=False):
    """The first (or last) count items of a list or letters of text: all of them when there are fewer."""
    if math.floor(count) != count or count < 0:
        raise RunError(line, f"I can't take {text(count)} of something: it must be a whole number, 0 or more.")
    n = int(count)
    part = (items[len(items) - n:] if n else items[:0]) if end else items[:n]
    return part if isinstance(items, str) else [dup(x) for x in part]


def unique(items):
    out = []
    for x in items:
        if x not in out:
            out.append(dup(x))
    return out


def shuffled(items):
    out = [dup(x) for x in items]
    pyrandom.shuffle(out)
    return out


def with_commas(n):
    s = text(n)
    sign, s = ("-", s[1:]) if s.startswith("-") else ("", s)
    whole, dot, rest = s.partition(".")
    if not whole.isdigit():
        return sign + s
    return sign + f"{int(whole):,}" + dot + rest


def padded(n, digits, line):
    if isinstance(n, str):  # '"food" padded to 12 letters': spaces after it
        if math.floor(digits) != digits or digits < 0:
            raise RunError(line, f"I can't pad to {text(digits)} letters: it must be a whole number, 0 or more.")
        return n.ljust(int(digits))
    if math.floor(digits) != digits or digits < 0:
        raise RunError(line, f"I can't pad to {text(digits)} digits: it must be a whole number, 0 or more.")
    s = text(n)
    sign, s = ("-", s[1:]) if s.startswith("-") else ("", s)
    whole, dot, rest = s.partition(".")
    return sign + whole.rjust(int(digits), "0") + dot + rest


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
    step.inner = then  # so a missing piece is named by what it really is
    step.loop_body = True
    return with_ir(step, getattr(then, "ir", None))  # machine.loop makes 'break free' and 'move on' jumps


# ---------------------------------------------------------------- direct runs as Python
# Each command run directly becomes one Python function, written out as Python text: its lines and sums inline, with
# real returns. A piece with no Python text of its own (pyf for a value, pyl for a line) is called as its run(env).
PY_PARTS = []  # what the written Python calls: runs without Python text of their own, and commands
FAST = not os.environ.get("STELLANOVA_NO_FAST")  # set it to run directly the old way (each piece a Python call)


def py_part(x):
    PY_PARTS.append(x)
    return f"_F[{len(PY_PARTS) - 1}]"


def py_expr(v):
    """A value's Python text (env holds the names)."""
    for x in (v, getattr(v, "run", None)):
        make = getattr(x, "pyf", None)
        if make:
            return make()
    return f"{py_part(v.run if isinstance(v, Value) else v)}(env)"


def py_lines(run, tab):
    """A line's Python: (its line number, or None for the line around it, and the text) for each Python line."""
    x, out = run, None
    while out is None:
        if getattr(x, "pyl", None):
            out = x.pyl(tab)
        elif getattr(x, "pyf", None):
            out = [(None, tab + x.pyf())]
        elif getattr(x, "inner", None) is not None and not getattr(x, "loop_body", False):
            x = x.inner
        else:
            out = [(None, f"{tab}{py_part(run)}(env)")]
    n = getattr(run, "line_n", None)
    return [(m if m is not None else n, t) for m, t in out]


def py_loop(head, then, tab):
    """A loop's lines: 'stop the loop' and 'skip to the next one' inside a run of the old way still work."""
    inner = py_lines(then.inner, tab + "        ")
    if not any("_F[" in t for _, t in inner):
        return [(None, tab + head)] + [(m, t[4:]) for m, t in inner]
    return [(None, tab + head), (None, tab + "    try:")] + inner + [
        (None, tab + "    except _Leave:"), (None, tab + "        break"), (None, tab + "    except _Next:"), (None, tab + "        pass")]


def py_copy(x, kind):  # Python text keeping x: lists, places and things are copied (not ones just made)
    return x if kind in (NUMBER, YESNO, TEXT) or x == "[]" or x.startswith(PY_FRESH) else f"_dup({x})"


PY_FRESH = ("_Thing(", "_sorted_by(")  # Python text that always makes a new value


def py_sorted_by(items, member, line):  # 'sorted pets by age' (a new list of copies)
    return [dup(x) for x in sorted(no_nothing(items, line), key=lambda t: t.fields[member])]


def py_item(items, number, line):
    k = int(number) if number >= 1 else 0
    if k == number and k <= len(items):
        return items[k - 1]
    return items[index_of(items, number, line)]


def py_put_item(items, number, line, x):
    k = int(number) if number >= 1 else 0
    if k == number and k <= len(items):
        items[k - 1] = x
    else:
        items[index_of(items, number, line)] = x


def py_empty_list(env):
    return []


py_empty_list.pyf = lambda: "[]"


def py_count(x, last, by=1.0):  # 'for each n from 1 to 10 by 2'
    if by == 1 and float(x).is_integer() and math.isfinite(last):  # (counting whole numbers: range is quicker)
        return map(float, range(int(x), math.floor(last) + 1))
    return py_counting(x, last, by)


def py_counting(x, last, by):
    while (by > 0 and x <= last) or (by < 0 and x >= last):
        yield x
        x += by


def py_each(items, simple):  # 'for each x in xs': a copy, so changing xs inside doesn't change the rounds
    return list(items) if simple else dup(items)


def py_reps(c):
    return range(int(c) if math.isfinite(c) else 0)


def py_fix(err, lines):
    """A surprise inside written Python, as the old way says it (with the line it happened on)."""
    tb = err.__traceback__
    n = lines[tb.tb_lineno - 1] if tb and 0 < tb.tb_lineno <= len(lines) else 0
    if isinstance(err, RunError):
        if not err.line:
            err.line = n
        return err
    if isinstance(err, RecursionError):
        return RunError(n, "commands called each other too many times in a row (they may never stop).")
    return RunError(n, f"Stellanova itself went wrong here; this is not a mistake in your program. Please tell whoever looks after Stellanova: {err}")


PY_ZERO = {NUMBER: "0.0", YESNO: "False", TEXT: "''"}
PY_NAME = re.compile(r"env\['(\w+)'\]")


def py_command(name, params, zeros, gives_zero, run):
    """The Python function for a command (or None when it can't be written)."""
    body = py_lines(run, "        ")
    start = [f"{c!r}: {PY_ZERO.get(k) or f'_Z[{j}]()'}" for j, (c, k) in enumerate(zeros)] + [f"{c!r}: _a{j}" for j, c in enumerate(params)]
    head = [(0, f"def command({', '.join(f'_a{j}' for j in range(len(params)))}):"), (0, f"    env = {{{', '.join(start)}}}")]
    plain = [(m, PY_NAME.sub(r"v_\1", t)) for m, t in body]
    if not any(re.search(r"\benv\b", t) for _, t in plain):  # nothing needs env itself: each name is a Python name
        body = plain
        head = head[:1] + [(0, f"    v_{c} = {PY_ZERO.get(k) or f'_Z[{j}]()'}") for j, (c, k) in enumerate(zeros)] + \
            [(0, f"    v_{c} = _a{j}") for j, c in enumerate(params)]
    src = head + [(0, "    try:")] + body + [
        (0, "    except _Stop:"), (0, "        return None"), (0, "    except _Give as g:"), (0, "        return g.value"),
        (0, "    except (_Flow, SystemExit, KeyboardInterrupt):"), (0, "        raise"),
        (0, "    except BaseException as err:"), (0, "        raise _fix(err, _L) from None"),
        (0, "    return _zero()")]
    lines = [m or 0 for m, _ in src]
    space = {"_F": PY_PARTS, "_Z": [(lambda k=k: py_zero(k, THINGS)) for _, k in zeros], "_P": params, "_zero": gives_zero,
             "_count": py_count, "_each": py_each, "_item": py_item, "_put_item": py_put_item, "_something": something,
             "_Place": Place, "_Thing": Thing, "_THINGS": THINGS, "_Stop": Stop, "_Give": GiveBack, "_Flow": Flow,
             "_Leave": LeaveLoop, "_Next": NextRound, "_fix": py_fix, "_L": lines, "_dup": dup, "_divide": divide,
             "_reps": py_reps, "_sorted_by": py_sorted_by, "_text": text}
    try:
        exec(compile("\n".join(t for _, t in src), f"<{name}>", "exec"), space)
    except SyntaxError:  # (a mistake here: the old way still works)
        return None
    return space["command"]


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


# Grammar is for people: 'the', 'a' and 'an' are checked where English needs them, then left out before the
# line is read, so 'if the size of kept notifications falls below 60' is read as 'if size of kept notifications ...'.
ARTICLES = ("the", "a", "an")
KEPT_PHRASES = [  # inner words that hold an article of their own
    ("stop", "the", "loop"), ("skip", "to", "the", "next"), ("wait", "for", "the", "others"), ("from", "the", "text"),
    ("touches", "a", "side"), ("touches", "the", "top"), ("of", "the", "world"), ("the", "command"), ("as", "a", "number"),
]
NOT_A_NAME_AFTER = {None, "to", "is", "of", "in", "and", "or", "plus", "minus", "times", "divided", "exceeds", "falls"}


def read_words(text, line, names):
    """A line's words, with its grammar checked and then left out (see ARTICLES)."""
    return drop_articles(tokenize(text, line), names, line)


def kept_span(tokens, i, names):
    """How many words from tokens[i] belong to a phrase, name or command that holds an article itself (0 if none)."""
    for phrase in KEPT_PHRASES:
        if tuple(tokens[i:i + len(phrase)]) == phrase:
            return len(phrase)
    best = 0
    for key in list(names.known) + library_phrases():
        if len(key) > best and tuple(tokens[i:i + len(key)]) == key and any(w in ARTICLES for w in key):
            best = len(key)
    for key in names.commands:  # a command's own name is kept whole: 'total age of shelter' is the command 'total age of'
        said = tuple(spoken(key).split())
        if len(said) > best and tuple(tokens[i:i + len(said)]) == said:
            best = len(said)
    return best


LIBRARY_PHRASES = []


def library_phrases():
    """Every library word that holds an article ('open a world'), so it is kept even before its library is used."""
    if not LIBRARY_PHRASES:
        for path in sorted((HERE / "libraries").glob("**/*.words")):
            for row in path.read_text(encoding="utf-8").splitlines():
                m = re.match(r"(?:to )?([a-z][a-z ]*?)\s*(?:,|=)", row)
                if m and any(w in ARTICLES for w in m.group(1).split()):
                    LIBRARY_PHRASES.append(tuple(m.group(1).split()))
        LIBRARY_PHRASES.append(("the", "problem"))  # so the list is never empty again
    return LIBRARY_PHRASES


def needs_the(tokens, i, names):
    """The part of something that must have 'the' before it here ('the size of x', 'the name of rex'), or None."""
    if tokens[i:i + 2] == ["size", "of"] and not names.match(tokens, i)[0] and not match_command(names, tokens[i:])[0]:
        return "size of"
    for n in range(min(6, len(tokens) - i - 1), 0, -1):
        key = tuple(tokens[i:i + n])
        if key in FIELDS and tokens[i + n] == "of" and key not in names.known:
            return " ".join(key) + " of"
    return None


def drop_articles(tokens, names, line):
    out, i = [], 0
    while i < len(tokens):
        span = kept_span(tokens, i, names)
        if span and tokens[i] in ARTICLES and (needs_the(tokens, i + 1, names) or any(
                tuple(tokens[i + 1:i + 1 + n]) in FIELDS and tokens[i + 1 + n:i + 2 + n] == ["of"] for n in range(1, 7))):
            span = 0  # 'the element of win' is the part 'element', not the library word 'the element ...'
        if span:  # the longest known words win, as before: 'the page' is the library word even if 'page' is a name
            out += tokens[i:i + span]
            i += span
            continue
        t = tokens[i]
        if t in ARTICLES:
            after = tokens[i + 1] if i + 1 < len(tokens) else None
            if t != "the" and (after in NOT_A_NAME_AFTER or not after[0].isalpha()):
                raise ScriptError(line, f"'{t}' is grammar, which the computer skips, so it can't be a name. Pick another name.")
            if after and after[0].isalpha():
                if t == "a" and after[0] in "aei":
                    raise ScriptError(line, f"Write 'an {after}', not 'a {after}'.")
                if t == "an" and after[0] not in "aeiouh":
                    raise ScriptError(line, f"Write 'a {after}', not 'an {after}'.")
            i += 1
            continue
        part = needs_the(tokens, i, names)
        if part and (i == 0 or tokens[i - 1] != "the"):
            raise ScriptError(line, f"Write 'the {part}', not '{part}': grammar is needed here for people reading it "
                                    f"(the computer skips it).")
        size = len(part.split()) - 1 if part else 1  # the whole part's name ('before x'), so 'x of' inside it isn't checked again
        out += tokens[i:i + size]
        i += size
    return out


# The language's words, and the words they replaced. A script line's words are turned into the
# older inner words before it is read; the older words themselves are not allowed in scripts.
OLD_WORDS = [  # (old words, how to say it now) - checked anywhere in a line, outside quote marks
    (r"\bis more than\b", "exceeds"), (r"\bis less than\b", "falls below"),
    (r"\bthe problem\b", "the wound"), (r"\ban? new\b", "conjure a"),
    (r"\bopen a window\b", "open a world"), (r"\bthe window is open\b", "the world lives"),
    (r"\bclose the window\b", "end the world"), (r"\bshow the frame\b", "reveal the frame"),
    (r"\bquote mark\b", "a quotation mark"), (r"\brounded to [^ ]+ places\b", "rounded to ... decimal places"),
    (r"\bgiving back\b", "returning"), (r"\bthere is an? folder\b", "folder ... exists"),
]
OLD_STARTS = [  # (old first words, how to say it now) - checked at the start of a line
    (r"while\b", "as long as"), (r"echo\b", "repeat"), (r"stop the loop$", "break free"),
    (r"skip to the next( one)?$", "move on"), (r"stop$", "cease"), (r"gather\b", "add ... to"),
    (r"banish\b", "remove ... from"), (r"write\b", "inscribe ... into"), (r"give back\b", "return"),
    (r"shatter\b", "raise an error with"),
]
NEW_WORDS = [  # (new words, the inner words they become) - anywhere outside quote marks
    (r"\bexceeds\b", "is more than"), (r"\bfalls below\b", "is less than"), (r"\bthe wound\b", "the problem"),
    (r"\bconjure (an?)\s+", "a new "), (r"\bwhether\s+", ""), (r"\ba quotation mark\b", "quote mark"),
    (r"\bthe item at\b(.+?)\bin\b", r"item\1of"), (r"\brounded to\b(.+?)\bdecimal places?\b", r"rounded to\1places"),
]
NEW_STARTS = [  # at the start of a line
    (r"as long as\b", "while"), (r"break free$", "stop the loop"),
    (r"move on$", "skip to the next one"), (r"cease$", "stop"), (r"return\b", "give back"),
    (r"raise an error\b", "shatter"), (r"an? new (.+?) as (.+)$", r"set \2 to a new \1"),
    (r"stop (.+?) from spreading$", r"stop spreading \1"),
]


def outside_quotes(text, change):
    """Applies change to the parts of text that are not between quote marks."""
    parts = re.split(r'("[^"]*")', text)
    return "".join(part if k % 2 else change(part, k == 0) for k, part in enumerate(parts))


FILLED = re.compile(r"\[([A-Za-z][A-Za-z0-9' ]*)\]")  # words in square brackets inside text: '[name]', '[count plus 1]'


def fill_in(text):
    """'"Hello, [name]!"' becomes '("Hello, " plus (name) plus "!")': what the words in brackets hold, put into the text.
    Brackets holding anything but words (like a pattern's [0-9]) are left as they are; doubled ones ('[[like this]]')
    are shown as single brackets."""
    def one(m):
        pieces = FILLED.split(m.group(0)[1:-1].replace("[[", "\x01").replace("]]", "\x02"))
        shown = [p.replace("\x01", "[").replace("\x02", "]") for p in pieces]
        if len(pieces) == 1:
            return '"' + shown[0] + '"'
        out = ['"' + shown[0] + '"']
        for k in range(1, len(pieces), 2):
            out.append(f"({pieces[k].strip()})")
            if pieces[k + 1]:
                out.append('"' + shown[k + 1] + '"')
        return "(" + " plus ".join(out) + ")"
    return re.sub(r'"[^"]*"', one, text)


def surface(text, line, filled=False):
    """A script line in the language's words, turned into the inner words (old words are a mistake).

    'if done: cease' is two parts; each is turned on its own."""
    if not filled:
        text = fill_in(text)
    head, colon, rest = split_colon(text)
    out = surface_part(head, line)
    if colon:
        out += ":" + (" " + surface(rest.strip(), line, True) if rest.strip() else "")
    return out


assert fill_in('scrawl "Hi [name], [n plus 1]!" and "[0-9] [[NaN]]"') == \
    'scrawl ("Hi " plus (name) plus ", " plus (n plus 1) plus "!") and "[0-9] [NaN]"'


def surface_part(text, line):
    def check(part, first):
        low = part.lower()
        for old, now in OLD_WORDS:
            m = re.search(old, low)
            if m:
                raise ScriptError(line, f"'{m.group(0)}' is now '{now}'.")
        m = re.search(r"\bconjure\s+(?!an?\b)(\S+)", low)
        if m:
            raise ScriptError(line, f"Write 'conjure a {m.group(1)}' (or 'an'): grammar is needed here for people reading it (the computer skips it).")
        m = re.search(r"\bconjure\s+(an?)\s+([a-z])", low)
        if m and (m.group(1) == "a") == (m.group(2) in "aei"):  # 'conjure an notice' is read before the other a/an checks
            word = re.search(r"\bconjure\s+an?\s+(\w+)", low).group(1)
            if not (m.group(1) == "an" and m.group(2) in "ouh"):
                raise ScriptError(line, f"Write '{'an' if m.group(1) == 'a' else 'a'} {word}', not '{m.group(1)} {word}'.")
        if re.search(r"(?<!\ba )(?<!\ban )\blist containing\b", low):
            raise ScriptError(line, "Write 'a list containing ...': grammar is needed here for people reading it (the computer skips it).")
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
            m = re.match(r"inscribe\b", body, re.IGNORECASE)
            if m:  # inscribe x into file -> write x to file
                body = "write" + body[m.end():]
                k = body.lower().rfind(" into ")
                if k < 0:
                    raise ScriptError(line, "'inscribe' looks like 'inscribe \"hello\" into file \"notes.txt\"'.")
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

    ir = None  # ir(f): writes this value's machine code into f and returns where it is (see machine.py)
    ir_store = None  # ir_store(f, x): puts x into it, for names

    def __init__(self, cpp, kind, run, store=None):
        self.cpp, self.kind, self.run, self.store = cpp, kind, run, store

    @property
    def writable(self):
        return self.store is not None

    @property
    def pyf(self):  # its Python text, for direct runs (kept on run, which is what sums of values hold)
        return getattr(self.run, "pyf", None)

    @pyf.setter
    def pyf(self, make):
        self.run.pyf = make


def reversed_list(v):
    """A copy of the list v, back to front (any kind of item)."""
    a = v.run
    out = builtin("stellanova::reversed({a0})", v.kind, lambda env: [dup(x) for x in reversed(a(env))], [v])
    return with_ir(out, lambda f: f.op(f"call ptr @cn_reversed(ptr {machine.emit(f, v)})"))


def with_ir(x, write):
    """x (a Value or a statement's run), able to write its own machine code with write(f)."""
    x.ir = write
    return x


HOLES = re.compile(r"\{([as])(\d+)\}|\{line\}")


def builtin(template, kind, run, args, line=0):
    """A value made by one of Stellanova's own C++ functions. template is its C++ with {a0}/{s0} for each input's C++
    (s: without outer brackets) and {line}; the machine code calls the same function, from the prebuilt library."""
    def fill(m):
        if not m.group(1):
            return str(line)
        a = args[int(m.group(2))].cpp
        return strip_parens(a) if m.group(1) == "s" else a
    v = Value(HOLES.sub(fill, template), kind, run)  # all at once, so an input's own C++ is never filled again
    return with_ir(v, lambda f: machine.wrap(f, "builtins", "", template, args, kind, cpp_type, line))


NUMBER_OPS = {"+": "fadd", "-": "fsub", "*": "fmul", "/": "fdiv"}
COMPARE_OPS = {">": "ogt", "<": "olt", ">=": "oge", "<=": "ole", "!=": "une", "==": "oeq"}


def compare_ir(f, op, left, right):
    a, b = machine.emit(f, left), machine.emit(f, right)
    if machine.ll_type(left.kind) == "ptr" and left.kind != TEXT and op in ("==", "!="):  # lists, places, things...
        same = f.op(f"call i1 @cn_equal(ptr {a}, ptr {b})")
        return same if op == "==" else f.op(f"xor i1 {same}, true")
    if left.kind == NUMBER:
        return f.op(f"fcmp {COMPARE_OPS[op]} double {a}, {b}")
    if left.kind == YESNO and op in ("==", "!="):
        return f.op(f"icmp {'eq' if op == '==' else 'ne'} i1 {a}, {b}")
    if left.kind == TEXT and op in ("==", "!="):
        same = f.op(f"call i1 @cn_same_text(ptr {a}, ptr {b})")
        return same if op == "==" else f.op(f"xor i1 {same}, true")
    raise machine.Unsupported(f"comparing {kind_name(left.kind)}")


def number_ir(f, op, left, right):
    if left.kind in (PLACE, FLAT):  # a place moved, made bigger or turned around
        a = machine.emit(f, left)
        if op == "neg":
            return f.op(f"call ptr @cn_place_scale(i32 0, ptr {a}, double {machine.number(-1.0)})")
        if op in ("+", "-"):
            return f.op(f"call ptr @cn_place_op(i32 {0 if op == '+' else 1}, ptr {a}, ptr {machine.emit(f, right)})")
        return f.op(f"call ptr @cn_place_scale(i32 {0 if op == '*' else 1}, ptr {a}, double {machine.emit(f, right)})")
    if left.kind != NUMBER:
        raise machine.Unsupported(f"maths on {kind_name(left.kind)}")
    if op == "neg":
        return f.op(f"fneg double {machine.emit(f, left)}")
    return f.op(f"{NUMBER_OPS[op]} double {machine.emit(f, left)}, {machine.emit(f, right)}")


def key_text(v, line):
    """A table's entry is named by text; a number names the entry with its written form (3 is the entry "3")."""
    if v.kind == TEXT:
        return v
    if v.kind != NUMBER:
        raise ScriptError(line, f"A table's entries are named with text or a number, but this is {kind_name(v.kind)}.")
    a = v.run
    return with_ir(Value(f"stellanova::text({v.cpp})", TEXT, lambda env: text(a(env))),
                   lambda f: f.as_text(machine.emit(f, v), v.kind))


def contains_ir(f, whole, part):
    a, b = machine.emit(f, whole), machine.emit(f, part)
    if whole.kind == TEXT:
        return f.op(f"call i1 @cn_text_contains(ptr {a}, ptr {b})")
    if is_table(whole.kind):
        return f.op(f"call i1 @cn_table_has(ptr {a}, ptr {b})")
    return f.op(f"call i1 @cn_list_contains(ptr {a}, ptr {f.box(b, part.kind)})")


def pick_ir(f, test, a, b):
    x, y = machine.emit(f, a), machine.emit(f, b)
    return f.op(f"select i1 {f.op(f'fcmp {test} double {y}, {x}')}, double {y}, double {x}")


def load_ir(target, source, fn, n):
    """'load scores from file ...' in machine code: the library reads it into a new value shaped like the name's kind."""
    if not target.ir_store:
        return None

    def write(f):
        shape = f.shape(target.kind)
        got = f.call("ptr", "cn_load", ("ptr", machine.emit(f, source)), ("ptr", shape), ("i32", str(int(fn == "load_file"))),
                     ("ptr", f.text_const(kind_name(target.kind))), ("i32", str(n)))
        target.ir_store(f, f.unbox(got, target.kind))
    return write


def within_ir(f, a, b, reach):
    """a and b (numbers or places) no further apart than reach."""
    x, y = machine.emit(f, a), machine.emit(f, b)
    if a.kind == NUMBER:
        gap = f.op(f"call double @llvm.fabs.f64(double {f.op(f'fsub double {x}, {y}')})")
    else:
        gap = f.op(f"call double @cn_place_size(ptr {f.op(f'call ptr @cn_place_op(i32 1, ptr {x}, ptr {y})')})")
    return f.op(f"fcmp ole double {gap}, {machine.emit(f, reach)}")


def field_index(kind, member):
    return next(k for k, (cpp, _, _) in enumerate(machine.THINGS[kind]) if cpp == member)


def thing_part_ir(owner_ir, kind, member, part_kind, owner_own=None):
    """A part of a thing: (get, put, own) machine-code writers. owner_ir(f) gives the thing itself (not a copy),
    owner_own(f) the same, ready to be changed."""
    k = field_index(kind, member)
    owner_own = owner_own or owner_ir

    def get(f):
        if part_kind == NUMBER:
            return f.thing_number(owner_ir(f), k)
        return f.unbox(f.op(f"call ptr @cn_field(ptr {owner_ir(f)}, i32 {k})"), part_kind)

    def put(f, x):
        if part_kind == NUMBER:
            return f.put_thing_number(owner_own(f), k, x)
        f.put(f"call void @cn_field_put(ptr {owner_own(f)}, i32 {k}, ptr {f.box(x, part_kind)})")

    def own(f):
        return f.op(f"call ptr @cn_own_field(ptr {owner_own(f)}, i32 {k})") if machine.ll_type(part_kind) == "ptr" else get(f)
    return get, put, own


WORLD_KINDS = {}  # 'the world remembers:' names: C++ name -> kind (for machine code's shared names)
LIBRARY_HEADS = {}  # a library's name -> the C++ its words need above them (includes and code)
LIBRARY_VALUES = {}  # a library word for a value: its words -> the library's name
SETTING_NUMBERS = {}  # a setting's C++ name -> its number


def join_ir(f, parts):
    """The parts' text, one after the other."""
    out = None
    for v in parts:
        if out is not None and v.kind == NUMBER:  # (one new text, not two)
            out = f.op(f"call ptr @cn_join_number(ptr {out}, double {machine.emit(f, v)})")
            continue
        t = f.as_text(machine.emit(f, v), v.kind)
        made = f"  {t} = call ptr @cn_text_number(double "
        if out is not None and f.lines and f.lines[-1].startswith(made):  # '"w" plus (n as text)': one new text, not two
            number = f.lines.pop()[len(made):-1]
            out = f.op(f"call ptr @cn_join_number(ptr {out}, double {number})")
            continue
        out = t if out is None else f.op(f"call ptr @cn_join(ptr {out}, ptr {t})")
    return out


class Command:
    """A command a program can call: one of the script's own, or a word from a library."""

    def __init__(self, cpp, kinds, gives, inputs=None, runner=None):
        self.cpp, self.kinds, self.gives = cpp, kinds, gives
        self.inputs = inputs  # library words: the input names their C++ uses as {name}
        self.runner = runner  # called with the inputs' values when running directly
        self.versions = None  # a command for a kind of thing: {kind: Command} for it and the kinds of it


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
        for k in self.commands:
            if hidden_from_here(k) and tuple(tokens[i:i + len(k) - 1]) == k[:-1]:
                return private_message(k)
        known = [" ".join(k) for k in self.known] + [spoken(k) for k in self.commands if not hidden_from_here(k)]
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
        if best[2]:
            return f"I don't know '{best[1]}'. Did you mean '{best[2]}'?"
        return (f"I don't know '{best[1]}'. If it is a name, set it before this line (like 'set {best[1]} to 0') "
                f"or list it as an input of the command.")

    def value(self, key):
        cpp, kind, read_only, run = self.known[key]
        if cpp.startswith(UNUSABLE):
            raise ScriptError(0, cpp[len(UNUSABLE):])
        if isinstance(run, tuple):  # (get, put): a shared name, or the thing a command is for, or one of its parts
            v = Value(cpp, kind, run[0], None if read_only else run[1])
            if cpp in WORLD_KINDS:
                v.ir, v.ir_store = (lambda f: f.load(cpp, kind)), (lambda f, x: f.store(cpp, kind, x))
                v.ir_own = lambda f: f.own(cpp, kind)
            elif "." in cpp:  # 'speed' inside 'to bounce, for a ball:' is the ball's speed
                own, member = cpp.split(".", 1)
                v.ir, v.ir_store, v.ir_own = thing_part_ir(lambda f: f.load(own, f.slots[own][1]), OWNER_KINDS[own], member, kind)
            else:  # the whole thing: setting it changes the caller's thing
                v.ir = lambda f: f.load(cpp, kind)
                v.ir_store = lambda f, x: f.put(f"call void @cn_replace(ptr {f.load(cpp, kind)}, ptr {x})")
            return v
        if run is not None:  # a setting, an Unreal word or a library word
            v = Value(cpp, kind, run, None if read_only else (lambda env, x: run(env)))
            if cpp in SETTING_NUMBERS:
                v.ir = lambda f: machine.number(SETTING_NUMBERS[cpp])
            elif key in LIBRARY_VALUES:
                lib = LIBRARY_VALUES[key]
                v.ir = lambda f: machine.wrap(f, lib, LIBRARY_HEADS[lib], cpp, [], kind, cpp_type, 0)
            return v
        get = lambda env: env[cpp]

        def put(env, x):
            env[cpp] = dup(x)
        get.pyf = lambda: f"env[{cpp!r}]"
        put.py_store = lambda x: f"env[{cpp!r}] = {py_copy(x, kind)}"
        v = with_ir(Value(cpp, kind, get, None if read_only else put), lambda f: f.load(cpp, kind))
        v.ir_store = lambda f, x: f.store(cpp, kind, x)
        v.ir_own = lambda f: f.own(cpp, kind)
        v.local_name = cpp
        return v


CPP_RESERVED = set("""auto bool break case catch char check class const continue default delete do double else enum
explicit false float for friend goto if inline int long new operator private protected public return short signed
sizeof static struct switch template this throw true try typedef union unsigned using virtual void while""".split())


def snake(words):
    name = "_".join(re.sub(r"[^a-z0-9]", "", w) for w in words)
    return name + "_" if name in CPP_RESERVED or (JS and name in JS_RESERVED) else name


def cpp_text(token):
    """A quoted text token as a C++ string (or a JavaScript one)."""
    if JS:
        return json.dumps(token[1:-1], ensure_ascii=False)
    return "std::string(" + token.replace("\\", "\\\\") + ")"


COMPARE_RUN = {">": operator.gt, "<": operator.lt, ">=": operator.ge, "<=": operator.le, "!=": operator.ne, "==": operator.eq}


INLINE_COUNT = [0]  # commands written where they are used, numbered for their machine code


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
        bare, self.bare = getattr(self, "bare", 0), 0  # inside brackets, 'as text' and the like belong to what is there
        try:
            return self.logic_or()
        finally:
            self.bare = bare

    def operand(self):
        """What follows 'of' or a command's name: 'as text', 'rounded to' and the like after it are left for the whole,
        so 'item 2 of scores as text' is (item 2 of scores) as text."""
        self.bare = getattr(self, "bare", 0) + 1
        try:
            return self.unary()
        finally:
            self.bare -= 1

    def logic_or(self):
        v = self.logic_and()
        while self.at("or"):
            self.i += 1
            r = self.logic_and()
            a, b = self.need(v, YESNO, "or").run, self.need(r, YESNO, "or").run
            v = with_ir(Value(f"({v.cpp} || {r.cpp})", YESNO, lambda env, a=a, b=b: a(env) or b(env)),
                        lambda f, l=v, r=r: machine.short_circuit(f, l, r, True))
            v.pyf = lambda a=a, b=b: f"({py_expr(a)} or {py_expr(b)})"
        return v

    def logic_and(self):
        v = self.logic_not()
        while self.at("and"):
            self.i += 1
            r = self.logic_not()
            a, b = self.need(v, YESNO, "and").run, self.need(r, YESNO, "and").run
            v = with_ir(Value(f"({v.cpp} && {r.cpp})", YESNO, lambda env, a=a, b=b: a(env) and b(env)),
                        lambda f, l=v, r=r: machine.short_circuit(f, l, r, False))
            v.pyf = lambda a=a, b=b: f"({py_expr(a)} and {py_expr(b)})"
        return v

    def logic_not(self):
        if self.at("not"):
            self.i += 1
            v = self.need(self.logic_not(), YESNO, "not")
            a = v.run
            out = with_ir(Value(f"!{v.cpp}", YESNO, lambda env: not a(env)),
                          lambda f: f.op(f"xor i1 {machine.emit(f, v)}, true"))
            out.pyf = lambda: f"(not {py_expr(a)})"
            return out
        return self.compare()

    COMPARE = [(("is", "more", "than"), ">"), (("is", "less", "than"), "<"), (("is", "at", "least"), ">="),
               (("is", "at", "most"), "<="), (("is", "not"), "!="), (("is",), "==")]

    def biggest_first(self):
        """', biggest first' after 'sorted ...': read it, and say whether it was there."""
        if self.at(",", "biggest", "first"):
            self.i += 3
            return True
        return False

    def circle(self, v):
        """Where something is and how big it is, for 'touches': a thing's existence and radius, or a place and the radius in reach."""
        if is_thing(v.kind):
            for part in ("existence", "radius"):
                if v.kind not in FIELDS.get((part,), {}):
                    raise ScriptError(self.line, f"'touches' needs {kind_name(v.kind)} to have {'a birth' if part == 'existence' else 'a radius'}.")
            at, size = part_of(v, ("existence",), self.line), part_of(v, ("radius",), self.line)
        elif v.kind in (PLACE, FLAT):
            at, size = v, (self.names.value(("radius",)) if self.names.known.get(("radius",), (None, None))[1] == NUMBER
                           else with_ir(Value("0", NUMBER, lambda env: 0), lambda f: machine.number(0.0)))
        else:
            raise ScriptError(self.line, f"'touches' needs a thing or a place, not {kind_name(v.kind)}.")
        if at.kind != PLACE and at.kind != FLAT or size.kind != NUMBER:
            raise ScriptError(self.line, "'touches' needs an existence that is a place and a radius that is a number.")
        return at, size

    def compare(self):
        v = self.sum()
        if self.at("contains"):
            self.i += 1
            r = self.sum()
            if is_table(v.kind) and r.kind == NUMBER:
                r = key_text(r, self.line)
            if not (v.kind == r.kind == TEXT or (is_list(v.kind) and element(v.kind) == r.kind)
                    or (is_table(v.kind) and r.kind == TEXT)):
                raise ScriptError(self.line, f"I can't look for {kind_name(r.kind)} in {kind_name(v.kind)}.")
            a, b = v.run, r.run
            return with_ir(builtin("stellanova::contains({a0}, {a1})", YESNO, lambda env: b(env) in a(env), [v, r]),
                           lambda f: contains_ir(f, v, r))
        for words, fn, test in ((("begins", "with"), "begins_with", str.startswith), (("ends", "with"), "ends_with", str.endswith)):
            if self.at(*words):  # 'name begins with "Dr"'
                self.i += 2
                r = self.need(self.sum(), TEXT, " ".join(words))
                self.need(v, TEXT, " ".join(words))
                a, b = v.run, r.run
                return builtin(f"stellanova::{fn}({{a0}}, {{a1}})", YESNO, lambda env, test=test: test(a(env), b(env)), [v, r])
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
                at = part_of(v, (part,), self.line)
                r = self.names.value(("radius",))
                far = self.names.value(edge)
                a, b, c = at.run, r.run, far.run
                near = with_ir(Value("", YESNO, None), lambda f, at=at, r=r: compare_ir(f, "<=", at, r))
                edge_gap = with_ir(Value("", NUMBER, None), lambda f, far=far, r=r: number_ir(f, "-", far, r))
                past = with_ir(Value("", YESNO, None), lambda f, at=at, e=edge_gap: compare_ir(f, ">=", at, e))
                return with_ir(Value(f"({at.cpp} <= {r.cpp} || {at.cpp} >= {far.cpp} - {r.cpp})", YESNO,
                                     lambda env: a(env) <= b(env) or a(env) >= c(env) - b(env)),
                               lambda f, near=near, past=past: machine.short_circuit(f, near, past, True))
        if self.at("touches"):  # 'ball touches coin': the two circles (existence and radius) overlap
            self.i += 1
            r = self.sum()
            (pa, ra), (pb, rb) = self.circle(v), self.circle(r)
            a, b, c, d = pa.run, pb.run, ra.run, rb.run
            both_radii = with_ir(Value("", NUMBER, None), lambda f: number_ir(f, "+", ra, rb))
            return with_ir(Value(f"stellanova::within({pa.cpp}, {pb.cpp}, {ra.cpp} + {rb.cpp})", YESNO,
                                 lambda env: (a(env) - b(env)).size() <= c(env) + d(env)),
                           lambda f: within_ir(f, pa, pb, both_radii))
        if self.at("is", "within"):  # 'existence is within 30 of coin': close enough to touch
            self.i += 2
            reach = self.need(self.sum(), NUMBER, "within")
            self.take("of")
            r = self.sum()
            if v.kind != r.kind or v.kind not in (NUMBER, PLACE, FLAT):
                raise ScriptError(self.line, f"'within' compares two numbers or two places, not {kind_name(v.kind)} and {kind_name(r.kind)}.")
            a, b, c = v.run, r.run, reach.run
            gap = (lambda x, y: abs(x - y)) if v.kind == NUMBER else (lambda x, y: (x - y).size())
            return with_ir(Value(f"stellanova::within({v.cpp}, {r.cpp}, {reach.cpp})", YESNO, lambda env: gap(a(env), b(env)) <= c(env)),
                           lambda f: within_ir(f, v, r, reach))
        if is_thing(v.kind) and self.at("is"):
            negated = self.peek(1) == "not"
            start = self.i + (2 if negated else 1)
            target = next((" ".join(self.t[start:end]) for end in range(len(self.t), start, -1)
                           if " ".join(self.t[start:end]) in THINGS and tuple(self.t[start:end]) not in self.names.known), None)
            if target:  # 'if pet is a dog': which kind it really is (a puppy is a dog too)
                self.i = start + len(target.split())
                names = [k for k in THINGS if is_kind_of("thing " + k, "thing " + target)]
                a, wanted = v.run, set(names)
                test = lambda env: ((o := a(env)) is not None and o.name in wanted) != negated
                if JS:
                    cpp = f"({'!' if negated else ''}stellanova::is_kind({v.cpp}, {json.dumps(names)}))"
                else:  # C++ text: a thing is only ever its own kind there
                    cpp = "true" if is_kind_of(v.kind, "thing " + target) != negated else "false"
                marks = "|" + "|".join(names) + "|"
                def ir(f, v=v, marks=marks):
                    const, _ = f.module.text(marks)
                    found = f.op(f"call i1 @cn_is_kind_of(ptr {machine.emit(f, v)}, ptr {const})")
                    return f.op(f"xor i1 {found}, true") if negated else found
                return with_ir(Value(cpp, YESNO, test), ir)
        if is_thing(v.kind) and (self.at("is", "nothing") or self.at("is", "something")):  # 'if target is nothing'
            there = self.peek(1) == "something"
            self.i += 2
            a = v.run
            return with_ir(Value(f"({v.cpp} {'!==' if there else '==='} undefined)", YESNO, lambda env: (a(env) is not None) == there),
                           lambda f: f.op(f"icmp {'ne' if there else 'eq'} ptr {machine.emit(f, v)}, null"))
        if self.at("is", "one", "of") or self.at("is", "not", "one", "of"):  # 'answer is one of ("yes", "y")'
            negated = self.at("is", "not")
            self.i += 4 if negated else 3
            if self.at("("):  # the choices written out: read as 'a list containing (...)'
                self.t[self.i:self.i] = ["list", "containing"]
            r = self.sum()
            if not (is_list(r.kind) and element(r.kind) == v.kind):
                raise ScriptError(self.line, f"'is one of' needs choices of the same kind, like 'answer is one of (\"yes\", \"y\")', "
                                             f"but this is {kind_name(r.kind)}.")
            a, b = r.run, v.run
            found = with_ir(builtin("stellanova::contains({a0}, {a1})", YESNO, lambda env: b(env) in a(env), [r, v]),
                            lambda f: contains_ir(f, r, v))
            if not negated:
                return found
            c = found.run
            return with_ir(Value(f"(!{found.cpp})", YESNO, lambda env: not c(env)),
                           lambda f: f.op(f"xor i1 {machine.emit(f, found)}, true"))
        for words, op in self.COMPARE:
            if self.at(*words):
                self.i += len(words)
                r = self.sum()
                if not (op in ("==", "!=") and v.kind == r.kind and v.kind not in (PLACE, FLAT) and not holds_command(v.kind)):
                    self.need(v, NUMBER, "Comparing")
                    self.need(r, NUMBER, "Comparing")
                a, b, f = v.run, r.run, COMPARE_RUN[op]
                if JS and is_deep(v.kind):  # JavaScript's == only asks whether they are the very same list
                    return Value(f"({'!' if op == '!=' else ''}stellanova::same({v.cpp}, {r.cpp}))", YESNO, lambda env: f(a(env), b(env)))
                out = with_ir(Value(f"({v.cpp} {op} {r.cpp})", YESNO, lambda env: f(a(env), b(env))),
                              lambda fn, op=op, l=v, r=r: compare_ir(fn, op, l, r))
                out.pyf = lambda: f"({py_expr(a)} {op} {py_expr(b)})"
                return out
        return v

    def sum(self):
        v = self.product()
        while self.peek() in ("plus", "+", "minus", "-"):
            op = "+" if self.peek() in ("plus", "+") else "-"
            self.i += 1
            r = self.product()
            a, b = v.run, r.run
            if v.kind == TEXT and op == "+":
                left = v
                v = with_ir(Value(f"(stellanova::text({v.cpp}) + stellanova::text({r.cpp}))", TEXT,
                                  lambda env, a=a, b=b: text(a(env)) + text(b(env))), lambda fn, l=v, r=r: join_ir(fn, [l, r]))
                v.pyf = lambda a=a, b=b: f"(_text({py_expr(a)}) + _text({py_expr(b)}))"
                v.joined = getattr(left, "joined", [left]) + [r]  # every part, left to right (for cn_append)
                continue
            if v.kind != r.kind or v.kind not in (NUMBER, PLACE, FLAT):
                raise ScriptError(self.line, f"I can't {'add' if op == '+' else 'subtract'} {kind_name(r.kind)} {'to' if op == '+' else 'from'} {kind_name(v.kind)}.")
            f = operator.add if op == "+" else operator.sub
            run = lambda env, a=a, b=b, f=f: f(a(env), b(env))
            if JS and v.kind != NUMBER:
                v = Value(f"stellanova::{'plus' if op == '+' else 'minus'}({v.cpp}, {r.cpp})", v.kind, run)
                continue
            v = with_ir(Value(f"({v.cpp} {op} {r.cpp})", v.kind, run), lambda fn, op=op, l=v, r=r: number_ir(fn, op, l, r))
            v.pyf = lambda a=a, b=b, op=op: f"({py_expr(a)} {op} {py_expr(b)})"
        return v

    BIT_WORDS = ((("bitwise", "and"), 0), (("bitwise", "or"), 1), (("bitwise", "exclusive", "or"), 2),
                 (("shifted", "left", "by"), 3), (("shifted", "right", "by"), 4))

    def powered(self):
        """'2 to the power 10' (before times and plus, as in maths)"""
        v = self.unary()
        while self.at("to", "power"):  # 'the' is grammar, skipped already
            self.i += 2
            r = self.unary()
            if v.kind != NUMBER or r.kind != NUMBER:
                raise ScriptError(self.line, f"'to the power' needs numbers, not {kind_name(v.kind)} and {kind_name(r.kind)}.")
            a, b, line, l = v.run, r.run, self.line, v
            v = with_ir(Value(f"stellanova::power({v.cpp}, {r.cpp}, {line})", NUMBER, lambda env, a=a, b=b: power(a(env), b(env), line)),
                        lambda f, l=l, r=r, line=line: f.call("double", "cn_power", ("double", machine.emit(f, l)), ("double", machine.emit(f, r)),
                                                             ("i32", line), checked=True))
        return v

    def product(self):
        v = self.powered()
        while True:
            bit = next(((words, op) for words, op in self.BIT_WORDS if self.at(*words)), None)
            if not bit:
                break
            words, op = bit
            self.i += len(words)
            r = self.powered()
            if v.kind != NUMBER or r.kind != NUMBER:
                raise ScriptError(self.line, f"'{' '.join(words)}' needs whole numbers, not {kind_name(v.kind)} and {kind_name(r.kind)}.")
            a, b, line, l = v.run, r.run, self.line, v
            v = with_ir(Value(f"stellanova::bits({op}, {v.cpp}, {r.cpp}, {line})", NUMBER, lambda env, a=a, b=b, op=op: bits(op, a(env), b(env), line)),
                        lambda f, l=l, r=r, op=op, line=line: f.call("double", "cn_bits", ("i32", op), ("double", machine.emit(f, l)),
                                                                     ("double", machine.emit(f, r)), ("i32", line), checked=True))
        while self.peek() in ("times", "*", "/") or self.at("divided", "by"):
            op = "/" if self.peek() in ("/", "divided") else "*"
            self.i += 2 if self.at("divided", "by") else 1
            r = self.powered()
            if r.kind != NUMBER or v.kind not in (NUMBER, PLACE, FLAT):
                raise ScriptError(self.line, f"I can only multiply or divide a number or a place by a number, not {kind_name(v.kind)} by {kind_name(r.kind)}.")
            a, b = v.run, r.run
            f = divide if op == "/" else operator.mul
            run = lambda env, a=a, b=b, f=f: f(a(env), b(env))
            if JS and v.kind != NUMBER:
                v = Value(f"stellanova::{'over' if op == '/' else 'times'}({v.cpp}, {r.cpp})", v.kind, run)
                continue
            v = with_ir(Value(f"({v.cpp} {op} {r.cpp})", v.kind, run), lambda fn, op=op, l=v, r=r: number_ir(fn, op, l, r))
            v.pyf = (lambda a=a, b=b: f"_divide({py_expr(a)}, {py_expr(b)})") if op == "/" else (lambda a=a, b=b: f"({py_expr(a)} * {py_expr(b)})")
        return v

    def signed(self):
        """A part of a place, which may be negative: '0 horizontal -2 vertical -10 depth'."""
        if self.peek() != "-":
            return self.single()
        self.i += 1
        x = self.single()
        if x.kind != NUMBER:
            raise ScriptError(self.line, f"Only a number can be negative, not {kind_name(x.kind)}.")
        a = x.run
        out = with_ir(Value(f"(-{x.cpp})", NUMBER, lambda env: -a(env)), lambda f: f.op(f"fneg double {machine.emit(f, x)}"))
        out.pyf = lambda: f"(-{py_expr(a)})"
        return out

    def unary(self):
        v = self.single()
        if v.kind != NUMBER or not self.at("horizontal"):
            return v
        self.i += 1  # 300 horizontal 200 vertical (5 depth): a place
        parts = [v, self.need(self.signed(), NUMBER, "a place")]
        self.take("vertical")
        start = self.i
        if self.peek() not in (None, ",", ")") and (self.peek() not in ITEM_NOT_INDEX or self.peek() == "-"):
            try:
                third = self.signed()
            except ScriptError:  # 'the place touches b': what follows isn't a depth
                third = None
            if third and third.kind == NUMBER and self.at("depth"):
                self.i += 1
                parts.append(third)
            else:
                self.i = start
        runs = [x.run for x in parts]
        cpp = "FVector" if len(parts) == 3 else "FVector2D"
        def write(f):
            done = [machine.emit(f, x) for x in parts]
            if len(done) == 3:
                return f.op(f"call ptr @cn_place(double {done[0]}, double {done[1]}, double {done[2]})")
            return f.op(f"call ptr @cn_flat(double {done[0]}, double {done[1]})")
        v = with_ir(Value(f"{cpp}({', '.join(strip_parens(x.cpp) for x in parts)})", PLACE if len(parts) == 3 else FLAT,
                          lambda env: Place(*[f(env) for f in runs])), write)
        v.pyf = lambda: f"_Place({', '.join(py_expr(f) for f in runs)})"
        return v

    def single(self):
        if self.peek() in ("-", "minus"):
            self.i += 1
            v = self.single()
            if v.kind not in (NUMBER, PLACE, FLAT):
                raise ScriptError(self.line, f"I can't make {kind_name(v.kind)} negative.")
            a = v.run
            if JS and v.kind != NUMBER:
                return Value(f"stellanova::negative({v.cpp})", v.kind, lambda env: -a(env))
            out = with_ir(Value(f"(-{v.cpp})", v.kind, lambda env: -a(env)), lambda f: number_ir(f, "neg", v, None))
            out.pyf = lambda: f"(-{py_expr(a)})"
            return out
        v = self.primary()
        while self.at("of"):  # 'existence of horizontal': a part named after the place or thing
            key = next((tuple(self.t[self.i + 1:self.i + 1 + n]) for n in range(min(6, len(self.t) - self.i - 1), 0, -1)
                        if v.kind in FIELDS.get(tuple(self.t[self.i + 1:self.i + 1 + n]), {})
                        or place_part(v.kind, tuple(self.t[self.i + 1:self.i + 1 + n]))), None)
            if not key:
                break
            self.i += 1 + len(key)
            v = part_of(v, key, self.line)
        if getattr(self, "bare", 0):
            return v
        if self.at("as", "a", "number") or self.at("as", "number"):
            self.i += 3 if self.at("as", "a") else 2
            if v.kind != TEXT:
                raise ScriptError(self.line, f"'as a number' turns text into a number, but this is {kind_name(v.kind)}.")
            a, line = v.run, self.line
            return with_ir(Value(f"stellanova::to_number({v.cpp}, {line})", NUMBER, lambda env: to_number(a(env), line)),
                           lambda f: f.op(f"call double @cn_to_number(ptr {machine.emit(f, v)}, i32 {line})"))
        for words in (("changed", "by"), ("kept", "by")):
            if self.at(*words):  # 'scores changed by the command double', 'scores kept by the command is big'
                self.i += 2
                if not is_list(v.kind):
                    raise ScriptError(self.line, f"'{' '.join(words)}' needs a list, but this is {kind_name(v.kind)}.")
                item = element(v.kind)
                f = self.inline_command([item]) if self.at("each") else self.unary()
                ins, gives = SIGNATURES.get(f.kind, (None, None))
                if ins != [item] or (words[0] == "kept" and gives != YESNO) or not gives:
                    want = f"a command given {kind_name(item)} returning " + ("yes or no" if words[0] == "kept" else "something")
                    raise ScriptError(self.line, f"'{' '.join(words)}' needs {want}, not {kind_name(f.kind)}.")
                a, g, line = v.run, f.run, self.line
                if JS:
                    v = Value(f"(await stellanova::{words[0]}_by({strip_parens(v.cpp)}, {strip_parens(f.cpp)}, {line}))",
                              v.kind if words[0] == "kept" else "list of " + gives,
                              (lambda env: (lambda fn: [dup(x) for x in a(env) if invoke_value(fn, [x], line)])(g(env))) if words[0] == "kept" else
                              (lambda env: (lambda fn: [dup(invoke_value(fn, [x], line)) for x in a(env)])(g(env))))
                elif words[0] == "kept":
                    seq, held = v, f
                    v = with_ir(Value(f"stellanova::kept_by({strip_parens(v.cpp)}, {strip_parens(f.cpp)}, {line})", v.kind,
                                      lambda env: (lambda fn: [dup(x) for x in a(env) if invoke_value(fn, [x], line)])(g(env))),
                                lambda fn: machine.by_command(fn, machine.emit(fn, seq), machine.emit(fn, held), item, gives, True, line))
                else:
                    seq, held = v, f
                    v = with_ir(Value(f"stellanova::changed_by<{cpp_type(gives)}>({strip_parens(v.cpp)}, {strip_parens(f.cpp)}, {line})", "list of " + gives,
                                      lambda env: (lambda fn: [dup(invoke_value(fn, [x], line)) for x in a(env)])(g(env))),
                                lambda fn: machine.by_command(fn, machine.emit(fn, seq), machine.emit(fn, held), item, gives, False, line))
                return v
        if self.at("as", "saved", "text"):  # 'scores as saved text': written out as JSON, as 'save' writes it
            self.i += 3
            if holds_command(v.kind):
                raise ScriptError(self.line, "A command can't be saved.")
            a, kind, line = v.run, v.kind, self.line
            shown = f", {json.dumps(kind)}" if JS else ""
            return with_ir(Value(f"stellanova::saved_text({v.cpp}, {line}{shown})", TEXT, lambda env: saved(a(env), kind, line)),
                           lambda f: f.op(f"call ptr @cn_saved_text(ptr {f.box(machine.emit(f, v), v.kind)}, ptr {f.shape(v.kind)}, i32 {line})"))
        if self.at("as", "text"):
            self.i += 2
            a = v.run
            out = with_ir(Value(f"stellanova::text({v.cpp})", TEXT, lambda env: text(a(env))),
                          lambda f: f.as_text(machine.emit(f, v), v.kind))
            out.pyf = lambda: f"_text({py_expr(a)})"
            return out
        if self.at("rounded", "to"):
            self.i += 2
            self.need(v, NUMBER, "rounded to")
            places = self.need(self.primary(), NUMBER, "rounded to")
            if self.peek() in ("places", "place", "decimal"):
                self.i += 1
                if self.at("places") or self.at("place"):
                    self.i += 1
            a, b, line = v.run, places.run, self.line
            return with_ir(Value(f"stellanova::rounded({v.cpp}, {places.cpp}, {line})", NUMBER, lambda env: rounded(a(env), b(env), line)),
                           lambda f: f.op(f"call double @cn_rounded(double {machine.emit(f, v)}, double {machine.emit(f, places)}, i32 {line})"))
        if self.at("with", "commas"):  # '1234567 with commas' is "1,234,567"
            self.i += 2
            self.need(v, NUMBER, "with commas")
            a = v.run
            return builtin("stellanova::with_commas({s0})", TEXT, lambda env: with_commas(a(env)), [v])
        if self.at("repeated"):  # '"ab" repeated 3 times' is "ababab"; a list works the same way
            self.i += 1
            if v.kind != TEXT and not is_list(v.kind):
                raise ScriptError(self.line, f"'repeated' needs text or a list, like '\"ab\" repeated 3 times', but this is {kind_name(v.kind)}.")
            count = self.need(self.primary(), NUMBER, "repeated")
            self.take("times")
            a, b, line = v.run, count.run, self.line

            def run(env):
                n = b(env)
                if n < 0 or n != int(n):
                    raise RunError(line, f"'repeated' needs a whole number of times, 0 or more, not {text(n)}.")
                x = a(env)
                return x * int(n) if isinstance(x, str) else [dup(y) for _ in range(int(n)) for y in x]
            out = builtin("stellanova::repeated({s0}, {s1}, {line})", v.kind, run, [v, count], line)
            return with_ir(out, lambda f, v=v, count=count, line=line:  # any kind of item, things too
                           f.call("ptr", "cn_repeated", ("ptr", machine.emit(f, v)), ("double", machine.emit(f, count)), ("i32", str(line)),
                                  checked=True))
        if self.at("padded", "to"):  # '7 padded to 3 digits' is "007"; '"food" padded to 12 letters' has spaces after it
            self.i += 2
            if v.kind not in (NUMBER, TEXT):
                raise ScriptError(self.line, f"'padded to' needs a number ('7 padded to 3 digits') or text ('\"food\" padded to 12 letters'), "
                                             f"not {kind_name(v.kind)}.")
            digits = self.need(self.primary(), NUMBER, "padded to")
            unit = ("letters", "letter") if v.kind == TEXT else ("digits", "digit")
            if self.peek() in unit:
                self.i += 1
            a, b, line = v.run, digits.run, self.line
            return builtin("stellanova::padded({s0}, {s1}, {line})", TEXT, lambda env: padded(a(env), b(env), line), [v, digits], line)
        if self.at("split", "by"):
            self.i += 2
            self.need(v, TEXT, "split by")
            by = self.need(self.primary(), TEXT, "split by")
            a, b, line = v.run, by.run, self.line
            out = builtin("stellanova::split({a0}, {a1}, {line})", "list of text", lambda env: split(a(env), b(env), line), [v, by], line)
            out.ir = lambda f: f.op(f"call ptr @cn_split(ptr {machine.emit(f, v)}, ptr {machine.emit(f, by)}, i32 {line})")
            return out
        return v

    def inline_command(self, given=None):
        """'each x becomes x times 2': a command written where it is used, with its inputs before 'becomes' (joined
        with 'and', each with its kind in brackets unless the place it goes says, like 'changed by') and its answer after.
        It keeps copies of the names it uses, as they are when it is made."""
        line = self.line
        self.take("each")
        try:
            stop = self.t.index("becomes", self.i)
        except ValueError:
            raise ScriptError(line, "Write 'each <name> becomes <what it gives back>', like: each x becomes x times 2.")
        pieces, now = [], []
        for tok in self.t[self.i:stop]:
            if tok == "and" and now.count("(") == now.count(")"):
                pieces.append(now)
                now = []
            else:
                now.append(tok)
        pieces.append(now)
        inputs = []
        for k, piece in enumerate(pieces):
            if "(" in piece:
                cut = piece.index("(")
                words, kind = piece[:cut], parse_kind(" ".join(piece[cut + 1:-1]))
                if piece[-1] != ")" or not kind:
                    raise ScriptError(line, f"I don't know the kind '{' '.join(piece[cut + 1:-1])}'.")
            else:
                words, kind = piece, given[k] if given and k < len(given) else None
            if not words or not kind:
                shown = " ".join(words) or "x"
                raise ScriptError(line, f"Say what kind '{shown}' is, like: each {shown} (a number) becomes ...")
            inputs.append((tuple(words), kind))
        if given is not None and [k for _, k in inputs] != list(given):
            raise ScriptError(line, f"This command is given {' and '.join(kind_name(k) for k in given)}.")
        self.i = stop + 1
        local = Names()
        local.__dict__.update(self.names.__dict__)
        local.known = dict(self.names.known)
        outer = {entry[0] for entry in self.names.known.values() if entry[3] is None}
        ins, used = set(), []
        base_value = local.value

        def value(key):
            v = base_value(key)
            if key not in ins and v.cpp in outer and v.cpp not in used:
                used.append(v.cpp)
            return v
        local.value = value
        for words, kind in inputs:
            local.add(words, snake(words), kind, read_only=True)
            ins.add(words)
        sub = Expr(self.t, local, line)
        sub.i = self.i
        body = sub.full()
        self.i = sub.i
        gives = body.kind
        kind = command_kind([k for _, k in inputs], gives)
        in_cpp = [snake(w) for w, _ in inputs]
        kinds = {entry[0]: entry[1] for entry in self.names.known.values()}  # C++ name -> kind, for the names it keeps
        run = body.run

        def make(env):
            kept = dict(env)
            for cpp in used:
                kept[cpp] = dup(kept[cpp])

            def command(*args):
                e = dict(kept)
                e.update(zip(in_cpp, args))
                return run(e)
            return command
        if JS:
            outer_used = [c for c in used if c not in in_cpp]
            cpp = (f"((({', '.join(outer_used)}) => (async ({', '.join(in_cpp)}) => {body.cpp}))"
                   f"({', '.join(js_copy(c, kinds[c]) for c in outer_used)}))")
        else:
            ins_cpp = ", ".join(f"{cpp_type(k)} {c}" for c, (_, k) in zip(in_cpp, inputs))
            cpp = f"{cpp_type(kind)}([=]({ins_cpp}) {{ return {strip_parens(body.cpp)}; }})"
        INLINE_COUNT[0] += 1
        name = f"each_{INLINE_COUNT[0]}"
        return with_ir(Value(cpp, kind, make),
                       lambda f: machine.closure(f, name, list(zip(in_cpp, (k for _, k in inputs))), gives, body))

    def primary(self):
        tok, line = self.peek(), self.line
        if tok is None:
            raise ScriptError(line, "This line ends too early: something is missing.")
        if (tok == "the" and self.peek(1) not in (None, "command") and not self.names.match(self.t, self.i)[0]
                and not match_command(self.names, self.t[self.i:])[0]):
            self.i += 1  # 'the theme of prefs' reads as 'theme of prefs', unless a name starts with 'the'
            try:
                return self.primary()
            except ScriptError:
                self.i -= 1  # not that either: the usual message about the whole phrase
        if re.fullmatch(r"\d+(?:\.\d+)?", tok):
            self.i += 1
            while self.peek() in UNITS:
                self.i += 1
            number = float(tok)
            v = with_ir(Value(tok if "." in tok else tok + ".0", NUMBER, lambda env: number), lambda f: machine.number(number))
            v.pyf = lambda: repr(number)
            return v
        for words, mark, cpp in ((("quote", "mark"), '"', '"\\""'), (("new", "line"), "\n", '"\\n"')):
            if self.at(*words):  # text can't hold these between its own quote marks
                self.i += 2
                v = with_ir(Value(cpp if JS else f"std::string({cpp})", TEXT, lambda env, mark=mark: mark),
                            lambda f, mark=mark: f.text_const(mark))
                v.pyf = lambda mark=mark: repr(mark)
                return v
        if tok.startswith('"'):
            self.i += 1
            s = tok[1:-1]
            v = with_ir(Value(cpp_text(tok), TEXT, lambda env: s), lambda f: f.text_const(s))
            v.pyf = lambda: repr(s)
            return v
        if self.at("random", "item", "of") or self.at("a", "random", "item", "of"):
            self.i += 4 if tok == "a" else 3
            v = self.operand()
            if not is_list(v.kind):
                raise ScriptError(line, f"'random item of' needs a list, but this is {kind_name(v.kind)}.")
            a = v.run

            def pick(env):
                items = a(env)
                if not items:
                    raise RunError(line, "the list is empty, so I can't pick a random item.")
                return pyrandom.choice(items)
            return builtin("stellanova::random_item({a0}, {line})", element(v.kind), pick, [v], line)
        if self.at("random", "fraction"):  # 'random fraction': a number from 0 up to (not quite) 1
            self.i += 2
            return with_ir(Value("stellanova::random_fraction()", NUMBER, lambda env: pyrandom.random()),
                           lambda f: f.op("call double @cn_random_fraction()"))
        if self.at("random", "number", "from"):
            self.i += 3
            lo = self.need(self.sum(), NUMBER, "random number")
            self.take("to")
            hi = self.need(self.sum(), NUMBER, "random number")
            a, b = lo.run, hi.run
            return with_ir(Value(f"stellanova::random({lo.cpp}, {hi.cpp}, {line})", NUMBER, lambda env: random_number(a(env), b(env), line)),
                           lambda f: f.op(f"call double @cn_random(double {machine.emit(f, lo)}, double {machine.emit(f, hi)}, i32 {line})"))
        if tok == "(":
            self.i += 1
            v = self.full()
            if self.at(","):
                raise ScriptError(line, "A place is written like 300 horizontal 200 vertical (and 5 depth, for a place with depth).")
            self.take(")")
            return v
        for n in range(min(16, len(self.t) - self.i), 0, -1):
            key = tuple(self.t[self.i:self.i + n])
            if key in FIELDS and self.peek(n) == "of" and not (
                    key in self.names.known and (self.names.known[key][1] in FIELDS.get((self.peek(n + 1),), {})
                                                 or place_part(self.names.known[key][1], (self.peek(n + 1),)))):
                # 'existence of x' is x of the name existence, when there is one, not the existence of x
                back = self.i
                self.i += n + 1
                owner = self.operand()
                if owner.kind not in FIELDS[key]:
                    if key in self.names.known or key in (("lines",), ("words",)):  # 'entry app of windows': the name app; 'words of text'
                        self.i = back
                        break
                    raise ScriptError(line, f"{kind_name(owner.kind).capitalize()} has no '{' '.join(key)}'.")
                return part_of(owner, key, self.line)
        if tok == "item" and self.peek(1) not in ITEM_NOT_INDEX:
            self.i += 1
            index = self.need(self.sum(), NUMBER, "item")
            self.take("of")
            seq = self.operand()
            if not is_list(seq.kind):
                raise ScriptError(line, f"'item ... of' needs a list, but this is {kind_name(seq.kind)}.")
            get, at = seq.run, index.run

            def item(env):
                items = get(env)
                return items[index_of(items, at(env), line)]

            def put(env, x):
                items = get(env)
                items[index_of(items, at(env), line)] = dup(x)
            item.pyf = lambda: f"_item({py_expr(get)}, {py_expr(at)}, {line})"
            put.py_store = lambda x: f"_put_item({py_expr(get)}, {py_expr(at)}, {line}, {py_copy(x, element(seq.kind))})"
            v = Value(f"stellanova::at({seq.cpp}, {strip_parens(index.cpp)}, {line})", element(seq.kind), item,
                      put if seq.writable else None)
            v.ir = lambda f: f.read_number_item(machine.emit(f, seq), machine.emit(f, index), line) if v.kind == NUMBER else \
                f.unbox(f.read_item(machine.emit(f, seq), machine.emit(f, index), line), v.kind)
            if seq.writable and v.kind == NUMBER:  # in place, in the machine code itself
                v.ir_store = lambda f, x: f.write_number_item(machine.owned(f, seq), machine.emit(f, index), x, line)
            elif seq.writable:
                v.ir_own = lambda f: f.call("ptr", "cn_own_item", ("ptr", machine.owned(f, seq)), ("double", machine.emit(f, index)),
                                            ("i32", line), checked=True)
                v.ir_store = lambda f, x: f.write_item(machine.owned(f, seq), machine.emit(f, index), f.box(x, v.kind), line, v.kind)
            if JS:  # a JavaScript call can't be set, so the item is put in by the runtime
                v.cpp_assign, v.cpp_close = f"stellanova::put_at({seq.cpp}, {strip_parens(index.cpp)}, {line}, ", ")"
            return v
        made = self.made()  # before names, so a name like 'a' doesn't hide 'a list of'
        if made:
            return made
        if tok == "entry" and self.peek(1) not in ITEM_NOT_INDEX:
            self.i += 1
            name = key_text(self.sum(), self.line)
            self.take("of")
            table = self.operand()
            if not is_table(table.kind):
                raise ScriptError(line, f"'entry ... of' needs a table, but this is {kind_name(table.kind)}.")
            get, at = table.run, name.run

            def put(env, x):
                get(env)[at(env)] = dup(x)
            v = Value(f"stellanova::entry({table.cpp}, {strip_parens(name.cpp)}, {line})", entry_kind(table.kind),
                      lambda env: entry_of(get(env), at(env), line), put if table.writable else None)
            v.ir = lambda f: f.unbox(f.call("ptr", "cn_entry", ("ptr", machine.emit(f, table)), ("ptr", machine.emit(f, name)),
                                            ("i32", line), checked=True), v.kind)
            if table.writable:
                v.ir_store = lambda f, x: f.put(f"call void @cn_entry_put_number(ptr {machine.owned(f, table)}, ptr {machine.emit(f, name)}, double {x})") \
                    if v.kind == NUMBER else f.put(f"call void @cn_entry_put(ptr {machine.owned(f, table)}, ptr {machine.emit(f, name)}, ptr {f.box(x, v.kind)})")
                if machine.ll_type(v.kind) == "ptr":
                    v.ir_own = lambda f: f.call("ptr", "cn_own_entry", ("ptr", machine.owned(f, table)), ("ptr", machine.emit(f, name)),
                                                ("i32", line), checked=True)
            v.cpp_assign = f"({table.cpp})[{strip_parens(name.cpp)}] = "  # setting an entry may make a new one
            if JS:
                v.cpp_assign, v.cpp_close = f"stellanova::put_entry({table.cpp}, {strip_parens(name.cpp)}, ", ")"
            return v
        for stat in ("sum", "average", "biggest", "smallest"):
            if self.at(stat, "of") and not match_command(self.names, self.t[self.i:])[0]:  # a command called 'sum of' still wins
                self.i += 2
                v = self.operand()
                if v.kind != "list of number":
                    raise ScriptError(line, f"'{stat} of' needs a list of numbers, but this is {kind_name(v.kind)}.")
                a = v.run
                which = ("sum", "average", "biggest", "smallest").index(stat)
                return with_ir(Value(f"stellanova::{stat}_of({v.cpp}, {line})", NUMBER, lambda env, stat=stat: list_stat(stat, a(env), line)),
                               lambda f, which=which, v=v: f.call("double", "cn_list_stat", ("i32", which), ("ptr", machine.emit(f, v)),
                                                                  ("i32", line), checked=True))
        if self.at("keys", "of"):
            self.i += 2
            table = self.operand()
            if not is_table(table.kind):
                raise ScriptError(line, f"'keys of' needs a table, but this is {kind_name(table.kind)}.")
            get = table.run
            return builtin("stellanova::keys({a0})", "list of text", lambda env: sorted(get(env)), [table])
        if self.at("each"):  # a command written where it is used: 'each x (a number) becomes x times 2'
            return self.inline_command()
        if self.at("the", "command"):  # a command kept as a value: 'set f to the command double'
            self.i += 2
            return command_value(self.names, self.t, self, line)
        if self.at("invoke"):  # 'invoke f with 4': do the command a name holds
            self.i += 1
            f = self.operand()
            if not is_command(f.kind):
                raise ScriptError(line, f"'invoke' needs a command, like 'invoke the command double with 4', not {kind_name(f.kind)}.")
            ins, gives = SIGNATURES[f.kind]
            if self.at("with"):
                self.i += 1
            args = []
            if len(ins) == 1:
                args = [self.operand()]
            elif len(ins) > 1:
                if not self.at("("):
                    raise ScriptError(line, f"This command needs {len(ins)} inputs. Put them in brackets, like: invoke f with (1, 2)")
                self.i += 1
                args = [self.full()]
                while self.at(","):
                    self.i += 1
                    args.append(self.full())
                self.take(")")
            for k, (a, kind) in enumerate(zip(args, ins), 1):
                if a.kind != kind:
                    raise ScriptError(line, f"Input {k} of this command must be {kind_name(kind)}, not {kind_name(a.kind)}.")
            if not gives and not getattr(self, "allow_nothing", False):
                raise ScriptError(line, "This command doesn't return anything, so it can't be used as a value.")
            get, gets = f.run, [a.run for a in args]
            held = f
            return with_ir(Value(f"{'(await ' if JS else ''}stellanova::invoke({', '.join([strip_parens(f.cpp), str(line)] + [strip_parens(a.cpp) for a in args])}){')' if JS else ''}", gives,
                                 lambda env: invoke_value(get(env), [g(env) for g in gets], line)),
                           lambda fn: machine.invoke(fn, machine.emit(fn, held), [(machine.emit(fn, a), a.kind) for a in args], ins, gives, line))
        key, n = self.names.match(self.t, self.i)
        command_key, command_n = match_command(self.names, self.t[self.i:])
        if key and n >= command_n:  # the longer match wins: 'balls moved down' is a command even when 'balls' is a name
            self.i += n
            try:
                return self.names.value(key)
            except ScriptError as err:
                raise ScriptError(err.line or line, err.message)
        key, n = command_key, command_n
        if key:
            self.i += n
            command = self.names.commands[key]
            needs = len(command.kinds)
            least = needs - len(getattr(command, "usual", {}))  # inputs with a usual value may be left out
            if self.at("with"):
                self.i += 1
            args = []
            ends = self.peek() in ITEM_NOT_INDEX or self.peek() in ("then", "exceeds", "falls")
            if needs == 0 or (least == 0 and ends):
                pass
            elif needs == 1 or (least <= 1 and not (self.at("(") and "," in self.t[self.i:max(self.i, closing_bracket(self.t, self.i))])):
                args = [self.operand()]
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
                raise ScriptError(line, f"'{' '.join(key)}' doesn't return anything, so it can't be used as a value.")
            cpp, run = call(key, args, self.names, line)
            if command.versions and args and is_thing(args[0].kind):  # copies of a kind for any kind give back their own kinds
                command = nearest_version(command.versions, args[0].kind) or command
            return with_ir(Value(cpp, command.gives, run), getattr(run, "ir", None))
        if tok == "no" and self.peek(1) is not None:  # 'no enemy': a thing that isn't there
            for n in range(min(6, len(self.t) - self.i - 1), 0, -1):
                name = " ".join(self.t[self.i + 1:self.i + 1 + n])
                if name in THINGS:
                    if UNREAL:
                        raise ScriptError(line, f"'no {name}' can't be used in Unreal parts yet.")
                    self.i += 1 + n
                    return with_ir(Value("undefined" if JS else "nullptr", "thing " + name, lambda env: None), lambda f: "null")
        if tok in ("yes", "no"):
            self.i += 1
            b = tok == "yes"
            v = with_ir(Value("true" if b else "false", YESNO, lambda env: b), lambda f: "true" if b else "false")
            v.pyf = lambda: repr(b)
            return v
        if self.at("clamp"):
            self.i += 1
            v = self.need(self.sum(), NUMBER, "clamp")
            self.take("between")
            lo = self.need(self.sum(), NUMBER, "clamp")
            self.take("and")
            hi = self.need(self.sum(), NUMBER, "clamp")
            x, a, b = v.run, lo.run, hi.run
            out = builtin("FMath::Clamp({a0}, {a1}, {a2})", NUMBER, lambda env: min(max(x(env), a(env)), b(env)), [v, lo, hi])
            out.pyf = lambda: f"min(max({py_expr(x)}, {py_expr(a)}), {py_expr(b)})"
            return out
        for word, fn, f in (("smaller", "Min", min), ("larger", "Max", max)):
            if self.at(word, "of"):
                self.i += 2
                a = self.need(self.sum(), NUMBER, f"{word} of")
                self.take("and")
                b = self.need(self.sum(), NUMBER, f"{word} of")
                x, y = a.run, b.run
                # as Python's min and max: the first, unless the second is smaller (or larger)
                return with_ir(Value(f"FMath::{fn}({a.cpp}, {b.cpp})", NUMBER, lambda env, f=f: f(x(env), y(env))),
                               lambda f, a=a, b=b, test="olt" if word == "smaller" else "ogt": pick_ir(f, test, a, b))
        if self.at("contents", "of", "file") or self.at("lines", "of", "file"):
            whole = self.at("contents")
            self.i += 3
            where = self.need(self.operand(), TEXT, "file")
            w = where.run
            if whole:
                return builtin("stellanova::read_file({a0}, {line})", TEXT, lambda env: read_file(w(env), line), [where], line)
            return builtin("stellanova::read_lines({a0}, {line})", "list of text", lambda env: lines_of(read_file(w(env), line)), [where], line)
        if self.at("file"):
            self.i += 1
            where = self.need(self.operand(), TEXT, "file")
            self.take("exists")
            w = where.run
            return builtin("stellanova::file_exists({a0})", YESNO, lambda env: os.path.isfile(w(env)), [where])
        if self.at("folder") and self.peek(1) not in (None, "exists") and "exists" in self.t[self.i:]:  # 'folder "saves" exists'
            self.i += 1
            where = self.need(self.operand(), TEXT, "folder")
            self.take("exists")
            w = where.run
            return builtin("stellanova::folder_exists({a0})", YESNO, lambda env: os.path.isdir(w(env)), [where])
        for words, fn, f in ((("lines", "of"), "lines_of", lines_of), (("words", "of"), "words_of", str.split)):
            if self.at(*words):
                self.i += 2
                v = self.need(self.operand(), TEXT, " ".join(words))
                a = v.run
                return builtin(f"stellanova::{fn}({{a0}})", "list of text", lambda env, f=f: f(a(env)), [v])
        if tok in ("letter", "letters") and self.peek(1) not in ITEM_NOT_INDEX:
            self.i += 1
            first = self.need(self.sum(), NUMBER, tok)
            last_ = None
            if tok == "letters":
                self.take("to")
                last_ = self.need(self.sum(), NUMBER, "letters ... to")
            self.take("of")
            v = self.need(self.operand(), TEXT, f"'{tok} ... of'")
            a, f = v.run, first.run
            if last_ is None:
                return builtin("stellanova::letter({a0}, {s1}, {line})", TEXT, lambda env: letter(a(env), f(env), line), [v, first], line)
            b = last_.run
            return builtin("stellanova::letters_from({a0}, {s1}, {s2}, {line})", TEXT,
                         lambda env: letters_from(a(env), f(env), b(env), line), [v, first, last_], line)
        if self.at("trimmed"):  # 'trimmed line': without spaces, tabs and line breaks at either end
            self.i += 1
            v = self.need(self.operand(), TEXT, "trimmed")
            a = v.run
            return builtin("stellanova::trimmed({a0})", TEXT, lambda env: a(env).strip(" \t\r\n"), [v])
        for words, fn, table in ((("upper", "case", "of"), "upper_case", CASE_UP), (("lower", "case", "of"), "lower_case", CASE_DOWN)):
            if self.at(*words):
                self.i += 3
                v = self.need(self.operand(), TEXT, " ".join(words))
                a = v.run
                return builtin(f"stellanova::{fn}({{a0}})", TEXT, lambda env, table=table: a(env).translate(table), [v])
        if self.at("position", "of"):
            self.i += 2
            part = self.sum()
            self.take("in")
            v = self.operand()
            a, b = v.run, part.run
            if is_list(v.kind):  # 'position of "Bo" in names': which item it is, or 0
                if element(v.kind) != part.kind:
                    raise ScriptError(line, f"'position of ... in' looks for {kind_name(element(v.kind))} in this list, not {kind_name(part.kind)}.")
                return builtin("stellanova::position({a0}, {a1})", NUMBER,
                               lambda env: float(next((k for k, x in enumerate(a(env), 1) if x == b(env)), 0)), [v, part])
            self.need(part, TEXT, "position of")
            self.need(v, TEXT, "position of ... in")
            return builtin("stellanova::position({a0}, {a1})", NUMBER, lambda env: float(a(env).find(b(env)) + 1), [v, part])
        if self.at("replace"):
            self.i += 1
            old = self.need(self.sum(), TEXT, "replace")
            self.take("with")
            new = self.need(self.sum(), TEXT, "replace ... with")
            self.take("in")
            v = self.need(self.operand(), TEXT, "replace ... in")
            a, o, w = v.run, old.run, new.run
            return builtin("stellanova::replace_all({a0}, {a1}, {a2}, {line})", TEXT,
                         lambda env: replace_all(a(env), o(env), w(env), line), [v, old, new], line)
        if self.at("join"):
            self.i += 1
            v = self.operand()
            if not is_list(v.kind):
                raise ScriptError(line, f"'join' needs a list, but this is {kind_name(v.kind)}.")
            self.take("with")
            between = self.need(self.operand(), TEXT, "join ... with")
            a, b = v.run, between.run
            out = builtin("stellanova::join({a0}, {a1})", TEXT, lambda env: b(env).join(text(x) for x in a(env)), [v, between])
            if element(v.kind) == TEXT:
                out.ir = lambda f: f.op(f"call ptr @cn_join_texts(ptr {machine.emit(f, v)}, ptr {machine.emit(f, between)})")
            return out
        if self.at("sorted"):
            start = self.i
            self.i += 1
            v = self.operand()
            if self.at("by", "each") and is_list(v.kind):  # 'sorted names by each n becomes the size of n': by what each works out to
                self.i += 1
                item = element(v.kind)
                f = self.inline_command([item])
                ins, gives = SIGNATURES.get(f.kind, (None, None))
                if gives not in (NUMBER, TEXT):
                    raise ScriptError(line, f"'sorted ... by each' needs to work out a number or text for each item, not {kind_name(gives)}.")
                down = self.biggest_first()
                if down:  # as for parts: back to front, sorted, back to front, so equal ones keep their order
                    v = reversed_list(v)
                a, g = v.run, f.run

                def run(env):
                    xs, fn = a(env), g(env)
                    ks = [invoke_value(fn, [x], line) for x in xs]
                    return [dup(xs[j]) for j in sorted(range(len(xs)), key=lambda j: ks[j])]

                def ir(fn, v=v, f=f):
                    xs = fn.hold(machine.emit(fn, v))  # held: the loop working out keys frees what isn't
                    ks = machine.by_command(fn, xs, machine.emit(fn, f), item, gives, False, line)
                    return fn.op(f"call ptr @cn_sorted_by_keys(ptr {xs}, ptr {ks})")
                how = f"(await stellanova::sorted_by_command(" if JS else f"stellanova::sorted_by_command<{cpp_type(gives)}>("
                out = with_ir(Value(how + f"{strip_parens(v.cpp)}, {strip_parens(f.cpp)}, {line})" + (")" if JS else ""), v.kind, run), ir)
                return reversed_list(out) if down else out
            if self.at("by") and is_list(v.kind) and is_thing(element(v.kind)):
                self.i += 1
                thing = element(v.kind)
                for n in range(min(16, len(self.t) - self.i), 0, -1):
                    key = tuple(self.t[self.i:self.i + n])
                    if key in FIELDS and thing in FIELDS[key]:
                        self.i += n
                        member, kind = FIELDS[key][thing]
                        if kind not in (NUMBER, TEXT):
                            raise ScriptError(line, f"'sorted ... by' needs a part that is a number or text, but '{' '.join(key)}' is {kind_name(kind)}.")
                        down = self.biggest_first()
                        if down:  # back to front, smallest first, back to front again: biggest first, and equal ones keep their order
                            v = reversed_list(v)
                        a = v.run
                        by = f"(t) => t.{member}" if JS else f"[](const auto& t) {{ return t.{member}; }}"
                        k = field_index(thing, member)
                        out = with_ir(Value(f"stellanova::sorted_by({v.cpp}, {by}, {line})", v.kind,
                                            lambda env: py_sorted_by(a(env), member, line)),
                                      lambda f, v=v, k=k: f.op(f"call ptr @cn_sorted_by(ptr {machine.emit(f, v)}, i32 {k}, i32 {line})"))
                        out.run.pyf = lambda v=v, member=member: f"_sorted_by({py_expr(v)}, {member!r}, {line})"
                        return reversed_list(out) if down else out
                raise ScriptError(line, f"{kind_name(thing).capitalize()} has no part called '{' '.join(self.t[self.i:self.i + 2])}'.")
            self.i = start
        if self.at("flattened"):  # 'flattened rows': a list of lists as one list
            self.i += 1
            v = self.operand()
            if not (is_list(v.kind) and is_list(element(v.kind))):
                raise ScriptError(line, f"'flattened' needs a list of lists, like 'flattened rows', but this is {kind_name(v.kind)}.")
            a = v.run
            out = builtin("stellanova::flattened({a0})", element(v.kind), lambda env: [dup(x) for xs in a(env) for x in xs], [v])
            return with_ir(out, lambda f, v=v: f.op(f"call ptr @cn_flattened(ptr {machine.emit(f, v)})"))  # any kind of item
        if self.at("reversed"):
            self.i += 1
            v = self.operand()
            if not is_list(v.kind):
                raise ScriptError(line, f"'reversed' needs a list, but this is {kind_name(v.kind)}.")
            return reversed_list(v)
        if self.at("sorted"):
            self.i += 1
            v = self.operand()
            if not is_list(v.kind) or element(v.kind) not in (NUMBER, TEXT):
                raise ScriptError(line, f"'sorted' needs a list of numbers or text, but this is {kind_name(v.kind)}.")
            a = v.run
            out = builtin("stellanova::sorted({a0})", v.kind, lambda env: sorted(a(env)), [v])
            if element(v.kind) == NUMBER:
                out.ir = lambda f: f.op(f"call ptr @cn_sorted_numbers(ptr {machine.emit(f, v)})")
            return reversed_list(out) if self.biggest_first() else out
        if tok == "items" and self.peek(1) not in ITEM_NOT_INDEX and not self.names.match(self.t, self.i)[0]:
            self.i += 1  # 'items 2 to 5 of names'
            first = self.need(self.sum(), NUMBER, "items")
            self.take("to")
            last_ = self.need(self.sum(), NUMBER, "items ... to")
            self.take("of")
            v = self.operand()
            if not is_list(v.kind):
                raise ScriptError(line, f"'items ... to ... of' needs a list, but this is {kind_name(v.kind)}.")
            a, f, b = v.run, first.run, last_.run
            return builtin("stellanova::items_from({a0}, {s1}, {s2}, {line})", v.kind,
                           lambda env: items_from(a(env), f(env), b(env), line), [v, first, last_], line)
        if (tok in ("first", "last") and self.peek(1) not in ITEM_NOT_INDEX and self.peek(1) != "item"
                and not self.names.match(self.t, self.i)[0]):
            self.i += 1  # 'first 3 of names', 'last 2 of word'
            count = self.need(self.sum(), NUMBER, tok)
            self.take("of")
            v = self.operand()
            if not (is_list(v.kind) or v.kind == TEXT):
                raise ScriptError(line, f"'{tok} ... of' needs a list or text, but this is {kind_name(v.kind)}.")
            a, c, end = v.run, count.run, tok == "last"
            fn = "last_of" if end else "first_of"
            return builtin(f"stellanova::{fn}({{a0}}, {{s1}}, {{line}})", v.kind,
                           lambda env: first_of(a(env), c(env), line, end), [v, count], line)
        for word, run_ in (("unique", unique), ("shuffled", shuffled)):
            if self.at(word):
                self.i += 1
                v = self.operand()
                if not is_list(v.kind):
                    raise ScriptError(line, f"'{word}' needs a list, but this is {kind_name(v.kind)}.")
                a = v.run
                return builtin(f"stellanova::{word}({{a0}})", v.kind, lambda env, r=run_: r(a(env)), [v])
        if self.at("last", "item", "of"):
            self.i += 3
            v = self.operand()
            if not is_list(v.kind):
                raise ScriptError(line, f"'last item of' needs a list, but this is {kind_name(v.kind)}.")
            a = v.run
            out = builtin("stellanova::last({a0}, {line})", element(v.kind), lambda env: last(a(env), line), [v], line)
            item = element(v.kind)  # in machine code, the library's own: any kind of item (things too)
            return with_ir(out, lambda f: f.unbox(f.call("ptr", "cn_list_last", ("ptr", machine.emit(f, v)), ("i32", line), checked=True), item))
        if self.at("square", "root", "of"):
            self.i += 3
            v = self.need(self.sum(), NUMBER, "square root")
            a = v.run
            return builtin("FMath::Sqrt({a0})", NUMBER, lambda env: math.sqrt(x) if (x := a(env)) >= 0 else math.nan, [v])
        if self.at("size", "of"):
            self.i += 2
            v = self.sum()
            a = v.run
            if v.kind == NUMBER:
                return with_ir(Value(f"FMath::Abs({v.cpp})", NUMBER, lambda env: abs(a(env))),
                               lambda f: f.op(f"call double @llvm.fabs.f64(double {machine.emit(f, v)})"))
            if v.kind in (PLACE, FLAT):
                return with_ir(Value(f"({v.cpp}).Size()", NUMBER, lambda env: a(env).size()),
                               lambda f: f.op(f"call double @cn_place_size(ptr {machine.emit(f, v)})"))
            if v.kind == TEXT:
                return with_ir(Value(f"stellanova::letters({v.cpp})", NUMBER, lambda env: letters(a(env))),
                               lambda f: f.op(f"call double @cn_letters(ptr {machine.emit(f, v)})"))
            if is_list(v.kind) or is_table(v.kind):
                out = with_ir(Value(f"stellanova::count({v.cpp})" if JS else f"double(({v.cpp}).size())", NUMBER, lambda env: float(len(a(env)))),
                              lambda f: f.op(f"call double @cn_count(ptr {machine.emit(f, v)})"))
                out.pyf = lambda: f"float(len({py_expr(a)}))"
                return out
            raise ScriptError(line, f"{kind_name(v.kind)} has no size.")
        if self.at("flat"):
            self.i += 1
            v = self.need(self.operand(), PLACE, "flat")
            a = v.run
            def write(f):
                p = machine.emit(f, v)
                x, y = (f.op(f"call double @cn_part(ptr {p}, i32 {k})") for k in (0, 1))
                return f.op(f"call ptr @cn_flat(double {x}, double {y})")
            return with_ir(Value(f"FVector2D({v.cpp})", FLAT, lambda env: Place(*a(env).parts()[:2])), write)
        if self.at("direction", "of"):
            self.i += 2
            v = self.need(self.sum(), FLAT, "direction of")
            a = v.run
            return builtin("FMath::RadiansToDegrees(FMath::Atan2(({a0}).Y, ({a0}).X))", NUMBER,
                         lambda env: (lambda q: math.atan2(q.fields["Y"], q.fields["X"]) * 180.0 / 3.14159265358979323846)(a(env)), [v])
        if self.at("angle", "from"):
            self.i += 2
            a = self.need(self.sum(), NUMBER, "angle from")
            self.take("to")
            b = self.need(self.sum(), NUMBER, "angle from")
            x, y = a.run, b.run
            return builtin("FMath::UnwindDegrees({a0} - {a1})", NUMBER, lambda env: unwind(y(env) - x(env)), [b, a])
        if tok in KEYWORDS:
            raise ScriptError(line, f"'{tok}' can't go here.")
        raise ScriptError(line, self.names.unknown(self.t, self.i))

    def made(self):
        """A new value: 'a list of numbers', 'an empty list of text', 'a list of (1, 2, 3)', 'a new pet'."""
        start = self.i
        for lead in (("a", "new"), ("an", "new"), ("new",)):
            if self.at(*lead) and not self.names.match(self.t, self.i)[0]:  # a name like 'new notification' wins
                self.i += len(lead)
                for n in range(min(5, len(self.t) - self.i), 0, -1):
                    name = " ".join(self.t[self.i:self.i + n])
                    if name in ABLE:
                        kinds_ = [k for k in THINGS if k not in ABLE and can("thing " + k, name)]
                        raise ScriptError(self.line, f"A {name} is anything that can {' and '.join(' '.join(w) for w in ABLE[name])}, so conjure one of "
                                                     f"those instead" + (f" ({', '.join(kinds_)})." if kinds_ else "."))
                    if name in THINGS:
                        self.i += n
                        things = THINGS
                        out = with_ir(Value(js_zero("thing " + name) if JS else f"{cpp_type('thing ' + name)}{{}}", "thing " + name,
                                            lambda env: Thing(name, things)), lambda f, name=name: f.zero("thing " + name))
                        out.pyf = lambda name=name: f"_Thing({name!r}, _THINGS)"
                        return out
                raise ScriptError(self.line, f"There is no kind of thing called '{' '.join(self.t[self.i:self.i + 2])}'."
                                  + (f" Kinds of things: {', '.join(THINGS)}." if THINGS else ""))
        for lead in (("a", "table", "of"), ("an", "empty", "table", "of"), ("table", "of"), ("empty", "table", "of")):
            if self.at(*lead):
                self.i += len(lead)
                for n in range(min(16, len(self.t) - self.i), 0, -1):
                    k = parse_kind(" ".join(self.t[self.i:self.i + n]))
                    if k:
                        self.i += n
                        return with_ir(Value(zero("table of " + k) if JS else f"{cpp_type('table of ' + k)}()", "table of " + k, lambda env: {}),
                                       lambda f: f.op("call ptr @cn_table_new()"))
                raise ScriptError(self.line, f"Say what the table holds, like 'a table of numbers'. Kinds are: {kind_words()}.")
        for lead in (("a", "list", "of"), ("an", "empty", "list", "of"), ("list", "of"), ("empty", "list", "of"), ("list", "containing")):
            if self.at(*lead):
                self.i += len(lead)
                close = closing_bracket(self.t, self.i) if self.at("(") else -1
                bracket = close > 0 and "," in self.t[self.i:close]
                if "empty" not in lead and (self.at("(") if "of" in lead else True):
                    if bracket or "of" in lead:  # 'a list of (1, 2, 3)', 'a list containing (1, 2, 3)'
                        self.i += 1
                        items = [self.full()]
                        while self.at(","):
                            self.i += 1
                            items.append(self.full())
                        self.take(")")
                    else:  # 'a list containing new notification': a list with that one item
                        items = [self.full()]
                    for v in items:
                        if v.kind != items[0].kind:
                            raise ScriptError(self.line, f"A list holds one kind of thing, but this mixes {kind_name(items[0].kind)} and {kind_name(v.kind)}.")
                    kind = "list of " + items[0].kind
                    runs = [v.run for v in items]
                    listed = ', '.join(js_copy(v.cpp, v.kind) if JS else strip_parens(v.cpp) for v in items)
                    def write(f, items=items):
                        made_list = f.op("call ptr @cn_list_new()")
                        for v in items:
                            f.put(f"call void @cn_list_add(ptr {made_list}, ptr {f.box(machine.emit(f, v), v.kind)})")
                        return made_list
                    out = with_ir(Value(f"[{listed}]" if JS else f"{cpp_type(kind)}{{{listed}}}", kind,
                                        lambda env: [dup(f(env)) for f in runs]), write)
                    out.pyf = lambda: f"[{', '.join(py_copy(py_expr(f), element(kind)) for f in runs)}]"
                    return out
                for n in range(min(16, len(self.t) - self.i), 0, -1):
                    k = parse_kind(" ".join(self.t[self.i:self.i + n]))
                    if k:
                        self.i += n
                        return with_ir(Value("[]" if JS else f"{cpp_type('list of ' + k)}()", "list of " + k, py_empty_list),
                                       lambda f: f.op("call ptr @cn_list_new()"))
                raise ScriptError(self.line, f"Say what the list holds, like 'a list of numbers'. Kinds are: {kind_words()}.")
        self.i = start
        return None


# ---------------------------------------------------------------- words files and libraries

def load_words(name, line):
    path = LOGIC / f"{name}.words"
    if not path.exists():
        raise ScriptError(line, f"There is no '{name}' to be part of (no {name}.words next to the script).")
    names, info = Names(), {}
    for n, raw in enumerate(source_text(path).splitlines(), 1):
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
            raise ScriptError(n, f"{path.name}: '{kind}' isn't a kind. Kinds here are: {', '.join(CPP_TYPE)}.")
        names.add(english.strip().lower().split(), cpp, kind, read_only, not_here(line, f"'{english.strip()}'"))
    return names, info


LIBRARY_HELP = """A library is <name>.words, next to the script or in Stellanova's libraries folder. Its lines:
  include: <cmath>                    a C++ header to include
  link: shell32                       a system library to link with
  linux link: :libsqlite3.so.0        the same on Linux (given to the linker as -l)
  code:                               C++ lines (indented below) the words can use
  python:                             Python lines (indented below) the 'runs:' lines can use
  pi = 3.14159, number, read only     a word for a value
  to wait, given seconds (a number) = std::this_thread::sleep_for(std::chrono::duration<double>({seconds}))
                                      a word for a command; {input name} stands for each input
    runs: time.sleep({seconds})       (indented under a word) what it does when the program runs directly"""


def place_part(kind, key):
    """True if a place of this kind has this part ('depth' only for places with depth)."""
    return kind in (PLACE, FLAT) and key in PLACE_PARTS and not (kind == FLAT and key == ("depth",))


def part_of(owner, key, line=0):
    """One part of a thing ('name of rex') or of a place ('existence of horizontal')."""
    member, kind = (PLACE_PARTS[key], NUMBER) if place_part(owner.kind, key) else FIELDS[key][owner.kind]
    hider = SECRET_PARTS.get((owner.kind, tuple(key)))
    if hider and not (OWNER_NOW[0] and is_kind_of(OWNER_NOW[0], hider)):
        one = ("an " if hider[6] in "aeiou" else "a ") + hider[6:]
        raise ScriptError(line, f"The {' '.join(key)} of {one} is hidden: only commands for {one} can use it.")
    get, cpp = owner.run, f"({owner.cpp}).{member}"
    if is_thing(owner.kind):  # it may be nothing
        whose, part, plain = owner.kind, " ".join(key), owner.run
        get = lambda env: something(plain(env), whose, part, line)
        get.pyf = lambda: (lambda e: f"({e} or _something({e}, {whose!r}, {part!r}, {line}))" if PY_NAME.fullmatch(e)
                           else f"_something({e}, {whose!r}, {part!r}, {line})")(py_expr(plain))  # (a thing is never false)
        if JS:
            cpp = f"stellanova::something({strip_parens(owner.cpp)}, {json.dumps(whose[6:])}, {json.dumps(part)}, {line}).{member}"

    def put(env, x):
        get(env).fields[member] = dup(x)
    put.py_store = lambda x: f"{py_expr(get)}.fields[{member!r}] = {py_copy(x, kind)}"
    v = Value(cpp, kind, lambda env: get(env).fields[member], put if owner.writable else None)
    v.pyf = lambda: f"{py_expr(get)}.fields[{member!r}]"
    if owner.kind in (PLACE, FLAT):
        k = "XYZ".index(member)
        v.ir = lambda f: f.op(f"call double @cn_part(ptr {machine.emit(f, owner)}, i32 {k})")
        v.ir_store = lambda f, x: f.put(f"call void @cn_part_put(ptr {machine.owned(f, owner)}, i32 {k}, double {x})")
    else:
        k = field_index(owner.kind, member)
        v.ir, v.ir_store, v.ir_own = thing_part_ir(
            lambda f: f.something(machine.emit(f, owner), f.spec(owner.kind), k, line), owner.kind, member, kind,
            lambda f: f.something(machine.owned(f, owner), f.spec(owner.kind), k, line))
    if not owner.writable:
        v.ir_store = v.ir_own = None
    if key == ("birth",) and is_thing(owner.kind) and owner.kind in FIELDS.get(("existence",), {}) and owner.writable:
        def born(env, x):
            fields = get(env).fields
            fields["birth"], fields["existence"] = dup(x), dup(x)
        v.store = born
        _, put_birth, _ = thing_part_ir(lambda f: machine.owned(f, owner), owner.kind, "birth", kind)
        _, put_existence, _ = thing_part_ir(lambda f: machine.owned(f, owner), owner.kind, "existence", kind)
        v.ir_store = lambda f, x: (put_birth(f, x), put_existence(f, x))
        v.cpp_assign, v.cpp_close = f"stellanova::born(({owner.cpp}).birth, ({owner.cpp}).existence, ", ")"
        if JS:
            v.cpp_assign = f"stellanova::born({strip_parens(owner.cpp)}, "
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
    found = sorted({spoken(k) for k in names.commands if k[0] == tokens[0] and not hidden_from_here(k)})
    if not found:
        return ""
    return f" Words that start with '{tokens[0]}': " + ", ".join(found) + "."


# C functions from a library (.dll, .so): the kinds a word's C line may use, as
# (C type, Stellanova kind, ctypes type name, C++ for an input {x}, C++ for an answer {x})
C_TYPES = {
    "int": ("int", NUMBER, "c_int", "(int)({x})", "(double)({x})"),
    "unsigned": ("unsigned", NUMBER, "c_uint", "(unsigned)({x})", "(double)({x})"),
    "long long": ("long long", NUMBER, "c_longlong", "(long long)({x})", "(double)({x})"),
    "unsigned long long": ("unsigned long long", NUMBER, "c_ulonglong", "(unsigned long long)({x})", "(double)({x})"),
    "double": ("double", NUMBER, "c_double", "({x})", "({x})"),
    "float": ("float", NUMBER, "c_float", "(float)({x})", "(double)({x})"),
    "pointer": ("void*", NUMBER, "c_void_p", "(void*)(intptr_t)({x})", "(double)(intptr_t)({x})"),
    "text": ("const char*", TEXT, "c_char_p", "({x}).c_str()", "stellanova_c::from({x})"),
    "wide text": ("const wchar_t*", TEXT, "c_wchar_p", "stellanova_c::wide({x}).c_str()", "stellanova_c::narrow({x})"),
    "yes or no": ("bool", YESNO, "c_bool", "({x})", "({x})"),
}
C_LINE = re.compile(r"(void|[a-z][a-z ]*?)\s+([A-Za-z_]\w*)\s*\(([a-z ,]*)\)")
C_HEAD = r"""#ifndef STELLANOVA_C_CALLS
#define STELLANOVA_C_CALLS
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#else
#include <dlfcn.h>
#endif
#include <cstdint>
#include <map>
#include <mutex>
namespace stellanova_c
{
	inline void* find(const std::string& library, const std::string& name, int line)  // kept after the first time
	{
		static std::mutex lock;
		static std::map<std::string, void*> found;
		std::lock_guard<std::mutex> hold(lock);
		auto& at = found[library + "|" + name];
		if (at)
			return at;
#ifdef _WIN32
		HMODULE lib = LoadLibraryA(library.c_str());
		if (!lib)
			stellanova::fail(line, "I couldn't find the library \"" + library + "\".");
		at = reinterpret_cast<void*>(GetProcAddress(lib, name.c_str()));
#else
		void* lib = dlopen(library.c_str(), RTLD_NOW);
		if (!lib)
			stellanova::fail(line, "I couldn't find the library \"" + library + "\".");
		at = dlsym(lib, name.c_str());
#endif
		if (!at)
			stellanova::fail(line, "the library \"" + library + "\" has no function called " + name + ".");
		return at;
	}
	inline std::string from(const char* s) { return s ? std::string(s) : std::string(); }
	inline std::wstring wide(const std::string& s)
	{
#ifdef _WIN32
		int n = MultiByteToWideChar(CP_UTF8, 0, s.data(), (int)s.size(), nullptr, 0);
		std::wstring out((size_t)n, L'\0');
		MultiByteToWideChar(CP_UTF8, 0, s.data(), (int)s.size(), out.data(), n);
		return out;
#else
		return std::wstring(s.begin(), s.end());
#endif
	}
	inline std::string narrow(const wchar_t* s)
	{
		if (!s)
			return std::string();
#ifdef _WIN32
		int n = WideCharToMultiByte(CP_UTF8, 0, s, -1, nullptr, 0, nullptr, nullptr);
		std::string out((size_t)(n > 0 ? n - 1 : 0), '\0');
		WideCharToMultiByte(CP_UTF8, 0, s, -1, out.data(), n, nullptr, nullptr);
		return out;
#else
		std::wstring w(s);
		return std::string(w.begin(), w.end());
#endif
	}
}
#endif"""


def c_call_python(library, function, ins, gives, line):
    """When running directly, a C function is called through ctypes."""
    import ctypes

    def run(*args):
        try:
            lib = C_LOADED.get(library) or C_LOADED.setdefault(library, ctypes.CDLL(library))
        except OSError:
            raise RunError(0, f'I couldn\'t find the library "{library}".')
        try:
            fn = getattr(lib, function)
        except AttributeError:
            raise RunError(0, f'the library "{library}" has no function called {function}.')
        fn.argtypes = [getattr(ctypes, C_TYPES[c][2]) for c in ins]
        fn.restype = getattr(ctypes, C_TYPES[gives][2]) if gives != "void" else None
        given = [a.encode("utf-8") if c == "text" else int(a) if C_TYPES[c][2] not in ("c_double", "c_float", "c_bool", "c_wchar_p") else a
                 for a, c in zip(args, ins)]
        out = fn(*given)
        if gives == "void":
            return None
        if gives == "text":
            return out.decode("utf-8", "replace") if out else ""
        if gives == "wide text":
            return out or ""
        if gives == "yes or no":
            return bool(out)
        return float(out or 0)
    return run


C_LOADED = {}


def from_python(x, kind):
    """A Python package's answer, as the kind its word returns."""
    try:
        if kind == NUMBER:
            return float(x)
        if kind == YESNO:
            return bool(x)
        if kind == TEXT:
            return x if isinstance(x, str) else str(x)
        if is_list(kind):
            return [from_python(v, element(kind)) for v in (x.tolist() if hasattr(x, "tolist") else x)]
        if is_table(kind):
            return {str(k): from_python(v, entry_kind(kind)) for k, v in dict(x).items()}
    except RunError:
        raise
    except Exception:
        raise RunError(0, f"the Python answer ({str(x)[:60]}) isn't {kind_name(kind)}.")
    return x


def py_call(module, path, gives, *args):
    """'use python "statistics":' words, when running directly: the package's function, given Stellanova's values."""
    import importlib
    try:
        fn = importlib.import_module(module)
    except ImportError:
        raise RunError(0, f"the Python package '{module}' isn't installed (install it with: py -m pip install {module}).")
    for part in path.split("."):
        if not hasattr(fn, part):
            raise RunError(0, f"the Python package '{module}' has nothing called '{path}'.")
        fn = getattr(fn, part)
    try:
        out = fn(*args)
    except RunError:
        raise
    except Exception as err:
        raise RunError(0, f"{module}.{path} went wrong: {err}")
    return from_python(out, gives) if gives else None


def c_word(command, word, library, spec, where, line, out):
    """'to beep, given pitch (a number) and length (a number), returning yes or no = c: bool Beep(unsigned, unsigned)'"""
    m = C_LINE.fullmatch(spec.strip())
    if not library:
        raise ScriptError(line, where + "say which library the C functions are in first, with a line like: c library: user32.dll")
    if not m:
        raise ScriptError(line, where + "a C function looks like 'c: int MessageBoxA(pointer, text, text, int)'.")
    gives, function = " ".join(m.group(1).split()), m.group(2)
    ins = [" ".join(x.split()) for x in m.group(3).split(",")] if m.group(3).strip() else []
    for c in ins + ([gives] if gives != "void" else []):
        if c not in C_TYPES:
            raise ScriptError(line, where + f"I don't know the C type '{c}'. C types are: {', '.join(C_TYPES)} (and void for no answer).")
    if len(ins) != len(command.kinds):
        raise ScriptError(line, where + f"'{word}' is given {len(command.kinds)} input{'s' if len(command.kinds) != 1 else ''}, but {function} takes {len(ins)}.")
    for k, (c, kind) in enumerate(zip(ins, command.kinds), 1):
        if C_TYPES[c][1] != kind:
            raise ScriptError(line, where + f"input {k} of '{word}' must be {kind_name(C_TYPES[c][1])} to go to C as {c}.")
    if (C_TYPES[gives][1] if gives != "void" else None) != command.gives:
        raise ScriptError(line, where + (f"'{word}' must return {kind_name(C_TYPES[gives][1])}, as {function} gives {gives}." if gives != "void"
                                         else f"{function} gives nothing back, so '{word}' can't return anything."))
    pointer = f"{C_TYPES[gives][0] if gives != 'void' else 'void'}(*)({', '.join(C_TYPES[c][0] for c in ins)})"
    called = (f"(({pointer})stellanova_c::find({json.dumps(library)}, {json.dumps(function)}, {{line}}))"
              f"({', '.join(C_TYPES[c][3].replace('{x}', '{' + n + '}') for c, n in zip(ins, command.inputs))})")
    command.cpp = C_TYPES[gives][4].replace("{x}", called) if gives != "void" else called
    command.runner = c_call_python(library, function, ins, gives, line)
    if JS:
        command.unusable = f"'{word}' calls the C library \"{library}\", so it can't be used in a web program."
    if C_HEAD not in out:
        out.append(C_HEAD)


def load_library(name, line, names, rows=None):
    """Reads the words a 'use:' line asks for into names; returns the C++ the library needs at the top of the file.
    rows: the library's lines, when they are in the program itself ('use the library "user32.dll":')."""
    if rows is None:
        places = ([LOGIC / f"{name}.words"] + ([HERE / "libraries" / "unreal" / f"{name}.words"] if UNREAL else [])
                  + [HERE / "libraries" / f"{name}.words", got_folder() / f"{name}.words"])
        path = next((p for p in places if p.exists()), None)
        if not path:
            have = sorted({p.stem for p in (HERE / "libraries").glob("*.words")} | {p.stem for p in got_folder().glob("*.words")})
            raise ScriptError(line, f"There is no library called '{name}'." + (f" Libraries: {', '.join(have)}." if have else ""))
        rows = source_text(path).splitlines()
    else:
        path = Path(name)
    c_library = None  # 'c library: user32.dll': where the words' C functions are
    out = [f"// From the library '{name}'"]
    space = {"math": math, "time": time, "os": os, "sys": sys, "subprocess": subprocess, "random": pyrandom,
             "text": text, "RunError": RunError, "ARGUMENTS": ARGUMENTS, "Place": Place, "py_call": py_call}
    pending = None  # the word whose 'runs:' line may come next: (where, input names, set run)
    web = None  # the word whose 'web:' line may come next: (where, input names, set its JavaScript)
    web_only = False  # 'web only': the library's words have no C++, only 'web:' lines
    runs_only = False  # 'runs only': the library's words have no C++, only 'runs:' lines (Python)
    k = 0
    while k < len(rows):
        raw = rows[k]
        stripped = raw.strip()
        n = k + 1
        k += 1
        where = f"In the library '{name}' ({path.name} line {n}): "
        if not stripped or stripped.startswith("note:"):
            continue
        if raw[:1].isspace() and stripped.startswith("web:"):
            if not JS:  # only a program made for the web uses it
                continue
            if not web:
                raise ScriptError(line, where + "'web:' goes indented under the word it is for.")
            src, (word_where, inputs, set_web) = stripped[4:].strip(), web
            for in_name in inputs:
                if "{" + in_name + "}" not in src:
                    raise ScriptError(line, where + f"the 'web:' line doesn't use the input '{in_name}' (write it as {{{in_name}}}).")
            set_web(src)
            web = None
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
        pending = web = None
        if stripped == "web only":
            web_only = True
        elif stripped == "runs only":
            runs_only = True
        elif stripped.startswith("c library:"):
            c_library = stripped[10:].strip()
        elif stripped.startswith("include:"):
            if not JS:
                out.append(f"#include {stripped[8:].strip()}")
        elif stripped.startswith("link:"):
            if not JS:
                out.append(f'#pragma comment(lib, "{stripped[5:].strip()}")')
        elif stripped.startswith("linux link:"):
            if not JS:
                out.append(f"// linux link: {stripped[11:].strip()}")  # (read by machine.make_exe)
        elif stripped in ("code:", "python:", "javascript:"):
            block = []
            while k < len(rows) and (not rows[k].strip() or rows[k][:1].isspace()):
                block.append(rows[k][2:] if rows[k].startswith("  ") else rows[k].lstrip())
                k += 1
            if stripped == "javascript:":
                if JS:
                    out += block
            elif stripped == "code:":
                if not JS:
                    out += block
            else:
                exec("\n".join(block), space)
        elif stripped.startswith("to ") and (" = " in stripped or web_only or runs_only):
            head, _, cpp = stripped.partition(" = ") if " = " in stripped else (stripped, "", "")
            try:
                words, _, inputs, gives = command_head(head + ":", line)
            except ScriptError as err:
                raise ScriptError(line, where + err.message)
            in_names = [" ".join(w) for w, _ in inputs]
            for in_name in in_names if not (web_only or runs_only or cpp.strip().startswith("c:")) else []:
                if "{" + in_name + "}" not in cpp:
                    raise ScriptError(line, where + f"the C++ doesn't use the input '{in_name}' (write it as {{{in_name}}}).")
            command = Command(cpp.strip(), [kd for _, kd in inputs], gives, in_names)
            command.usual = USUAL.get("".join(w.capitalize() for w in words), {})  # inputs that may be left out
            command.library = name
            word = " ".join(words)
            if cpp.strip().startswith("c:"):
                c_word(command, word, c_library, cpp.strip()[2:], where, line, out)
                names.commands[tuple(words)] = command
                continue

            def missing(*args, word=word):
                raise RunError(0, f"'{word}' (from the library '{name}') only works when the program is built into C++.")
            command.runner = missing
            names.commands[tuple(words)] = command
            pending = (where, in_names, lambda fn, command=command: setattr(command, "runner", fn))
            if JS:
                command.unusable = f"'{word}' (from the library '{name}') can't be used in a web program yet."

                def set_web(src, command=command):
                    command.cpp, command.unusable = src, None
                web = (where, in_names, set_web)
            elif web_only:
                command.unusable = f"'{word}' (from the library '{name}') only works in a program made for the web ('stellanova web')."
            elif runs_only and MAKING_CPP:
                command.unusable = f"'{word}' (from the library '{name}') only works when the program runs directly ('stellanova <script>'), not built."
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
            LIBRARY_VALUES[tuple(words)] = name
            if not read_only:
                raise ScriptError(line, where + "library words for values must be 'read only' for now.")

            def set_value(fn, holder=holder):
                holder["run"] = lambda env: fn()
            pending = (where, [], set_value)
            if runs_only and MAKING_CPP and not JS:
                names.known[tuple(words)] = (UNUSABLE + f"'{english.strip()}' (from the library '{name}') only works when the program runs directly ('stellanova <script>'), not built.",) + names.known[tuple(words)][1:]
            if JS or web_only:
                key = tuple(words)
                said = "can't be used in a web program yet." if JS else "only works in a program made for the web ('stellanova web')."
                names.known[key] = (UNUSABLE + f"'{english.strip()}' (from the library '{name}') {said}",) + names.known[key][1:]

                def set_web(src, key=key):
                    names.known[key] = (src,) + names.known[key][1:]
                web = (where, [], set_web)
        else:
            raise ScriptError(line, where + f"I don't understand '{stripped}'.\n{LIBRARY_HELP}")
    LIBRARY_HEADS[name] = "\n".join(out)
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
    """Returns the C++ text for one .stella file, or raises ScriptError."""
    global MAKING_CPP
    MAKING_CPP = True
    try:
        return read_script(path)[0]
    finally:
        MAKING_CPP = False


FILES = []  # the script, then each script it uses ('use: shapes.stella'), in the order they were read
PER_FILE = 100000  # a line number n in FILES[k] is kept as k * PER_FILE + n


def where(line):
    """'guess.stella line 3' for a kept line number."""
    k, n = divmod(line, PER_FILE)
    return f"{FILES[k] if k < len(FILES) else '?'} line {n}"


def run_where(line):
    """How an error while running names its line: 'Line 3' in the program itself, 'shapes.stella line 3' in a used script."""
    return f"Line {line}" if line < PER_FILE else where(line)


def gather(path, from_line=None, seen=None):
    """The lines of a script with every 'use: other.stella' line replaced by that script's lines.

    Returns (lines, numbers): numbers[i] is the kept line number of lines[i]."""
    seen = set() if seen is None else seen
    seen.add(path.resolve())
    k = len(FILES)
    FILES.append(path.name)
    own = source_text(path).splitlines()
    if len(own) >= PER_FILE:
        raise ScriptError(k * PER_FILE + 1, f"A script can have at most {PER_FILE - 1} lines.")
    lines, numbers = [], []
    for n, raw in enumerate(own, 1):
        SOURCE[k * PER_FILE + n] = raw.strip()
        if raw.strip().lower().startswith("note:"):
            raise ScriptError(k * PER_FILE + n, "'note:' is now 'whisper:'.")
        if raw.strip().lower().startswith("whisper:"):  # read as an inner 'note:' line
            raw = raw[:len(raw) - len(raw.lstrip())] + "note:" + raw.strip()[8:]
        m = re.fullmatch(r"\s*use:\s*(.+\.stella)\s*", raw, re.IGNORECASE)
        if m and not raw[:1].isspace():
            other = path.parent / m.group(1).strip()
            if not other.exists() and (HERE / "libraries" / m.group(1).strip()).exists():  # one of Stellanova's own
                other = HERE / "libraries" / m.group(1).strip()
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


GENERIC_COPIES = set()  # the kinds written out from a kind for any kind ('stack of numbers'): their commands may differ
GENERIC_HEAD = re.compile(r"an? ([a-z][a-z ]*?) of anything (?:has|is a kind of .+):", re.IGNORECASE)
GENERIC_FOR = re.compile(r"to .+?, for an? ([a-z][a-z ]*?) of anything\b.*:", re.IGNORECASE)
ANYTHING = re.compile(r"\banything\b(?! else)")


def expand_generics(lines, numbers):
    """Kinds for any kind: 'a stack of anything has:' (and commands 'to push, for a stack of anything, given x (anything):')
    are written out again for each kind the program uses them with, so 'a stack of numbers' is a kind of its own, with
    'anything' read as 'a number' (and 'of anything' as 'of numbers'). Each copy keeps the line numbers it came from."""
    def block_end(i):
        j = i + 1
        while j < len(lines) and not is_closing(lines[j]):
            j += 1
        return j

    generic = {}  # name -> [(start, end)] of its description and commands
    i, kept, kept_numbers = 0, [], []
    while i < len(lines):
        raw = lines[i]
        m = None if raw[:1].isspace() else (GENERIC_HEAD.fullmatch(raw.strip()) or GENERIC_FOR.fullmatch(raw.strip()))
        if m:
            end = block_end(i)
            generic.setdefault(m.group(1).lower(), []).append((lines[i:end + 1], numbers[i:end + 1]))
            kept.append(("generic", m.group(1).lower()))
            kept_numbers.append(None)
            i = end + 1
            continue
        kept.append(raw)
        kept_numbers.append(numbers[i])
        i += 1
    if not generic:
        return lines, numbers
    described = {m.group(1).lower() for raw in lines for m in [re.match(r"an? ([a-z][a-z ]*?) (?:has|is a kind of .+):", raw.strip(), re.IGNORECASE)] if m}
    names = "|".join(sorted((re.escape(g) for g in generic), key=len, reverse=True))
    use = re.compile(rf"\b({names})s? of ((?:[a-z]+ ?){{1,5}})", re.IGNORECASE)

    def kind_at(words):
        """the longest start of words that is a kind (as 'of ...' says it: 'numbers', 'lists of pets'): (kind, how many words)"""
        global THINGS
        saved, THINGS = THINGS, {name: [] for name in described}
        try:
            for n in range(len(words), 0, -1):
                phrase = " ".join(words[:n])
                if phrase == "anything":
                    continue
                kind = parse_kind(phrase) or (parse_kind(phrase[:-1]) if phrase.endswith("s") and " " not in phrase else None)
                if kind:
                    return kind, n
        finally:
            THINGS = saved
        return None, 0

    made = {}  # (generic, kind) -> the copy's name
    out, out_numbers = [], []
    pending = [(x, n) for x, n in zip(kept, kept_numbers)]

    def rewrite(raw):
        """uses of a generic kind, written the one way its copy is named ('stack of number' -> 'stack of numbers')"""
        if raw.lstrip().lower().startswith("note:"):
            return raw

        def one(m):
            kind, n = kind_at(m.group(2).split())
            if not kind:
                return m.group(0)
            rest = m.group(2).split()[n:]
            made.setdefault((m.group(1).lower(), kind), f"{m.group(1).lower()} of {plural(kind)}")
            tail = (" " + " ".join(rest) if rest else "") + (" " if m.group(2).endswith(" ") else "")
            return f"{m.group(0)[:len(m.group(1))]}{'s' if m.group(0)[len(m.group(1)):].startswith('s') else ''} of {plural(kind)}{tail}"
        return use.sub(one, raw)

    for x, n in pending:
        if isinstance(x, tuple):
            out.append(x)
            out_numbers.append(None)
        else:
            out.append(rewrite(x))
            out_numbers.append(n)
    copies = {}  # generic -> [lines and numbers of its copies]
    done = set()
    for _ in range(20):  # copies can use other generic kinds: write those out too
        new = [key for key in made if key not in done]
        if not new:
            break
        for name, kind in new:
            done.add((name, kind))
            for block, block_numbers in generic[name]:
                for raw, n in zip(block, block_numbers):
                    raw = re.sub(r"\bof anything\b(?! else)", "of " + plural(kind), raw)
                    raw = ANYTHING.sub(kind_name(kind), raw)
                    copies.setdefault(name, []).append((rewrite(raw), n))
    GENERIC_COPIES.update(made.values())
    lines, numbers = [], []
    for x, n in zip(out, out_numbers):
        if isinstance(x, tuple):
            for raw, number in copies.pop(x[1], []):
                lines.append(raw)
                numbers.append(number)
        else:
            lines.append(x)
            numbers.append(n)
    return lines, numbers


def read_script(path):
    """Reads one .stella file. Returns (C++ text, Program or None), or raises ScriptError.

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


DEFINITION = re.compile(r"to .+:|an? [a-z][a-z ]* (?:has|is a kind of .+):|the world remembers:")


def read_one(path, auto):
    global THINGS
    FILES.clear()
    lines, numbers = expand_generics(*gather(path))
    main_lines = sum(1 for x in numbers if x < PER_FILE)
    names, info, settings, out = None, {}, [], []
    commands = []  # (header text, line, body)
    things = []  # (name, line, [(line, field text)])
    remembered = []  # (line, 'score (a number)') from 'the world remembers:'
    OWNER_PARAMS.clear()
    libs, used = [], set()  # C++ that 'use:' libraries need, and their names
    THINGS = {}
    OWNERS.clear()
    PARENTS.clear()
    SECRET_PARTS.clear()
    ABLE.clear()
    machine.ABLE.clear()
    reset_fields()
    first = next((t.strip() for t in lines if t.strip() and not t.strip().startswith("note:")), "")
    if not first.startswith("this is part of:"):
        names, info = Names(), None  # a program of its own
        NAMES_NOW[0] = names
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
                cpp = f"Stellanova_{snake(path.stem.split())}::{snake(words)}"
                number = float(m.group(2))
                names.add(words, cpp, NUMBER, True, lambda env, number=number: number)
                SETTING_NUMBERS[cpp] = number
                value = m.group(2) if "." in m.group(2) else m.group(2) + ".0"
                settings.append(f"\t{snake(words)}: {value},{'  // ' + m.group(3) if m.group(3) else ''}" if JS else
                                f"\tconstexpr double {snake(words)} = {value};{'  // ' + m.group(3) if m.group(3) else ''}")
            continue
        if text_.lower() == "to start:":
            raise ScriptError(n, "'to start:' is now 'genesis:'.")
        if text_.lower() == "genesis:":
            j = i
            while j < len(lines) and (not lines[j].strip() or lines[j].strip().startswith("note:")):
                j += 1
            if j < len(lines) and DEFINITION.fullmatch(lines[j].strip().lower()):
                lines[j] = lines[j].strip()  # 'genesis:' over a definition only marks where it begins
                continue
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
                                  f"The command '{'genesis' if text_ == 'to start:' else text_[:-1]}' must end with the line '{CLOSING}', unindented, after its last indented line.")
            i += 1
            continue
        m = re.fullmatch(r'use the library "([^"]+)":', text_, re.IGNORECASE)
        if m:  # C functions from a library, one word for each: 'to beep, given ... = bool Beep(unsigned, unsigned)'
            rows = ["c library: " + m.group(1)]
            while i < len(lines) and lines[i][:1].isspace():
                word = lines[i].strip()
                if word and not word.startswith("note:"):
                    head, eq, spec = word.partition(" = ")
                    rows.append(f"{head} = c: {spec}" if eq and not spec.startswith("c:") else word)
                i += 1
            if i >= len(lines) or not is_closing(lines[i]):
                raise ScriptError(n, f"'use the library' must end with the line '{CLOSING}', unindented, after its words.")
            i += 1
            lib = "c library " + m.group(1)
            if lib in used:
                raise ScriptError(n, f"The library \"{m.group(1)}\" is already used above.")
            used.add(lib)
            libs += load_library(lib, n, names, rows)
            continue
        m = re.fullmatch(r'use python "([A-Za-z_][\w.]*)":', text_, re.IGNORECASE)
        if m:  # a Python package's functions, one word for each: 'to middle of, given xs (a list of numbers), returning a number = median'
            rows = ["runs only"]
            while i < len(lines) and lines[i][:1].isspace():
                word = lines[i].strip()
                if word and not word.startswith("note:"):
                    head, eq, path_ = word.partition(" = ")
                    if not eq or not re.fullmatch(r"[A-Za-z_][\w.]*", path_.strip()):
                        raise ScriptError(numbers[i], f"Each word looks like 'to middle of, given xs (a list of numbers), returning a number = median', with the package's function after the =.")
                    try:
                        _, _, ins_, gives_ = command_head(head + ":", numbers[i])
                    except ScriptError as err:
                        raise ScriptError(numbers[i], err.message)
                    given = "".join(", {" + " ".join(w) + "}" for w, _ in ins_)
                    rows += [head, f"  runs: py_call({m.group(1)!r}, {path_.strip()!r}, {gives_!r}{given})"]
                i += 1
            if i >= len(lines) or not is_closing(lines[i]):
                raise ScriptError(n, f"'use python' must end with the line '{CLOSING}', unindented, after its words.")
            i += 1
            lib = "python " + m.group(1)
            if lib in used:
                raise ScriptError(n, f"The Python package '{m.group(1)}' is already used above.")
            used.add(lib)
            libs += load_library(lib, n, names, rows)
            continue
        if text_.lower().startswith("use:"):  # a library ('use: x.stella' lines were already replaced by gather)
            lib = " ".join(text_[4:].split()).lower()
            if lib in auto:
                continue
            if lib in used:
                raise ScriptError(n, f"The library '{lib}' is already used above.")
            used.add(lib)
            libs += load_library(lib, n, names)
            continue
        able = re.fullmatch(r"an? ([a-z][a-z ]*?) is anything that can ([a-z][a-z ]*?)\.?", text_.lower())
        if able:  # a shared ability: any kind of thing with its own version of each command fits
            name = " ".join(able.group(1).split())
            if name in THINGS or name in BASIC_WORDS:
                raise ScriptError(n, f"There is already a kind of thing called '{name}'.")
            if UNREAL:
                raise ScriptError(n, "'anything that can' can't be used in Unreal parts yet.")
            THINGS[name] = []
            ABLE[name] = [tuple(w.split()) for w in re.split(r"\s+and\s+", able.group(2))]
            machine.ABLE["thing " + name] = []
            things.append((name, n, []))
            continue
        m = (re.fullmatch(r"an? ([a-z][a-z ]*?) is a kind of (?:an? )?([a-z][a-z ]*?)(?: that (?:also )?has)?:", text_.lower())
             or re.fullmatch(r"an? ([a-z][a-z ]*?) has:()", text_.lower()))
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
            if m.group(2):
                parent = " ".join(m.group(2).split())
                if parent not in THINGS:
                    raise ScriptError(n, f"Describe what a {parent} has above the {name}, so a {name} can be a kind of {parent}.")
                PARENTS[name] = parent
            things.append((name, n, fields))
            continue
        if text_.lower() == "the world remembers:":  # names every command can use and change
            while i < len(lines) and (not lines[i].strip() or lines[i][:1].isspace()):
                if lines[i].strip() and not lines[i].strip().startswith("note:"):
                    remembered.append((numbers[i], lines[i].strip()))
                i += 1
            if i >= len(lines) or not is_closing(lines[i]):
                raise ScriptError(numbers[i] if i < len(lines) else numbers[-1],
                                  f"'the world remembers:' must end with the line '{CLOSING}', unindented.")
            i += 1
            continue
        if is_closing(text_):
            raise ScriptError(n, f"'{CLOSING}' closes a command, so it goes right after the command's last indented line.")
        raise ScriptError(n, f"I don't know what to do with '{text_}'. Top-level lines are notes, 'use:', 'settings:', 'a ... has:', 'the world remembers:' or 'to ...:'.")
    if names is None:
        raise ScriptError(1, "The script is empty.")
    program = info is None
    if things and not program:
        raise ScriptError(things[0][1], "New kinds of things can only be described in programs for now.")
    structs = describe_things(things)
    if remembered and not program:
        raise ScriptError(remembered[0][0], "'the world remembers:' is for programs of their own (with 'genesis:').")
    structs += remember(remembered, names)
    commands = [listed_inputs(text_, n, body) for text_, n, body in commands]
    heads = [command_head(text_, n) for text_, n, _ in commands]
    made = []  # the Command for each head
    for (words, cpp, inputs, gives), (_, n, _) in zip(heads, commands):
        command = Command(cpp, [kind for _, kind in inputs], gives)
        command.line = n
        command.usual = USUAL.get(cpp, {})
        have = names.commands.get(tuple(words))
        if have is not None:
            owner = inputs[0][1] if cpp in OWNERS and inputs and is_thing(inputs[0][1]) else None
            if have.versions is None or owner is None or owner in have.versions:
                if getattr(have, "line", None) is None:
                    raise ScriptError(n, f"There is already a word called '{spoken(words)}' (from a library): rename this command.")
                first = where(have.line)
                if n // PER_FILE != have.line // PER_FILE:
                    raise ScriptError(n, f"There are two commands called '{spoken(words)}': this one, and one in {first}. "
                                         f"Rename one, or write 'to {spoken(words)}, privately' in the script that only uses it there.")
                raise ScriptError(n, f"There are two commands called '{spoken(words)}' (the other is at {first}): rename one.")
            copies = owner[6:] in GENERIC_COPIES and all(k[6:] in GENERIC_COPIES for k in have.versions)
            if not copies and (len(have.kinds) != len(command.kinds) or have.kinds[1:] != command.kinds[1:] or have.gives != gives):
                raise ScriptError(n, f"Every version of '{' '.join(words)}' must take the same inputs and return the same kind.")
            have.versions[owner] = command
        else:
            names.commands[tuple(words)] = command
            if cpp in OWNERS:
                command.versions = {inputs[0][1]: command}
        made.append(command)
    # A kind of pet does a pet's command the pet's way, unless it has its own version: the command is made again for it.
    extra, written = [], list(made)
    for head, (text_, n, body), command in zip(heads, commands, made):
        words, cpp, inputs, gives = head
        if cpp not in OWNERS or not inputs or not is_thing(inputs[0][1]):
            continue
        versions = names.commands[tuple(words)].versions
        own = {k: c for k, c in versions.items() if any(c is m for m in written)}  # written in the script, not made here
        for kind_ in ["thing " + k for k in THINGS if is_kind_of("thing " + k, inputs[0][1]) and "thing " + k != inputs[0][1]]:
            if kind_ in versions or nearest_version(own, kind_) is not command:
                continue
            copy = Command(cpp, [kind_] + command.kinds[1:], gives)
            copy.usual = command.usual
            versions[kind_] = copy
            extra.append(((words, cpp, [(inputs[0][0], kind_)] + inputs[1:], gives), (text_, n, body), copy))
    for item in extra:
        heads.append(item[0])
        commands.append(item[1])
        made.append(item[2])
    for able in ABLE:  # the kinds a saved speaker may be loaded as
        machine.ABLE["thing " + able] = ["thing " + k for k in THINGS if can("thing " + k, able)]
        if JS:
            structs.append(f"stellanova::able_kinds({json.dumps(able)}, {json.dumps([k[6:] for k in machine.ABLE['thing ' + able]])});")
    if JS:
        for (words, cpp, inputs, gives), command in zip(heads, made):
            command.js = f"{cpp}_{snake(inputs[0][1][6:].split())}" if cpp in OWNERS and inputs and is_thing(inputs[0][1]) else cpp
    if program:
        if ("start",) not in names.commands and not PLUGIN and "engine" not in used:  # (the engine calls a plugin's commands)
            raise ScriptError(main_lines or 1, "A program needs a 'genesis:' command: that is where it begins.")
        if ("start",) in names.commands and (names.commands[("start",)].kinds or names.commands[("start",)].gives):
            raise ScriptError(next(n for (w, *_), (_, n, _) in zip(heads, commands) if w == ["start"]),
                              "'genesis:' has no inputs and gives nothing back.")
    functions = [function(head, n, body, names, info, command) for head, (_, n, body), command in zip(heads, commands, made)]
    if JS:
        if not program:
            raise ScriptError(1, "Only programs of their own (with 'genesis:') can be made for the web.")
        files = json.dumps(FILES, ensure_ascii=False)
        ns = [f"const Stellanova_{snake(path.stem.split())} = {{"] + settings + ["};", ""] if settings else []
        body = js_dots("\n".join(structs + ns + out + [""] + only_waiting_async(functions)))
        top = [f"// Generated from {path.name} by stellanova.py. Edit the .stella file, not this one.",
               "(async () => {",
               'const { stellanova, FMath, FVector, FVector2D } = globalThis.stellanova || require("./stellanova.js");', ""]
        return "\n".join(top + libs + [body, f"await stellanova.main({files}, Start);", "})();"]) + "\n", Program(names.commands)
    if program:
        protos = [f"{cpp_type(gives) if gives else 'void'} {cpp}({params(cpp, inputs)});"
                  for _, cpp, inputs, gives in heads]
        head = [f"// Generated from {path.name} by stellanova.py. Edit the .stella file, not this one.",
                '#include "stellanova.h"', ""] + libs + structs + protos + [""]
        files = ", ".join('"' + f.replace("\\", "\\\\").replace('"', '\\"') + '"' for f in FILES)
        start = "int StellanovaMain()\n{\n\tint count = 0;\n\tchar** given = nullptr;" if UNREAL else "int main(int count, char** given)\n{"
        functions.append(f"{start}\n\tstellanova::begin({{{files}}}, count, given);\n\ttry\n\t{{\n\t\tStart();\n\t\tstellanova::wait_for_others();\n\t}}\n"
                         f"\tcatch (const stellanova::Problem& problem)\n\t{{\n\t\tstellanova::report(problem);\n\t\treturn 1;\n\t}}\n\treturn 0;\n}}\n")
    else:
        # The class's header must declare each command, so they can call each other (C++ needs that).
        wanted = [f"//   {cpp_type(gives) if gives else 'void'} {cpp}({params(cpp, inputs)});"
                  for _, cpp, inputs, gives in heads]
        head = [f"// Generated from {path.name} by stellanova.py. Edit the .stella file, not this one.",
                f"// {info['header']} declares these in {info['class']}:"] + wanted + [
                f'#include "{info["header"]}"', ""] + libs
    ns = [f"namespace Stellanova_{snake(path.stem.split())}", "{"] + settings + ["}", ""] if settings else []
    return "\n".join(head + ns + out + [""] + functions) + "\n", Program(names.commands) if program else None


SHARED = {}  # the values of 'the world remembers:' names, while a program runs directly


def remember(rows, names):
    """'the world remembers:' lines: names every command shares. Returns the C++ (or JavaScript) that makes them."""
    SHARED.clear()
    WORLD_KINDS.clear()
    out = []
    for n, text_ in rows:
        m = re.fullmatch(r"([a-z][a-z ]*?)\s*\(([a-z ]+)\)", text_.lower())
        kind = m and parse_kind(m.group(2))
        if not kind:
            raise ScriptError(n, f"Each name the world remembers looks like 'score (a number)'. Kinds are: {kind_words()}.")
        words = m.group(1).split()
        if bad_name(words):
            raise ScriptError(n, f"'{' '.join(words)}' can't be a name: it uses the language's own words.")
        if tuple(words) in names.known:
            raise ScriptError(n, f"'{' '.join(words)}' already means something, so the world can't remember it as a name.")
        cpp = "world_" + snake(words)
        things = THINGS
        SHARED[cpp] = None

        def get(env, cpp=cpp, kind=kind, things=things):
            if SHARED[cpp] is None:
                SHARED[cpp] = py_zero(kind, things)
            return SHARED[cpp]

        def put(env, x, cpp=cpp):
            SHARED[cpp] = dup(x)
        get.pyf = lambda get=get: f"{py_part(get)}(None)"
        put.py_store = lambda x, put=put: f"{py_part(put)}(None, {x})"
        names.add(words, cpp, kind, False, (get, put))
        WORLD_KINDS[cpp] = kind
        out.append(f"let {cpp} = {js_zero(kind)};" if JS else f"inline {cpp_type(kind)} {cpp} = {zero(kind)};")
    return out + ([""] if out else [])


def describe_things(things):
    """Reads 'a pet has:' descriptions; returns the C++ structs."""
    machine.THINGS.clear()
    described = set()
    for name, n, fields in things:
        if name in PARENTS:
            for words, kind in THINGS[PARENTS[name]]:
                THINGS[name].append((words, kind))
                if ("thing " + PARENTS[name], tuple(words)) in SECRET_PARTS:
                    SECRET_PARTS["thing " + name, tuple(words)] = SECRET_PARTS["thing " + PARENTS[name], tuple(words)]
                FIELDS.setdefault(tuple(words), {})["thing " + name] = (snake(words), kind)
        elif not fields and name not in ABLE:
            raise ScriptError(n, f"Say what a {name} has, one thing per indented line, like: name (text)")
        for fn, text_ in fields:
            m = re.fullmatch(r"([a-z][a-z ]*?)\s*\(([a-z ]+?)(\s*,\s*hidden)?\)", text_.lower())
            kind = m and parse_kind(m.group(2))
            if not kind:
                raise ScriptError(fn, f"Each thing a {name} has looks like 'name (text)'. Kinds are: {kind_words()}.")
            if kind == "thing " + name:
                raise ScriptError(fn, f"A {name} can't hold a whole {name} inside itself, but it can hold a list of {name}s.")
            if is_thing(kind) and kind[6:] not in described:
                raise ScriptError(fn, f"Describe what a {kind[6:]} has above the {name}, or hold a list of {kind[6:]}s.")
            words = m.group(1).split()
            if bad_name(words):
                raise ScriptError(fn, f"'{' '.join(words)}' can't be a name: it uses the language's own words.")
            if any(w == words for w, _ in THINGS[name]):
                raise ScriptError(fn, f"A {name} already has a part called '{' '.join(words)}'" + (f" (every {PARENTS[name]} has one)." if name in PARENTS else "."))
            THINGS[name].append((words, kind))
            FIELDS.setdefault(tuple(words), {})["thing " + name] = (snake(words), kind)
            if m.group(3):  # 'balance (a number, hidden)'
                SECRET_PARTS["thing " + name, tuple(words)] = "thing " + name
        if any(w == ["birth"] for w, _ in THINGS[name]) and not any(w == ["existence"] for w, _ in THINGS[name]):
            kind = next(k for w, k in THINGS[name] if w == ["birth"])  # where it is now, next to where it started
            THINGS[name].insert(next(i for i, (w, _) in enumerate(THINGS[name]) if w == ["birth"]) + 1, (["existence"], kind))
            FIELDS.setdefault(("existence",), {})["thing " + name] = ("existence", kind)
        described.add(name)
        machine.THINGS["thing " + name] = [(snake(w), w, k) for w, k in THINGS[name]]
    out = []
    if things and JS:
        for name, _, _ in things:
            cls = js_class("thing " + name)
            fields = " ".join(f"this.{snake(w)} = {js_zero(k)};" for w, k in THINGS[name])
            spec = ", ".join(json.dumps([" ".join(w), snake(w), k]) for w, k in THINGS[name])
            out.append(f"class {cls} {{ constructor() {{ {fields} }} }}")
            out.append(f"stellanova::kind({cls}, {json.dumps(name)}, [{spec}]);")
        return out + [""]
    if things:
        out.append("namespace stellanova\n{")
        out += [f"\tstruct {cpp_type('thing ' + name)};" for name, _, _ in things]
        for name, _, _ in things:
            cpp = cpp_type("thing " + name)
            out.append(f"\tstruct {cpp}\n\t{{")
            out += [f"\t\t{cpp_type(k)} {snake(w)} = {zero(k)};" for w, k in THINGS[name]]
            parent = PARENTS.get(name)
            while parent:
                pc = cpp_type("thing " + parent)
                copies = " ".join(f"p.{snake(w)} = {snake(w)};" for w, _ in THINGS[parent])
                out.append(f"\t\toperator {pc}() const {{ {pc} p; {copies} return p; }}")
                parent = PARENTS.get(parent)
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
            loads = "".join(f' if (auto p = d.part("{" ".join(w)}"); p && p->type != SavedData::Nothing && !load(*p, v.{snake(w)})) return false;' for w, k in THINGS[name])
            out.append(f"\tinline bool load(const SavedData& d, {cpp}& v) {{ if (d.type != SavedData::Table) return false; v = {cpp}{{}};{loads} return true; }}")
        out.append("}")
        out += [f"using stellanova::{cpp_type('thing ' + name)};" for name, _, _ in things]
        out.append("")
    return out


INPUT_LINE = re.compile(r"((?:[a-z][a-z' ]*?))\s*\(([a-z ]+)\)")


def listed_inputs(header, line, body):
    """'to tell, use:' with the inputs on the indented lines under it -> the same command as 'to tell, given ...:'.

    The inputs are the first lines, each 'name (kind)'; the first line that isn't one starts the instructions."""
    m = re.fullmatch(r"(to .+?),\s*(?:use|using|utilize):", header.strip().lower())
    if not m:
        return header, line, body
    if ", given " in m.group(1):
        raise ScriptError(line, "Give the inputs either after 'given' or on the lines under 'use:', not both.")
    inputs, k = [], 0
    rows = [(n, raw) for n, raw in body]
    while k < len(rows):
        n, raw = rows[k]
        s = " ".join(w for w in raw.strip().lower().split() if w not in ARTICLES)
        if not s or s.startswith("note:") or raw.strip().lower().startswith("whisper:"):
            k += 1
            continue
        im = INPUT_LINE.fullmatch(s)
        if not im:
            break
        if not parse_kind(im.group(2)):
            raise ScriptError(n, f"'{im.group(2)}' isn't a kind, so '{raw.strip()}' can't be an input. Kinds are: {kind_words()}.")
        inputs.append(f"{im.group(1).strip()} ({im.group(2).strip()})")
        k += 1
    if not inputs:
        raise ScriptError(line, "Under 'use:', list each input on its own indented line, like 'title (text)', before the instructions.")
    for n, raw in rows[k:]:
        s = " ".join(w for w in raw.strip().lower().split() if w not in ARTICLES)
        im = INPUT_LINE.fullmatch(s)
        if im and parse_kind(im.group(2)):
            raise ScriptError(n, f"'{raw.strip()}' looks like an input, but it is among the instructions. "
                                 "Inputs go together right under 'use:', before the first instruction.")
    head, back, gives = m.group(1).partition(", returning ")  # 'given' goes before 'returning'
    return f"{head}, given {' and '.join(inputs)}{back}{gives}:", line, rows[k:]


def command_head(header, line):
    """'to greet, given name (text):' -> (['greet'], 'Greet', [(['name'], TEXT)], None)."""
    if "giving back" in header.lower():
        raise ScriptError(line, "'giving back' is now 'returning'.")
    private = re.match(r"to [a-z ]+?, privately(?=[,:])", header.lower())
    if private:  # 'to helper, privately:' only its own script can use it
        header = header[:private.end() - len(", privately")] + header[private.end():]
    m = re.fullmatch(r"to ([a-z ]+?)(?:, for an? ([a-z ]+?))?(?:, given (.+?))?(?:, returning (.+))?:", header.lower())
    if not m:
        raise ScriptError(line, "A command starts like 'to steer toward, given goal (a place) and running (yes or no):'.")
    inputs = []
    words = m.group(1).split() + ([f"privately{line // PER_FILE}"] if private else [])
    if m.group(2):  # a command for a kind of thing: it gets that thing and can change it
        owner = " ".join(m.group(2).split())
        if owner not in THINGS:
            raise ScriptError(line, f"There is no kind of thing called '{owner}'." + (f" Kinds of things: {', '.join(THINGS)}." if THINGS else ""))
        inputs.append((owner.split(), "thing " + owner))
        OWNERS["".join(w.capitalize() for w in words)] = "thing " + owner
    usual = {}
    if m.group(3):
        given = header[m.start(3):m.end(3)]  # as written: a usual value's text keeps its capitals
        for part in re.split(r"\s+and\s+(?=[A-Za-z ]+\()", given):
            pm = re.fullmatch(r"([A-Za-z ]+?)\s*\(([A-Za-z ]+?)(?:\s*,\s*usually\s+(.+?))?\s*\)", part.strip())
            kind = pm and parse_kind(pm.group(2).lower())
            if not kind:
                raise ScriptError(line, f"An input looks like 'goal (a place)', or 'name (text, usually \"friend\")'. Kinds are: {kind_words()}.")
            if pm.group(3) is not None:
                if not re.fullmatch(r'"[^"]*"|-?\d+(?:\.\d+)?|yes|no', pm.group(3).strip(), re.IGNORECASE):
                    raise ScriptError(line, "A usual value is written out, like 'usually \"friend\"', 'usually 3' or 'usually yes'.")
                usual[len(inputs)] = pm.group(3).strip()
            elif usual:
                raise ScriptError(line, "Inputs with a usual value go last, after the ones without.")
            inputs.append((pm.group(1).lower().split(), kind))
    USUAL["".join(w.capitalize() for w in words)] = usual
    gives = None
    if m.group(4):
        gives = parse_kind(m.group(4))
        if not gives:
            raise ScriptError(line, f"'returning' needs a kind, like 'returning a number'. Kinds are: {kind_words()}.")
    return words, "".join(w.capitalize() for w in words), inputs, gives


USUAL = {}  # a command's C++ name -> {input number: the value it usually has, as written}


def is_kind_of(kind, other):
    """Is a dog (or a kind of dog) a pet?"""
    while kind != other and is_thing(kind) and kind[6:] in PARENTS:
        kind = "thing " + PARENTS[kind[6:]]
    return kind == other


machine.HAS_KINDS_OF = lambda kind: any(is_kind_of("thing " + k, kind) for k in PARENTS if "thing " + k != kind)


def can(kind, able):
    """Can this kind of thing do everything the ability needs?"""
    commands = NAMES_NOW[0].commands if NAMES_NOW[0] else {}
    return kind[6:] not in ABLE and all(w in commands and commands[w].versions and nearest_version(commands[w].versions, kind)
                                        for w in ABLE[able])


def fit(v, kind):
    """v as the kind wanted: itself, a dog made into a pet (a copy with just a pet's parts), or a dog as a speaker (itself,
    all its parts kept). None if it can't be."""
    if v.kind == kind:
        return v
    if is_thing(v.kind) and is_thing(kind) and kind[6:] in ABLE and can(v.kind, kind[6:]):
        same = Value(v.cpp, kind, v.run)
        return with_ir(same, lambda f: machine.emit(f, v))
    if is_thing(v.kind) and is_thing(kind) and is_kind_of(v.kind, kind):
        get, name, things = v.run, kind[6:], THINGS
        made = f"stellanova::as_kind({strip_parens(v.cpp)}, {js_class(kind)})" if JS else f"{cpp_type(kind)}({strip_parens(v.cpp)})"
        return with_ir(Value(made, kind, lambda env: as_kind(get(env), name, things)),
                       lambda f: f.op(f"call ptr @cn_as_kind(ptr {machine.emit(f, v)}, ptr {f.spec(kind)})"))
    return None


def as_kind(thing, name, things):
    if thing is None:
        return None
    new = Thing.__new__(Thing)
    new.name, new.spec = name, things[name]
    new.fields = {snake(w): dup(thing.fields[snake(w)]) for w, _ in new.spec}
    return new


def nearest_version(versions, kind):
    """The version of a command for this kind of thing, or for the closest kind it is a kind of."""
    while kind not in versions and is_thing(kind) and kind[6:] in PARENTS:
        kind = "thing " + PARENTS[kind[6:]]
    return versions.get(kind)


def params(cpp, inputs):
    """The C++ inputs of a command; the thing a command is for is passed so the command can change it."""
    return ", ".join((f"{cpp_type(k)}& " if i == 0 and cpp in OWNERS else param_type(k) + " ") + snake(w)
                     for i, (w, k) in enumerate(inputs))


def machine_name(cpp, inputs):
    """A command's name in machine code: a command for a kind of thing has one version per kind ('Bounce__ball')."""
    return f"{cpp}__{snake(inputs[0][1][6:].split())}" if cpp in OWNERS and inputs and is_thing(inputs[0][1]) else cpp


def function(head, line, body, names, info, command=None):
    words, name, inputs, gives = head
    local = Names()
    local.known = dict(names.known)
    local.commands = names.commands
    local.gives = gives
    OWNER_NOW[0] = inputs[0][1] if name in OWNERS and inputs and is_thing(inputs[0][1]) else None
    if any(cpp_type("thing " + t) == name for t in THINGS):
        raise ScriptError(line, f"The command '{' '.join(words)}' has the same name as a kind of thing. Give one of them another name.")
    for k, (in_words, kind) in enumerate(inputs):
        if k == 0 and name in OWNERS:
            own = snake(in_words)

            def put_all(env, x, own=own):
                env[own].fields = dup(x).fields  # change the caller's thing itself, not a copy
            own_get = lambda env, own=own: env[own]
            own_get.pyf = lambda own=own: f"env[{own!r}]"
            local.add(in_words, own, kind, False, (own_get, put_all))
            OWNER_PARAMS.add(own)
            OWNER_KINDS[own] = kind
            for part_words, part_kind in THINGS[kind[6:]]:
                member = snake(part_words)

                def get(env, own=own, member=member):
                    return env[own].fields[member]
                get.pyf = lambda own=own, member=member: f"env[{own!r}].fields[{member!r}]"

                def put(env, x, own=own, member=member):
                    env[own].fields[member] = dup(x)
                put.py_store = lambda x, own=own, member=member, part_kind=part_kind: f"env[{own!r}].fields[{member!r}] = {py_copy(x, part_kind)}"
                local.add(part_words, f"{own}.{member}", part_kind, False, (get, put))
        else:
            local.add(in_words, snake(in_words), kind, read_only=True)
    declared = {}
    code, run = statements(body, local, declared, 1)
    hoisted = [f"\t{'let' if JS else cpp_type(k)} {c} = {zero(k)};" for c, k in declared.values()]
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
        made = command or names.commands[tuple(words)]
        made.runner = runner
        if FAST and not (WATCHING or DEBUG is not None or PROFILE is not None or MAKING_CPP or JS):
            zeros = [(c, k) for c, k in declared.values() if c not in param_names]
            made.runner = py_command(name, param_names, zeros, lambda: py_zero(gives, things) if gives else None, run) or runner
        # what machine.py needs to write this command (a command for a kind of thing can't be made into machine code yet)
        made.machine = (machine_name(name, inputs), [(snake(w), k) for w, k in inputs], gives, run)
    if JS:
        title = getattr(command, "js", name) if command else name
        return "\n".join([f"async function {title}({', '.join(snake(w) for w, _ in inputs)})", "{"]
                         + hoisted + code + end + ["}"]) + "\n"
    return "\n".join([f"{cpp_type(gives) if gives else 'void'} {owner}{name}({params(name, inputs)})", "{"]
                     + hoisted + code + end + ["}"]) + "\n"


def only_waiting_async(functions):
    """Web commands are made async so they can wait (for a web page, a timer, the person). Async calls cost time,
    so a command stays async only if it waits itself or calls one that does; the rest become plain functions."""
    titles = {re.match(r"async function (\w+)\(", f).group(1): f for f in functions}
    call = re.compile(r"await (\w+)\(")
    waits = {name for name, f in titles.items() if "await" in call.sub(lambda m: "" if m.group(1) in titles else m.group(0), f)}
    grew = True
    while grew:
        grew = False
        for name, f in titles.items():
            if name not in waits and any(m.group(1) in waits for m in call.finditer(f)):
                waits.add(name)
                grew = True

    def plain(m):
        return m.group(0) if m.group(1) in waits or m.group(1) not in titles else f"{m.group(1)}("
    return [call.sub(plain, f if name in waits else f.replace("async function", "function", 1)) for name, f in titles.items()]


# ---------------------------------------------------------------- lines inside a command

def statements(body, names, declared, depth):
    """Reads an indented block. body: list of (line number, raw text). Returns (C++ lines, run)."""
    out, runs = [], []
    rows = [(n, r) for n, r in body if r.strip()]
    indent = len(rows[0][1].expandtabs(4)) - len(rows[0][1].expandtabs(4).lstrip()) if rows else 0
    rows = watch_rows(rows, indent)
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
            handlers = []  # (kind of problem or None for any, its lines)
            while k < len(rows) and len(rows[k][1].expandtabs(4)) - len(rows[k][1].expandtabs(4).lstrip()) == indent:
                m = WENT_WRONG.fullmatch(rows[k][1].strip().lower())
                if not m:
                    break
                if handlers and handlers[-1][0] is None:
                    raise ScriptError(rows[k][0], "The plain 'if that went wrong:' catches every problem, so it goes last.")
                hn = rows[k][0]
                k += 1
                handler = []
                while k < len(rows) and len(rows[k][1].expandtabs(4)) - len(rows[k][1].expandtabs(4).lstrip()) > indent:
                    handler.append(rows[k])
                    k += 1
                if not handler:
                    raise ScriptError(hn, "Say what to do on the indented lines below the ':'.")
                handlers.append((m.group(1) and " ".join(m.group(1).split()), handler))
            if not handlers:
                raise ScriptError(n, "'try:' needs an 'if that went wrong:' line after its indented lines, at the same indent.")
            if not inner:
                raise ScriptError(n, "Say what to do on the indented lines below the ':'.")
            lines, run = attempt(n, inner, handlers, names, declared, depth)
            out += lines
            chain = None
            runs.append(run)
            continue
        if WENT_WRONG.fullmatch(raw.strip().lower()):
            raise ScriptError(n, "'if that went wrong:' goes right after the indented lines of a 'try:'.")
        if raw.strip().lower().startswith("holding the lock ") and raw.strip().endswith(":"):
            lines, run = holding(n, raw.strip()[len("holding the lock "):-1], inner, names, declared, depth)
            out += lines
            chain = None
            runs.append(run)
            continue
        if raw.strip().lower().startswith("depending on ") and raw.strip().endswith(":"):
            start = k - 1 - len(inner)
            rows = rows[:start] + depending_rows(n, raw.strip(), inner, indent) + rows[k:]
            k = start
            continue
        words_ = raw.strip().lower().split()
        if (words_[:1] == ["check"] and not inner
                and not any(tuple(words_[:len(key)]) == key for key in names.commands if key[0] == "check")):  # not 'check fuel with 5'
            pad = raw[:len(raw) - len(raw.lstrip())]
            what = raw.strip()[6:].strip()
            shown = what.replace('"', "'").replace("[", "(").replace("]", ")")
            rows[k - 1:k] = [(n, f"{pad}if not ({what}):"), (n, f'{pad}  raise an error with "this check failed: {shown}"')]
            k -= 1
            continue
        said = raw.strip()
        lines, run, branch = statement(n, said if said.startswith("note:") else surface(said, n), inner, names, declared, depth)
        out += lines
        if branch:
            which, cond = branch
            if WATCHING and cond is not None:
                cond = watched_test(cond, n)
            if which == "if":
                chain = [(cond, run)]
                pick = choose(chain)
                pick.line_n = n
                # the whole choice is the if line's (its test too), so it stops and is timed even when the test is no
                if DEBUG is not None:
                    pick = debugged(pick, n)
                if PROFILE is not None:
                    pick = profiled(pick, n)
                runs.append(pick)
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


DIGIT_WORDS = "zero one two three four five six seven eight nine".split()


def top_commas(text):
    """text split at its commas that aren't inside quote marks or brackets."""
    parts, depth, quoted, start = [], 0, False, 0
    for i, ch in enumerate(text):
        if ch == '"':
            quoted = not quoted
        elif not quoted and ch == "(":
            depth += 1
        elif not quoted and ch == ")":
            depth -= 1
        elif not quoted and depth == 0 and ch == ",":
            parts.append(text[start:i].strip())
            start = i + 1
    return parts + [text[start:].strip()]


def depending_rows(n, said, inner, indent):
    """'depending on weather:' with lines like '"rain": ...' and 'anything else: ...', as the if / otherwise if lines it
    means. The value is worked out once, into a name of its own."""
    subject = said[len("depending on"):].rstrip()[:-1].strip()
    if not subject:
        raise ScriptError(n, "Say what to look at, like 'depending on weather:'.")
    if not inner:
        raise ScriptError(n, "Put the choices on the indented lines below, like '\"rain\": scrawl \"Take an umbrella\"'.")
    held = "depending value " + " ".join(DIGIT_WORDS[int(d)] for d in str(n))
    pad = " " * indent
    out = [(n, f"{pad}set {held} to {subject}")]
    width = len(inner[0][1].expandtabs(4)) - len(inner[0][1].expandtabs(4).lstrip())
    first, other = True, False
    for m, raw in inner:
        here = len(raw.expandtabs(4)) - len(raw.expandtabs(4).lstrip())
        if here > width:  # a choice's own indented lines
            out.append((m, pad + "    " + raw.expandtabs(4)[width:]))
            continue
        if here < width:
            raise ScriptError(m, "This line is indented differently from the lines around it.")
        head, colon, rest = split_colon(raw.strip())
        if not colon:
            raise ScriptError(m, "Each choice is the value, a ':', then what to do, like '\"rain\": scrawl \"Take an umbrella\"'.")
        if other:
            raise ScriptError(m, "'anything else:' is the last choice.")
        if head.strip().lower() == "anything else":
            if first:
                raise ScriptError(m, "Put at least one choice before 'anything else:'.")
            out.append((m, f"{pad}otherwise:{(' ' + rest.strip()) if rest.strip() else ''}"))
            other = True
            continue
        test = " or ".join(f"{held} is ({v})" for v in top_commas(head))
        out.append((m, f"{pad}{'if' if first else 'otherwise if'} {test}:{(' ' + rest.strip()) if rest.strip() else ''}"))
        first = False
    return out


def watch_rows(rows, indent):
    """'whenever <something>:', 'every 2 seconds:' and 'every frame:' blocks, taken out of rows and put in a loop after
    the other lines: it goes on until the world ends ('every frame:' is there) or the program ends.
    'whenever' runs its lines each time its yes-or-no turns to yes; the frame is revealed after each round on its own."""
    def width(raw):
        return len(raw.expandtabs(4)) - len(raw.expandtabs(4).lstrip())

    kept, watches, k = [], [], 0
    while k < len(rows):
        n, raw = rows[k]
        k += 1
        inner = []
        while k < len(rows) and width(rows[k][1]) > indent:
            inner.append(rows[k])
            k += 1
        low = raw.strip().lower()
        if width(raw) == indent and low.endswith(":") and (low.startswith("whenever ") or low.startswith("every ")):
            head = raw.strip()[:-1].strip()
            if not inner:
                raise ScriptError(n, "Say what to do on the indented lines below the ':'.")
            if low.startswith("whenever "):
                watches.append(("whenever", head[len("whenever "):].strip(), n, inner))
            elif low == "every frame:":
                watches.append(("frame", None, n, inner))
            else:
                m = re.fullmatch(r"every (.+?) seconds?", head, re.IGNORECASE)
                if not m:
                    raise ScriptError(n, "Write 'every 2 seconds:' or 'every frame:'.")
                watches.append(("every", m.group(1), n, inner))
            continue
        kept.append((n, raw))
        kept += inner
    if not watches:
        return rows
    pad, deep = " " * indent, " " * (indent + 4)
    framed = any(w[0] == "frame" for w in watches)
    first = watches[0][2]
    out = list(kept)
    loop = []
    for kind, what, n, inner in watches:
        name = " ".join(DIGIT_WORDS[int(d)] for d in str(n))
        base = width(inner[0][1])

        def body(more):
            return [(m, deep + " " * more + raw.expandtabs(4)[base:]) for m, raw in inner]
        if kind == "whenever":
            out.append((n, f"{pad}set whenever was {name} to no"))
            loop += [(n, f"{deep}set whenever now {name} to ({what})"),
                     (n, f"{deep}if whenever now {name} and not whenever was {name}:")] + body(4)
            loop.append((n, f"{deep}set whenever was {name} to whenever now {name}"))
        elif kind == "every":
            out.append((n, f"{pad}set every next {name} to seconds since the start plus ({what})"))
            loop += [(n, f"{deep}if not (seconds since the start falls below every next {name}):"),
                     (n, f"{deep}    set every next {name} to every next {name} plus ({what})")] + body(4)
        else:
            loop += body(0)
    out.append((first, f"{pad}as long as {'the world lives' if framed else 'yes'}:"))
    out += loop
    out.append((first, f"{deep}{'reveal the frame' if framed else 'wait 0.01'}"))
    return out


def holding(n, which, inner, names, declared, depth):
    """'holding the lock "total":' - only one command at a time runs the indented lines (or any others holding that
    lock): the rest wait their turn. For names commands going alongside ('meanwhile') share."""
    if not inner:
        raise ScriptError(n, "Say what to do on the indented lines below the ':'.")
    for k, raw in inner:
        if re.match(r"(return|give back|break free|stop the loop|move on|skip to the next)\b", raw.strip().lower()):
            raise ScriptError(k, "Lines holding a lock can't leave it partway (with return, break free or move on): let them finish.")
    lock = expr_to_end(tokenize(which, n), 0, names, n)
    if lock.kind != TEXT:
        raise ScriptError(n, f"A lock is named with text, like: holding the lock \"total\":")
    tab = "\t" * depth
    body_lines, body = statements(inner, names, declared, depth + 1)
    get = lock.run

    def run(env):
        with named_lock(get(env)):
            body(env)

    def write(f):
        name = f.hold(machine.emit(f, lock))
        f.put(f"call void @cn_lock(ptr {name})")
        let_go, end = f.label("letgo"), f.label("held")
        f.handlers.append(let_go)
        machine.emit(f, body)
        f.handlers.pop()
        f.put(f"call void @cn_unlock(ptr {name})")
        f.jump(end)
        f.place(let_go)  # a problem inside: let the lock go, then on to where problems go
        f.put(f"call void @cn_unlock(ptr {name})")
        f.check()
        f.jump(end)
        f.place(end)
    with_ir(run, write)
    held = f"held_{n}"
    if JS:
        return ([f"{tab}const {held} = {strip_parens(lock.cpp)};", f"{tab}await stellanova::lock({held});", f"{tab}try", tab + "{"]
                + body_lines + [tab + "}", f"{tab}finally", tab + "{", f"{tab}\tstellanova::unlock({held});", tab + "}"]), run
    return [tab + "{", f"{tab}\tstellanova::Held {held}({strip_parens(lock.cpp)});"] + body_lines + [tab + "}"], run


WENT_WRONG = re.compile(r"if that went wrong(?: with an? ([a-z][a-z ]*))?:")


def attempt(n, tried, handlers, names, declared, depth):
    """try: ... if that went wrong with a fuel problem: ... if that went wrong: ...
    Each handler takes its kind of problem (None: any); a problem no handler takes goes on, as if there were no try.
    Inside a handler, 'the problem' is what went wrong, as text."""
    tab = "\t" * depth
    try_lines, try_run = statements(tried, names, declared, depth + 1)
    key = ("the", "problem")
    if key in names.known:
        raise ScriptError(n, "There is a 'try:' inside the 'if that went wrong:' of another one. Put it in a command of its own.")
    cpp = f"the_problem_{n}"
    names.add(key, cpp, TEXT, read_only=True)
    fixes = []  # (kind, lines, run, the kind as a text value)
    try:
        for kind, handler in handlers:
            lines, fix = statements(handler, names, declared, depth + 2)
            fixes.append((kind, lines, fix, kind and expr_to_end(tokenize(json.dumps(kind), n), 0, names, n)))
    finally:
        del names.known[key]

    def run(env):
        try:
            try_run(env)
        except RunError as err:
            for kind, _, fix, _ in fixes:
                if kind is None or kind == err.kind:
                    env[cpp] = err.message
                    fix(env)
                    return
            raise
    with_ir(run, lambda f: machine.attempt(f, try_run, cpp, [(k, fix, v) for k, _, fix, v in fixes]))
    caught = f"stellanova_problem_{n}"
    out = [f"{tab}try", tab + "{"] + try_lines + [tab + "}"]
    if JS:
        out += [f"{tab}catch ({caught})", tab + "{", f"{tab}\tconst {cpp} = stellanova::problem_text({caught});"]
        kind_of = f"stellanova::problem_kind({caught})"
    else:
        out += [f"{tab}catch (const stellanova::Problem& {caught})", tab + "{", f"{tab}\tconst std::string {cpp} = {caught}.message;"]
        kind_of = f"{caught}.kind"
    for k, (kind, lines, _, _) in enumerate(fixes):
        test = "if (true)" if kind is None else f"if ({kind_of} == {json.dumps(kind)})"
        out += [f"{tab}\t{'else ' if k else ''}{test}", tab + "\t{"] + lines + [tab + "\t}"]
    if fixes[-1][0] is not None:
        out.append(f"{tab}\telse throw{' ' + caught if JS else ''};")
    return out + [tab + "}"], run


def choose(chain):
    def run(env):
        for cond, then in chain:
            if cond is None or cond(env):
                then(env)
                return

    def pyl(tab):
        out = []
        for k, (cond, then) in enumerate(chain):
            head = "else:" if cond is None else f"{'elif' if k else 'if'} {py_expr(cond)}:"
            out += [(None, tab + head)] + py_lines(then, tab + "    ")
        return out
    run.pyl = pyl
    return with_ir(run, lambda f: machine.choose(f, chain))


def block(runs):
    runs = tuple(runs)

    def run(env):
        for f in runs:
            f(env)
    run.pyl = lambda tab: [x for r in runs for x in py_lines(r, tab)] or [(None, tab + "pass")]

    def write(f):
        for r in runs:
            at = len(f.lines)
            f.put("call void @cn_statement()")  # what the line before made may be freed
            machine.emit(f, r)
            if f.lines[at] == "  call void @cn_statement()" and machine.makes_nothing(f.lines[at + 1:]):
                del f.lines[at]  # a line that makes nothing leaves nothing to free
    return with_ir(run, write)


WATCHING = False  # 'stellanova watch': each line is shown as it runs, with the names it changed
SOURCE = {}  # a kept line number -> the line as it was written
HIDDEN = ("depending_value", "whenever_was", "whenever_now", "every_next")  # names Stellanova makes for itself


def names_shown(env):
    out = {}
    for k, v in env.items():
        if not k.startswith(HIDDEN) and not callable(v):
            try:
                s = text(v)
            except Exception:
                continue
            out[re.sub(r"_\d+$", "", k).replace("_", " ")] = s if len(s) <= 70 else s[:67] + "..."  # (a loop's name ends in its line)
    return out


def watch_line(n, after=""):
    sys.stdout.flush()
    where_ = f"line {n}" if n < PER_FILE else where(n)
    print(f"\u25b8 {where_}: {SOURCE.get(n, '?')}{after}", flush=True)


TESTED = threading.local()  # the line whose test was just shown ('if ...: -> yes'), so it isn't shown twice


def watched(run, n):
    """run, showing its line before it runs and the names it changed after (a line with indented lines below leaves
    the changes to them)."""
    def go(env):
        if getattr(TESTED, "line", None) != n:
            watch_line(n)
        TESTED.line = None
        if SOURCE.get(n, "").endswith(":"):
            return run(env)
        before = names_shown(env)
        try:
            run(env)
        finally:
            for k, v in names_shown(env).items():
                if before.get(k) != v:
                    print(f"    {k}: {v}", flush=True)
    return go


def watched_test(cond, n):
    def go(env):
        answer = cond(env)
        watch_line(n, f"   \u2192 {'yes' if answer else 'no'}")
        TESTED.line = n if answer else None
        return answer
    return go


DEBUG = None  # 'stellanova debug': where to stop, and how it goes on from a stop (see debug_pause)
DEBUG_HELP = ("Enter or step: run this line, stop at the next one.  over: run this line and any commands it calls.  "
              "out: run until this command gives back.  go: run until the next stop.  names: the names and what they hold.  "
              "look <name>: one name.  stop at <line> / forget <line>: add or remove a stop.  stops: the stops.  quit: end the program.")


def debug_pause(env, n):
    """Before line n: stops if it is a stop, or the last command (step, over, out) says so; then waits for commands."""
    d = DEBUG
    envs = d["envs"]  # each running command has its own names, so they tell how deep the program is
    if any(e is env for e in envs):
        while envs[-1] is not env:
            envs.pop()
    else:
        envs.append(env)
    depth, mode = len(envs), d["mode"]
    if not (n in d["stops"] or mode == "step" or (mode == "over" and depth <= d["depth"]) or (mode == "out" and depth < d["depth"])):
        return
    sys.stdout.flush()
    where_ = f"line {n}" if n < PER_FILE else where(n)
    names = names_shown(env)
    while True:
        if d["studio"]:  # one marked line the studio reads (and doesn't show as printed)
            print("@@debug " + json.dumps({"line": n, "where": where_, "source": SOURCE.get(n, ""), "depth": depth,
                                              "names": names, "stops": sorted(d["stops"])}), flush=True)
        else:
            print(f"■ {where_}: {SOURCE.get(n, '?')}", flush=True)
        while True:
            if not d["studio"]:
                print("(debug) ", end="", flush=True)
            said = sys.stdin.readline()
            if not said:
                d["mode"] = "go"  # nothing more to read: carry on to the end
                return
            words = said.strip().lower().split()
            what = " ".join(words)
            if what in ("", "step", "s"):
                d["mode"] = "step"
                return
            if what in ("over", "o", "next", "n"):
                d.update(mode="over", depth=depth)
                return
            if what == "out":
                d.update(mode="out", depth=depth)
                return
            if what in ("go", "g", "c"):
                d["mode"] = "go"
                return
            if what in ("quit", "q"):
                print("(the program was ended)", flush=True)
                sys.stdout.flush()
                os._exit(1)
            if what == "names":
                if not d["studio"]:
                    print("\n".join(f"    {k}: {v}" for k, v in names.items()) or "    (no names yet)", flush=True)
            elif words[:1] == ["look"] and len(words) > 1:
                wanted = " ".join(words[1:])
                print(f"    {wanted}: {names[wanted]}" if wanted in names else f"    there is no name '{wanted}' here.", flush=True)
            elif words[:2] == ["stop", "at"] or words[:1] == ["forget"]:
                number = words[-1]
                if not number.isdigit():
                    print("    say a line number, like: stop at 12", flush=True)
                elif words[0] == "stop":
                    d["stops"].add(int(number))
                else:
                    d["stops"].discard(int(number))
                if d["studio"]:
                    break  # show the stop again, with the stops as they are now
            elif what == "stops":
                print("    stops: " + (", ".join(map(str, sorted(d["stops"]))) or "none"), flush=True)
            else:
                print("    " + DEBUG_HELP, flush=True)
            if d["studio"]:
                break


PROFILE = None  # 'stellanova profile': line -> [times run, seconds with what it runs, its own seconds]
PROFILE_INSIDE = threading.local()  # the seconds spent in the lines inside the line running now


def profiled(run, n):
    def go(env):
        outer = getattr(PROFILE_INSIDE, "seconds", 0.0)
        PROFILE_INSIDE.seconds = 0.0
        began = time.perf_counter()
        try:
            return run(env)
        finally:
            took = time.perf_counter() - began
            row = PROFILE.setdefault(n, [0, 0.0, 0.0])
            row[0] += 1
            row[1] += took
            row[2] += took - PROFILE_INSIDE.seconds
            PROFILE_INSIDE.seconds = outer + took
    return go


def profile_report():
    """The lines that took the most time, after a 'stellanova profile' run."""
    rows = sorted(PROFILE.items(), key=lambda kv: -kv[1][2])[:20]
    if not rows:
        return
    total = sum(r[2] for _, r in PROFILE.items()) or 1e-12
    print("\nWhere the time went (the 20 slowest lines, by their own time):", flush=True)
    print(f"{'line':>12}  {'runs':>9}  {'own time':>10}  {'share':>5}  {'with inside':>11}  the line", flush=True)
    for n, (count, inclusive, own) in rows:
        where_ = f"{n}" if n < PER_FILE else where(n)
        source = SOURCE.get(n, "?")
        print(f"{where_:>12}  {count:>9}  {own:>9.3f}s  {own / total:>5.0%}  {inclusive:>10.3f}s  {source if len(source) <= 60 else source[:57] + '...'}", flush=True)


def debugged(run, n):
    def go(env):
        debug_pause(env, n)
        return run(env)
    return go


def guard(run, n):
    """Turns a surprise inside Stellanova into a plain message with the line it happened on."""
    if WATCHING and not getattr(run, "watched", False):
        run = watched(run, n)
        run.watched = True
    if DEBUG is not None and not getattr(run, "debugged", False):
        run = debugged(run, n)
        run.debugged = True
    if PROFILE is not None and not getattr(run, "profiled", False):
        run = profiled(run, n)
        run.profiled = True

    def guarded(env):
        try:
            run(env)
        except (RunError, Flow, SystemExit, KeyboardInterrupt):
            raise
        except RecursionError:
            raise RunError(n, "commands called each other too many times in a row (they may never stop).")
        except Exception as err:
            raise RunError(n, f"Stellanova itself went wrong here; this is not a mistake in your program. Please tell whoever looks after Stellanova: {err}")
    guarded.inner = run  # so a missing piece is named by what it really is
    guarded.line_n = n
    return with_ir(guarded, getattr(run, "ir", None))


def statement(n, text_, inner, names, declared, depth):
    """One line (with its indented lines). Returns (C++ lines, run, branch); branch is set for if/otherwise lines."""
    tab = "\t" * depth
    READING_FILE[0] = n // PER_FILE
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
        tokens = read_words(head, n, names)
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
            run.pyl = lambda tab: py_loop(f"while {py_expr(v)}:", then, tab)
            with_ir(run, lambda f: machine.loop(f, lambda: machine.emit(f, v), then))
            return [f"{tab}while ({strip_parens(v.cpp)})", tab + "{"] + lines + [tab + "}"], run, None
        if tokens[-1:] != ["times"]:
            raise ScriptError(n, "'repeat' looks like 'repeat 10 times:'.")
        count = expr_to_end(tokens[:-1], 1, names, n)
        if count.kind != NUMBER:
            raise ScriptError(n, f"'repeat' needs a number of times, but this is {kind_name(count.kind)}.")
        lines, then = body(loop=True)
        k = f"stellanova_count_{depth}_{n}"
        times = count.run

        def run(env):
            c = times(env)
            for _ in range(int(c) if math.isfinite(c) else 0):
                if not then(env):
                    break
        run.pyl = lambda tab: py_loop(f"for _ in _reps({py_expr(count)}):", then, tab)
        with_ir(run, lambda f: machine.repeat(f, count, then))
        if JS:
            head = f"{tab}for (let {k} = 0, {k}_end = stellanova::repeats({strip_parens(count.cpp)}); {k} < {k}_end; ++{k})"
            return [head, tab + "{"] + lines + [tab + "}"], run, None
        return [f"{tab}for (long long {k} = 0; {k} < (long long)({strip_parens(count.cpp)}); ++{k})", tab + "{"] + lines + [tab + "}"], run, None
    if colon and re.match(r"(if |otherwise\b)", text_):
        tokens = read_words(head, n, names)
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
            test = with_ir(v.run, v.ir)
        lines, then = body()
        if which == "if":
            then.debugged = then.profiled = True  # the choice holding it does these (see block)
        return [line, tab + "{"] + lines + [tab + "}"], guard(then, n), (which, test)
    if inner:
        raise ScriptError(inner[0][0], "Only 'if', 'otherwise', 'repeat', 'as long as', 'for each' and 'try' lines can have indented lines under them.")
    tokens = read_words(text_, n, names)
    if tokens in (["stop", "the", "loop"], ["skip", "to", "the", "next", "one"], ["skip", "to", "the", "next"]):
        if not names.loops:
            said = "break free" if tokens[0] == "stop" else "move on"
            raise ScriptError(n, f"'{said}' only works inside 'repeat', 'as long as' or 'for each'.")
        leave = tokens[0] == "stop"

        def run(env):
            raise LeaveLoop() if leave else NextRound()
        run.pyl = lambda tab: [(None, tab + ("break" if leave else "continue"))]
        with_ir(run, lambda f: f.jump(f.loops[-1][1 if leave else 0]))
        return [f"{tab}{'break' if leave else 'continue'};"], run, None
    if tokens == ["stop"]:
        if names.gives:
            raise ScriptError(n, f"This command returns {kind_name(names.gives)}, so leave it with 'return ...' instead of 'cease'.")

        def run(env):
            raise Stop()
        run.pyl = lambda tab: [(None, tab + "return None")]
        with_ir(run, lambda f: f.finish_with("ret void"))
        return [f"{tab}return;"], run, None
    if tokens == ["wait", "for", "the", "others"]:
        run = with_ir(lambda env: wait_for_others(), lambda f: f.put("call void @cn_wait_for_others()"))
        return [f"{tab}{'await ' if JS else ''}stellanova::wait_for_others();"], run, None
    if tokens[0] == "meanwhile":  # 'meanwhile download with ...': the command goes on alongside the lines after this one
        rest = tokens[1 + (tokens[1:2] == [","]):]
        key, size = match_command(names, rest)
        if rest[:1] == ["invoke"]:
            e = Expr(rest, names, n)
            e.allow_nothing = True
            v = e.single()
            if e.i != len(e.t):
                raise ScriptError(n, f"I don't understand '{' '.join(e.t[e.i:])}' here.")
            cpp, run = strip_parens(v.cpp), v.run
        elif key:
            if names.commands[key].versions is not None:
                raise ScriptError(n, f"'{' '.join(key)}' changes the thing it is given, so it can't run alongside the rest.")
            start = size + (rest[size:size + 1] == ["with"])
            more = rest[start:]
            if more[:1] == ["("] and more[-1:] == [")"] and closing_bracket(more, 0) == len(more) - 1 and "," in more:
                more = more[1:-1]
            cpp, run = call(key, expr_list(more, 0, names, n), names, n)
        else:
            raise ScriptError(n, "'meanwhile' starts a command going alongside the rest, like 'meanwhile count down with 10'." + library_hint(rest))
        if JS:  # shortcut: it sees the names as they are when it runs, not a copy made when it started
            return [f"{tab}stellanova::meanwhile(async () => {{ {cpp}; }});"], lambda env: meanwhile(run, env), None
        piece = v if rest[:1] == ["invoke"] else run
        return ([f"{tab}stellanova::meanwhile([=]() {{ {cpp}; }});"],
                with_ir(lambda env: meanwhile(run, env), lambda f: machine.meanwhile(f, piece)), None)
    if tokens[0] == "invoke":
        e = Expr(tokens, names, n)
        e.allow_nothing = True
        v = e.single()
        if e.i != len(e.t):
            raise ScriptError(n, f"I don't understand '{' '.join(e.t[e.i:])}' here.")
        get = v.run
        return [f"{tab}{strip_parens(v.cpp)};"], with_ir(lambda env: get(env) and None, lambda f: machine.emit(f, v) and None), None
    if tokens[0] == "shatter":  # 'raise an error with "no fuel"': a problem of your own, caught by try: like any other
        v = expr_to_end(tokens, 2 if tokens[1:2] == ["with"] else 1, names, n)
        if v.kind != TEXT:
            raise ScriptError(n, f"'raise an error with' needs text saying what went wrong, not {kind_name(v.kind)}.")
        get = v.run

        def run(env):
            raise RunError(n, get(env))
        with_ir(run, lambda f: (f.put(f"call void @cn_raise(i32 {n}, ptr {machine.emit(f, v)})"), f.check()))
        return [f"{tab}stellanova::fail({n}, {strip_parens(v.cpp)});"], run, None
    if tokens[0] == "raise" and "with" in tokens[2:]:  # 'raise a fuel problem with "the tank is empty"': a kind of problem
        cut = tokens.index("with", 2)
        kind = " ".join(tokens[1:cut])
        if not re.fullmatch(r"[a-z][a-z ]*", kind):
            raise ScriptError(n, "Name the kind of problem in plain words, like: raise a fuel problem with \"the tank is empty\"")
        v = expr_to_end(tokens, cut + 1, names, n)
        if v.kind != TEXT:
            raise ScriptError(n, f"'raise a {kind} with' needs text saying what went wrong, not {kind_name(v.kind)}.")
        get, kind_v = v.run, expr_to_end(tokenize(json.dumps(kind), n), 0, names, n)

        def run(env):
            raise RunError(n, get(env), kind)
        with_ir(run, lambda f: (f.put(f"call void @cn_raise_kind(i32 {n}, ptr {machine.emit(f, v)}, ptr {machine.emit(f, kind_v)})"), f.check()))
        return [f"{tab}stellanova::fail({n}, {strip_parens(v.cpp)}, {json.dumps(kind)});"], run, None
    if tokens[:2] == ["give", "back"]:
        if not names.gives:
            raise ScriptError(n, "'return' only works in a command that says what it returns, like 'to double, given x (a number), returning a number:'.")
        v = expr_to_end(tokens, 2, names, n)
        v = fit(v, names.gives) or v
        if v.kind != names.gives:
            raise ScriptError(n, f"This command returns {kind_name(names.gives)}, not {kind_name(v.kind)}.")
        get = v.run

        def run(env):
            raise GiveBack(get(env))
        run.pyl = lambda tab: [(None, f"{tab}return {py_expr(v)}")]
        with_ir(run, lambda f: f.finish_with(f"ret {machine.ll_type(v.kind)} {machine.emit(f, v)}"))
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
        shown = with_ir(Value("", TEXT, None), lambda f: f.as_text(machine.emit(f, v), v.kind))
        with_ir(run, lambda f: machine.wrap(f, "builtins", "", f"stellanova::{fn}({{s0}}, {{s1}}, {{line}})", [where, shown], None, cpp_type, n))
        return [f"{tab}stellanova::{fn}({strip_parens(where.cpp)}, stellanova::text({strip_parens(v.cpp)}), {n});"], run, None
    if tokens[0] == "add" and "to" in tokens:
        cut = len(tokens) - 1 - tokens[::-1].index("to")
        target = expr_to_end(tokens[cut + 1:], 0, names, n)
        if target.kind == NUMBER:  # 'add 1 to count': the number goes up
            if not target.writable:
                raise ScriptError(n, f"'{' '.join(tokens[cut + 1:])}' can't be changed.")
            v = expr_to_end(tokens[:cut], 1, names, n)
            if v.kind != NUMBER:
                raise ScriptError(n, f"'{' '.join(tokens[cut + 1:])}' is a number, so I can only add a number to it, not {kind_name(v.kind)}.")
            put, now, get = target.store, target.run, v.run
            assign = js_set(target) if JS else getattr(target, "cpp_assign", None) or f"{strip_parens(target.cpp)} = "
            write = (lambda f: target.ir_store(f, number_ir(f, "+", target, v))) if target.ir_store else None
            return ([f"{tab}{assign}{target.cpp} + {v.cpp}{getattr(target, 'cpp_close', '')};"],
                     with_ir(lambda env: put(env, now(env) + get(env)), write), None)
        if not is_list(target.kind):
            raise ScriptError(n, f"'add ... to' needs a list or a number, but this is {kind_name(target.kind)}.")
        target = writable_list(tokens[cut + 1:], names, n, "add to")
        v = expr_to_end(tokens[:cut], 1, names, n)
        v = fit(v, element(target.kind)) or v
        if v.kind != element(target.kind):
            raise ScriptError(n, f"This list holds {plural(element(target.kind))}, so I can't add {kind_name(v.kind)} to it.")
        seq, get = target.run, v.run
        added = with_ir(lambda env: seq(env).append(dup(get(env))),
                        lambda f: f.add_number(machine.owned(f, target), machine.emit(f, v)) if v.kind == NUMBER else
                        f.put(f"call void @cn_list_add(ptr {machine.owned(f, target)}, ptr {f.box(machine.emit(f, v), v.kind)})"))
        added.pyl = lambda tab: [(None, f"{tab}{py_expr(target)}.append({py_expr(v) if v.kind in (NUMBER, YESNO, TEXT) else '_dup(' + py_expr(v) + ')'})")]
        if JS:
            return [f"{tab}({target.cpp}).push({js_copy(v.cpp, v.kind)});"], added, None
        return [f"{tab}({target.cpp}).push_back({strip_parens(v.cpp)});"], added, None
    if tokens[0] == "insert" and "at" in tokens and "in" in tokens:
        cut = len(tokens) - 1 - tokens[::-1].index("in")
        if "at" not in tokens[:cut]:
            raise ScriptError(n, "Write 'insert ... at <number> in <list>', like: insert \"tea\" at 2 in drinks.")
        at_cut = cut - 1 - tokens[:cut][::-1].index("at")
        target = writable_list(tokens[cut + 1:], names, n, "insert in")
        raw = expr_to_end(tokens[:at_cut], 1, names, n)
        v = fit(raw, element(target.kind)) or raw
        if v.kind != element(target.kind):
            raise ScriptError(n, f"This list holds {plural(element(target.kind))}, so I can't put {kind_name(v.kind)} in it.")
        index = expr_to_end(tokens[:cut], at_cut + 1, names, n)
        if index.kind != NUMBER:
            raise ScriptError(n, f"'insert ... at' needs a number for the place, but this is {kind_name(index.kind)}.")
        seq, get, at = target.run, v.run, index.run
        inserted = with_ir(lambda env: insert_at(seq(env), at(env), dup(get(env)), n),
                           lambda f: f.call("void", "cn_list_insert", ("ptr", machine.owned(f, target)), ("double", machine.emit(f, index)),
                                            ("ptr", f.box(machine.emit(f, v), v.kind)), ("i32", n), checked=True))
        if JS:
            return [f"{tab}stellanova.insert_item({target.cpp}, {strip_parens(index.cpp)}, {js_copy(v.cpp, v.kind)}, {n});"], inserted, None
        return [f"{tab}stellanova::insert_item({target.cpp}, {strip_parens(index.cpp)}, {strip_parens(v.cpp)}, {n});"], inserted, None
    if tokens[:2] == ["remove", "entry"] and "from" in tokens:
        cut = len(tokens) - 1 - tokens[::-1].index("from")
        table = expr_to_end(tokens, cut + 1, names, n)
        if not is_table(table.kind) or not table.writable:
            raise ScriptError(n, f"'remove entry ... from' needs a table that can be changed, but this is {kind_name(table.kind)}.")
        key = key_text(expr_to_end(tokens[:cut], 2, names, n), n)
        get, at = table.run, key.run
        return ([f"{tab}stellanova::remove_entry({table.cpp}, {strip_parens(key.cpp)}, {n});"],
                with_ir(lambda env: remove_entry(get(env), at(env), n),
                        lambda f: f.call("void", "cn_entry_remove", ("ptr", machine.owned(f, table)), ("ptr", machine.emit(f, key)),
                                         ("i32", n), checked=True)), None)
    if tokens[0] == "remove" and "from" in tokens:
        cut = len(tokens) - 1 - tokens[::-1].index("from")
        target = writable_list(tokens[cut + 1:], names, n, "remove from")
        seq = target.run
        if tokens[1] == "item":
            index = expr_to_end(tokens[:cut], 2, names, n)
            if index.kind != NUMBER:
                raise ScriptError(n, f"'remove item' needs a number, but this is {kind_name(index.kind)}.")
            at = index.run

            def run(env):
                items = seq(env)
                items.pop(index_of(items, at(env), n))
            with_ir(run, lambda f: f.call("void", "cn_list_remove_item", ("ptr", machine.owned(f, target)),
                                          ("double", machine.emit(f, index)), ("i32", n), checked=True))
            return [f"{tab}stellanova::remove_item({target.cpp}, {strip_parens(index.cpp)}, {n});"], run, None
        v = expr_to_end(tokens[:cut], 1, names, n)
        if v.kind != element(target.kind):
            raise ScriptError(n, f"This list holds {plural(element(target.kind))}, so it has no {kind_name(v.kind)} to remove.")
        get = v.run

        def run(env):
            items, x = seq(env), get(env)
            if x in items:
                items.remove(x)
        with_ir(run, lambda f: f.put(f"call void @cn_list_remove_value(ptr {machine.owned(f, target)}, ptr {f.box(machine.emit(f, v), v.kind)})"))
        return [f"{tab}stellanova::remove_value({target.cpp}, {strip_parens(v.cpp)});"], run, None
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
        run.pyl = lambda tab: [(None, f"{tab}print({' + '.join('_text(' + py_expr(g) + ')' for g in gets)})")]
        with_ir(run, lambda f: f.put(f"call void @cn_say(ptr {join_ir(f, parts)})"))
        shown = ', '.join('stellanova::text(' + strip_parens(p.cpp) + ')' for p in parts)
        return [f"{tab}stellanova::say([{shown}]);" if JS else f"{tab}stellanova::say({{{shown}}});"], run, None
    if tokens[0] == "ask":
        return ask(tokens, names, declared, n, tab)
    if tokens[0] == "load" and "from" in tokens and tokens[len(tokens) - tokens[::-1].index("from"):][:2] == ["the", "text"]:
        cut = len(tokens) - 1 - tokens[::-1].index("from")
        source = expr_to_end(tokens, cut + 3, names, n)
        if source.kind != TEXT:
            raise ScriptError(n, f"'load ... from the text' needs text, but this is {kind_name(source.kind)}.")
        e = Expr(tokens[1:cut], names, n)
        target = e.full() if cut > 1 else None
        if not target or e.i != len(e.t) or not target.writable or getattr(target, "cpp_assign", None):
            raise ScriptError(n, f"'{' '.join(tokens[1:cut])}' can't be changed, so I can't load into it.")
        if holds_command(target.kind):
            raise ScriptError(n, "A command can't be loaded.")
        put, kind, things, w = target.store, target.kind, THINGS, source.run
        if JS:
            return ([f"{tab}{js_set(target)}stellanova::load_text({strip_parens(source.cpp)}, {json.dumps(target.kind)}, {cpp_text(chr(34) + kind_name(target.kind) + chr(34))}, {n}){getattr(target, 'cpp_close', '')};"],
                    lambda env: put(env, load_text(w(env), kind, things, n)), None)
        run = with_ir(lambda env: put(env, load_text(w(env), kind, things, n)), load_ir(target, source, "load_text", n))
        return ([f"{tab}stellanova::load_text({strip_parens(target.cpp)}, {strip_parens(source.cpp)}, {cpp_text(chr(34) + kind_name(target.kind) + chr(34))}, {n});"],
                run, None)
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
                run = with_ir(lambda env: write_file(w(env), saved(get(env), kind, n) + "\n", n),
                              lambda f: f.put_checked(f"call void @cn_save_file(ptr {f.box(machine.emit(f, v), v.kind)}, ptr {machine.emit(f, where)}, "
                                                      f"ptr {f.shape(v.kind)}, i32 {n})"))
                shown = f", {json.dumps(kind)}" if JS else ""
                return [f"{tab}stellanova::save_file({strip_parens(v.cpp)}, {strip_parens(where.cpp)}, {n}{shown});"], run, None
            e = Expr(tokens[1:cut], names, n)
            target = e.full()
            if e.i != len(e.t) or not target.writable or getattr(target, "cpp_assign", None):
                raise ScriptError(n, f"'{' '.join(tokens[1:cut])}' can't be changed, so I can't load into it.")
            put, kind, things = target.store, target.kind, THINGS
            if JS:
                return ([f"{tab}{js_set(target)}stellanova::load_file({strip_parens(where.cpp)}, {json.dumps(target.kind)}, {cpp_text(chr(34) + kind_name(target.kind) + chr(34))}, {n}){getattr(target, 'cpp_close', '')};"],
                        lambda env: put(env, load_saved(w(env), kind, things, n)), None)
            run = with_ir(lambda env: put(env, load_saved(w(env), kind, things, n)), load_ir(target, where, "load_file", n))
            return ([f"{tab}stellanova::load_file({strip_parens(target.cpp)}, {strip_parens(where.cpp)}, {cpp_text(chr(34) + kind_name(target.kind) + chr(34))}, {n});"],
                    run, None)
    key, size = match_command(names, tokens)
    if key:
        start = size + (tokens[size:size + 1] == ["with"])
        rest = tokens[start:]
        if rest[:1] == ["("] and rest[-1:] == [")"] and closing_bracket(rest, 0) == len(rest) - 1 and "," in rest:
            rest = rest[1:-1]  # 'move along with (b, 2)': the inputs may be in brackets here too
        args = expr_list(rest, 0, names, n)
        cpp, run = call(key, args, names, n)
        if getattr(run, "ir", None):
            write = run.ir
            inner = run
            run = with_ir(lambda env, run=run: run(env), lambda f: write(f) and None)
            run.inner = inner
        return [f"{tab}{cpp};"], run, None
    if tokens[0] == "set" and "to" in tokens and ("of" in tokens[1:tokens.index("to")] or tokens[1:2] in (["item"], ["entry"])):
        cut = tokens.index("to")
        e = Expr(tokens[1:cut], names, n)
        target = e.full()
        if e.i != len(e.t) or not target.writable:
            raise ScriptError(n, f"'{' '.join(tokens[1:cut])}' can't be changed.")
        v = expr_to_end(tokens, cut + 1, names, n)
        v = fit(v, target.kind) or v
        if v.kind != target.kind:
            raise ScriptError(n, f"'{' '.join(tokens[1:cut])}' holds {kind_name(target.kind)}, not {kind_name(v.kind)}.")
        put, get = target.store, v.run
        assign = getattr(target, "cpp_assign", None) or f"{strip_parens(target.cpp)} = "
        if JS:
            assign = js_set(target)
        write = (lambda f: target.ir_store(f, machine.emit(f, v))) if target.ir_store else None
        run = with_ir(lambda env: put(env, get(env)), write)
        if getattr(put, "py_store", None):
            run.pyl = lambda tab: [(None, tab + put.py_store(py_expr(v)))]
        return [f"{tab}{assign}{js_copy(v.cpp, v.kind)}{getattr(target, 'cpp_close', '')};"], run, None
    if tokens[0] == "set":
        key, size = names.match(tokens, 1)
        if key and tokens[1 + size:2 + size] == ["to"]:
            cpp, kind, read_only, _ = names.known[key]
            if read_only:
                raise ScriptError(n, f"'{' '.join(key)}' can't be changed by a script.")
            v = expr_to_end(tokens, 2 + size, names, n)
            v = fit(v, kind) or v
            if v.kind != kind:
                raise ScriptError(n, f"'{' '.join(key)}' holds {kind_name(kind)}, not {kind_name(v.kind)}.")
            put, get = names.value(key).store, v.run
            if key == ("birth",) and names.known.get(("existence",), (None, None))[1] == kind:
                there = names.value(("existence",)).store

                def run(env):
                    x = get(env)
                    put(env, x)
                    there(env, dup(x))
                birth, existence = names.value(key), names.value(("existence",))
                if birth.ir_store and existence.ir_store:
                    def write(f):
                        x = machine.emit(f, v)
                        birth.ir_store(f, x)
                        existence.ir_store(f, x)
                    with_ir(run, write)
                return [f"{tab}{cpp} = {js_copy(v.cpp, v.kind)};", f"{tab}{names.known[('existence',)][0]} = {js_copy(cpp, kind)};"], run, None
            if JS and cpp in OWNER_PARAMS:  # the thing a command is for: change the caller's own
                return [f"{tab}stellanova::replace_thing({cpp}, {strip_parens(v.cpp)});"], lambda env: put(env, get(env)), None
            target = names.value(key)
            write = (lambda f: target.ir_store(f, machine.emit(f, v))) if target.ir_store else None
            if write and kind == TEXT and getattr(getattr(v, "joined", [None])[0], "local_name", None) == cpp:
                def write(f, plain=write):  # 'set s to s plus ...': added onto s (a name this command keeps)
                    if cpp in f.slots and cpp not in f.module.shared:
                        f.append(cpp, v.joined[1:])
                    else:
                        plain(f)
            run = with_ir(lambda env: put(env, get(env)), write)
            if getattr(put, "py_store", None):
                run.pyl = lambda tab: [(None, tab + put.py_store(py_expr(v)))]
            return [f"{tab}{cpp} = {js_copy(v.cpp, v.kind)};"], run, None
        hint = library_hint(tokens)
        if hint:
            raise ScriptError(n, f"I don't know '{' '.join(tokens[:tokens.index('to') + 1] if 'to' in tokens else tokens)}'." + hint)
        if "to" not in tokens:
            raise ScriptError(n, "'set' looks like 'set speed to 5'.")
        words = tokens[1:tokens.index("to")]
        if not words or bad_name(words) or any(not w[0].isalpha() for w in words):
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

            def write(f):
                x = machine.emit(f, v)
                f.store(cpp, v.kind, x)
                f.store("existence", v.kind, x)
            with_ir(run, write)
            return [f"{tab}{cpp} = {js_copy(v.cpp, v.kind)};", f"{tab}existence = {js_copy(cpp, v.kind)};"], run, None

        def run(env):
            env[cpp] = dup(get(env))
        run.pyl = lambda tab: [(None, f"{tab}env[{cpp!r}] = {py_copy(py_expr(v), v.kind)}")]
        with_ir(run, lambda f: f.store(cpp, v.kind, machine.emit(f, v)))
        return [f"{tab}{cpp} = {js_copy(v.cpp, v.kind)};"], run, None
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
        s = f"stellanova_step_{depth}_{n}"
        target = names.value(key)
        now, put, g, st = target.run, target.store, goal.run, step.run

        def run(env):
            x, by = now(env), st(env)
            put(env, min(max(g(env), x - by), x + by))
        return [f"{tab}const {'' if JS else 'double '}{s} = {strip_parens(step.cpp)};",
                f"{tab}{cpp} = FMath::Clamp({strip_parens(goal.cpp)}, {cpp} - {s}, {cpp} + {s});"], run, None
    hint = library_hint(tokens)
    if hint:
        raise ScriptError(n, f"I don't know how to start a line with '{tokens[0]}'." + hint)
    for k in names.commands:
        if hidden_from_here(k) and tuple(tokens[:len(k) - 1]) == k[:-1]:
            raise ScriptError(n, private_message(k))
    near = similar_words(tokens, names)
    if near:
        raise ScriptError(n, f"I don't know '{' '.join(tokenize(text_, n)[:4])}'." + near)  # as written, with its grammar
    starts = ["set", "move", "scrawl", "ask", "add", "insert", "remove", "inscribe", "if", "otherwise", "repeat", "as long as", "for each",
              "try", "return", "raise an error with", "cease", "whisper", "depending on", "whenever", "every", "meanwhile",
              "invoke", "save", "load", "conjure", "break free", "move on"] + [spoken(k) for k in names.commands if not hidden_from_here(k)]
    for size in (3, 2, 1):  # a misspelt first word (or words): the nearest way a line can start
        guess = difflib.get_close_matches(" ".join(tokens[:size]), [s for s in starts if len(s.split()) == size], n=1, cutoff=0.75)
        if guess:
            raise ScriptError(n, f"I don't know how to start a line with '{' '.join(tokens[:size])}'. Did you mean '{guess[0]}'?")
    raise ScriptError(n, f"I don't know how to start a line with '{tokens[0]}'. Lines start with set, move, scrawl, ask, add, remove, inscribe, if, otherwise, repeat, as long as, for each, depending on, whenever, every, try, return, raise an error with, cease, whisper or the name of a command.")


def for_each(n, head, body, names, declared, depth):
    """for each score in scores:  /  for each n from 1 to 10:"""
    tab = "\t" * depth
    tokens = read_words(head, n, names)
    cut = next((k for k, t in enumerate(tokens) if t in ("in", "from")), None)
    words = tokens[2:cut] if cut else []
    if not words or bad_name(words) or any(not w[0].isalpha() for w in words):
        raise ScriptError(n, "'for each' looks like 'for each score in scores:' or 'for each n from 1 to 10:'.")
    before = names.known.get(tuple(words))  # a name already set here: each item for the loop, then what it was again
    if before is not None and before[2]:
        raise ScriptError(n, f"'{' '.join(words)}' already means something here that can't change, so pick another name for each item.")
    cpp = snake(words) + f"_{n}"
    if tokens[cut] == "in":
        seq = expr_to_end(tokens, cut + 1, names, n)
        if not is_list(seq.kind):
            raise ScriptError(n, f"'for each ... in' needs a list, but this is {kind_name(seq.kind)}.")
        kind = element(seq.kind)
        line = f"{tab}for (const {cpp_type(kind)} {cpp} : stellanova::copy({strip_parens(seq.cpp)}))"
        if JS:
            line = f"{tab}for (const {cpp} of stellanova::dup({strip_parens(seq.cpp)}))"
        get = seq.run
        simple = kind in (NUMBER, YESNO, TEXT)

        def items(env):
            return list(get(env)) if simple else dup(get(env))
    else:
        e = Expr(tokens[cut + 1:], names, n)
        lo = e.need(e.sum(), NUMBER, "for each ... from")
        e.take("to")
        hi = e.need(e.sum(), NUMBER, "for each ... from")
        step = None
        if e.at("by"):  # 'for each n from 0 to 100 by 5', 'from 10 to 1 by -1' (by 0: no rounds)
            e.i += 1
            step = e.need(e.sum(), NUMBER, "for each ... by")
        if e.i != len(e.t):
            raise ScriptError(n, f"I don't understand '{' '.join(e.t[e.i:])}' here.")
        kind = NUMBER
        end, by = f"stellanova_end_{n}", f"stellanova_by_{n}"
        let = 'let' if JS else 'double'
        if step is None:
            line = f"{tab}for ({let} {cpp} = {strip_parens(lo.cpp)}, {end} = {strip_parens(hi.cpp)}; {cpp} <= {end}; {cpp} += 1)"
        else:
            line = (f"{tab}for ({let} {cpp} = {strip_parens(lo.cpp)}, {end} = {strip_parens(hi.cpp)}, {by} = {strip_parens(step.cpp)}; "
                    f"({by} > 0 && {cpp} <= {end}) || ({by} < 0 && {cpp} >= {end}); {cpp} += {by})")
        a, b, s = lo.run, hi.run, (step.run if step else lambda env: 1.0)

        def items(env):
            x, last, by_ = a(env), b(env), s(env)
            while (by_ > 0 and x <= last) or (by_ < 0 and x >= last):
                yield x
                x += by_
    names.add(words, cpp, kind, read_only=True)
    lines, then = body(loop=True)
    del names.known[tuple(words)]
    if before is not None:
        names.known[tuple(words)] = before

    def run(env):
        for x in items(env):
            env[cpp] = x
            if not then(env):
                break
    if tokens[cut] == "from":
        run.pyl = lambda tab: py_loop(f"for env[{cpp!r}] in _count({py_expr(lo)}, {py_expr(hi)}{', ' + py_expr(step) if step else ''}):", then, tab)
    else:
        run.pyl = lambda tab: py_loop(f"for env[{cpp!r}] in _each({py_expr(seq)}, {simple}):", then, tab)
    if tokens[cut] == "from":
        with_ir(run, lambda f: machine.count_from(f, cpp, lo, hi, then, step))
    else:
        with_ir(run, lambda f: machine.each_in(f, cpp, kind, seq, then))
    return [line, tab + "{"] + lines + [tab + "}"], run, None


def able_call(key, command, args, names, n):
    """'speak s' where s is a speaker: the version for whatever kind of thing s is now."""
    able, what = args[0].kind[6:], " ".join(key)
    if key not in ABLE[able]:
        raise ScriptError(n, f"A {able} can only {' and '.join(' '.join(w) for w in ABLE[able])}, not '{what}'.")
    kinds = command.kinds
    args = args[:1] + [fit(a, k) or a for a, k in zip(args[1:], kinds[1:])]
    for k, (a, kind) in enumerate(zip(args[1:], kinds[1:]), 2):
        if a.kind != kind:
            raise ScriptError(n, f"Input {k} of '{what}' must be {kind_name(kind)}, not {kind_name(a.kind)}.")
    versions = command.versions
    pairs = [("thing " + t, nearest_version(versions, "thing " + t)) for t in THINGS if t not in ABLE]
    pairs = [(k, ver) for k, ver in pairs if ver is not None]
    gets = [a.run for a in args]

    def run(env):
        given = [g(env) for g in gets]
        if given[0] is None:
            raise RunError(n, f"this {able} is nothing, so it can't {what}.")
        return nearest_version(versions, "thing " + given[0].name).runner(*given)

    def write(f):
        done = [machine.owned(f, args[0])] + [machine.emit(f, a) for a in args[1:]]
        done = done[:1] + [f.copied(x, a.kind) for x, a in zip(done[1:], args[1:])]
        f.op(f"call ptr @cn_able(ptr {done[0]}, ptr {f.module.bytes_const(able.encode())}, ptr {f.module.bytes_const(what.encode())}, i32 {n})")
        slot = None
        if command.gives:
            slot = f"%able{f.label('')}"
            f.entry.append(f"  {slot} = alloca {machine.ll_type(command.gives)}")
        joined = f.label("joined")
        for kind, ver in pairs:
            yes, no = f.label("is"), f.label("isnt")
            f.branch(f.op(f"call i1 @cn_is_kind(ptr {done[0]}, ptr {f.spec(kind)})"), yes, no)
            f.place(yes)
            given = ", ".join(f"{machine.ll_type(k)} {x}" for x, k in zip(done, [kind] + ver.kinds[1:]))
            name = machine_name(ver.cpp, [((), k) for k in ver.kinds])
            if slot:
                out = f.op(f"call {machine.ll_type(command.gives)} @cn_user_{name}({given})")
                f.put(f"store {machine.ll_type(command.gives)} {out}, ptr {slot}")
            else:
                f.put(f"call void @cn_user_{name}({given})")
            f.check()
            f.jump(joined)
            f.place(no)
        f.jump(joined)  # (never: cn_able let only kinds that can through)
        f.place(joined)
        return f.op(f"load {machine.ll_type(command.gives)}, ptr {slot}") if slot else None
    run.ir = write
    table = ", ".join(f"{json.dumps(k[6:])}: {ver.js}" for k, ver in pairs) if JS else ""
    rest = "".join(", " + strip_parens(a.cpp) for a in args)
    return f"(await stellanova::able({{{table}}}, {json.dumps(able)}, {json.dumps(what)}, {n}{rest}))", run


def call(key, args, names, n):
    """Calling a command, after checking its inputs. Returns (C++, run)."""
    command = names.commands[key]
    if command.versions and args and is_thing(args[0].kind):
        command = nearest_version(command.versions, args[0].kind) or command
    kinds = command.kinds
    usual = getattr(command, "usual", {})
    while len(args) < len(kinds) and len(args) in usual:  # left out: the value it usually has
        args = args + [expr_to_end(tokenize(usual[len(args)], n), 0, names, n)]
    if len(args) != len(kinds):
        raise ScriptError(n, f"'{' '.join(key)}' needs {len(kinds)} input{'s' if len(kinds) != 1 else ''}, but this gives it {len(args)}.")
    if args and is_thing(args[0].kind) and args[0].kind[6:] in ABLE and command.versions:
        return able_call(key, command, args, names, n)
    args = [fit(a, kind) or a for a, kind in zip(args, kinds)] if len(args) == len(kinds) else args
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
    run.pyf = lambda: f"{py_part(command)}.runner({', '.join(py_expr(g) for g in gets)})"
    cpp = command.cpp
    if command.inputs is None:  # one of the script's own commands: after it, look whether a problem happened in it
        def write(f, command=command, args=args):
            done = [machine.owned(f, a) if k == 0 and command.cpp in OWNERS else machine.emit(f, a) for k, a in enumerate(args)]
            if command.cpp not in OWNERS or not done:  # inputs are copies, except the thing a command for a kind changes
                done = [f.copied(x, a.kind) for x, a in zip(done, args)]
            else:
                done = done[:1] + [f.copied(x, a.kind) for x, a in zip(done[1:], args[1:])]
            given = ", ".join(f"{machine.ll_type(a.kind)} {x}" for x, a in zip(done, args))
            name = machine_name(command.cpp, [((), k) for k in command.kinds])
            out = None
            if command.gives:
                out = f.op(f"call {machine.ll_type(command.gives)} @cn_user_{name}({given})")
            else:
                f.put(f"call void @cn_user_{name}({given})")
            f.check()
            return out
        run.ir = write
    elif getattr(command, "library", None):  # a library word: one of the library's C functions
        template = command.cpp
        for k, in_name in enumerate(command.inputs):
            template = template.replace("{" + in_name + "}", "{a%d}" % k)
        lib = command.library
        run.ir = lambda f: machine.wrap(f, lib, LIBRARY_HEADS[lib], template, args, command.gives, cpp_type, n)
    if getattr(command, "unusable", None):
        raise ScriptError(n, command.unusable)
    if command.inputs is not None:  # a library word: put each input into its {input name} place
        given = {"{" + in_name + "}": f"({strip_parens(a.cpp)})" for in_name, a in zip(command.inputs, args)}
        given["{line}"] = str(n)  # so the library's C++ can say which line went wrong
        # all at once, so an input's own text is never replaced again
        cpp = re.sub("|".join(re.escape(g) for g in given), lambda m: given[m.group(0)], cpp)
        return f"({cpp})", run
    if JS:
        return f"(await {getattr(command, 'js', cpp)}({', '.join(strip_parens(a.cpp) for a in args)}))", run
    return f"{cpp}({', '.join(strip_parens(a.cpp) for a in args)})", run


def owner_command_value(c, line):
    """'the command speak', for a command for a kind of thing: kept as a value, it works on a copy of the thing it is given
    and gives the changed copy back (or, if it returns something, that)."""
    thing = c.kinds[0]
    gives = c.gives or thing
    kind = command_kind(c.kinds, gives)
    ins = [f"_{k}" for k in range(len(c.kinds))]
    if JS:
        call_ = f"await {getattr(c, 'js', c.cpp)}({', '.join(ins)})"
        body_cpp = f"return {call_};" if c.gives else f"_0 = stellanova::dup(_0); {call_}; return _0;"
        cpp = f"(async ({', '.join(ins)}) => {{ {body_cpp} }})"
    else:
        call_ = f"{c.cpp}({', '.join(ins)})"
        body_cpp = f"return {call_};" if c.gives else f"{call_}; return _0;"
        params = ", ".join(f"{cpp_type(k)} {x}" for x, k in zip(ins, c.kinds))
        cpp = f"{cpp_type(kind)}([=]({params}) {{ {body_cpp} }})"

    def make(env):
        def command(first, *rest):
            first = dup(first)
            out = c.runner(first, *rest)
            return out if c.gives else first
        return command

    def body_ir(f):
        args = [f.load(x, k) for x, k in zip(ins, c.kinds)]
        args = [args[0] if c.gives else f.op(f"call ptr @cn_own(ptr {f.copied(args[0], thing)})")] + [f.copied(x, k) for x, k in zip(args[1:], c.kinds[1:])]
        given = ", ".join(f"{machine.ll_type(k)} {x}" for x, k in zip(args, c.kinds))
        name = machine_name(c.cpp, [((), k) for k in c.kinds])
        if c.gives:
            out = f.op(f"call {machine.ll_type(c.gives)} @cn_user_{name}({given})")
        else:
            f.put(f"call void @cn_user_{name}({given})")
            out = args[0]
        f.check()
        return out
    body = with_ir(Value("", gives, None), body_ir)
    INLINE_COUNT[0] += 1
    return with_ir(Value(cpp, kind, make), lambda f, name=f"kept_{INLINE_COUNT[0]}": machine.closure(f, name, list(zip(ins, c.kinds)), gives, body))


def command_value(names, tokens, e, line):
    """'the command double': the command itself, to keep in a name or a list, or give to another command."""
    key, size = match_command(names, tokens[e.i:])
    if not key:
        raise ScriptError(line, "'the command' needs the name of a command after it, like 'the command double'." + library_hint(list(tokens[e.i:])))
    e.i += size
    c = names.commands[key]
    if c.versions is not None:
        return owner_command_value(c, line)
    kind = command_kind(c.kinds, c.gives)
    if getattr(c, "unusable", None):
        raise ScriptError(line, c.unusable)
    if JS:
        if c.inputs is None:
            cpp = c.cpp
        else:
            given = {"{" + in_name + "}": f"(_{k})" for k, in_name in enumerate(c.inputs)}
            given["{line}"] = str(line)
            body = re.sub("|".join(re.escape(g) for g in given), lambda m: given[m.group(0)], c.cpp) if given else c.cpp
            cpp = f"(async ({', '.join(f'_{k}' for k in range(len(c.kinds)))}) => {body})"
        return Value(cpp, kind, lambda env: (lambda *args: c.runner(*args)))
    if c.inputs is None:  # one of the script's own commands
        cpp = f"{cpp_type(kind)}({c.cpp})"
    else:  # a library word: its C++ goes inside a small function
        given = {"{" + in_name + "}": f"(_{k})" for k, in_name in enumerate(c.inputs)}
        given["{line}"] = str(line)
        body = re.sub("|".join(re.escape(g) for g in given), lambda m: given[m.group(0)], c.cpp)
        ins = ", ".join(f"{cpp_type(k_)} _{k}" for k, k_ in enumerate(c.kinds))
        cpp = f"{cpp_type(kind)}([&]({ins}) {{ {'return ' if c.gives else ''}{body}; }})"
    v = Value(cpp, kind, lambda env: (lambda *args: c.runner(*args)))
    if c.inputs is None:
        v.ir = lambda f: f.op(f"call ptr @cn_command_make(ptr @cn_user_{machine_name(c.cpp, [((), k) for k in c.kinds])})")
    elif getattr(c, "library", None):
        v.ir = lambda f: f.op(f"call ptr @cn_command_make(ptr {library_command_ir(f, c, line)})")
    return v


class Piece:
    """A bit of machine code standing in for a Value or a statement (it has only .ir and .kind)."""

    def __init__(self, ir, kind=None):
        self.ir, self.kind = ir, kind


def library_command_ir(f, c, line):
    """'the command square root of' in machine code: a small function of the program's own that calls the library word."""
    import hashlib
    template = c.cpp
    for k, in_name in enumerate(c.inputs):
        template = template.replace("{" + in_name + "}", "{a%d}" % k)
    name = "lib_" + hashlib.sha1("|".join([c.library, template, str(line)] + c.kinds).encode("utf-8")).hexdigest()[:16]
    made = f.module.__dict__.setdefault("library_commands", set())
    if name not in made:
        made.add(name)
        inputs = [(f"in{k}", kind) for k, kind in enumerate(c.kinds)]
        args = [Piece(lambda g, cpp=cpp, kind=kind: g.load(cpp, kind), kind) for cpp, kind in inputs]

        def body(g):
            out = machine.wrap(g, c.library, LIBRARY_HEADS[c.library], template, args, c.gives, cpp_type, line)
            if c.gives:
                g.finish_with(f"ret {machine.ll_type(c.gives)} {out}")
        machine.function(f.module, name, inputs, c.gives, Piece(body))
    return f"@cn_user_{name}"


def writable_list(tokens, names, n, what):
    v = expr_to_end(tokens, 0, names, n)
    if not is_list(v.kind):
        raise ScriptError(n, f"'{what}' needs a list, but this is {kind_name(v.kind)}.")
    if not v.writable:
        raise ScriptError(n, f"'{' '.join(tokens)}' can't be changed.")
    return v


READING_FILE = [0]  # which script the line being read is in (FILES), for its private commands


def match_command(names, tokens):
    for size in range(len(tokens), 0, -1):
        mine = tuple(tokens[:size]) + (f"privately{READING_FILE[0]}",)
        if mine in names.commands:
            return mine, size
        if tuple(tokens[:size]) in names.commands:
            return tuple(tokens[:size]), size
    return None, 0


def hidden_from_here(key):
    """A private command of another script."""
    return bool(key) and key[-1].startswith("privately") and key[-1] != f"privately{READING_FILE[0]}"


def private_message(key):
    elsewhere = FILES[int(key[-1][len("privately"):])]
    return f"'{spoken(key)}' is kept to {elsewhere} (it is written 'privately' there), so only {elsewhere} can use it."


def spoken(key):
    """A command's name as written: without the mark a private one has."""
    return " ".join(key[:-1] if key and key[-1].startswith("privately") else key)


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
        if not rest or bad_name(rest) or any(not w[0].isalpha() for w in rest):
            raise ScriptError(n, f"'{' '.join(rest)}' can't be a name.")
        cpp = snake(rest)
        declared[tuple(rest)] = (cpp, kind)
        names.add(rest, cpp, kind)
    question = tokens[1][1:-1]
    reader = {NUMBER: ask_number, YESNO: ask_yes_no, TEXT: ask_text}[kind]

    def run(env):
        env[cpp] = reader(question)
    if not (key and size == len(rest) and names.known[key][3] is not None):  # a name kept in the command's own places
        ll_reader = {NUMBER: "double @cn_ask_number", YESNO: "i1 @cn_ask_yes_no", TEXT: "ptr @cn_ask_text"}[kind]
        with_ir(run, lambda f: f.store(cpp, kind, f.op(f"call {ll_reader}(ptr {f.text_const(question)})")))
    cpp_reader = {NUMBER: "stellanova::ask_number", YESNO: "stellanova::ask_yes_no", TEXT: "stellanova::ask_text"}[kind]
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

def run_tests(program):
    """'stellanova test': runs each command whose name starts with 'test' (and has no inputs), not genesis."""
    tests = [(key, c) for key, c in program.commands.items() if key[0] == "test" and not c.kinds and c.inputs is None]
    if not tests:
        print("There are no tests: a test is a command like 'to test adding:' with 'check' lines in it.")
        return 1
    failed = 0
    for key, command in tests:
        try:
            command.runner()
            print(f"\u2713 {' '.join(key)}")
        except RunError as err:
            failed += 1
            sys.stdout.flush()
            at = run_where(err.line)
            print(f"\u2717 {' '.join(key)}: {at[:1].lower() + at[1:]}: {err.message}")
    print(f"{len(tests)} test{'s' if len(tests) != 1 else ''}: {len(tests) - failed} passed, {failed} failed.")
    return 1 if failed else 0


SOURCES = set()  # every script and .words file read since run_built began (start.py checks them before using a kept copy)


def source_text(path):
    SOURCES.add(str(path.resolve()))
    return path.read_text(encoding="utf-8")




def run_built(script):
    """Runs the program as machine code: built the first time, then the kept copy runs. Its exit code,
    or None when it can't be built (it then runs the old way, which says any mistake itself)."""
    global LOGIC, MAKING_CPP
    import hashlib
    import start
    RUNS = start.RUNS
    SOURCES.clear()
    try:
        LOGIC = script.parent
        MAKING_CPP = True
        try:
            _, program = read_script(script)
        finally:
            MAKING_CPP = False
        if program is None:
            return None
        ll = machine_code(program)
        runtime = HERE / "runtime"
        key = hashlib.sha256("\x00".join([machine.TARGET, ll, repr(sorted(MACHINE_UNITS.items()))] +
                                         [(runtime / f).read_text(encoding="utf-8") for f in ("machine.cpp", "machine.h", "stellanova.h")])
                             .encode("utf-8")).hexdigest()[:24]
        exe = RUNS / (key + ("" if machine.TARGET == "linux" else ".exe"))
        if not exe.exists():
            RUNS.mkdir(parents=True, exist_ok=True)
            fresh = RUNS / f"{key}.{os.getpid()}.making{exe.suffix}"
            work = tempfile.mkdtemp(prefix="stellanova_")
            try:
                if machine.make_exe(ll, fresh, work, MACHINE_UNITS):
                    return None
            finally:
                shutil.rmtree(work, ignore_errors=True)
            try:
                os.replace(fresh, exe)
            except OSError:  # (another run made it first, and it is running)
                fresh.unlink(missing_ok=True)
            for notes in (False, True):  # only the newest 40 built copies (and notes) are kept
                made = [p for p in RUNS.iterdir() if (p.suffix == ".json") == notes]
                for old in sorted(made, key=lambda p: p.stat().st_mtime)[:-40]:
                    try:
                        old.unlink()
                    except OSError:
                        pass
        else:
            os.utime(exe)  # (used again: kept longer)
        # shortcut: a new file that a 'use:' would find before the one it found isn't noticed until the script changes.
        note = {"exe": exe.name, "stamp": start.install_stamp(), "sources": [start.stamp(Path(p)) for p in sorted(SOURCES)]}
        start.note_of(script).write_text(json.dumps(note), encoding="utf-8")
    except (ScriptError, machine.Unsupported, RuntimeError, OSError, RecursionError):
        return None
    sys.stdout.flush()
    try:
        return subprocess.run([str(exe), *ARGUMENTS]).returncode
    except KeyboardInterrupt:
        return 130


def run_program(script, tests=False):
    """Runs a program directly (or its tests). Returns the exit code (0 when it finished, 1 when it stopped with an error)."""
    global LOGIC
    if not tests and DEBUG is None and PROFILE is None and not WATCHING and not os.environ.get("STELLANOVA_DIRECT"):
        code = run_built(script)  # as fast as C++: the same program, built
        if code is not None:
            return code
    LOGIC = script.parent
    try:
        _, program = read_script(script)
    except ScriptError as err:
        print(f"{where(err.line)}: {err.message}")
        return 1
    if program is None:
        print(f"{script.name} is part of something else ('this is part of:'), so it can't run on its own.")
        return 1
    if ("start",) not in program.commands:
        print(f"{script.name} is for a game engine (it has no 'genesis:'): make it into a plugin with 'stellanova plugin {script.name}'.")
        return 1
    result = {"code": 0}
    # Text is UTF-8 everywhere, as in built programs (Windows would otherwise use its old code page when piped).
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")

    def go():
        try:
            if tests:
                result["code"] = run_tests(program)
                return
            program.start()
            wait_for_others()
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


MACHINE_UNITS = {}  # the built-in and library words the program being built uses (see machine.wrap)


def machine_code(program, plugin=False):
    """The whole program as LLVM code (raises machine.Unsupported for what can't be made into machine code yet)."""
    module = machine.Module()
    module.shared = dict(WORLD_KINDS)
    for key, base in program.commands.items():
        if base.inputs is not None:  # a library word: only a problem if the program uses it (its call has no writer)
            continue
        for command in (base.versions.values() if base.versions else [base]):  # a version for each kind of thing
            if getattr(command, "machine", None) is None:
                raise machine.Unsupported(f"the command '{' '.join(key)}'")
            name, inputs, gives, run = command.machine
            machine.function(module, name, inputs, gives, run)
    MACHINE_UNITS.clear()
    MACHINE_UNITS.update(module.units)
    if not plugin:
        return module.finish(FILES)
    calls = []  # the commands an engine can call: numbers in, nothing or a number back
    for key, base in program.commands.items():
        if base.inputs is None and not base.versions and getattr(base, "machine", None):
            name, inputs, gives, _ = base.machine
            if name != "Start" and len(inputs) <= 4 and all(k == NUMBER for _, k in inputs) and gives in (None, NUMBER):
                calls.append((" ".join(key), name, len(inputs), gives == NUMBER))
    return module.finish(FILES, calls)


def build(script, exe, plugin=False):
    """Reads a program script and compiles it into exe (a plugin for a game engine, when plugin). Returns an error message, or None."""
    global LOGIC, MAKING_CPP
    LOGIC = script.parent
    MAKING_CPP = True
    try:
        cpp_out, program = read_script(script)
    except ScriptError as err:
        return f"{where(err.line)}: {err.message}"
    finally:
        MAKING_CPP = False
    if program is None:
        return f"{script.name} is part of something else ('this is part of:'), so it can't run on its own."
    try:
        ll = machine_code(program, plugin)
    except machine.Unsupported as missing:
        made = {"wasm": "WebAssembly", "linux": "a program"}.get(machine.TARGET, "an .exe")
        return f"{script.name} can't be built into {made} yet: {missing} isn't in machine code. It still runs directly (stellanova {script.name})."
    return machine.make_exe(ll, exe, tempfile.mkdtemp(prefix="stellanova_"), MACHINE_UNITS, plugin)


def wasm(script):
    """Builds the program into WebAssembly (WASI): <name>.wasm, and <name>.mjs to run it with node. Returns an error message, or None."""
    native, machine.TARGET = machine.TARGET, "wasm"
    try:
        problem = build(script, script.with_suffix(".wasm"))
    finally:
        machine.TARGET = native
    if not problem:
        runner = (HERE / "runtime" / "wasi.mjs").read_text(encoding="utf-8").replace("PROGRAM", script.stem)
        script.with_suffix(".mjs").write_text(runner, encoding="utf-8")
    return problem


def web(script, folder=None):
    """Turns a program into JavaScript: <name>.js and stellanova.js (what every web program uses) in folder.
    Returns an error message, or None. Run it with node, or load both into a page (stellanova.js first)."""
    global LOGIC, JS
    LOGIC, JS = script.parent, True
    try:
        js_out, program = read_script(script)
    except ScriptError as err:
        return f"{where(err.line)}: {err.message}"
    finally:
        JS = False
    if program is None:
        return f"{script.name} is part of something else ('this is part of:'), so it can't run on its own."
    folder = Path(folder) if folder else script.parent
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{script.stem}.js").write_text(js_out, encoding="utf-8")
    shutil.copy2(HERE / "runtime" / "stellanova.js", folder / "stellanova.js")
    return None


ENGINE = Path(r"C:\Program Files\Epic Games\UE_5.8")
WORLD = Path.home() / "Documents" / "StellanovaWorld"  # the Unreal project 'stellanova unreal' builds into


def unreal(script, launch=True):
    """Turns a program into the StellanovaWorld Unreal project, builds it, and starts it. Returns an error message, or None."""
    global LOGIC, UNREAL, MAKING_CPP
    LOGIC, UNREAL, MAKING_CPP = script.parent, True, True
    try:
        cpp_out, program = read_script(script)
    except ScriptError as err:
        return f"{where(err.line)}: {err.message}"
    finally:
        UNREAL = MAKING_CPP = False
    if program is None:
        return f"{script.name} is part of something else ('this is part of:'), so it can't run on its own."
    editor = ENGINE / "Engine" / "Binaries" / "Win64" / "UnrealEditor.exe"
    if not editor.exists():
        return f"I can't find Unreal Engine at {ENGINE}."
    shutil.copytree(HERE / "unreal", WORLD, dirs_exist_ok=True)
    made = WORLD / "Source" / "StellanovaWorld" / "Generated"
    made.mkdir(parents=True, exist_ok=True)
    shutil.copy2(HERE / "runtime" / "stellanova.h", made / "stellanova.h")
    target = made / "Program.stella.cpp"
    if not target.exists() or target.read_text(encoding="utf-8") != cpp_out:  # unchanged files aren't compiled again
        target.write_text(cpp_out, encoding="utf-8")
    subprocess.run(["taskkill", "/f", "/im", "UnrealEditor.exe"], capture_output=True)
    log = WORLD / "Saved" / "build.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    project = WORLD / "StellanovaWorld.uproject"
    print(f"Building {project} (the first time takes a few minutes)...")
    with open(log, "w", encoding="utf-8", errors="replace") as out:
        result = subprocess.run([str(ENGINE / "Engine" / "Build" / "BatchFiles" / "Build.bat"), "StellanovaWorldEditor", "Win64",
                                 "Development", f"-Project={project}", "-WaitMutex"], stdout=out, stderr=subprocess.STDOUT)
    if result.returncode != 0:
        lines = [l for l in log.read_text(errors="replace").splitlines() if "error" in l.lower()]
        return "Unreal didn't accept the C++. That is a bug in Stellanova (or a library), not in your script.\n" + "\n".join(lines[:20]) + f"\n(all of it: {log})"
    if launch:
        subprocess.Popen([str(editor), str(project), "-game", "-windowed", "-ResX=1280", "-ResY=720", "-nosplash"])
    return None


TRY_HELLO = """Stellanova: type a line and press Enter to see what it does. For example:
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
            for _ in range(20):  # a library's word loads its library, as in a script
                try:
                    v = None
                    if len(rows) == 1:
                        try:  # a value on its own (like '5 plus 3' or 'round 2.6') is shown
                            v = expr_to_end(read_words(surface(line.strip(), n), n, names), 0, names, n)
                        except ScriptError as err:
                            if "put the line 'use: " in err.message:
                                raise
                            v = None
                    if v is not None:
                        run = lambda env, get=v.run: show(text(get(env)))
                    else:
                        _, run = statements(rows, names, declared, 1)
                    break
                except ScriptError as err:
                    m = re.search(r"put the line 'use: (\w+)' at the top", err.message)
                    if not m:
                        raise
                    load_library(m.group(1), n, names)
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


def got_folder():
    """Where 'stellanova get' keeps the libraries it gets ('use:' looks there too)."""
    return Path(os.environ.get("STELLANOVA_GOT") or HERE / "libraries" / "got")


def get_package(where):
    """'stellanova get <address>': a library from the internet (or a file), kept so any program can 'use:' it.
    The address is a .words file, a .zip holding .words files, or a GitHub project written user/project."""
    import io
    import urllib.request
    import zipfile
    if re.fullmatch(r"[\w.-]+/[\w.-]+", where) and not Path(where).exists():
        where = f"https://codeload.github.com/{where}/zip/HEAD"
    elif Path(where).exists():
        where = Path(where).resolve().as_uri()
    try:
        with urllib.request.urlopen(urllib.request.Request(where, headers={"User-Agent": "stellanova-get"}), timeout=60) as answer:
            data = answer.read()
    except Exception as err:
        print(f"I couldn't get {where}: {getattr(err, 'reason', err)}.")
        return 1
    found = {}  # name -> its words
    if data[:4] == b"PK\x03\x04":
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for item in z.namelist():
                if item.lower().endswith(".words") and "/unreal/" not in item.lower():
                    found[Path(item).stem] = z.read(item)  # only the file's own name: nothing lands outside the folder
    elif where.lower().split("?")[0].endswith(".words"):
        found[Path(where.split("?")[0]).stem.replace("%20", " ")] = data
    if not found:
        print(f"There is no library (.words file) at {where}.")
        return 1
    folder = got_folder()
    folder.mkdir(parents=True, exist_ok=True)
    sources = folder / "sources.txt"
    kept = dict(line.split("\t", 1) for line in sources.read_text(encoding="utf-8").splitlines() if "\t" in line) if sources.exists() else {}
    for name, words in sorted(found.items()):
        name = re.sub(r"[^\w .-]", "", name).strip().lower()
        if not name or (HERE / "libraries" / f"{name}.words").exists():
            print(f"Skipped '{name}': Stellanova has its own library called that.")
            continue
        (folder / f"{name}.words").write_bytes(words)
        kept[name] = where
        print(f"Got the library '{name}': use it with  use: {name}")
    sources.write_text("".join(f"{n}\t{w}\n" for n, w in sorted(kept.items())), encoding="utf-8")
    print("A library can run any code on this computer: only use ones from people you trust.")
    return 0


def got_packages():
    """'stellanova got': the libraries 'stellanova get' has kept, and where each came from."""
    sources = got_folder() / "sources.txt"
    kept = dict(line.split("\t", 1) for line in sources.read_text(encoding="utf-8").splitlines() if "\t" in line) if sources.exists() else {}
    names = sorted(p.stem for p in got_folder().glob("*.words"))
    if not names:
        print("No libraries got yet. Get one with:  stellanova get <address>")
    for name in names:
        print(f"{name}  (from {kept.get(name, 'somewhere')})")
    return 0


def drop_package(name):
    """'stellanova drop <name>': lets a got library go."""
    path = got_folder() / f"{name.lower()}.words"
    if not path.exists():
        print(f"There is no got library called '{name}'.")
        return 1
    path.unlink()
    sources = got_folder() / "sources.txt"
    if sources.exists():
        sources.write_text("".join(l + "\n" for l in sources.read_text(encoding="utf-8").splitlines() if not l.startswith(name.lower() + "\t")), encoding="utf-8")
    print(f"Dropped the library '{name}'.")
    return 0


USAGE = """Use:
  stellanova <script.stella>                     run a program
  stellanova run <script.stella>                 the same
  stellanova build <script.stella>               make it into an .exe (needs LLVM: winget install LLVM.LLVM)
  stellanova wasm <script.stella>                make it into WebAssembly: <script>.wasm (run it: node <script>.mjs)
  stellanova check <script.stella>               look for mistakes without running it
  stellanova unreal <script.stella>              run it inside Unreal Engine: the 3D words become a real lit world
  stellanova test <script.stella>                run each command called 'to test ...:' and show which checks failed
  stellanova watch <script.stella>               run it, showing each line as it runs and the names it changes
  stellanova web <script.stella> [folder]        make it into JavaScript, for a web page (or: node <script>.js)
  stellanova get <address>                        get a library: a .words file, a .zip of them, or a GitHub user/project
  stellanova got                                  show the libraries got so far
  stellanova drop <name>                          let a got library go
  stellanova                                      try lines out, one at a time
  stellanova <scripts folder> <output folder>     turn 'this is part of:' scripts into C++ (for Unreal)
(stellanova is short for: py -3 stellanova.py)"""


def tidy(text):
    """A script with its spacing put right: two spaces for each step in, no spaces at line ends, a tab as 4 spaces,
    one empty line between the top-level parts, and one new line at the end. Words and quotes are left as they are."""
    out, steps = [], [0]  # steps: the indents seen so far, the deepest last
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            if out and out[-1] != "":
                out.append("")
            continue
        body = line.lstrip(" \t")
        width = len(line[:len(line) - len(body)].replace("\t", "    "))
        while width < steps[-1]:
            steps.pop()
        if width > steps[-1]:
            steps.append(width)
        if len(steps) == 1 and out and out[-1] == CLOSING:
            out.append("")  # a new part starts after the one before it ends
        out.append("  " * (len(steps) - 1) + body)
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out) + "\n"


def main(argv):
    global LOGIC, OUT
    args = argv[1:]
    for stream in (sys.stdout, sys.stderr):  # each line shows straight away, even into a file or another program (as built ones do)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(line_buffering=True)
    if not args:
        return try_it()
    if args[0].lower().endswith(".stella"):
        args = ["run"] + args
    if len(args) > 2 and args[0] == "run":  # the words after the script are for the program: 'the words given'
        ARGUMENTS[:] = args[2:]
        args = args[:2]
    if len(args) == 2 and args[0] == "test":
        return run_program(Path(args[1]), tests=True)
    if len(args) == 2 and args[0] == "get":
        return get_package(args[1])
    if args == ["got"]:
        return got_packages()
    if len(args) == 2 and args[0] == "drop":
        return drop_package(args[1])
    if len(args) >= 2 and args[0] == "debug":  # runs it directly, stopping at lines: 'stellanova debug game.stella 12 30'
        global DEBUG
        studio = args[1] == "--studio"
        rest = args[2:] if studio else args[1:]
        if not rest or not all(a.isdigit() for a in rest[1:]):
            print("Say the script, then the lines to stop at (if any): stellanova debug game.stella 12 30")
            return 2
        DEBUG = {"stops": {int(a) for a in rest[1:]}, "mode": "step" if len(rest) == 1 else "go", "depth": 0, "envs": [], "studio": studio}
        if not studio:
            print(DEBUG_HELP)
        args = ["run", rest[0]]
    if len(args) == 2 and args[0] == "profile":  # runs it directly, then shows which lines took the time
        global PROFILE
        PROFILE = {}
        args = ["run", args[1]]
    if len(args) == 2 and args[0] == "watch":  # runs it directly, showing each line and the names it changes
        global WATCHING
        WATCHING = True
        args = ["run", args[1]]
    if len(args) == 2 and args[0] == "tidy":
        script = Path(args[1])
        if not script.is_file():
            print(f"There is no script called {args[1]}.")
            return 2
        old = script.read_bytes().decode("utf-8")  # as it is: read_text would hide the \r\n line ends
        new = tidy(old).replace("\n", "\r\n" if "\r\n" in old else "\n")
        if new != old:
            script.write_bytes(new.encode("utf-8"))
        print(f"{script.name}: " + ("tidied." if new != old else "already tidy."))
        return 0
    if len(args) == 2 and args[0] == "check":
        LOGIC = Path(args[1]).parent
        try:
            read_script(Path(args[1]))
        except FileNotFoundError:
            print(f"There is no script called {args[1]}.")
            return 2
        except ScriptError as err:
            if "only works in a program made for the web" not in err.message:
                print(f"{where(err.line)}: {err.message}")
                return 1
            # a program for a web page: check it the way it will be made
            with tempfile.TemporaryDirectory(prefix="stellanova_check_") as made:
                problem = web(Path(args[1]), made)
            if problem:
                print(problem)
                return 1
        print(f"{Path(args[1]).name}: no mistakes found.")
        return 0
    if args[0] == "web" and len(args) in (2, 3):
        script = Path(args[1])
        if not script.exists():
            print(f"There is no script called {script}.")
            return 2
        problem = web(script, args[2] if len(args) == 3 else None)
        if problem:
            print(problem)
            return 1
        print(f"Made {Path(args[2]) / (script.stem + '.js') if len(args) == 3 else script.stem + '.js'}")  # (no whole paths: they hold the user's name)
        return 0
    if len(args) == 2 and args[0] == "unreal":
        script = Path(args[1])
        if not script.exists():
            print(f"There is no script called {script}.")
            return 2
        problem = unreal(script, launch=not os.environ.get("STELLANOVA_NO_LAUNCH"))
        if problem:
            print(problem)
            return 1
        print(f"Built {WORLD}" + ("" if os.environ.get("STELLANOVA_NO_LAUNCH") else " and started it."))
        return 0
    if len(args) == 2 and args[0] == "unity":  # sets a Unity project up for Stellanova programs
        project = Path(args[1])
        if not (project / "Assets").is_dir() or not (project / "ProjectSettings").is_dir():
            print(f"{args[1]} isn't a Unity project: it needs an Assets and a ProjectSettings folder (make one with Unity Hub first).")
            return 2
        into = project / "Assets" / "Stellanova"
        shutil.copytree(HERE / "engines" / "unity" / "Stellanova", into, dirs_exist_ok=True)
        (into / "home.txt").write_text(str(HERE), encoding="utf-8")
        print("Stellanova is in Assets/Stellanova. Put a .stella file in Assets, then add a Stellanova Script to an object and drag the file onto it.")
        return 0
    if len(args) == 2 and args[0] == "plugin":  # a plugin for a game engine: Unity, Unreal or Godot calls its commands
        script = Path(args[1])
        if not script.exists():
            print(f"There is no script called {script}.")
            return 2
        made = script.with_suffix(".so" if machine.TARGET == "linux" else ".dll")
        global PLUGIN
        PLUGIN = True
        problem = build(script, made, plugin=True)
        for extra in (".lib", ".exp"):  # (what the linker makes for C++ programs using the .dll: an engine doesn't need them)
            if made.suffix == ".dll":
                made.with_suffix(extra).unlink(missing_ok=True)
        if problem:
            print(problem)
            return 1
        print(f"Built {made.name}")
        return 0
    if len(args) == 2 and args[0] == "wasm":
        script = Path(args[1])
        if not script.exists():
            print(f"There is no script called {script}.")
            return 2
        problem = wasm(script)
        if problem:
            print(problem)
            return 1
        print(f"Built {script.stem}.wasm (run it: node {script.stem}.mjs)")
        return 0
    if len(args) == 2 and args[0] in ("run", "build"):
        script = Path(args[1])
        if not script.exists():
            print(f"There is no script called {script}.")
            return 2
        if args[0] == "run":
            code = run_program(script)
            if PROFILE is not None:
                sys.stdout.flush()
                profile_report()
            sys.stdout.flush()
            sys.stderr.flush()
            # Exit straight away: a library's leftovers (like a closed window) must not be tidied up from the wrong thread.
            os._exit(code)
        exe = script.with_suffix("" if machine.TARGET == "linux" else ".exe")
        problem = build(script, exe)
        if problem:
            print(problem)
            return 1
        print(f"Built {exe.name}")
        return 0
    if len(args) != 2:
        print(USAGE)
        return 2
    LOGIC, OUT = Path(args[0]), Path(args[1])
    OUT.mkdir(parents=True, exist_ok=True)
    failed = False
    wanted = set()
    for path in sorted(LOGIC.glob("*.stella")):
        target = OUT / f"{path.stem}.stella.cpp"
        wanted.add(target.name)
        try:
            cpp_out = translate(path)
        except ScriptError as err:
            print(f"{where(err.line)}: {err.message}")
            failed = True
            continue
        if not target.exists() or target.read_text(encoding="utf-8") != cpp_out:
            target.write_text(cpp_out, encoding="utf-8")
    for old in OUT.glob("*.stella.cpp"):
        if old.name not in wanted:
            old.unlink()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
