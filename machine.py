"""Stellanova's machine-code builder: turns a program into LLVM code, which clang makes into an .exe.

Each piece of a program (a number, a sum, an 'if' line) carries an 'ir' function next to its Python and C++:
ir(f) writes that piece's LLVM instructions into the function being made, f, and returns where the answer is.
A piece without one raises Unsupported, and the program is built the older way (through C++) instead.

Numbers are doubles and yes/no is i1. Everything else is a pointer to a value made by runtime/machine.cpp
(compiled once into a library), which copies, shows and compares values exactly as Python does.
A problem doesn't jump: the library keeps it, and the code checks cn_failed() after each step that may fail.
"""
import os
import re
import struct
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
NUMBER, YESNO, TEXT, PLACE, FLAT = "number", "yes or no", "text", "place", "flat"
THINGS = {}  # 'thing pet' -> [(the part's C++ name, its words, its kind)], set by stellanova.py before writing


# library functions that may find a problem (machine.cpp's GUARDED ones): the code looks at cn_failed() after each
FALLIBLE = {"cn_entry", "cn_entry_remove", "cn_list_at", "cn_list_last", "cn_list_put", "cn_list_random",
            "cn_list_remove_item", "cn_list_stat", "cn_random", "cn_rounded", "cn_to_number", "cn_command_or_fail",
            "cn_saved_text", "cn_save_file", "cn_load"}


class Unsupported(Exception):
    """This part of the language can't be made into machine code yet."""


def emit(f, x, what="a part of the language"):
    """Writes x's LLVM code into f (x is a Value or a statement's run); returns where its answer is."""
    write = getattr(x, "ir", None)
    if write is None:
        code = getattr(x, "cpp", None)  # a Value: its C++ says which piece it is
        x = getattr(x, "inner", x)
        made_by = getattr(x, "__qualname__", "")  # a statement's run: which reader made it ('say.<locals>.run')
        if hasattr(x, "__code__"):
            made_by += f", stellanova.py line {x.__code__.co_firstlineno}"
        raise Unsupported(f"{what}: {code[:60]}" if code else f"{what} ({made_by})" if made_by else what)
    return write(f)


def ll_type(kind):
    if kind == NUMBER:
        return "double"
    if kind == YESNO:
        return "i1"
    if kind in (TEXT, PLACE, FLAT) or kind.startswith(("list of ", "table of ", "command(")) or kind in THINGS:
        return "ptr"
    raise Unsupported(kind)


def number(x):
    """A double exactly as LLVM wants it written."""
    return "0x%016X" % struct.unpack("<Q", struct.pack("<d", x))[0]


def ll_text(data):
    return "".join(chr(b) if 32 <= b < 127 and b not in (34, 92) else "\\%02X" % b for b in data)


