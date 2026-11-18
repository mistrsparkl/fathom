"""Turns a program into LLVM code; clang makes the .exe. Values live in runtime/machine.cpp."""
import os
import re
import struct
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
NUMBER, YESNO, TEXT, PLACE, FLAT = "number", "yes or no", "text", "place", "flat"
THINGS = {}  # 'thing pet' -> [(C++ name, words, kind)]
HAS_KINDS_OF = lambda kind: True  # kinds of this kind? Set by stellanova.py


# library functions that may fail: check cn_failed() after each
FALLIBLE = {"cn_split", "cn_list_at_slow", "cn_list_put_slow", "cn_own_item", "cn_own_entry", "cn_list_put_number", "cn_entry", "cn_entry_remove", "cn_list_at", "cn_list_at_number", "cn_list_last", "cn_list_put", "cn_list_random",
            "cn_list_remove_item", "cn_list_insert", "cn_power", "cn_bits", "cn_list_stat", "cn_random", "cn_rounded", "cn_to_number", "cn_command_or_fail",
            "cn_saved_text", "cn_save_file", "cn_load", "cn_something", "cn_sorted_by", "cn_able"}
ABLE = {}  # ability -> the kinds that can do it


class Unsupported(Exception):
    """This part of the language can't be made into machine code yet."""


TARGET = "linux" if sys.platform.startswith("linux") else "windows"  # or "wasm": WebAssembly (WASI), for 'stellanova wasm'
WASI = Path.home() / ".stellanova" / "wasi"  # from github.com/WebAssembly/wasi-sdk


# libraries that never wait: no registers kept
NEVER_WAIT = {"builtins", "maths", "letters", "patterns", "big numbers"}
NO_VALUES = re.compile(r"call (?:void|double|i1) @(?:cn_user_|cn_list_add_number\(|cn_list_number\(|cn_list_at_number\(|cn_list_put_number\(|cn_part_number\(|cn_part_number_put\()|call ptr @cn_(?:text_kept|own|own_field|own_item|own_entry|list_at_slow)\(|call ptr @cn_something\(ptr null|call void @cn_(?:list_put_slow|assign)\("  # (adding a number to a list keeps it in the list)
                       r"|call (?:double|i1) @cn_w_\w+\((?:(?:double|i1|i32) [^,()]*(?:, )?)*\)$")  # a library word given and giving only numbers or yes/no


def makes_nothing(lines):
    """True when these lines make no values of their own."""
    return all("call " not in l or (TARGET != "wasm" and NO_VALUES.search(l)) for l in lines)


def owned(f, v):
    """Copy v first if it is held elsewhere."""
    own = getattr(v, "ir_own", None)
    return own(f) if own else emit(f, v)


def emit(f, x, what="a part of the language"):
    """Writes x's LLVM code into f; returns where its answer is."""
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
declare void @cn_plugin_begin(ptr, ptr)
declare i32 @cn_plugin_settle()
declare void @cn_plugin_command(ptr, ptr, i32, i32)
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
declare void @cn_share(ptr)
declare void @cn_append(ptr, ptr)
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
declare double @cn_power(double, double, i32)
declare void @cn_raise_kind(i32, ptr, ptr)
declare void @cn_lock(ptr)
declare void @cn_unlock(ptr)
declare i1 @cn_problem_is(ptr)
declare double @cn_bits(i32, double, double, i32)
declare ptr @cn_box_number(double)
declare ptr @cn_box_yesno(i1)
declare double @cn_unbox_number(ptr)
declare i1 @cn_unbox_yesno(ptr)
declare ptr @cn_command_make(ptr)
declare ptr @cn_closure_env()
declare ptr @cn_command_or_fail(ptr, i32)
declare ptr @cn_dup(ptr)
declare i1 @cn_equal(ptr, ptr)
declare ptr @cn_list_new()
declare ptr @cn_table_new()
declare void @cn_list_add(ptr, ptr)
declare void @cn_list_add_number(ptr, double)
declare double @cn_list_number(ptr, i64)
declare double @cn_list_at_number(ptr, double, i32)
declare ptr @cn_list_at(ptr, double, i32)
declare ptr @cn_list_item(ptr, i64)
declare void @cn_list_put(ptr, double, ptr, i32)
declare void @cn_list_put_number(ptr, double, double, i32)
declare void @cn_list_remove_item(ptr, double, i32)
declare void @cn_list_insert(ptr, double, ptr, i32)
declare void @cn_list_remove_value(ptr, ptr)
declare double @cn_count(ptr)
declare i64 @cn_count_whole(ptr)
declare i1 @cn_list_contains(ptr, ptr)
declare i1 @cn_is_kind_of(ptr, ptr)
declare ptr @cn_reversed(ptr)
declare ptr @cn_sorted_by_keys(ptr, ptr)
declare ptr @cn_repeated(ptr, double, i32)
declare ptr @cn_flattened(ptr)
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
declare ptr @cn_text_kept(ptr, i64, ptr)
declare ptr @cn_deep(ptr)
declare void @cn_entry_put_number(ptr, ptr, double)
declare ptr @cn_sorted_numbers(ptr)
declare ptr @cn_sorted_texts(ptr)
declare ptr @cn_thing_zeroed(ptr, ptr)
declare ptr @cn_join_texts(ptr, ptr)
declare ptr @cn_split(ptr, ptr, i32)
declare void @cn_assign(ptr, ptr)
declare ptr @cn_list_at_slow(ptr, double, i32)
declare void @cn_list_put_slow(ptr, double, ptr, i32)
declare ptr @cn_join_number(ptr, double)
declare double @cn_part_number(ptr, i32)
declare void @cn_part_number_put(ptr, i32, double)
declare ptr @cn_own(ptr)
declare ptr @cn_own_field(ptr, i32)
declare ptr @cn_own_item(ptr, double, i32)
declare ptr @cn_own_entry(ptr, ptr, i32)
declare ptr @cn_zero_part(i1)
declare ptr @cn_as_kind(ptr, ptr)
declare ptr @cn_field(ptr, i32)
declare ptr @cn_something(ptr, ptr, i32, i32)
declare ptr @cn_able(ptr, ptr, ptr, i32)
declare i1 @cn_is_kind(ptr, ptr)
declare void @cn_field_put(ptr, i32, ptr)
declare void @cn_field_shape(ptr, i32, ptr)
declare void @cn_shape_item(ptr, ptr)
declare void @cn_shape_entry(ptr, ptr)
declare void @cn_replace(ptr, ptr)
declare ptr @cn_sorted_by(ptr, i32, i32)
declare ptr @cn_saved_text(ptr, ptr, i32)
declare void @cn_save_file(ptr, ptr, ptr, i32)
declare void @cn_able_kind(ptr, ptr)
declare ptr @cn_load(ptr, ptr, i32, ptr, i32)
declare double @llvm.fabs.f64(double)
declare void @cn_meanwhile(ptr, ptr, i64)
declare void @cn_statement()
@cn_stopping = external global i8
@cn_failed_flag = external thread_local global i8
declare void @cn_root(ptr, i64)
declare void @cn_wait_for_others()
declare ptr @cn_memory(i64)
declare void @cn_enter()
declare void @cn_leave(ptr)
declare void @cn_slot(ptr)
"""


class Module:
    """A whole program: constants, shared names, functions."""

    def __init__(self):
        self.constants, self.functions, self.declared = [], [], []
        self.shared = {}  # 'the world remembers:' names: C++ name -> kind
        self.units = {}  # words used: unit -> [head, {C name: C++}]
        self.texts = {}
        self.text_slots = set()  # texts written in the program, each made once (see text_const)

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

    def finish(self, files, plugin=None):
        """The module's LLVM code; plugins start with stellanova_start."""
        start = Fn(self, "main", [], None)
        start.here = "entry"  # (its lines go straight after main's entry:)
        for cpp, kind in self.shared.items():
            self.constants.append(f"@g.{cpp} = internal global {ll_type(kind)} {zero_const(kind)}")
            start.put(f"store {ll_type(kind)} {start.zero(kind)}, ptr @g.{cpp}")
            start.put(f"call void @cn_root(ptr @g.{cpp}, i64 8)")
        for able, kinds in ABLE.items():  # each kind a saved speaker may be loaded as
            for kind in kinds:
                start.put(f"call void @cn_able_kind(ptr {start.spec(able)}, ptr {start.shape(kind)})")
        for words, name, count, gives in plugin or []:
            start.put(f"call void @cn_plugin_command(ptr {self.text(words)[0]}, ptr @cn_user_{name}, i32 {count}, i32 {int(gives)})")
        genesis = any("@cn_user_Start(" in f for f in self.functions)
        if plugin is not None:  # stellanova_start(output, engine): 0, or 2 when genesis went wrong
            main = ["define dllexport i32 @stellanova_start(ptr %out, ptr %engine) {", "entry:",
                    "  call void @cn_plugin_begin(ptr %out, ptr %engine)", "  call void @cn_begin(i32 0, ptr null)"]
        else:
            entry_name = "__main_argc_argv" if TARGET == "wasm" else "main"  # (what WASI's start calls)
            main = [f"define i32 @{entry_name}(i32 %count, ptr %given) {{", "entry:", "  call void @cn_begin(i32 %count, ptr %given)"]
        for name in files:
            const, _ = self.text(name)
            main.append(f"  call void @cn_add_file(ptr {const})")
        main += start.entry + [l if l.endswith(":") else l for l in start.lines]
        if plugin is not None:
            main += (["  call void @cn_user_Start()"] if genesis else []) + ["  %code = call i32 @cn_plugin_settle()", "  ret i32 %code", "}"]
        else:
            main += ["  call void @cn_user_Start()", "  %code = call i32 @cn_end()", "  ret i32 %code", "}"]
        return "\n".join(self.constants + [c_bools(RUNTIME)] + [c_bools(d) for d in self.declared] + self.functions + main) + "\n"


