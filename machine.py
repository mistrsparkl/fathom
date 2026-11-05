"""Cosmonova's machine-code builder: turns a program into LLVM code, which clang makes into an .exe.

Each piece of a program (a number, a sum, an 'if' line) carries an 'ir' function next to its Python and C++:
ir(f) writes that piece's LLVM instructions into the function being made, f, and returns where the answer is.
A piece without one raises Unsupported, and the program is built the older way (through C++) instead.

What every program needs (text, scrawl, ask, problems) is in runtime/machine.cpp, compiled once into a library.
"""
import os
import struct
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
NUMBER, YESNO, TEXT = "number", "yes or no", "text"
LL = {NUMBER: "double", YESNO: "i1", TEXT: "ptr"}


class Unsupported(Exception):
    """This part of the language can't be made into machine code yet."""


def emit(f, x, what="a part of the language"):
    """Writes x's LLVM code into f (x is a Value or a statement's run); returns where its answer is."""
    write = getattr(x, "ir", None)
    if write is None:
        raise Unsupported(what)
    return write(f)


def ll_type(kind):
    if kind not in LL:
        raise Unsupported(kind)
    return LL[kind]


def number(x):
    """A double exactly as LLVM wants it written."""
    return "0x%016X" % struct.unpack("<Q", struct.pack("<d", x))[0]


RUNTIME = """declare void @cn_begin(i32, ptr)
declare void @cn_add_file(ptr)
declare void @cn_end()
declare ptr @cn_text(ptr, i64)
declare ptr @cn_text_number(double)
declare ptr @cn_text_yesno(i1)
declare ptr @cn_join(ptr, ptr)
declare i1 @cn_same_text(ptr, ptr)
declare void @cn_say(ptr)
declare ptr @cn_ask_text(ptr)
declare double @cn_ask_number(ptr)
declare i1 @cn_ask_yes_no(ptr)
declare i64 @cn_repeats(double)
declare double @cn_random(double, double, i32)
declare double @cn_letters(ptr)
declare double @cn_to_number(ptr, i32)
declare double @cn_rounded(double, double, i32)
declare double @llvm.fabs.f64(double)
"""


class Module:
    """A whole program: its text constants and its functions."""

    def __init__(self):
        self.constants, self.functions = [], []

    def text(self, s):
        data = s.encode("utf-8")
        name = f"@s{len(self.constants)}"
        body = "".join(chr(b) if 32 <= b < 127 and b not in (34, 92) else "\\%02X" % b for b in data)
        self.constants.append(f'{name} = private unnamed_addr constant [{len(data) + 1} x i8] c"{body}\\00"')
        return name, len(data)

    def finish(self, files):
        main = ["define i32 @main(i32 %count, ptr %given) {", "  call void @cn_begin(i32 %count, ptr %given)"]
        for name in files:
            const, _ = self.text(name)
            main.append(f"  call void @cn_add_file(ptr {const})")
        main += ["  call void @cn_user_Start()", "  call void @cn_end()", "  ret i32 0", "}"]
        return "\n".join(self.constants + [RUNTIME] + self.functions + main) + "\n"


class Fn:
    """One function being written: its instructions, its names' places, and the loops it is inside."""

    def __init__(self, module, name, inputs, gives):
        self.module, self.name, self.inputs, self.gives = module, name, inputs, gives
        self.entry, self.lines, self.n = [], [], 0
        self.slots = {}  # a name's C++ spelling -> (its place, kind)
        self.loops = []  # (where 'move on' goes, where 'break free' goes)
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

    def op(self, text):
        r = self.tmp()
        self.put(f"{r} = {text}")
        return r

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

    def slot(self, cpp, kind):
        """The place a name is kept, made (and given its starting value) the first time it is used."""
        if cpp not in self.slots:
            t = ll_type(kind)
            where = f"%n.{cpp}"
            self.entry.append(f"  {where} = alloca {t}")
            start = {"double": number(0.0), "i1": "false"}.get(t)
            if t == "ptr":
                const, size = self.module.text("")
                self.entry.append(f"  %z.{cpp} = call ptr @cn_text(ptr {const}, i64 {size})")
                start = f"%z.{cpp}"
            self.entry.append(f"  store {t} {start}, ptr {where}")
            self.slots[cpp] = (where, kind)
        return self.slots[cpp][0]

    def load(self, cpp, kind):
        return self.op(f"load {ll_type(kind)}, ptr {self.slot(cpp, kind)}")

    def store(self, cpp, kind, value):
        self.put(f"store {ll_type(kind)} {value}, ptr {self.slot(cpp, kind)}")

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
        raise Unsupported(f"showing {kind} as text")

    def done(self):
        params = ", ".join(f"{ll_type(k)} %p.{cpp}" for cpp, k in self.inputs)
        gives = ll_type(self.gives) if self.gives else "void"
        for cpp, k in self.inputs:  # inputs are kept in places too, like every other name
            where = f"%n.{cpp}"
            self.entry[:0] = [f"  {where} = alloca {ll_type(k)}", f"  store {ll_type(k)} %p.{cpp}, ptr {where}"]
            self.slots.setdefault(cpp, (where, k))
        if not self.ended:  # the end of a command: give back nothing, or the kind's empty value
            zero = {"double": number(0.0), "i1": "false"}.get(gives)
            if gives == "ptr":
                zero = self.text_const("")
            self.finish_with(f"ret {gives} {zero}" if self.gives else "ret void")
        body = ["entry:"] + self.entry + ["  br label %start", "start:"] + self.lines
        self.module.functions.append(f"define {gives} @cn_user_{self.name}({params}) {{\n" + "\n".join(body) + "\n}\n")