RUNTIME = """declare void @cn_begin(i32, ptr)
declare void @cn_add_file(ptr)
declare i32 @cn_end()
declare i1 @cn_failed()
declare void @cn_raise(i32, ptr)
declare ptr @cn_problem_text()
declare ptr @cn_text(ptr, i64)
declare ptr @cn_text_number(double)
declare ptr @cn_text_yesno(i1)
declare ptr @cn_show(ptr)
declare ptr @cn_join(ptr, ptr)
declare i1 @cn_same_text(ptr, ptr)
declare void @cn_say(ptr)
declare ptr @cn_ask_text(ptr)
declare double @cn_ask_number(ptr)
declare i1 @cn_ask_yes_no(ptr)
declare double @cn_letters(ptr)
declare double @cn_to_number(ptr, i32)
declare i64 @cn_repeats(double)
declare double @cn_random(double, double, i32)
declare double @cn_random_fraction()
declare double @cn_rounded(double, double, i32)
declare ptr @cn_box_number(double)
declare ptr @cn_box_yesno(i1)
declare double @cn_unbox_number(ptr)
declare i1 @cn_unbox_yesno(ptr)
declare ptr @cn_box_command(ptr)
declare ptr @cn_unbox_command(ptr)
declare ptr @cn_command_or_fail(ptr, i32)
declare ptr @cn_dup(ptr)
declare i1 @cn_equal(ptr, ptr)
declare ptr @cn_list_new()
declare ptr @cn_table_new()
declare void @cn_list_add(ptr, ptr)
declare ptr @cn_list_at(ptr, double, i32)
declare ptr @cn_list_item(ptr, i64)
declare void @cn_list_put(ptr, double, ptr, i32)
declare void @cn_list_remove_item(ptr, double, i32)
declare void @cn_list_remove_value(ptr, ptr)
declare double @cn_count(ptr)
declare i64 @cn_count_whole(ptr)
declare i1 @cn_list_contains(ptr, ptr)
declare i1 @cn_text_contains(ptr, ptr)
declare i1 @cn_table_has(ptr, ptr)
declare ptr @cn_list_random(ptr, i32)
declare ptr @cn_list_last(ptr, i32)
declare double @cn_list_stat(i32, ptr, i32)
declare ptr @cn_entry(ptr, ptr, i32)
declare void @cn_entry_put(ptr, ptr, ptr)
declare void @cn_entry_remove(ptr, ptr, i32)
declare ptr @cn_keys(ptr)
declare ptr @cn_place(double, double, double)
declare ptr @cn_flat(double, double)
declare double @cn_part(ptr, i32)
declare void @cn_part_put(ptr, i32, double)
declare ptr @cn_place_op(i32, ptr, ptr)
declare ptr @cn_place_scale(i32, ptr, double)
declare double @cn_place_size(ptr)
declare ptr @cn_thing(ptr)
declare ptr @cn_as_kind(ptr, ptr)
declare ptr @cn_field(ptr, i32)
declare void @cn_field_put(ptr, i32, ptr)
declare void @cn_replace(ptr, ptr)
declare ptr @cn_sorted_by(ptr, i32)
declare ptr @cn_saved_text(ptr, i32)
declare void @cn_save_file(ptr, ptr, i32)
declare ptr @cn_load(ptr, ptr, i32, ptr, i32)
declare double @llvm.fabs.f64(double)
declare void @cn_meanwhile(ptr, ptr)
declare void @cn_wait_for_others()
declare ptr @malloc(i64)
"""


class Module:
    """A whole program: its text constants, the names the whole program shares, and its functions."""

    def __init__(self):
        self.constants, self.functions, self.declared = [], [], []
        self.shared = {}  # 'the world remembers:' names: C++ name -> kind
        self.units = {}  # built-in and library words the program uses: unit -> [head, {C function name: its C++}]
        self.texts = {}

    def bytes_const(self, data):
        if data not in self.texts:
            name = f"@s{len(self.constants)}"
            self.constants.append(f'{name} = private unnamed_addr constant [{len(data) + 1} x i8] c"{ll_text(data)}\\00"')
            self.texts[data] = name
        return self.texts[data]

    def text(self, s):
        data = s.encode("utf-8")
        return self.bytes_const(data), len(data)

    def declare(self, line):
        if line not in self.declared and line not in RUNTIME:
            self.declared.append(line)

    def finish(self, files):
        start = Fn(self, "main", [], None)
        for cpp, kind in self.shared.items():
            self.constants.append(f"@g.{cpp} = internal global {ll_type(kind)} {zero_const(kind)}")
            start.put(f"store {ll_type(kind)} {start.zero(kind)}, ptr @g.{cpp}")
        main = ["define i32 @main(i32 %count, ptr %given) {", "entry:", "  call void @cn_begin(i32 %count, ptr %given)"]
        for name in files:
            const, _ = self.text(name)
            main.append(f"  call void @cn_add_file(ptr {const})")
        main += start.entry + [l if l.endswith(":") else l for l in start.lines]
        main += ["  call void @cn_user_Start()", "  %code = call i32 @cn_end()", "  ret i32 %code", "}"]
        return "\n".join(self.constants + [c_bools(RUNTIME)] + [c_bools(d) for d in self.declared] + self.functions + main) + "\n"