def c_bools(declarations):
    """A C++ bool is 0 or 1: zero-extend."""
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


def nums_at():
    """Where Full keeps nums (machine.cpp checks)."""
    return 16


def boxed_at():
    """Where it keeps boxed (just after nums)."""
    return 64


class Fn:
    """One function being written."""

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
        if self.ended:  # unreachable code still needs a block
            self.place(self.label("dead"))
        self.lines.append("  " + line)

    def put_checked(self, line):
        """put, then check if the call may fail."""
        self.put(line)
        m = re.search(r"@(cn_\w+)\(", line)
        if m and m.group(1) in FALLIBLE:
            self.check()

    def hold(self, value):
        """in WebAssembly, keep it in memory for the collector"""
        if TARGET == "wasm":
            self.n += 1
            self.entry.append(f"  %held{self.n} = alloca ptr")
            self.put(f"store ptr {value}, ptr %held{self.n}")
        return value

    def op(self, text):
        r = self.tmp()
        self.put_checked(f"{r} = {text}")
        return r

    def call(self, gives, fn, *args, checked=False):
        """A call into the library."""
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
        """On a problem, go to 'if that went wrong:' or leave."""
        if TARGET == "wasm":
            bad = self.op("call i1 @cn_failed()")
        else:  # (read straight from memory: no call)
            bad = self.op(f"trunc i8 {self.op('load i8, ptr @cn_failed_flag')} to i1")
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

    def nums_place(self, lst):
        """Where a list's plain numbers are."""
        word = 4 if TARGET == "wasm" else 8  # (a pointer, then Few's 32-bit count and room)
        at = lambda k: self.op(f"getelementptr inbounds i8, ptr {lst}, i64 {k}")
        return at(3), at(nums_at()), at(nums_at() + word), at(nums_at() + word + 4), "i32"

    def add_number(self, lst, d):
        """Adds a number in place when it can."""
        flag, data, count, room, size = self.nums_place(lst)
        check, fast, slow, done = self.label("addcheck"), self.label("addfast"), self.label("addslow"), self.label("added")
        self.branch(self.op(f"icmp ne i8 {self.op(f'load i8, ptr {flag}')}, 0"), check, slow)
        self.place(check)
        n = self.op(f"load {size}, ptr {count}")
        self.branch(self.op(f"icmp ult {size} {n}, {self.op(f'load {size}, ptr {room}')}"), fast, slow)
        self.place(fast)
        self.put(f"store double {d}, ptr {self.op(f'getelementptr inbounds double, ptr {self.op(f'load ptr, ptr {data}')}, {size} {n}')}")
        self.put(f"store {size} {self.op(f'add {size} {n}, 1')}, ptr {count}")
        self.jump(done)
        self.place(slow)
        self.put(f"call void @cn_list_add_number(ptr {lst}, double {d})")
        self.jump(done)
        self.place(done)

    def number_item(self, lst, index):
        """Item index of a plain number list, if there."""
        flag, data, count, _, size = self.nums_place(lst)
        whole, ranged, fast, slow = self.label("idxwhole"), self.label("idxrange"), self.label("itemfast"), self.label("itemslow")
        self.branch(self.op(f"icmp ne i8 {self.op(f'load i8, ptr {flag}')}, 0"), whole, slow)
        self.place(whole)
        k = self.op(f"fptosi double {index} to i64")
        back = self.op(f"sitofp i64 {k} to double")
        self.branch(self.op(f"fcmp oeq double {back}, {index}"), ranged, slow)
        self.place(ranged)
        n = self.op(f"load {size}, ptr {count}")
        n64 = n if size == "i64" else self.op(f"zext i32 {n} to i64")
        k0 = self.op(f"sub i64 {k}, 1")
        self.branch(self.op(f"icmp ult i64 {k0}, {n64}"), fast, slow)  # (k - 1 below the count, unsigned: also k >= 1)
        self.place(fast)
        at = k0 if size == "i64" else self.op(f"trunc i64 {k0} to i32")
        return self.op(f"getelementptr inbounds double, ptr {self.op(f'load ptr, ptr {data}')}, {size} {at}"), fast, slow

    def item_place(self, lst, index):
        """Item index of a boxed list, if there."""
        flag, _, _, _, size = self.nums_place(lst)
        word = 4 if TARGET == "wasm" else 8
        start = boxed_at()  # (a vector begins with its first place)
        whole, ranged, fast, slow = self.label("bwhole"), self.label("brange"), self.label("bfast"), self.label("bslow")
        self.branch(self.op(f"icmp eq i8 {self.op(f'load i8, ptr {flag}')}, 0"), whole, slow)
        self.place(whole)
        k = self.op(f"fptosi double {index} to i64")
        self.branch(self.op(f"fcmp oeq double {self.op(f'sitofp i64 {k} to double')}, {index}"), ranged, slow)
        self.place(ranged)
        first = self.op(f"load ptr, ptr {self.op(f'getelementptr inbounds i8, ptr {lst}, i64 {start}')}")
        n = self.op(f"load {size}, ptr {self.op(f'getelementptr inbounds i8, ptr {lst}, i64 {start + word}')}")  # (machine.h's Few: data, then count)
        n = n if size == "i64" else self.op(f"zext i32 {n} to i64")
        k0 = self.op(f"sub i64 {k}, 1")
        self.branch(self.op(f"icmp ult i64 {k0}, {n}"), fast, slow)
        self.place(fast)
        at = k0 if size == "i64" else self.op(f"trunc i64 {k0} to i32")
        return self.op(f"getelementptr inbounds ptr, ptr {first}, {size} {at}"), fast, slow

    def read_item(self, lst, index, line):
        """'item i of pets', in place when it can."""
        at, fast, slow = self.item_place(lst, index)
        done = self.label("bread")
        a = self.op(f"load ptr, ptr {at}")
        self.jump(done)
        self.place(slow)
        b = self.call("ptr", "cn_list_at_slow", ("ptr", lst), ("double", index), ("i32", line), checked=True)  # (only a list of plain numbers or a problem)
        slow_end = self.here
        self.jump(done)
        self.place(done)
        return self.op(f"phi ptr [ {a}, %{fast} ], [ {b}, %{slow_end} ]")

    def own_item(self, lst, index, line):
        """Item index of pets, about to be changed: in place unless it is held elsewhere too."""
        at, fast, slow = self.item_place(lst, index)
        done, plain = self.label("iown"), self.label("iplain")
        a = self.op(f"load ptr, ptr {at}")
        self.branch(self.op(f"icmp eq ptr {a}, null"), slow, plain)
        self.place(plain)
        shared = self.op(f"load i8, ptr {self.op(f'getelementptr inbounds i8, ptr {a}, i64 4')}")  # (V's shared count)
        self.branch(self.op(f"icmp eq i8 {shared}, 0"), done, slow)
        self.place(slow)
        b = self.call("ptr", "cn_own_item", ("ptr", lst), ("double", index), ("i32", line), checked=True)
        slow_end = self.here
        self.jump(done)
        self.place(done)
        return self.op(f"phi ptr [ {a}, %{plain} ], [ {b}, %{slow_end} ]")

    def write_item(self, lst, index, x, line, kind=None):
        """'set item i of pets to p', in place when it can."""
        at, fast, slow = self.item_place(lst, index)
        done = self.label("bput")
        if kind and kind.startswith("thing "):
            self.assign_thing(at, x, kind)
        else:
            old = self.op(f"load ptr, ptr {at}")
            self.share(x)
            self.put(f"store ptr {x}, ptr {at}")
            self.release(old)
        self.jump(done)
        self.place(slow)
        self.call("void", "cn_list_put_slow", ("ptr", lst), ("double", index), ("ptr", x), ("i32", line), checked=True)
        self.jump(done)
        self.place(done)

    def read_number_item(self, lst, index, line):
        """'item i of scores', in place when it can."""
        at, fast, slow = self.number_item(lst, index)
        done = self.label("itemread")
        a = self.op(f"load double, ptr {at}")
        self.jump(done)
        self.place(slow)
        b = self.call("double", "cn_list_at_number", ("ptr", lst), ("double", index), ("i32", line), checked=True)
        slow_end = self.here
        self.jump(done)
        self.place(done)
        return self.op(f"phi double [ {a}, %{fast} ], [ {b}, %{slow_end} ]")

    def write_number_item(self, lst, index, x, line):
        """'set item i of scores to x', in place when it can."""
        at, fast, slow = self.number_item(lst, index)
        done = self.label("itemput")
        self.put(f"store double {x}, ptr {at}")
        self.jump(done)
        self.place(slow)
        self.call("void", "cn_list_put_number", ("ptr", lst), ("double", index), ("double", x), ("i32", line), checked=True)
        self.jump(done)
        self.place(done)

    def thing_number(self, thing, k):
        """Number part k of a thing: read in place while its number parts are kept plain."""
        flag, data, _, _, _ = self.nums_place(thing)
        fast, slow, done = self.label("partfast"), self.label("partslow"), self.label("partread")
        self.branch(self.op(f"icmp ne i8 {self.op(f'load i8, ptr {flag}')}, 0"), fast, slow)
        self.place(fast)
        a = self.op(f"load double, ptr {self.op(f'getelementptr inbounds double, ptr {self.op(f'load ptr, ptr {data}')}, i32 {k}')}")
        self.jump(done)
        self.place(slow)
        b = self.op(f"call double @cn_part_number(ptr {thing}, i32 {k})")
        self.jump(done)
        self.place(done)
        return self.op(f"phi double [ {a}, %{fast} ], [ {b}, %{slow} ]")

    def put_thing_number(self, thing, k, d):
        """Sets number part k in place."""
        flag, data, _, _, _ = self.nums_place(thing)
        fast, slow, done = self.label("partput"), self.label("partplain"), self.label("partset")
        self.branch(self.op(f"icmp ne i8 {self.op(f'load i8, ptr {flag}')}, 0"), fast, slow)
        self.place(fast)
        self.put(f"store double {d}, ptr {self.op(f'getelementptr inbounds double, ptr {self.op(f'load ptr, ptr {data}')}, i32 {k}')}")
        self.jump(done)
        self.place(slow)
        self.put(f"call void @cn_part_number_put(ptr {thing}, i32 {k}, double {d})")
        self.jump(done)
        self.place(done)

    def list_number(self, lst, k):
        """Item k (from 0) of a plain number list."""
        flag, data, _, _, size = self.nums_place(lst)
        fast, slow, done = self.label("numfast"), self.label("numslow"), self.label("numread")
        self.branch(self.op(f"icmp ne i8 {self.op(f'load i8, ptr {flag}')}, 0"), fast, slow)
        self.place(fast)
        index = k if size == "i64" else self.op(f"trunc i64 {k} to i32")
        a = self.op(f"load double, ptr {self.op(f'getelementptr inbounds double, ptr {self.op(f'load ptr, ptr {data}')}, {size} {index}')}")
        self.jump(done)
        self.place(slow)
        b = self.op(f"call double @cn_list_number(ptr {lst}, i64 {k})")
        self.jump(done)
        self.place(done)
        return self.op(f"phi double [ {a}, %{fast} ], [ {b}, %{slow} ]")

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
        """A new empty value of the kind."""
        saved, ended = self.lines, self.ended
        if into is not None:  # in the entry block
            self.lines, self.ended = into, False
        try:
            t = ll_type(kind)
            if t != "ptr":
                return zero_const(kind)
            if kind == TEXT:
                return self.text_const("", quick=into is None)
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
            if kind in ABLE:
                return "null"
            zeros = "".join("n" if part_kind == NUMBER else "t" if part_kind == TEXT else "-" for _, _, part_kind in THINGS[kind])
            thing = self.op(f"call ptr @cn_thing_zeroed(ptr {self.spec(kind)}, ptr {self.module.bytes_const(zeros.encode())})")
            for k, (_, _, part_kind) in enumerate(THINGS[kind]):
                if part_kind not in (NUMBER, TEXT):  # (those are a shared 0 or "" already, not a new value for each thing)
                    self.put(f"call void @cn_field_put(ptr {thing}, i32 {k}, ptr {self.box(self.zero(part_kind), part_kind)})")
            return thing
        finally:
            if into is not None:
                self.lines, self.ended = saved, ended

    def shape(self, kind, made=None):
        """What 'load X from' fills."""
        made = {} if made is None else made
        if kind in made:
            return made[kind]
        if kind.startswith("list of "):
            out = self.op("call ptr @cn_list_new()")
            self.put(f"call void @cn_shape_item(ptr {out}, ptr {self.shape(kind[8:], made)})")
            return out
        if kind.startswith("table of "):
            out = self.op("call ptr @cn_table_new()")
            self.put(f"call void @cn_shape_entry(ptr {out}, ptr {self.shape(kind[9:], made)})")
            return out
        if kind.startswith("command("):
            raise Unsupported(kind)
        if kind in ABLE:  # just the ability
            return self.op(f"call ptr @cn_thing(ptr {self.spec(kind)})")
        if kind in THINGS:
            thing = made[kind] = self.op(f"call ptr @cn_thing(ptr {self.spec(kind)})")
            for k, (_, _, part_kind) in enumerate(THINGS[kind]):
                self.put(f"call void @cn_field_shape(ptr {thing}, i32 {k}, ptr {self.shape(part_kind, made)})")
            return thing
        return self.box(self.zero(kind), kind)

    def spec(self, kind):
        """A kind as the library reads it."""
        return self.module.bytes_const("\x01".join([kind[6:]] + [" ".join(w) for _, w, _ in THINGS[kind]]).encode("utf-8"))

    def box(self, value, kind):
        """A number or yes/no as a value."""
        if kind == NUMBER:
            return self.op(f"call ptr @cn_box_number(double {value})")
        if kind == YESNO:
            return self.op(f"call ptr @cn_box_yesno(i1 {value})")
        return value  # a command is already a value: its machine code, and the names it keeps

    def unbox(self, value, kind):
        if kind in (NUMBER, YESNO):  # a value's number is 8 bytes in (machine.h's V)
            d = self.op(f"load double, ptr {self.op(f'getelementptr inbounds i8, ptr {value}, i64 8')}")
            return d if kind == NUMBER else self.op(f"fcmp une double {d}, 0.0")
        return value

    def copied(self, value, kind):
        """Lists, tables, places and things are copied when stored."""
        if ll_type(kind) == "ptr" and kind != TEXT and not kind.startswith("command("):
            if self.fresh(value):
                return value  # only just made, so nothing else holds it
            self.share(value)
        return value

    def share(self, value):
        """Held in one more place now."""
        self.count_holders(value, "add")

    def release(self, value):
        """A place that held value holds something else now."""
        self.count_holders(value, "sub")

    def count_holders(self, value, how):
        """How many more places hold it."""
        mark, done = self.label("count"), self.label("counted")
        self.branch(self.op(f"icmp eq ptr {value}, null"), done, mark)
        self.place(mark)
        at = self.op(f"getelementptr inbounds i8, ptr {value}, i64 4")
        n = self.op(f"load i8, ptr {at}")
        keep = self.op(f"icmp eq i8 {n}, {255 if how == 'add' else 0}")
        keep = self.op(f"or i1 {keep}, {self.op(f'icmp eq i8 {n}, 255')}") if how == "sub" else keep
        self.put(f"store i8 {self.op(f'select i1 {keep}, i8 {n}, i8 {self.op(f'{how} i8 {n}, 1')}')}, ptr {at}")
        self.jump(done)
        self.place(done)

    def something(self, thing, spec, k, line):
        """thing, or the "is nothing" problem."""
        bad, done = self.label("nothing"), self.label("something")
        self.branch(self.op(f"icmp eq ptr {thing}, null"), bad, done)
        self.place(bad)
        self.op(f"call ptr @cn_something(ptr null, ptr {spec}, i32 {k}, i32 {line})")
        self.jump(done)
        self.place(done)
        return thing

    def fresh(self, value):
        """value is new (not shared)."""
        made = f"  {value} = call ptr @"
        for line in reversed(self.lines[-8:]):
            if line.startswith(made):
                return line[len(made):].startswith(("cn_thing(", "cn_thing_zeroed(", "cn_list_new(", "cn_dup("))
        return False

    def slot(self, cpp, kind):
        """A name's place, made on first use."""
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
        value = self.op(f"load {ll_type(kind)}, ptr {self.where(cpp, kind)}")
        if kind == TEXT and cpp not in self.module.shared:  # (see cn_append)
            self.put(f"call void @cn_share(ptr {value})")
        return value

    def append(self, cpp, parts):
        """'set s to s plus ...' in place when it can."""
        texts = [self.as_text(emit(self, v), v.kind) for v in parts]
        for t in texts:
            self.put(f"call void @cn_append(ptr {self.where(cpp, TEXT)}, ptr {t})")

    def assign_thing(self, slot, value, kind):
        """A thing put where one is held."""
        parts = THINGS.get(kind, [])
        if not parts or any(k != NUMBER for _, _, k in parts) or HAS_KINDS_OF(kind):
            self.put(f"call void @cn_assign(ptr {slot}, ptr {value})")
            return
        to = self.op(f"load ptr, ptr {slot}")
        checks = [f"icmp eq ptr {to}, null", f"icmp eq ptr {value}, null", f"icmp eq ptr {to}, {value}"]
        bad = [self.op(c) for c in checks]
        look, fast, slow, done = self.label("asklook"), self.label("asfast"), self.label("asslow"), self.label("asdone")
        self.branch(self.op(f"or i1 {self.op(f'or i1 {bad[0]}, {bad[1]}')}, {bad[2]}"), slow, look)
        self.place(look)
        flag = lambda v: self.op(f"load i8, ptr {self.op(f'getelementptr inbounds i8, ptr {v}, i64 3')}")
        shared = self.op(f"load i8, ptr {self.op(f'getelementptr inbounds i8, ptr {to}, i64 4')}")
        ok = self.op(f"and i1 {self.op(f'icmp ne i8 {flag(to)}, 0')}, {self.op(f'icmp ne i8 {flag(value)}, 0')}")
        self.branch(self.op(f"and i1 {ok}, {self.op(f'icmp eq i8 {shared}, 0')}"), fast, slow)
        self.place(fast)
        data = lambda v: self.op(f"load ptr, ptr {self.op(f'getelementptr inbounds i8, ptr {v}, i64 {nums_at()}')}")
        a, b = data(value), data(to)
        for k in range(len(parts)):
            d = self.op(f"load double, ptr {self.op(f'getelementptr inbounds double, ptr {a}, i32 {k}')}")
            self.put(f"store double {d}, ptr {self.op(f'getelementptr inbounds double, ptr {b}, i32 {k}')}")
        self.jump(done)
        self.place(slow)
        self.put(f"call void @cn_assign(ptr {slot}, ptr {value})")
        self.jump(done)
        self.place(done)

    def own(self, cpp, kind):
        """Copy before changing if held elsewhere."""
        if ll_type(kind) != "ptr" or kind == TEXT or kind.startswith("command("):
            return self.load(cpp, kind)
        where = self.where(cpp, kind)
        have = self.op(f"load ptr, ptr {where}")
        look, copy, done = self.label("ownlook"), self.label("owncopy"), self.label("owned")
        before = self.here
        self.branch(self.op(f"icmp eq ptr {have}, null"), done, look)  # (nothing: no thing to copy)
        self.place(look)
        shared = self.op(f"icmp ne i8 {self.op(f'load i8, ptr {self.op(f'getelementptr inbounds i8, ptr {have}, i64 4')}')}, 0")
        self.branch(shared, copy, done)  # (V's shared flag, 4 bytes in)
        self.place(copy)
        made = self.op(f"call ptr @cn_own(ptr {have})")
        self.put(f"store ptr {made}, ptr {where}")
        self.jump(done)
        self.place(done)
        return self.op(f"phi ptr [ {have}, %{before} ], [ {have}, %{look} ], [ {made}, %{copy} ]")

    def store(self, cpp, kind, value):
        if kind.startswith("thing ") and not self.fresh(value):  # (into the thing already there, when only this name holds it)
            self.assign_thing(self.where(cpp, kind), value, kind)
            return
        mutable = ll_type(kind) == "ptr" and kind != TEXT and not kind.startswith("command(")
        old = self.op(f"load ptr, ptr {self.where(cpp, kind)}") if mutable else None
        self.put(f"store {ll_type(kind)} {self.copied(value, kind)}, ptr {self.where(cpp, kind)}")
        if mutable:
            self.release(old)

    def text_const(self, s, quick=True):
        """Program text: made once (quick: read straight from its slot once made)."""
        const, size = self.module.text(s)
        slot = const.replace("@s", "@ts")
        if slot not in self.module.text_slots:
            self.module.text_slots.add(slot)
            self.module.constants.append(f"{slot} = internal global ptr null")
        if not quick:
            return self.op(f"call ptr @cn_text_kept(ptr {const}, i64 {size}, ptr {slot})")
        a = self.op(f"load atomic ptr, ptr {slot} acquire, align {4 if TARGET == 'wasm' else 8}")
        start, make, done = self.here, self.label("tmake"), self.label("tdone")
        self.branch(self.op(f"icmp eq ptr {a}, null"), make, done)
        self.place(make)
        b = self.op(f"call ptr @cn_text_kept(ptr {const}, i64 {size}, ptr {slot})")
        end = self.here
        self.jump(done)
        self.place(done)
        return self.op(f"phi ptr [ {a}, %{start} ], [ {b}, %{end} ]")

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
        if TARGET != "wasm" and self.name != "main":  # look for a collector as it begins
            body[len(self.entry) + 1:len(self.entry) + 3] = [
                "  %waiting = load atomic i8, ptr @cn_stopping monotonic, align 1", "  %wanted = icmp ne i8 %waiting, 0",
                "  br i1 %wanted, label %wait, label %start", "wait:", "  call void @cn_statement()", "  br label %start", "start:"]
        if TARGET == "wasm":  # see cn_enter in runtime/machine.cpp
            slots = [l.split(" = ")[0].strip() for l in self.entry if l.endswith("= alloca ptr")]
            body[1 + len(self.entry):1 + len(self.entry)] = ["  call void @cn_enter()"] + [f"  call void @cn_slot(ptr {s})" for s in slots]
            body = [f"  call void @cn_leave(ptr {l.split()[2] if l.startswith('  ret ptr ') else 'null'})\n{l}" if l.startswith("  ret ") else l
                    for l in body]
        self.module.functions.append(f"define {gives} @cn_user_{self.name}({params}) {{\n" + "\n".join(body) + "\n}\n")