def function(module, name, inputs, gives, body):
    """Writes one command. inputs: [(C++ name, kind)]; body: the command's statements, as one run with .ir."""
    for _, kind in inputs:
        ll_type(kind)
    if gives:
        ll_type(gives)
    f = Fn(module, name, inputs, gives)
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
    """if / otherwise if / otherwise: chain is [(condition Value or None, run)]."""
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
    """A loop: test() writes the yes-or-no to keep going (or None for 'always'); step runs after each round."""
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


def repeat(f, count, body):
    """'repeat N times:' with a whole-number counter, as C++ and Python count."""
    rounds = f.op(f"call i64 @cn_repeats(double {emit(f, count)})")
    k = f"%k{f.label('')}"
    f.entry.append(f"  {k} = alloca i64")
    f.put(f"store i64 0, ptr {k}")

    def test():
        now = f.op(f"load i64, ptr {k}")
        return f.op(f"icmp slt i64 {now}, {rounds}")

    def step():
        now = f.op(f"load i64, ptr {k}")
        f.put(f"store i64 {f.op(f'add i64 {now}, 1')}, ptr {k}")
    loop(f, test, body, step)


def count_from(f, cpp, lo, hi, body):
    """'for each n from 1 to 10:' (the end is worked out once, before the first round)."""
    f.store(cpp, NUMBER, emit(f, lo))
    last = f"%last{f.label('')}"
    f.entry.append(f"  {last} = alloca double")
    f.put(f"store double {emit(f, hi)}, ptr {last}")

    def test():
        return f.op(f"fcmp ole double {f.load(cpp, NUMBER)}, {f.op(f'load double, ptr {last}')}")

    def step():
        f.store(cpp, NUMBER, f.op(f"fadd double {f.load(cpp, NUMBER)}, {number(1.0)}"))
    loop(f, test, body, step)


# ---------------------------------------------------------------- making the .exe

def runtime_object():
    """runtime/machine.cpp compiled once (again only when it or cosmonova.h changes)."""
    clang = find_clang()
    src, header = HERE / "runtime" / "machine.cpp", HERE / "runtime" / "cosmonova.h"
    out = HERE / "runtime" / "built" / "cosmonova_machine.obj"
    if not out.exists() or out.stat().st_mtime < max(src.stat().st_mtime, header.stat().st_mtime):
        out.parent.mkdir(exist_ok=True)
        done = subprocess.run([clang, "-c", "-O2", "-std=c++20", "-fms-extensions", "-Wno-everything",
                               "-I", str(HERE / "runtime"), str(src), "-o", str(out)], capture_output=True, text=True)
        if done.returncode:
            raise RuntimeError("Cosmonova's machine-code library didn't compile:\n" + done.stderr)
    return out


def find_clang():
    for place in [os.environ.get("COSMONOVA_CLANG"), r"C:\Program Files\LLVM\bin\clang++.exe"]:
        if place and Path(place).exists():
            return place
    raise RuntimeError("I can't find LLVM's clang. Install LLVM (winget install LLVM.LLVM).")


def make_exe(ll_text, exe, work):
    """Turns the LLVM code into exe. Returns an error message, or None."""
    ll = Path(work) / "program.ll"
    ll.write_text(ll_text, encoding="utf-8")
    try:
        lib = runtime_object()
        clang = find_clang()
    except RuntimeError as err:
        return str(err)
    done = subprocess.run([clang, "-O2", "-Wno-override-module", str(ll), str(lib), "-o", str(exe)],
                          capture_output=True, text=True)
    if done.returncode:
        return ("Cosmonova wrote machine code LLVM didn't accept. That is a bug in Cosmonova, not in your script.\n"
                + done.stderr + f"\n(the LLVM code is in {ll})")
    return None