def c_bools(declarations):
    """A C++ bool is one byte that must be 0 or 1, so a yes/no given to (or got from) the library is zero-extended."""
    out = []
    for line in declarations.splitlines():
        if line.startswith("declare ") and "llvm." not in line:
            head, _, params = line.partition("(")
            head = head.replace("declare i1 ", "declare zeroext i1 ")
            line = head + "(" + re.sub(r"\bi1\b(?! zeroext)", "i1 zeroext", params)
        out.append(line)
    return "\n".join(out) + ("\n" if declarations.endswith("\n") else "")


def zero_const(kind):
    return {"double": number(0.0), "i1": "false"}.get(ll_type(kind), "null")


class Fn:
    """One function being written: its instructions, its names' places, and the loops and 'try:'s it is inside."""

    def __init__(self, module, name, inputs, gives):
        self.module, self.name, self.inputs, self.gives = module, name, inputs, gives
        self.entry, self.lines, self.n = [], [], 0
        self.slots = {}  # a name's C++ spelling -> (its place, kind)
        self.loops = []  # (where 'move on' goes, where 'break free' goes)
        self.handlers = []  # where a problem goes inside 'try:' (innermost last)
        self.ended = False  # the last instruction was a jump or a return, so a new block must start
        self.here = "start"  # the block being written

    def tmp(self):
        self.n += 1
        return f"%t{self.n}"

    def label(self, hint="b"):
        self.n += 1
        return f"{hint}{self.n}"

    def put(self, line):
        if self.ended:  # code after 'cease' or 'break free' is never reached, but still needs a block
            self.place(self.label("dead"))
        self.lines.append("  " + line)

    def put_checked(self, line):
        """put, and then a check when the line calls a library function that may fail (see FALLIBLE)."""
        self.put(line)
        m = re.search(r"@(cn_\w+)\(", line)
        if m and m.group(1) in FALLIBLE:
            self.check()

    def op(self, text):
        r = self.tmp()
        self.put_checked(f"{r} = {text}")
        return r

    def call(self, gives, fn, *args, checked=False):
        """A call into the library (args are (type, value) pairs); checked: it may fail, so look afterwards."""
        given = ", ".join(f"{t} {v}" for t, v in args)
        if gives == "void":
            self.put_checked(f"call void @{fn}({given})")
            out = None
        else:
            out = self.op(f"call {gives} @{fn}({given})")
        if checked and fn not in FALLIBLE:
            self.check()
        return out

    def check(self):
        """If a problem happened, go to the 'if that went wrong:' lines, or leave this command."""
        bad = self.op("call i1 @cn_failed()")
        go = self.label("ok")
        self.branch(bad, self.handlers[-1] if self.handlers else self.leave_label(), go)
        self.place(go)

    def leave_label(self):
        if not hasattr(self, "leave"):
            self.leave = self.label("leave")
        return self.leave

    def place(self, label):
        """Starts the block called label."""
        if not self.ended:
            self.lines.append(f"  br label %{label}")
        self.lines.append(f"{label}:")
        self.ended = False
        self.here = label

    def jump(self, label):
        self.put(f"br label %{label}")
        self.ended = True

    def branch(self, cond, yes, no):
        self.put(f"br i1 {cond}, label %{yes}, label %{no}")
        self.ended = True

    def finish_with(self, line):
        self.put(line)
        self.ended = True

    def zero(self, kind, into=None):
        """A new empty value of the kind (0, no, "", an empty list, a new thing with empty parts)."""
        saved, ended = self.lines, self.ended
        if into is not None:  # written somewhere else (the entry block): what comes before here doesn't matter
            self.lines, self.ended = into, False
        try:
            t = ll_type(kind)
            if t != "ptr":
                return zero_const(kind)
            if kind == TEXT:
                return self.text_const("")
            if kind.startswith("command("):  # no command in it yet (invoking it is a problem)
                return "null"
            if kind == PLACE:
                return self.op(f"call ptr @cn_place(double {number(0)}, double {number(0)}, double {number(0)})")
            if kind == FLAT:
                return self.op(f"call ptr @cn_flat(double {number(0)}, double {number(0)})")
            if kind.startswith("list of "):
                return self.op("call ptr @cn_list_new()")
            if kind.startswith("table of "):
                return self.op("call ptr @cn_table_new()")
            thing = self.op(f"call ptr @cn_thing(ptr {self.spec(kind)})")
            for k, (_, _, part_kind) in enumerate(THINGS[kind]):
                self.put(f"call void @cn_field_put(ptr {thing}, i32 {k}, ptr {self.box(self.zero(part_kind), part_kind)})")
            return thing
        finally:
            if into is not None:
                self.lines, self.ended = saved, ended

    def shape(self, kind):
        """What 'load X from' fills: an empty value of the kind, a list's or table's one item showing its items' kind."""
        if kind.startswith("list of "):
            out = self.op("call ptr @cn_list_new()")
            self.put(f"call void @cn_list_add(ptr {out}, ptr {self.shape(kind[8:])})")
            return out
        if kind.startswith("table of "):
            out = self.op("call ptr @cn_table_new()")
            self.put(f"call void @cn_entry_put(ptr {out}, ptr {self.text_const('')}, ptr {self.shape(kind[9:])})")
            return out
        if kind.startswith("command("):
            raise Unsupported(kind)
        if kind in THINGS:
            thing = self.op(f"call ptr @cn_thing(ptr {self.spec(kind)})")
            for k, (_, _, part_kind) in enumerate(THINGS[kind]):
                self.put(f"call void @cn_field_put(ptr {thing}, i32 {k}, ptr {self.shape(part_kind)})")
            return thing
        return self.box(self.zero(kind), kind)

    def spec(self, kind):
        """A kind of thing as the library reads it: its name and its parts' names, split by \\x01."""
        return self.module.bytes_const("\x01".join([kind[6:]] + [" ".join(w) for _, w, _ in THINGS[kind]]).encode("utf-8"))

    def box(self, value, kind):
        """A number or yes/no as a value a list or a thing can hold (other values already are one)."""
        if kind == NUMBER:
            return self.op(f"call ptr @cn_box_number(double {value})")
        if kind == YESNO:
            return self.op(f"call ptr @cn_box_yesno(i1 {value})")
        if kind.startswith("command("):
            return self.op(f"call ptr @cn_box_command(ptr {value})")
        return value

    def unbox(self, value, kind):
        if kind == NUMBER:
            return self.op(f"call double @cn_unbox_number(ptr {value})")
        if kind == YESNO:
            return self.op(f"call i1 @cn_unbox_yesno(ptr {value})")
        if kind.startswith("command("):
            return self.op(f"call ptr @cn_unbox_command(ptr {value})")
        return value

    def copied(self, value, kind):
        """Lists, tables, places and things are copied when they are stored (numbers, yes/no and text never change)."""
        if ll_type(kind) == "ptr" and kind != TEXT and not kind.startswith("command("):
            return self.op(f"call ptr @cn_dup(ptr {value})")
        return value

    def slot(self, cpp, kind):
        """The place a name is kept, made (and given its starting value) the first time it is used."""
        if cpp not in self.slots:
            t = ll_type(kind)
            where = f"%n.{cpp}"
            self.entry.append(f"  {where} = alloca {t}")
            start = self.zero(kind, self.entry)
            self.entry.append(f"  store {t} {start}, ptr {where}")
            self.slots[cpp] = (where, kind)
        return self.slots[cpp][0]

    def where(self, cpp, kind):
        return f"@g.{cpp}" if cpp in self.module.shared else self.slot(cpp, kind)

    def load(self, cpp, kind):
        return self.op(f"load {ll_type(kind)}, ptr {self.where(cpp, kind)}")

    def store(self, cpp, kind, value):
        self.put(f"store {ll_type(kind)} {self.copied(value, kind)}, ptr {self.where(cpp, kind)}")

    def text_const(self, s):
        const, size = self.module.text(s)
        return self.op(f"call ptr @cn_text(ptr {const}, i64 {size})")

    def as_text(self, value, kind):
        if kind == TEXT:
            return value
        if kind == NUMBER:
            return self.op(f"call ptr @cn_text_number(double {value})")
        if kind == YESNO:
            return self.op(f"call ptr @cn_text_yesno(i1 {value})")
        ll_type(kind)
        return self.op(f"call ptr @cn_show(ptr {self.box(value, kind)})")

    def done(self):
        params = ", ".join(f"{ll_type(k)} %p.{cpp}" for cpp, k in self.inputs)
        gives = ll_type(self.gives) if self.gives else "void"
        for cpp, k in self.inputs:  # inputs are kept in places too, like every other name
            where = f"%n.{cpp}"
            self.entry[:0] = [f"  {where} = alloca {ll_type(k)}", f"  store {ll_type(k)} %p.{cpp}, ptr {where}"]
        if not self.ended:  # the end of a command: give back nothing, or the kind's empty value
            self.finish_with(f"ret {gives} {self.zero(self.gives)}" if self.gives else "ret void")
        if hasattr(self, "leave"):  # a problem nobody caught: leave, and the caller looks too
            self.place(self.leave)
            self.finish_with(f"ret {gives} {zero_const(self.gives)}" if self.gives else "ret void")
        body = ["entry:"] + self.entry + ["  br label %start", "start:"] + self.lines
        self.module.functions.append(f"define {gives} @cn_user_{self.name}({params}) {{\n" + "\n".join(body) + "\n}\n")