def function(module, name, inputs, gives, body, owner=None):
    """Writes one command."""
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


# ---- pieces the reader uses

def short_circuit(f, left, right, is_or):
    """'a or b' / 'a and b', short-circuit."""
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
    head = len(f.lines)
    f.put("call void @cn_statement()")  # each round: what the last round made may be freed
    cond = test()
    tested = len(f.lines)
    f.branch(cond, inside, out)
    f.place(inside)
    first = len(f.lines)
    f.loops.append((nxt, out))
    emit(f, body)
    f.loops.pop()
    f.place(nxt)
    if step:
        step()
    if (f.lines[head] == "  call void @cn_statement()" and makes_nothing(f.lines[head + 1:tested]) and first < len(f.lines)
            and f.lines[first] == "  call void @cn_statement()" and makes_nothing(f.lines[f.lines.index(f"{nxt}:", first):])):
        del f.lines[head]  # the body's first line does it each round (the test and the step make nothing)
    elif f.lines[head] == "  call void @cn_statement()" and makes_nothing(f.lines[head + 1:]):
        del f.lines[head]  # a loop that calls nothing only checks for a collector
        poll, wait = f.label("poll"), f.label("wait")
        f.jump(poll)
        f.place(poll)
        waiting = f.op("load atomic i8, ptr @cn_stopping monotonic, align 1")
        f.branch(f.op(f"icmp ne i8 {waiting}, 0"), wait, top)
        f.place(wait)
        f.put("call void @cn_statement()")
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