def function(module, name, inputs, gives, body, owner=None):
    """Writes one command. inputs: [(C++ name, kind)]; body: the command's statements, as one run with .ir.
    owner: the C++ name of the thing a command for a kind of thing is given (it is changed, not copied)."""
    for _, kind in inputs:
        ll_type(kind)
    if gives:
        ll_type(gives)
    f = Fn(module, name, inputs, gives)
    f.owner = owner
    for cpp, kind in inputs:
        f.slots[cpp] = (f"%n.{cpp}", kind)
    emit(f, body)
    f.done()


# ---------------------------------------------------------------- pieces the reader uses

def short_circuit(f, left, right, is_or):
    """'a or b' / 'a and b': b is only worked out when it matters, as in Python and C++."""
    a = emit(f, left)
    start, more, end = f.here, f.label("more"), f.label("join")
    f.branch(a, end if is_or else more, more if is_or else end)
    f.place(more)
    b = emit(f, right)
    came = f.here
    f.jump(end)
    f.place(end)
    return f.op(f"phi i1 [ {'true' if is_or else 'false'}, %{start} ], [ {b}, %{came} ]")


def choose(f, chain):
    """if / otherwise if / otherwise: chain is [(condition or None, run)]."""
    end = f.label("endif")
    for cond, then in chain:
        if cond is None:
            emit(f, then)
            break
        yes, no = f.label("then"), f.label("else")
        f.branch(emit(f, cond), yes, no)
        f.place(yes)
        emit(f, then)
        f.jump(end)
        f.place(no)
    f.jump(end)
    f.place(end)