def count_from(f, cpp, lo, hi, body, by=None):
    """'for each n from 1 to 10' (end and step worked out once)."""
    f.store(cpp, NUMBER, emit(f, lo))
    last = f"%last{f.label('')}"
    f.entry.append(f"  {last} = alloca double")
    f.put(f"store double {emit(f, hi)}, ptr {last}")
    size = f"%by{f.label('')}"
    f.entry.append(f"  {size} = alloca double")
    f.put(f"store double {emit(f, by) if by is not None else number(1.0)}, ptr {size}")

    def step():
        f.store(cpp, NUMBER, f.op(f"fadd double {f.load(cpp, NUMBER)}, {f.op(f'load double, ptr {size}')}"))

    def test():
        x, end, s = f.load(cpp, NUMBER), f.op(f"load double, ptr {last}"), f.op(f"load double, ptr {size}")
        if by is None:
            return f.op(f"fcmp ole double {x}, {end}")
        up = f.op(f"and i1 {f.op(f'fcmp ogt double {s}, 0.0')}, {f.op(f'fcmp ole double {x}, {end}')}")
        down = f.op(f"and i1 {f.op(f'fcmp olt double {s}, 0.0')}, {f.op(f'fcmp oge double {x}, {end}')}")
        return f.op(f"or i1 {up}, {down}")
    loop(f, test, body, step)