def loop(f, test, body, step=None):
    """A loop: test() writes the yes-or-no to keep going; step runs after each round."""
    top, inside, nxt, out = f.label("loop"), f.label("body"), f.label("next"), f.label("out")
    f.place(top)
    cond = test()
    f.branch(cond, inside, out)
    f.place(inside)
    f.loops.append((nxt, out))
    emit(f, body)
    f.loops.pop()
    f.place(nxt)
    if step:
        step()
    f.jump(top)
    f.place(out)


def counter(f, hint):
    k = f"%{hint}{f.label('')}"
    f.entry.append(f"  {k} = alloca i64")
    f.put(f"store i64 0, ptr {k}")
    return k


def repeat(f, count, body):
    """'repeat N times:' with a whole-number counter, as C++ and Python count."""
    rounds = f.op(f"call i64 @cn_repeats(double {emit(f, count)})")
    k = counter(f, "k")

    def step():
        f.put(f"store i64 {f.op(f'add i64 {f.op(f'load i64, ptr {k}')}, 1')}, ptr {k}")
    loop(f, lambda: f.op(f"icmp slt i64 {f.op(f'load i64, ptr {k}')}, {rounds}"), body, step)


def count_from(f, cpp, lo, hi, body):
    """'for each n from 1 to 10:' (the end is worked out once, before the first round)."""
    f.store(cpp, NUMBER, emit(f, lo))
    last = f"%last{f.label('')}"
    f.entry.append(f"  {last} = alloca double")
    f.put(f"store double {emit(f, hi)}, ptr {last}")

    def step():
        f.store(cpp, NUMBER, f.op(f"fadd double {f.load(cpp, NUMBER)}, {number(1.0)}"))
    loop(f, lambda: f.op(f"fcmp ole double {f.load(cpp, NUMBER)}, {f.op(f'load double, ptr {last}')}"), body, step)