def each_in(f, cpp, kind, seq, body):
    """'for each x in xs' over a copy."""
    items = f.hold(f.op(f"call ptr @cn_dup(ptr {emit(f, seq)})"))
    size = f.op(f"call i64 @cn_count_whole(ptr {items})")
    k = counter(f, "i")

    def test():
        now = f.op(f"load i64, ptr {k}")
        go = f.op(f"icmp slt i64 {now}, {size}")
        more, out = f.label("item"), f.label("noitem")
        f.branch(go, more, out)
        f.place(more)
        got = f.list_number(items, now) if kind == NUMBER else \
            f.unbox(f.op(f"call ptr @cn_list_item(ptr {items}, i64 {now})"), kind)
        f.put(f"store {ll_type(kind)} {got}, ptr {f.slot(cpp, kind)}")
        stored = f.label("itemkept")  # (reading the item may have made blocks of its own)
        f.place(stored)
        f.jump(out)
        f.place(out)
        return f.op(f"phi i1 [ true, %{stored} ], [ false, %{test.before} ]")

    def wrapped():
        test.before = f.here
        return test()

    def step():
        f.put(f"store i64 {f.op(f'add i64 {f.op(f'load i64, ptr {k}')}, 1')}, ptr {k}")
    loop(f, wrapped, body, step)


def invoke(f, command, args, ins, gives, line):
    """Does the command a value holds."""
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
    """'kept by' / 'changed by'."""
    holder = f.hold(f.op("call ptr @cn_list_new()"))  # a pointer: the same in every block below
    items = f.hold(f.op(f"call ptr @cn_dup(ptr {seq})"))
    f.hold(command)  # (made on this line, perhaps: each round below starts a new one)
    size = f.op(f"call i64 @cn_count_whole(ptr {items})")
    if TARGET == "wasm":  # what the line made stays young (see cn_enter)
        f.put("call void @cn_enter()")
    k = counter(f, "m")
    top, inside, out_label = f.label("each"), f.label("doing"), f.label("done")
    f.place(top)
    f.put("call void @cn_statement()")
    now = f.op(f"load i64, ptr {k}")
    f.branch(f.op(f"icmp slt i64 {now}, {size}"), inside, out_label)
    f.place(inside)
    if item == NUMBER:
        x = boxed = f.list_number(items, now)
    else:
        boxed = f.op(f"call ptr @cn_list_item(ptr {items}, i64 {now})")
        x = f.unbox(boxed, item)
    target = f.call("ptr", "cn_command_or_fail", ("ptr", command), ("i32", line))  # each time: it says which names it keeps
    answer = f.op(f"call {ll_type(gives)} {target}({ll_type(item)} {f.copied(x, item)})")
    f.check()
    if keep:
        yes, after = f.label("keep"), f.label("kept")
        f.branch(answer, yes, after)
        f.place(yes)
        if item == NUMBER:
            f.add_number(holder, x)
        else:
            f.put(f"call void @cn_list_add(ptr {holder}, ptr {f.copied(boxed, item)})")
        f.jump(after)
        f.place(after)
    else:
        if gives == NUMBER:
            f.add_number(holder, answer)
        else:
            f.put(f"call void @cn_list_add(ptr {holder}, ptr {f.box(answer, gives)})")
    f.put(f"store i64 {f.op(f'add i64 {now}, 1')}, ptr {k}")
    f.jump(top)
    f.place(out_label)
    if TARGET == "wasm":
        f.put(f"call void @cn_leave(ptr {holder})")
    return holder