def each_in(f, cpp, kind, seq, body):
    """'for each score in scores:' goes through a copy, so changing the list inside doesn't change the rounds."""
    items = f.op(f"call ptr @cn_dup(ptr {emit(f, seq)})")
    size = f.op(f"call i64 @cn_count_whole(ptr {items})")
    k = counter(f, "i")

    def test():
        now = f.op(f"load i64, ptr {k}")
        go = f.op(f"icmp slt i64 {now}, {size}")
        more, out = f.label("item"), f.label("noitem")
        f.branch(go, more, out)
        f.place(more)
        f.put(f"store {ll_type(kind)} {f.unbox(f.op(f'call ptr @cn_list_item(ptr {items}, i64 {now})'), kind)}, ptr {f.slot(cpp, kind)}")
        f.jump(out)
        f.place(out)
        return f.op(f"phi i1 [ true, %{more} ], [ false, %{test.before} ]")

    def wrapped():
        test.before = f.here
        return test()

    def step():
        f.put(f"store i64 {f.op(f'add i64 {f.op(f'load i64, ptr {k}')}, 1')}, ptr {k}")
    loop(f, wrapped, body, step)


def invoke(f, command, args, ins, gives, line):
    """Does the command a value holds. command: where it is; args: [(where, kind)] already worked out."""
    target = f.call("ptr", "cn_command_or_fail", ("ptr", command), ("i32", line))
    given = ", ".join(f"{ll_type(k)} {f.copied(x, k)}" for x, k in args)
    if gives:
        out = f.op(f"call {ll_type(gives)} {target}({given})")
    else:
        f.put(f"call void {target}({given})")
        out = None
    f.check()
    return out


def by_command(f, seq, command, item, gives, keep, line):
    """'scores kept by is big' / 'scores changed by doubled': a new list, made by doing the command to each item."""
    holder = f.op("call ptr @cn_list_new()")  # a pointer: the same in every block below
    target = f.call("ptr", "cn_command_or_fail", ("ptr", command), ("i32", line))
    items = f.op(f"call ptr @cn_dup(ptr {seq})")
    size = f.op(f"call i64 @cn_count_whole(ptr {items})")
    k = counter(f, "m")
    top, inside, out_label = f.label("each"), f.label("doing"), f.label("done")
    f.place(top)
    now = f.op(f"load i64, ptr {k}")
    f.branch(f.op(f"icmp slt i64 {now}, {size}"), inside, out_label)
    f.place(inside)
    boxed = f.op(f"call ptr @cn_list_item(ptr {items}, i64 {now})")
    x = f.unbox(boxed, item)
    answer = f.op(f"call {ll_type(gives)} {target}({ll_type(item)} {f.copied(x, item)})")
    f.check()
    if keep:
        yes, after = f.label("keep"), f.label("kept")
        f.branch(answer, yes, after)
        f.place(yes)
        f.put(f"call void @cn_list_add(ptr {holder}, ptr {f.copied(boxed, item)})")
        f.jump(after)
        f.place(after)
    else:
        f.put(f"call void @cn_list_add(ptr {holder}, ptr {f.box(answer, gives)})")
    f.put(f"store i64 {f.op(f'add i64 {now}, 1')}, ptr {k}")
    f.jump(top)
    f.place(out_label)
    return holder