def closure(f, name, inputs, gives, body):
    """'each x becomes ...': a function plus copies of the names it uses."""
    g = Fn(f.module, name, inputs, gives)
    g.owner = None
    for cpp, kind in inputs:
        g.slots[cpp] = (f"%n.{cpp}", kind)
    if gives:
        g.finish_with(f"ret {ll_type(gives)} {g.copied(emit(g, body), gives)}")
    else:
        emit(g, body)
    given = {cpp for cpp, _ in inputs}
    used = [(cpp, where, kind) for cpp, (where, kind) in g.slots.items() if cpp not in given]
    keeps = g.tmp()
    g.entry.append(f"  {keeps} = call ptr @cn_closure_env()")
    for k, (cpp, where, kind) in enumerate(used):
        item = g.tmp()
        g.entry.append(f"  {item} = call ptr @cn_list_item(ptr {keeps}, i64 {k})")
        if kind in (NUMBER, YESNO):
            plain = g.tmp()
            g.entry.append(f"  {plain} = call {ll_type(kind)} @cn_unbox_{'number' if kind == NUMBER else 'yesno'}(ptr {item})")
            item = plain
        g.entry.append(f"  store {ll_type(kind)} {item}, ptr {where}")
    g.done()
    made = f.op(f"call ptr @cn_command_make(ptr @cn_user_{g.name})")
    for cpp, _, kind in used:
        f.put(f"call void @cn_list_add(ptr {made}, ptr {f.box(f.load(cpp, kind), kind)})")
    return made


def meanwhile(f, piece):
    """'meanwhile ...': a function run alongside."""
    module = f.module
    module.alongside = getattr(module, "alongside", 0) + 1
    g = Fn(module, f"meanwhile_{module.alongside}", [("names", TEXT)], None)
    g.owner = None
    emit(g, piece)
    used = list(g.slots.items())  # (C++ name, (its place, kind)): only names the piece itself needed
    block = f.op(f"call ptr @cn_memory(i64 {8 * max(1, len(used))})")
    for k, (cpp, (where, kind)) in enumerate(used):
        at = f.op(f"getelementptr i8, ptr {block}, i64 {8 * k}")
        x = f.load(cpp, kind)
        f.put(f"store {ll_type(kind)} {f.op(f'call ptr @cn_deep(ptr {x})') if ll_type(kind) == 'ptr' and kind != TEXT and not kind.startswith('command(') else x}, ptr {at}")  # (nothing shared across threads)
        at = g.tmp()
        g.entry += [f"  {at} = getelementptr i8, ptr %p.names, i64 {8 * k}"]
        value = g.tmp()
        g.entry += [f"  {value} = load {ll_type(kind)}, ptr {at}", f"  store {ll_type(kind)} {value}, ptr {where}"]
    g.done()
    f.put(f"call void @cn_meanwhile(ptr @cn_user_{g.name}, ptr {block}, i64 {8 * max(1, len(used))})")


def attempt(f, tried, problem_cpp, fixes):
    """try: ... if that went wrong ..."""
    handler, end = f.label("wrong"), f.label("tried")
    f.handlers.append(handler)
    emit(f, tried)
    f.handlers.pop()
    f.jump(end)
    f.place(handler)
    for kind, fixed, kind_v in fixes:
        mine, other = f.label("mine"), f.label("other")
        if kind is None:
            f.jump(mine)
        else:
            f.branch(f.op(f"call i1 @cn_problem_is(ptr {emit(f, kind_v)})"), mine, other)
        f.place(mine)
        f.store(problem_cpp, TEXT, f.op("call ptr @cn_problem_text()"))
        emit(f, fixed)
        f.jump(end)
        f.place(other)
    f.check()  # still failed: on to the next 'try:' out, or out of the command
    f.jump(end)
    f.place(end)


def give_up(f):
    """After 'raise an error with'."""
    f.check()


# ---- built-in and library words: each is a small C function in a prebuilt library

ONE_STEP = {"remainder_of": "frem", "round": "llvm.round.f64", "floor": "llvm.floor.f64", "ceil": "llvm.ceil.f64",
            "trunc": "llvm.trunc.f64", "sqrt": "llvm.sqrt.f64", "fabs": "llvm.fabs.f64"}  # library words machine code does itself


def wrap(f, unit, head, template, args, gives, cpp_type, line):
    """Calls the C function for a built-in or library word."""
    simple = re.fullmatch(r"(?:std|stellanova)::(\w+)\(\{[as]0\}(?:, \{[as]1\})?\)", template)
    if simple and simple.group(1) in ONE_STEP and gives == NUMBER and all(a.kind == NUMBER for a in args):
        op = ONE_STEP[simple.group(1)]  # one machine instruction, not a call (the same answers)
        given = [emit(f, a) for a in args]
        if op == "frem":
            return f.op(f"frem double {given[0]}, {given[1]}")
        f.module.declare(f"declare double @{op}(double)")
        return f.op(f"call double @{op}(double {given[0]})")
    for a in args:
        if a.kind in THINGS or ll_type(a.kind) is None:
            raise Unsupported(f"{a.kind} given to {template[:40]}")
    if gives in THINGS:
        raise Unsupported(f"{gives} from {template[:40]}")
    types = [cpp_type(a.kind) for a in args]
    ret = {"double": "double", "i1": "bool"}.get(ll_type(gives), "V*") if gives else "void"
    import hashlib
    name = "cn_w_" + hashlib.sha1("|".join([unit, template, ret, str(unit in NEVER_WAIT)] + types).encode("utf-8")).hexdigest()[:16]
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
            "{\n" + ("" if unit in NEVER_WAIT else "\tCnParked parked;\n") + f"\ttry {{ {result} }}\n\tcatch (const stellanova::Problem& problem) {{ cn_set_problem(problem); return {fallback}; }}\n"
            f"#ifdef __wasm__\n\tcatch (const std::system_error&) {{ cn_set_problem({{line, ONE_THREAD}}); return {fallback}; }}\n#endif\n}}\n")
    f.module.units.setdefault(unit, [head, {}])[1][name] = code
    ll_ret = ll_type(gives) if gives else "void"
    f.module.declare(f"declare {ll_ret} @{name}({', '.join([ll_type(a.kind) for a in args] + ['i32'])})")
    values = [(ll_type(a.kind), f.box(emit(f, a), a.kind) if a.kind.startswith("command(") else emit(f, a)) for a in args] + [("i32", str(line))]
    return f.call(ll_ret, name, *values, checked=True)