def meanwhile(f, piece):
    """'meanwhile count up with 5': piece goes in a function of its own, run alongside, with copies of the names it uses."""
    module = f.module
    module.alongside = getattr(module, "alongside", 0) + 1
    g = Fn(module, f"meanwhile_{module.alongside}", [("names", TEXT)], None)
    g.owner = None
    emit(g, piece)
    used = list(g.slots.items())  # (C++ name, (its place, kind)): only names the piece itself needed
    block = f.op(f"call ptr @malloc(i64 {8 * max(1, len(used))})")
    for k, (cpp, (where, kind)) in enumerate(used):
        at = f.op(f"getelementptr i8, ptr {block}, i64 {8 * k}")
        f.put(f"store {ll_type(kind)} {f.copied(f.load(cpp, kind), kind)}, ptr {at}")
        at = g.tmp()
        g.entry += [f"  {at} = getelementptr i8, ptr %p.names, i64 {8 * k}"]
        value = g.tmp()
        g.entry += [f"  {value} = load {ll_type(kind)}, ptr {at}", f"  store {ll_type(kind)} {value}, ptr {where}"]
    g.done()
    f.put(f"call void @cn_meanwhile(ptr @cn_user_{g.name}, ptr {block})")


def attempt(f, tried, problem_cpp, fixed):
    """try: ... if that went wrong: ...   (problem_cpp: the name 'the problem' is kept in)"""
    handler, end = f.label("wrong"), f.label("tried")
    f.handlers.append(handler)
    emit(f, tried)
    f.handlers.pop()
    f.jump(end)
    f.place(handler)
    f.store(problem_cpp, TEXT, f.op("call ptr @cn_problem_text()"))
    emit(f, fixed)
    f.jump(end)
    f.place(end)


def give_up(f):
    """After a problem of the program's own ('raise an error with'): go where any problem goes."""
    f.check()


# ---------------------------------------------------------------- built-in words and library words
# A built-in like 'trimmed x' or a library word like 'square root of' is one of Stellanova's own C++ functions.
# Each becomes a small C function in the prebuilt library (made the first time a program needs it, kept after),
# so a program calls it like any other library function: the program's own code still never becomes C++.

def wrap(f, unit, head, template, args, gives, cpp_type, line):
    """Calls the C function for one built-in (unit 'builtins') or library word (unit = the library's name).

    template: its C++, with {a0} / {s0} for the inputs and {line} for the line number; head: what the unit's file
    needs above its functions (a library's includes and code). Returns where the answer is (None for nothing)."""
    for a in args:
        if a.kind in THINGS or ll_type(a.kind) is None:
            raise Unsupported(f"{a.kind} given to {template[:40]}")
    if gives in THINGS:
        raise Unsupported(f"{gives} from {template[:40]}")
    types = [cpp_type(a.kind) for a in args]
    ret = {"double": "double", "i1": "bool"}.get(ll_type(gives), "V*") if gives else "void"
    import hashlib
    name = "cn_w_" + hashlib.sha1("|".join([unit, template, ret] + types).encode("utf-8")).hexdigest()[:16]
    params = []
    body = template.replace("{line}", "line")
    for k, (a, t) in enumerate(zip(args, types)):
        c = {"double": "double", "i1": "bool"}.get(ll_type(a.kind), "V*")
        params.append(f"{c} a{k}")
        value = f"a{k}" if c != "V*" else f"cn_to_cpp<{t}>(a{k})"
        body = body.replace("{a%d}" % k, f"({value})").replace("{s%d}" % k, value)
    if ret == "void":
        result = f"{body};"
    elif ret == "V*":
        result = f"return cn_from_cpp({body});"
    else:
        result = f"return static_cast<{ret}>({body});"
    fallback = {"double": "0.0", "bool": "false", "V*": "cn_box_number(0)"}.get(ret, "")
    code = (f'extern "C" {ret} {name}({", ".join(params + ["int line"])})\n'
            f"{{\n\ttry {{ {result} }}\n\tcatch (const stellanova::Problem& problem) {{ cn_set_problem(problem); return {fallback}; }}\n}}\n")
    f.module.units.setdefault(unit, [head, {}])[1][name] = code
    ll_ret = ll_type(gives) if gives else "void"
    f.module.declare(f"declare {ll_ret} @{name}({', '.join([ll_type(a.kind) for a in args] + ['i32'])})")
    values = [(ll_type(a.kind), f.box(emit(f, a), a.kind) if a.kind.startswith("command(") else emit(f, a)) for a in args] + [("i32", str(line))]
    return f.call(ll_ret, name, *values, checked=True)


def unit_file(unit, head, wrappers):
    """runtime/built/w_<unit>.cpp, holding every wrapper any program has needed so far (rewritten only when one is new)."""
    import hashlib
    path = HERE / "runtime" / "built" / f"w_{re.sub(r'[^a-z0-9]+', '_', unit)}.cpp"
    mark = "// head " + hashlib.sha1(head.encode("utf-8")).hexdigest()
    have = {}
    if path.exists():
        old = path.read_text(encoding="utf-8")
        if mark in old:  # the same library as before: keep the wrappers made for earlier programs
            for m in re.finditer(r"// wrapper (\w+)\n(.*?)// end\n", old, re.S):
                have[m.group(1)] = m.group(2)
    if all(n in have for n in wrappers):
        return path
    have.update(wrappers)
    top = [mark, "// Made by machine.py: Stellanova's own words as C functions for machine code. Not a program's code.",
           '#include "stellanova.h"', head, "#define STELLANOVA_CONVERSIONS", '#include "machine.h"', ""]
    path.parent.mkdir(exist_ok=True)
    path.write_text("\n".join(top) + "".join(f"// wrapper {n}\n{c}// end\n" for n, c in sorted(have.items())), encoding="utf-8")
    return path


# ---------------------------------------------------------------- making the .exe

def find_clang():
    for place in [os.environ.get("STELLANOVA_CLANG"), r"C:\Program Files\LLVM\bin\clang++.exe"]:
        if place and Path(place).exists():
            return place
    raise RuntimeError("I can't find LLVM's clang. Install LLVM (winget install LLVM.LLVM).")


def compile_once(src, out, newer_than):
    """src compiled into out, again only when one of newer_than changed."""
    if not out.exists() or out.stat().st_mtime < max(p.stat().st_mtime for p in newer_than):
        out.parent.mkdir(exist_ok=True)
        done = subprocess.run([find_clang(), "-c", "-O2", "-std=c++20", "-fms-extensions", "-Wno-everything",
                               "-I", str(HERE / "runtime"), str(src), "-o", str(out)], capture_output=True, text=True)
        if done.returncode:
            raise RuntimeError(f"Stellanova's machine-code library ({src.name}) didn't compile:\n" + done.stderr)
    return out


def runtime_object():
    """runtime/machine.cpp compiled once (again only when it or stellanova.h changes)."""
    runtime = HERE / "runtime"
    return compile_once(runtime / "machine.cpp", runtime / "built" / "stellanova_machine.obj",
                        [runtime / "machine.cpp", runtime / "machine.h", runtime / "stellanova.h"])


def make_exe(ll_text_, exe, work, units=None):
    """Turns the LLVM code into exe. units: the module's built-in and library words. Returns an error message, or None."""
    ll = Path(work) / "program.ll"
    ll.write_text(ll_text_, encoding="utf-8")
    try:
        objects = [str(runtime_object())]
        runtime = HERE / "runtime"
        for unit, (head, wrappers) in sorted((units or {}).items()):
            src = unit_file(unit, head, wrappers)
            objects.append(str(compile_once(src, src.with_suffix(".obj"), [src, runtime / "machine.h", runtime / "stellanova.h"])))
        clang = find_clang()
    except RuntimeError as err:
        return str(err)
    done = subprocess.run([clang, "-O2", "-Wno-override-module", str(ll), *objects, "-o", str(exe)],
                          capture_output=True, text=True)
    if done.returncode:
        return ("Stellanova wrote machine code LLVM didn't accept. That is a bug in Stellanova, not in your script.\n"
                + done.stderr + f"\n(the LLVM code is in {ll})")
    return None