WRAPPER_FORM = "3: one thread"  # change when wrap() changes, so old ones are remade


def unit_file(unit, head, wrappers):
    """runtime/built/w_<unit>.cpp: every wrapper needed so far."""
    import hashlib
    path = HERE / "runtime" / "built" / f"w_{re.sub(r'[^a-z0-9]+', '_', unit)}.cpp"
    mark = "// head " + hashlib.sha1((head + WRAPPER_FORM).encode("utf-8")).hexdigest()
    have = {}
    if path.exists():
        old = path.read_text(encoding="utf-8")
        if mark in old:  # same library: keep the wrappers
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


# ---- making the .exe

def find_clang():
    for place in [os.environ.get("STELLANOVA_CLANG"), r"C:\Program Files\LLVM\bin\clang++.exe", shutil.which("clang++")]:
        if place and Path(place).exists():
            return place
    if sys.platform.startswith("linux"):
        raise RuntimeError("I can't find clang. Install it (sudo apt install clang).")
    raise RuntimeError("I can't find LLVM's clang. Install LLVM (winget install LLVM.LLVM).")


def compile_once(src, out, newer_than):
    """src compiled into out, again only when one of newer_than changed."""
    if not out.exists() or out.stat().st_mtime < max(p.stat().st_mtime for p in newer_than):
        out.parent.mkdir(exist_ok=True)
        done = subprocess.run([find_clang(), "-c", "-O2", "-std=c++20", "-Wno-everything", *target_flags(),
                               "-I", str(HERE / "runtime"), str(src), "-o", str(out)], capture_output=True, text=True, stdin=subprocess.DEVNULL)
        if done.returncode:
            if src.name.startswith("w_"):  # a wrapper that can't compile: start that file again
                src.unlink(missing_ok=True)
            raise RuntimeError(f"Stellanova's machine-code library ({src.name}) didn't compile:\n" + done.stderr)
    return out


def sysroot():
    root = WASI / "wasi-sysroot-34.0"
    if not root.exists():
        raise RuntimeError(f"WebAssembly needs the WASI sysroot: unpack wasi-sysroot-34.0.tar.gz and libclang_rt-34.0.tar.gz "
                           f"(from github.com/WebAssembly/wasi-sdk/releases/tag/wasi-sdk-34) into {WASI}.")
    return root


def target_flags():
    if TARGET == "linux":
        return ["-I/usr/include/freetype2", "-fPIC"]  # FreeType's headers; -fPIC so plugins can link it
    if TARGET != "wasm":
        return ["-fms-extensions"]
    root = sysroot()
    return ["--target=wasm32-wasip1-threads", "-pthread", f"--sysroot={root}", "-isystem", str(root / "include" / "wasm32-wasip1-threads" / "eh"),
            "-fwasm-exceptions", "-mllvm", "-wasm-use-legacy-eh=false"]


def object_suffix():
    return {"wasm": ".wasm.o", "linux": ".o"}.get(TARGET, ".obj")


def runtime_object():
    """runtime/machine.cpp compiled once (again only when it or stellanova.h changes)."""
    runtime = HERE / "runtime"
    return compile_once(runtime / "machine.cpp", runtime / "built" / f"stellanova_machine{object_suffix()}",
                        [runtime / "machine.cpp", runtime / "machine.h", runtime / "stellanova.h", HERE / "machine.py"])


def make_exe(ll_text_, exe, work, units=None, plugin=False):
    """LLVM code to an exe (or .dll/.so plugin). Returns an error, or None."""
    ll = Path(work) / "program.ll"
    ll.write_text(ll_text_, encoding="utf-8")
    try:
        objects = [str(runtime_object())]
        runtime = HERE / "runtime"
        for unit, (head, wrappers) in sorted((units or {}).items()):
            src = unit_file(unit, head, wrappers)
            if TARGET == "wasm":
                if unit.startswith("c library"):
                    return f"C libraries ({unit[len('c library'):].strip()}) can't be used in a WebAssembly program."
                try:
                    objects.append(str(compile_once(src, src.with_suffix(object_suffix()), [src, runtime / "machine.h", runtime / "stellanova.h"])))
                except RuntimeError:
                    return f"The {unit} words can't be used in a WebAssembly program yet."
                continue
            try:
                objects.append(str(compile_once(src, src.with_suffix(object_suffix()), [src, runtime / "machine.h", runtime / "stellanova.h"])))
            except RuntimeError:
                if TARGET != "linux":
                    raise
                return f"The {unit} words can't be used in a Linux program yet."
        clang = find_clang()
    except RuntimeError as err:
        return str(err)
    link = []
    if TARGET == "wasm":
        root = sysroot()
        link = [f for f in target_flags() if "include" not in f and f != "-isystem"] + ["-nodefaultlibs", f"-L{root / 'lib' / 'wasm32-wasip1-threads' / 'eh'}", "-lc++", "-lc++abi", "-lunwind", "-lc",
                str(WASI / "libclang_rt-34.0" / "wasm32-unknown-wasip1-threads" / "libclang_rt.builtins.a"), "-Wl,-z,stack-size=8388608",
                "-Wl,--import-memory,--export-memory,--shared-memory,--max-memory=4294967296"]  # memory shared by threads ('meanwhile')
    elif TARGET == "linux":
        link = ["-pthread", "-fPIC"] + sorted({"-l" + lib for head, _ in (units or {}).values() for lib in re.findall(r"^// linux link: (.+)$", head, re.M)})
    if plugin:
        link += ["-shared"] + (["-Wl,/EXPORT:stellanova_call", "-Wl,/EXPORT:stellanova_has"] if TARGET == "windows" else [])
    done = subprocess.run([clang, "-O2", "-Wno-override-module", str(ll), *objects, *link, "-o", str(exe)],
                          capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if done.returncode:
        return ("Stellanova wrote machine code LLVM didn't accept. That is a bug in Stellanova, not in your script.\n"
                + done.stderr + f"\n(the LLVM code is in {ll})")
    return None
