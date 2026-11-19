"""Self-check for stellanova.py. Run: py -3 test_stellanova.py"""
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.environ["STELLANOVA_DIRECT"] = "1"  # direct runs use the interpreter here, to compare with built ones
sys.path.insert(0, str(HERE))
import stellanova as translate
translate.LOGIC = Path(__file__).resolve().parent / "examples"


END = "and the universe said i love you\n"
os.environ["STELLANOVA_GOT"] = tempfile.mkdtemp()  # libraries got while testing (none of the real ones)


def smtp_catcher(port, got):
    """A tiny SMTP server for the email test."""
    import socket
    import threading
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", port))
    listener.listen()

    def one(s):
        with s:
            f = s.makefile("rb")
            s.sendall(b"220 here\r\n")
            while True:
                line = f.readline()
                if not line:
                    return
                word = line.strip().upper()
                if word.startswith(b"EHLO") or word.startswith(b"HELO"):
                    s.sendall(b"250-here\r\n250 OK\r\n")
                elif word.startswith(b"DATA"):
                    s.sendall(b"354 go on\r\n")
                    text = b""
                    while True:
                        row = f.readline()
                        if row in (b".\r\n", b".\n", b""):
                            break
                        text += row
                    got.append(text.decode("utf-8", "replace").replace("\r\n", "\n"))
                    s.sendall(b"250 kept\r\n")
                elif word.startswith(b"QUIT"):
                    s.sendall(b"221 bye\r\n")
                    return
                else:
                    s.sendall(b"250 OK\r\n")

    def loop():
        while True:
            s, _ = listener.accept()
            threading.Thread(target=one, args=(s,), daemon=True).start()
    threading.Thread(target=loop, daemon=True).start()


def web_stub(port):
    """A tiny web server that says back what it got."""
    import http.server
    import threading

    class Said(http.server.BaseHTTPRequestHandler):
        def go(self):
            body = self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode()
            said = (f"{self.command} {self.path} [{self.headers.get('X-Pet', '')}] [{self.headers.get('Content-Type', '')}] "
                    f"[{body}]").encode()
            self.send_response(404 if self.path == "/missing" else 201 if self.command == "POST" else 200)
            self.send_header("Content-Length", str(len(said)))
            self.end_headers()
            self.wfile.write(said)
        do_GET = do_POST = do_PUT = do_DELETE = go

        def log_message(self, *_):
            pass
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Said)
    threading.Thread(target=server.serve_forever, daemon=True).start()


def websocket_echo(port):
    """A tiny WebSocket echo server."""
    import base64
    import hashlib
    import socket
    import threading

    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", port))
    listener.listen()

    def one(s):
        with s:
            data = b""
            while b"\r\n\r\n" not in data:
                more = s.recv(4096)
                if not more:
                    return
                data += more
            key = next(l.split(b":", 1)[1].strip() for l in data.split(b"\r\n") if l.lower().startswith(b"sec-websocket-key"))
            accept = base64.b64encode(hashlib.sha1(key + b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11").digest())
            s.sendall(b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: " + accept + b"\r\n\r\n")
            buf = data[data.index(b"\r\n\r\n") + 4:]

            def need(n):
                nonlocal buf
                while len(buf) < n:
                    more = s.recv(4096)
                    if not more:
                        raise ConnectionError
                    buf += more
                out, buf = buf[:n], buf[n:]
                return out
            try:
                while True:
                    a, b = need(2)
                    op, n = a & 15, b & 127
                    if n >= 126:
                        n = int.from_bytes(need(2 if n == 126 else 8), "big")
                    mask = need(4) if b & 0x80 else b"\0\0\0\0"
                    payload = bytes(x ^ mask[k % 4] for k, x in enumerate(need(n)))
                    if op == 8:
                        s.sendall(b"\x88\x00")
                        return
                    reply = b"echo: " + payload
                    head = bytes([0x81, len(reply)]) if len(reply) < 126 else bytes([0x81, 126]) + len(reply).to_bytes(2, "big")
                    s.sendall(head + reply)
            except (ConnectionError, OSError):
                return

    def loop():
        while True:
            s, _ = listener.accept()
            threading.Thread(target=one, args=(s,), daemon=True).start()
    threading.Thread(target=loop, daemon=True).start()


def run(body, part_of="this is part of: creature body\n\n"):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "probe.stella"
        p.write_text(part_of + body, encoding="utf-8")
        return translate.translate(p)


def error(body, part_of="this is part of: creature body\n\n"):
    try:
        run(body, part_of)
    except translate.ScriptError as e:
        return e.line, e.message
    raise AssertionError("expected a script error")


def tutorial_checks():
    """TUTORIAL.md programs print what they show."""
    import re
    import subprocess
    doc = (HERE / "TUTORIAL.md").read_text(encoding="utf-8")
    blocks = re.findall(r"```(\w*)\n(.*?)```", doc, re.S)
    ran = 0
    for k, (fence, body) in enumerate(blocks):
        if CLOSING_LINE not in body:
            continue
        with tempfile.TemporaryDirectory() as d:
            script = Path(d) / "tutorial.stella"
            script.write_text(body, encoding="utf-8")
            translate.LOGIC = Path(d)
            translate.read_script(script)  # raises on any mistake
            if fence == "stellanova":
                assert blocks[k + 1][0] == "output", f"a program in TUTORIAL.md has no output block after it:\n{body}"
                out = subprocess.run([sys.executable, str(HERE / "stellanova.py"), "run", str(script)],
                                     capture_output=True, text=True, encoding="utf-8", cwd=d)
                assert out.stdout == blocks[k + 1][1] and not out.stderr, f"TUTORIAL.md:\n{body}\nprinted:\n{out.stdout}{out.stderr}"
                ran += 1
    assert ran >= 8, ran
    # whole programs in LANGUAGE.md have no mistakes
    whole = [b for b in re.findall(r"^```\n(.*?)^```", (HERE / "LANGUAGE.md").read_text(encoding="utf-8"), re.S | re.M)
             if re.search(r"^genesis:", b, re.M)]
    for body in whole:
        with tempfile.TemporaryDirectory() as d:
            script = Path(d) / "language.stella"
            script.write_text(body, encoding="utf-8")
            translate.LOGIC = Path(d)
            try:
                translate.read_script(script)
            except translate.ScriptError as err:  # a program for a web page: checked the way it will be made
                assert "only works in a program made for the web" in err.message, err.message
                assert translate.web(script, d) is None, body
    assert len(whole) >= 6, len(whole)
    translate.LOGIC = HERE / "examples"


CLOSING_LINE = "and the universe said i love you"


def program_checks():
    """Programs of their own: text, say, ask, loops, calling commands."""
    prog = lambda body: run(body, "")
    perr = lambda body: error(body, "")
    cpp = prog('genesis:\n  ask "Name? " into name\n  repeat 3 times:\n    greet with name, 2\nand the universe said i love you\n\n'
               'to greet, given who (text) and times (a number):\n  scrawl "Hi " plus who, "! x", times\n' + END)
    assert "void Greet(const std::string& who, double times);" in cpp, cpp
    assert 'name = stellanova::ask_text(std::string("Name? "));' in cpp, cpp
    assert "Greet(name, 2.0);" in cpp, cpp
    assert "int main(int count, char** given)" in cpp, cpp
    pass
    assert perr("genesis:\n  greet with 1\n" + END)[1].startswith("I don't know how to start a line with 'greet'")
    assert perr("genesis:\n  hi with 1\n" + END + 'to hi, given who (text):\n  cease\n' + END) == (2, "Input 1 of 'hi' must be text, not a number.")
    assert perr("genesis:\n  hi\n" + END + 'to hi, given who (text):\n  cease\n' + END) == (2, "'hi' needs 1 input, but this gives it 0.")
    assert perr('genesis:\n  scrawl "oops\n' + END)[1].startswith("This text has no closing")
    assert perr('genesis:\n  set x to "a" minus 1\n' + END)[1] == "I can't subtract a number from text."
    assert perr('genesis:\n  as long as 5:\n    cease\n' + END)[1].startswith("'as long as' needs something that is yes or no")
    assert perr('genesis:\n  repeat "x" times:\n    cease\n' + END)[1].startswith("'repeat' needs a number of times")

    # Giving back, lists, kinds of things, files: the plain errors.
    assert perr('genesis:\n  cease\n' + END + "to twice, given x (a number), returning a number:\n  return \"no\"\n" + END) \
        == (5, "This command returns a number, not text.")
    assert perr("genesis:\n  return 1\n" + END)[1].startswith("'return' only works in a command that says")
    assert perr('genesis:\n  cease\n' + END + 'to two, returning a number:\n  cease\n' + END)[1].startswith("This command returns a number, so leave it")
    assert perr("genesis:\n  set x to hello\n" + END + 'to hello:\n  cease\n' + END)[1] == "'hello' doesn't return anything, so it can't be used as a value."
    assert perr('genesis:\n  set s to a list of numbers\n  add "x" to s\n' + END)[1] == "This list holds numbers, so I can't add text to it."
    assert perr("genesis:\n  set s to a list of (1, \"a\")\n" + END)[1] == "A list holds one kind of thing, but this mixes a number and text."
    assert perr('genesis:\n  for each n in 5:\n    cease\n' + END)[1] == "'for each ... in' needs a list, but this is a number."
    assert perr("a pet has:\n  name (text)\n" + END + 'genesis:\n  set p to conjure a pet\n  scrawl the age of p\n' + END)[1].startswith("I don't know 'age")
    assert perr("a pet has:\n  name (text)\n" + END + 'genesis:\n  set p to conjure a dog\n' + END)[1].startswith("There is no kind of thing called 'dog'")
    assert perr("a pet has:\n  best friend (a pet)\n" + END + 'genesis:\n  cease\n' + END)[1].startswith("A pet can't hold a whole pet")
    assert perr('a pet has:\n  name (text)\n\ngenesis:\n  cease\n' + END)[1].startswith("The description of 'pet' must end with")
    assert perr("genesis:\n  set n to 5 as a number\n" + END)[1] == "'as a number' turns text into a number, but this is a number."

    assert perr('genesis:\n  otherwise: cease\n' + END)[1] == "'otherwise' needs an 'if' line just above it, at the same indent."
    assert perr('use: nothing here\ngenesis:\n  cease\n' + END)[1].startswith("There is no library called 'nothing here'. Libraries: animation, big numbers, computer, database, email, encryption, engine, folders, forms, hashing, json, letters, maths, network, page, patterns, pictures, screen, server, sound, sound making, spreadsheet, time, web, window, zip")

    # Real programs run both ways must print the same.
    import subprocess
    try:
        compiler = None if os.environ.get("STELLANOVA_NO_BUILD") else translate.machine.find_clang()
    except RuntimeError:
        compiler = None
    if not compiler:
        print("(only running directly: no LLVM found)")
    node = shutil.which("node") if not os.environ.get("STELLANOVA_NO_WEB") else None
    web_skipped, web_runs = [], [0]
    wasm_skipped, wasm_runs = [], [0]
    linux_skipped = []

    def both(source, typed="", others=None):
        with tempfile.TemporaryDirectory() as d:
            script = Path(d) / "probe.stella"
            script.write_text(source, encoding="utf-8")
            for name, other in (others or {}).items():
                if isinstance(other, bytes):
                    (Path(d) / name).write_bytes(other)
                else:
                    (Path(d) / name).write_text(other, encoding="utf-8")
            direct = subprocess.run([sys.executable, str(HERE / "stellanova.py"), "run", str(script)],
                                    input=typed, capture_output=True, text=True, encoding="utf-8", cwd=d)
            if compiler:
                exe = Path(d) / "probe.exe"
                problem = translate.build(script, exe)
                if problem and "can't be used in a Linux program yet" in problem:
                    linux_skipped.append(problem)
                else:
                    assert problem is None, problem
                    built = subprocess.run([str(exe)], input=typed, capture_output=True, text=True, encoding="utf-8", cwd=d)
                    assert (built.stdout, built.stderr, built.returncode) == (direct.stdout, direct.stderr, direct.returncode), \
                        f"built: {built.stdout!r} {built.stderr!r} {built.returncode}\ndirect: {direct.stdout!r} {direct.stderr!r} {direct.returncode}"
            if node and os.environ.get("STELLANOVA_TEST_WASM"):  # as WebAssembly, the collector working hard
                problem = translate.wasm(script)
                if problem is None:
                    wasm_runs[0] += 1
                    made = subprocess.run([node, "probe.mjs"], input=typed, capture_output=True, text=True, encoding="utf-8", cwd=d,
                                          env=dict(os.environ, STELLANOVA_COLLECT_OFTEN="1"))
                    if "a WebAssembly program has only one thread" in made.stderr:
                        wasm_skipped.append(made.stderr.strip())
                    else:
                        assert (made.stdout, made.stderr, made.returncode) == (direct.stdout, direct.stderr, direct.returncode), \
                            f"wasm: {made.stdout!r} {made.stderr!r} {made.returncode}\ndirect: {direct.stdout!r} {direct.stderr!r} {direct.returncode}\n" + source
                else:
                    assert "WebAssembly" in problem, problem
                    wasm_skipped.append(problem)
            if node:  # and made for the web: the same again, run by node
                problem = translate.web(script)
                if problem is None:
                    web_runs[0] += 1
                    made = subprocess.run([node, "probe.js"], input=typed, capture_output=True, text=True, encoding="utf-8", cwd=d)
                    assert (made.stdout, made.stderr, made.returncode) == (direct.stdout, direct.stderr, direct.returncode), \
                        f"web: {made.stdout!r} {made.stderr!r} {made.returncode}\ndirect: {direct.stdout!r} {direct.stderr!r} {direct.returncode}\n" \
                        + (Path(d) / "probe.js").read_text(encoding="utf-8")
                else:
                    assert "can't be used in a web program" in problem, problem
                    web_skipped.append(problem)
            return direct

    out = both('genesis:\n  ask "Name? " into name\n  ask "Age? " into age (a number)\n'
               '  repeat 2 times: scrawl "Hello, " plus name plus "!"\n'
               '  scrawl "Next year you are ", age plus 1, ". Grown up: ", age is at least 18\n' + END, "Sam\nlots\n20.5\n").stdout
    assert out == "Name? Age? Please type a number.\nAge? Hello, Sam!\nHello, Sam!\nNext year you are 21.5. Grown up: yes\n", repr(out)

    out = both('genesis:\n  ask "Again? " into again (yes or no)\n  scrawl again\n  ask "Sure? " into again\n  scrawl not again\n' + END,
               "maybe\n YES \nn\n").stdout
    assert out == "Again? Please type yes or no.\nAgain? yes\nSure? yes\n", repr(out)

    # try: catches problems the same both ways.
    out = both('use: web\ngenesis:\n  for each n from 1 to 3:\n    try:\n      scrawl item n of a list of (10, 20)\n'
               '    if that went wrong:\n      scrawl "Oops: ", the wound\n  try:\n    set x to contents of file "nope.txt"\n'
               '    scrawl "not here"\n  if that went wrong:\n    scrawl the wound\n  try:\n    risky\n  if that went wrong:\n'
               '    scrawl "caught ", the wound\n  try:\n    scrawl web page "http://localhost:1/"\n  if that went wrong:\n'
               '    scrawl "no web"\n  scrawl item 7 of a list of (1)\n' + END +
               'to risky:\n  scrawl "before"\n  scrawl letter 5 of "abc"\n  scrawl "after"\n' + END)
    assert out.stdout == ("10\n20\nOops: there is no item 3 in a list of 2 items. Items are counted from 1.\n"
                          'there is no file called "nope.txt" (or it can\'t be opened).\n'
                          "before\ncaught there is no letter 5 in text of 3 letters.\nno web\n"), repr(out.stdout)
    assert out.stderr == "Line 21: there is no item 7 in a list of 1 item. Items are counted from 1.\n", repr(out.stderr)
    assert perr('genesis:\n  try:\n    cease\n  scrawl 1\n' + END)[1].startswith("'try:' needs an 'if that went wrong:' line")
    assert perr('genesis:\n  if that went wrong:\n    cease\n' + END)[1].startswith("'if that went wrong:' goes right after")

    out = both('genesis:\n  scrawl (2 divided by 3) rounded to 2 decimal places, " ", 2.675 rounded to 2 decimal places, " ", 1234.5 rounded to 0 decimal places,'
               ' " ", -1.25 rounded to 1 place\n  scrawl 1 rounded to 1.5 decimal places\n' + END)
    assert out.stdout == "0.67 2.68 1235 -1.3\n", repr(out.stdout)
    assert out.stderr == "Line 3: I can round to 0 to 15 places, not 1.5.\n", repr(out.stderr)

    # insert, and commands written where used.
    out = both('to do twice, given f (a command given a number returning a number) and x (a number), returning a number:\n'
               '  return invoke f with (invoke f with x)\n' + END +
               'genesis:\n  set drinks to a list of ("milk", "juice")\n  insert "tea" at 2 in drinks\n  insert "water" at 1 in drinks\n'
               '  insert "cola" at 5 in drinks\n  scrawl drinks\n  set k to 3\n  set numbers to a list of (4, 9, 15, 30)\n'
               '  scrawl numbers changed by each n becomes n times k\n  scrawl numbers kept by each n becomes n exceeds 10\n'
               '  set add k to each x (a number) becomes x plus k\n  set k to 100\n  scrawl invoke add k with 1\n'
               '  scrawl do twice with (each x (a number) becomes x times x, 3)\n'
               '  set join to each left (text) and right (text) becomes left plus "-" plus right\n  scrawl invoke join with ("tea", "cake")\n'
               '  set fs to a list of (each x (a number) becomes x plus 1, add k)\n  for each g in fs: scrawl invoke g with 10\n'
               '  insert "x" at 9 in drinks\n' + END)
    assert out.stdout == "water, milk, tea, juice, cola\n12, 27, 45, 90\n15, 30\n4\n81\ntea-cake\n11\n13\n", repr(out.stdout)
    assert out.stderr == "Line 22: there is no item 9 in a list of 5 items. Items are counted from 1.\n", repr(out.stderr)
    assert perr('genesis:\n  set f to each x becomes x\n' + END)[1].startswith("Say what kind 'x' is")

    # Powers, bits, and whole numbers of any size.
    out = both('use: big numbers\ngenesis:\n  scrawl 2 to the power 10, " ", 3 times 2 to the power 3\n'
               '  scrawl 12 bitwise and 10, " ", 12 bitwise or 10, " ", 12 bitwise exclusive or 10\n'
               '  scrawl 1 shifted left by 40, " ", 1024 shifted right by 3, " ", -8 shifted right by 1\n'
               '  set huge to big power with ("2", 100)\n  scrawl huge, " ", big plus with (huge, "1")\n'
               '  scrawl big times with ("-123456789123456789", "987654321987654321")\n'
               '  scrawl big divided by with (huge, "7"), " r ", big remainder with (huge, "7")\n'
               '  scrawl big divided by with ("-7", "2"), " ", big remainder with ("-7", "2"), " ", big compare with ("-3", "3")\n'
               '  try:\n    scrawl 1.5 bitwise and 1\n  if that went wrong:\n    scrawl the wound\n'
               '  scrawl (-8) to the power 0.5\n' + END)
    assert out.stdout == ("1024 24\n8 14 6\n1099511627776 128 -4\n"
                          "1267650600228229401496703205376 1267650600228229401496703205377\n"
                          "-121932631356500531347203169112635269\n181092942889747057356671886482 r 2\n-4 1 -1\n"
                          "bits need whole numbers smaller than 9007199254740992, not 1.5.\n"), repr(out.stdout)
    assert out.stderr == "Line 15: -8 to the power 0.5 can't be worked out (it is too big, or not a real number).\n", repr(out.stderr)

    # Bytes: text to the numbers 0 to 255 and back.
    out = both('use: letters\ngenesis:\n  set b to the bytes of the text "hi!"\n  scrawl b\n  add 33 to b\n'
               '  scrawl the text of the bytes b\n  scrawl the text of the bytes a list of (300)\n' + END)
    assert out.stdout == "104, 105, 33\nhi!!\n", repr(out.stdout)
    assert out.stderr == "Line 7: a byte is a whole number from 0 to 255, not 300.\n", repr(out.stderr)

    # Kinds of problem.
    out = both(''.join([
               'to fill up, given litres (a number):\n'
               '  if litres exceeds 50:\n'
               '    raise a fuel problem with "the tank holds 50 litres"\n'
               '  if litres falls below 0:\n'
               '    raise a sign problem with "litres can\'t be less than 0"\n'
               '  scrawl "filled ", litres\n'
               'and the universe said i love you\n'
               '\n'
               'to careful fill, given litres (a number):\n'
               '  try:\n'
               '    fill up with litres\n'
               '  if that went wrong with a fuel problem:\n'
               '    scrawl "fuel: ", the wound\n'
               'and the universe said i love you\n'
               '\n'
               'genesis:\n'
               '  careful fill with 10\n'
               '  careful fill with 80\n'
               '  try:\n'
               '    careful fill with -1\n'
               '  if that went wrong with a fuel problem:\n'
               '    scrawl "never"\n'
               '  if that went wrong with a sign problem:\n'
               '    scrawl "sign: ", the wound\n'
               '  try:\n'
               '    scrawl item 9 of a list of (1)\n'
               '  if that went wrong with a fuel problem:\n'
               '    scrawl "never"\n'
               '  if that went wrong:\n'
               '    scrawl "other: ", the wound\n'
               '  careful fill with -2\n'
               'and the universe said i love you\n'
               ]))
    assert out.stdout == ("filled 10\nfuel: the tank holds 50 litres\nsign: litres can't be less than 0\n"
                          "other: there is no item 9 in a list of 1 item. Items are counted from 1.\n"), repr(out.stdout)
    assert out.stderr == "Line 5: litres can't be less than 0\n", repr(out.stderr)

    # Commands for a kind, kept as values.
    out = both(''.join([
               'a pet has:\n'
               '  name (text)\n'
               '  age (a number)\n'
               'and the universe said i love you\n'
               '\n'
               'to speak, for a pet:\n'
               '  scrawl name, " makes a sound"\n'
               'and the universe said i love you\n'
               '\n'
               'to grow, for a pet, given years (a number):\n'
               '  set age to age plus years\n'
               'and the universe said i love you\n'
               '\n'
               'to summary, for a pet, returning text:\n'
               '  return name plus " is " plus age\n'
               'and the universe said i love you\n'
               '\n'
               'genesis:\n'
               '  set tom to conjure a pet\n'
               '  set the name of tom to "Tom"\n'
               '  set talk to the command speak\n'
               '  invoke talk with tom\n'
               '  set older to the command grow\n'
               '  set tom to invoke older with (tom, 3)\n'
               '  invoke older with (tom, 100)\n'
               '  scrawl the age of tom\n'
               '  set tell to the command summary\n'
               '  scrawl invoke tell with tom\n'
               '  set jobs to a list of commands given a pet returning a pet\n'
               '  add the command speak to jobs\n'
               '  for each job in jobs:\n'
               '    invoke job with tom\n'
               'and the universe said i love you\n'
               ]))
    assert out.stdout == "Tom makes a sound\n3\nTom is 3\nTom makes a sound\n", repr(out.stdout)

    # Markup: HTML's loose ways, and XML.
    out = both('use: markup.stella\n\ngenesis:\n'
               '  set page to "<!DOCTYPE html><html><body><!-- note --><p class=\'intro\'>Fish &amp; chips<br>today</p><ul><li><a href=" plus '
               'a quotation mark plus "/one" plus a quotation mark plus ">One</a><li><a href=two>Two</a></ul><script>if (a < b) x();</script></body></html>"\n'
               '  set whole to read markup page\n  for each link in parts named with (whole, "a"):\n'
               '    scrawl attribute with (link, "href"), " ", the content of link\n'
               '  set p to item 1 of parts named with (whole, "p")\n'
               '  scrawl attribute with (p, "class"), " [", all words in p, "] ", the size of the parts of p\n'
               '  scrawl the size of parts named with (whole, "li"), " ", the content of item 1 of parts named with (whole, "script")\n'
               '  set feed to read markup "<?xml version=\'1.0\'?><feed><item id=\'1\'><title>A</title></item><item id=\'2\'><title>B &lt;b&gt;</title></item></feed>"\n'
               '  for each item in parts named with (feed, "item"):\n    scrawl attribute with (item, "id"), ": ", all words in item\n' + END)
    assert out.stdout == "/one One\ntwo Two\nintro [Fish & chipstoday] 1\n2 if (a < b) x();\n1: A\n2: B <b>\n", repr(out.stdout)

    # Options: --name, --name=value, plain words, --.
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "o.stella").write_text('use: options.stella\n\ngenesis:\n  scrawl has option "loud", " ", has option "quiet", " [", option value "size", '
                                          '"] [", option value with ("name", "nobody"), "] [", option value "loud", "]"\n  scrawl plain words\n' + END, encoding="utf-8")
        typed = ["--size=3", "--loud", "a.txt", "--", "--quiet", "b"]
        said = subprocess.run([sys.executable, str(HERE / "stellanova.py"), "run", "o.stella", *typed], capture_output=True, text=True, cwd=d).stdout
        assert said == "yes no [3] [nobody] []\na.txt, --quiet, b\n", said
        if compiler:
            assert translate.build(Path(d) / "o.stella", Path(d) / "o.exe") is None
            assert subprocess.run([str(Path(d) / "o.exe"), *typed], capture_output=True, text=True, cwd=d).stdout == said

    # Physics: a box falls, bounces and lands.
    out = both(''.join([
               'use: physics.stella\n'
               '\n'
               'genesis:\n'
               '  set w to conjure a physics world\n'
               '  set the gravity of w to 1000\n'
               '  include the body with (w, a wall at with (0, 300, 400, 20))\n'
               '  include the body with (w, a wall at with (300, 0, 20, 300))\n'
               '  set ball to a box at with (100, 100, 20, 20)\n'
               '  set the bounciness of ball to 0.5\n'
               '  include the body with (w, ball)\n'
               '  push the body with (w, 3, 250, 0)\n'
               '  repeat 120 times:\n'
               '    step the physics with (w, 1 divided by 60)\n'
               '  set b to the body numbered with (w, 3)\n'
               '  scrawl round the x of b, " ", round the y of b, " ", the landed of b\n'
               '  scrawl touching with (b, the body numbered with (w, 1))\n'
               'and the universe said i love you\n'
               ]))
    assert out.stdout == "122 280 yes\nno\n", repr(out.stdout + out.stderr)
    assert translate.plural_word("body") == "bodies" and translate.plural_word("box") == "boxes" and translate.plural_word("day") == "days"

    # 3D: models, triangles, pictures, light, the eye, shaders.
    if compiler and os.name == "nt":
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "three.stella").write_text('to tint, given where (a place) and colour (text), returning text:\n  if (where of horizontal) exceeds 3:\n    return "#0000ff"\n  return colour\nand the universe said i love you\n\ngenesis:\n  open a world with ("3d", 160, 120)\n  repeat 3 times:\n    consume the window with "black"\n    place the eye at 0 horizontal 0 vertical -6 depth\n    set the eye view to 60\n    shine the light from 0 horizontal 0 vertical -1 depth\n    etch the model with ("cube.obj", -2 horizontal 0 vertical 0 depth, 0.8, 30, "")\n    etch a triangle in space with (1 horizontal 1 vertical 0 depth, 2 horizontal -1 vertical 0 depth, 0 horizontal -1 vertical 0 depth, "yellow")\n    etch the picture in space with ("sheet.png", 2.5 horizontal 1 vertical 0 depth, 2 horizontal 0 vertical 0 depth, 0 horizontal -1 vertical 0 depth)\n    shade the shapes with the command tint\n    etch a ball with (4 horizontal 0 vertical 0 depth, 0.3, "white")\n    stop shading the shapes\n    reveal the frame\n  end the world\nand the universe said i love you\n'.replace('"sheet.png"', '"cube.png"'), encoding="utf-8")
            (Path(d) / "cube.obj").write_text('mtllib cube.mtl\nv -1 -1 -1\nv 1 -1 -1\nv 1 1 -1\nv -1 1 -1\nv -1 -1 1\nv 1 -1 1\nv 1 1 1\nv -1 1 1\nusemtl redstuff\nf 1 2 3 4\nf 5 8 7 6\nusemtl greenstuff\nf 1 5 6 2\nf 4 3 7 8\nf 1 4 8 5\nf 2 6 7 3\n', encoding="utf-8")
            (Path(d) / "cube.mtl").write_text('newmtl redstuff\nKd 1 0 0\nnewmtl greenstuff\nKd 0 1 0\n', encoding="utf-8")
            import struct, zlib
            chunk = lambda kind, body: struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))
            rows = b"".join(b"\x00" + bytes([255, 0, 0, 255] * 4) for _ in range(2))  # a 4 by 2 red picture
            (Path(d) / "cube.png").write_bytes(bytes([137, 80, 78, 71, 13, 10, 26, 10]) + chunk(b"IHDR", struct.pack(">IIBBBBB", 4, 2, 8, 6, 0, 0, 0))
                                               + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))
            assert translate.build(Path(d) / "three.stella", Path(d) / "three.exe") is None
            subprocess.run([str(Path(d) / "three.exe")], cwd=d, env=dict(os.environ, STELLANOVA_DEMO_FRAMES="f.raw"), timeout=60, check=True)
            frame = (Path(d) / "f.raw").read_bytes()[-160 * 120 * 4:]
            dots = {tuple(frame[k:k + 3]) for k in range(0, len(frame), 4)}  # blue, green, red
            assert all(any(c[k] > 180 and c[(k + 1) % 3] < 60 and c[(k + 2) % 3] < 60 for c in dots) for k in range(3)), "3D colours missing"  # red, green, blue
            out = subprocess.run([sys.executable, str(HERE / "stellanova.py"), "check", "three.stella"], cwd=d, capture_output=True, text=True)
            assert "no mistakes found" in out.stdout, out.stdout

    # A command that calls itself forever says so when built, instead of vanishing.
    if compiler:
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "deep.stella").write_text('to deep, given n (a number), returning a number:\n  return (deep with n) plus 1\nand the universe said i love you\n\ngenesis:\n  scrawl "start"\n  scrawl deep with 1\nand the universe said i love you\n', encoding="utf-8")
            exe = Path(d) / ("deep" if translate.machine.TARGET == "linux" else "deep.exe")
            assert translate.build(Path(d) / "deep.stella", exe) is None
            out = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
            assert (out.stdout, out.stderr, out.returncode) == ("start\n", "commands called each other too many times in a row (they may never stop).\n", 1), (out.stdout, out.stderr, out.returncode)

    # glTF models: a bone bends its arm, the same every way; .glb too.
    def bending_arm(glb):
        import struct, base64, json
        pts = [(x, y, 0.0) for y in (0, 1, 2) for x in (-0.5, 0.5)]
        tris = [0, 1, 3, 0, 3, 2, 2, 3, 5, 2, 5, 4]
        tris += tris[::-1]  # both sides
        pieces = [b"".join(struct.pack("<3f", *p) for p in pts), bytes([0, 0, 0, 0] * 4 + [1, 0, 0, 0] * 2), struct.pack("<24f", *[1, 0, 0, 0] * 6),
                  struct.pack("<24H", *tris), struct.pack("<32f", 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, -1, 0, 1),
                  struct.pack("<3f", 0, 1, 2), struct.pack("<12f", 0, 0, 0, 1, 0, 0, 0.7071068, 0.7071068, 0, 0, 0, 1)]
        views, at = [], 0
        for p in pieces:
            views.append({"buffer": 0, "byteOffset": at, "byteLength": len(p)})
            at += len(p)
        data = b"".join(pieces)
        acc = lambda v, kind, n, count: {"bufferView": v, "componentType": kind, "type": n, "count": count}
        doc = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0, 1]}],
               "nodes": [{"mesh": 0, "skin": 0}, {"children": [2]}, {"translation": [0, 1, 0]}],
               "meshes": [{"primitives": [{"attributes": {"POSITION": 0, "JOINTS_0": 1, "WEIGHTS_0": 2}, "indices": 3, "material": 0}]}],
               "materials": [{"pbrMetallicRoughness": {"baseColorFactor": [1, 0, 0, 1]}}],
               "skins": [{"joints": [1, 2], "inverseBindMatrices": 4}],
               "animations": [{"name": "bend", "channels": [{"sampler": 0, "target": {"node": 2, "path": "rotation"}}],
                               "samplers": [{"input": 5, "output": 6}]}],
               "accessors": [acc(0, 5126, "VEC3", 6), acc(1, 5121, "VEC4", 6), acc(2, 5126, "VEC4", 6), acc(3, 5123, "SCALAR", 24),
                             acc(4, 5126, "MAT4", 2), acc(5, 5126, "SCALAR", 3), acc(6, 5126, "VEC4", 3)],
               "bufferViews": views, "buffers": [{"byteLength": len(data)}]}
        if not glb:
            doc["buffers"][0]["uri"] = "data:application/octet-stream;base64," + base64.b64encode(data).decode()
            return json.dumps(doc)
        words = json.dumps(doc).encode()
        words += b" " * (-len(words) % 4)
        return b"glTF" + struct.pack("<II", 2, 28 + len(words) + len(data)) + struct.pack("<I", len(words)) + b"JSON" + words + struct.pack("<I", len(data)) + b"BIN\x00" + data
    arm = ('genesis:\n  open a world with ("arm", 160, 120)\n  place the eye at 0 horizontal 1 vertical -6 depth\n  shine the light from 0 horizontal 0 vertical -1 depth\n'
           '  consume the window with "black"\n  etch the moving model with ("arm.gltf", 0 horizontal 0 vertical 0 depth, 1, 0, "", "bend", 3)\n'
           '  etch the model with ("arm.glb", 3 horizontal 0 vertical 0 depth, 1, 0, "")\n  reveal the frame\n'
           '  try:\n    etch the moving model with ("arm.gltf", 0 horizontal 0 vertical 0 depth, 1, 0, "", "wave", 0)\n  if that went wrong:\n    scrawl the wound\n'
           '  try:\n    etch the moving model with ("box.obj", 0 horizontal 0 vertical 0 depth, 1, 0, "", "", 0)\n  if that went wrong:\n    scrawl the wound\n'
           '  try:\n    etch the model with ("broken.gltf", 0 horizontal 0 vertical 0 depth, 1, 0, "")\n  if that went wrong:\n    scrawl the wound\n'
           '  end the world\nand the universe said i love you\n')
    out = both(arm, others={"arm.gltf": bending_arm(False), "arm.glb": bending_arm(True), "broken.gltf": '{"meshes": [{"primitives": [{"attributes": {"POSITION": 7}}]}]}'})
    assert out.stdout == ('the model "arm.gltf" has no motion called "wave". It has: "bend"\n'
                          'only .gltf and .glb models move, and "box.obj" isn\'t one. Use: etch the model with ("box.obj", middle, size, turn, colour)\n'
                          'the model "broken.gltf" isn\'t a glTF model I can read.\n'), repr(out.stdout + out.stderr)
    if compiler and os.name == "nt":
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "arm.stella").write_text(arm, encoding="utf-8")
            (Path(d) / "arm.gltf").write_text(bending_arm(False), encoding="utf-8")
            (Path(d) / "arm.glb").write_bytes(bending_arm(True))
            (Path(d) / "broken.gltf").write_text("{\"meshes\": []}", encoding="utf-8")
            assert translate.build(Path(d) / "arm.stella", Path(d) / "arm.exe") is None
            subprocess.run([str(Path(d) / "arm.exe")], cwd=d, env=dict(os.environ, STELLANOVA_DEMO_FRAMES="f.raw"), timeout=60, capture_output=True)
            frame = (Path(d) / "f.raw").read_bytes()[-160 * 120 * 4:]
            red = [k // 4 % 160 for k in range(0, len(frame), 4) if frame[k + 2] > 100 and frame[k + 1] < 60 and frame[k] < 60]
            arm_cols = [c for c in red if c < 100]  # the bent one; the .glb one stands to the right
            assert arm_cols and 80 - min(arm_cols) > 1.5 * (max(arm_cols) - 80), (min(arm_cols), max(arm_cols))  # bent to one side
            assert any(c > 110 for c in red), "the .glb model is missing"

    # Pictures: read, change, save, load.
    out = both(''.join([
               'use: pictures\n'
               'use: maths\n'
               '\n'
               'genesis:\n'
               '  set p to a blank picture with (4, 3, "#336699")\n'
               '  scrawl the dots across p, " ", the dots down p, " ", the dot at with (p, 3, 2)\n'
               '  colour the dot with (p, 1, 1, "red")\n'
               '  colour the dot with (p, 2, 1, "#00ff0080")\n'
               '  save the picture with (p, "out.png")\n'
               '  set back to the picture in the file "out.png"\n'
               '  scrawl the dot at with (back, 1, 1), " ", the dot at with (back, 2, 1), " ", the dot at with (back, 0, 0)\n'
               '  set dots to the dots of the picture back\n'
               '  scrawl the size of dots, " ", item 1 of dots, " ", item 4 of dots\n'
               '  set grey to a list of numbers\n'
               '  for each k from 1 to the size of dots:\n'
               '    if remainder of with (k, 4) is 0:\n'
               '      add item k of dots to grey\n'
               '    otherwise:\n'
               '      add 255 minus item k of dots to grey\n'
               '  set flipped to a picture from the dots with (4, 3, grey)\n'
               '  scrawl the dot at with (flipped, 0, 0)\n'
               '  set c to a copy of the picture flipped\n'
               '  colour the dot with (c, 0, 0, "black")\n'
               '  scrawl the dot at with (flipped, 0, 0), " ", the dot at with (c, 0, 0)\n'
               '  scrawl the dot at with (p, 4, 0)\n'
               'and the universe said i love you\n'
               ]))
    assert out.stdout == "4 3 #336699\n#ff0000 #00ff0080 #336699\n48 51 255\n#cc9966\n#cc9966 #000000\n", repr(out.stdout)
    assert out.stderr == "Line 25: there is no dot at 4, 0 in a picture 4 by 3 (dots go from 0, 0).\n", repr(out.stderr)

    # Hashes and signatures (HMAC), the same every way.
    out = both(''.join([
               'use: hashing\n'
               '\n'
               'genesis:\n'
               '  scrawl the hash of with ("sha256", "hello")\n'
               '  scrawl the hash of with ("md5", "hello"), " ", the hash of with ("sha1", "")\n'
               '  scrawl the hash of the bytes with ("sha256", a list of (104, 101, 108, 108, 111))\n'
               '  scrawl the signature of with ("sha256", "key", "The quick brown fox jumps over the lazy dog")\n'
               '  scrawl the size of the hash of with ("sha512", "héllo")\n'
               '  scrawl the hash of with ("crc", "x")\n'
               'and the universe said i love you\n'
               ]))
    assert out.stdout == '2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824\n5d41402abc4b2a76b9719d911017c592 da39a3ee5e6b4b0d3255bfef95601890afd80709\n2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824\nf7bc83f430538424b13298e6aa6fb143ef4d59a14946175997479dbc2d1a3cd8\n128\n', repr(out.stdout + out.stderr)
    assert out.stderr.startswith('Line 9: there is no kind of hash called "crc".'), repr(out.stderr)

    # Encryption: each way decrypts its own, and text node encrypted.
    out = both(''.join([
               'use: encryption\n'
               '\n'
               'genesis:\n'
               '  set long to "a secret message, long enough to need more than one block of sixty-four bytes: héllo wörld 12345 67890"\n'
               '  set secret to encrypted with (long, "pässword")\n'
               '  scrawl decrypted with (secret, "pässword") is long, " ", secret is encrypted with (long, "pässword")\n'
               '  scrawl decrypted with (encrypted with ("", "k"), "k"), "|"\n'
               '  scrawl the size of a random code of 16\n'
               '  scrawl decrypted with ("hN4gCn+f93dP8TSvvzNh9dToaFANdvhaf0Eo9FuuFpkOERglv8qLsqJGKN6Jse9vzFV4SsGoHeA9UVNu/SJ9T9pAYM+u8mLUd/QEJPYAESCkQpojktoWm5f6G4NeoZsmDPPqhxGGGBaOg21rRYgtuADZmrh6GyabObz9tz1UqfFCHVvrdy95AVDeHeKbZdjMORbJ9gTagMVwk9rr/TOvfjmx0xaNThA=", "pässword")\n'
               '  try:\n'
               '    scrawl decrypted with (secret, "wrong")\n'
               '  if that went wrong:\n'
               '    scrawl the wound\n'
               '  scrawl decrypted with ("not!secret", "x")\n'
               'and the universe said i love you\n'
               ]))
    assert out.stdout == 'yes no\n|\n32\na secret message, long enough to need more than one block of sixty-four bytes: héllo wörld 12345 67890 and more more more\nthe password is wrong, or the encrypted text was changed.\n', repr(out.stdout + out.stderr)
    assert out.stderr.startswith("Line 14: that isn't encrypted text"), repr(out.stderr)

    # JSON paths: reading parts, lists and names, and changing parts.
    out = both(''.join([
               'use: json\n'
               '\n'
               'genesis:\n'
               '  set q to a quotation mark\n'
               '  set weather to "{" plus q plus "city" plus q plus ": " plus q plus "Oslo" plus q plus ", " plus q plus "days" plus q plus ": [{" plus q plus "high" plus q plus ": 12.5, " plus q plus "sunny" plus q plus ": true}, {" plus q plus "high" plus q plus ": 9, " plus q plus "note" plus q plus ": " plus q plus "rain\\nlater" plus q plus "}]}"\n'
               '  scrawl the json at with (weather, "city"), " ", the json number at with (weather, "days[1].high")\n'
               '  scrawl the json at with (weather, "days[1]")\n'
               '  scrawl the json list at with (weather, "days")\n'
               '  scrawl the json names at with (weather, "days[2]"), " ", there is json at with (weather, "days[3]"), " ", there is json at with (weather, "days[2].note")\n'
               '  set weather to the json changed at with (weather, "days[2].high", "11")\n'
               '  set weather to the json changed at with (weather, "country", as json text ("Nor" plus q plus "way"))\n'
               '  set weather to the json changed at with (weather, "days[3]", "null")\n'
               '  scrawl weather\n'
               '  scrawl the json at with ("[1, 2.5e3, -0.25]", "")\n'
               '  scrawl the json at with (weather, "days[9]")\n'
               'and the universe said i love you\n'
               ]))
    assert out.stdout == 'Oslo 12.5\n{"high":12.5,"sunny":true}\n{"high":12.5,"sunny":true}, {"high":9,"note":"rain\\nlater"}\nhigh, note no yes\n{"city":"Oslo","days":[{"high":12.5,"sunny":true},{"high":11,"note":"rain\\nlater"},null],"country":"Nor\\"way"}\n[1,2500,-0.25]\n', repr(out.stdout + out.stderr)
    assert out.stderr.startswith('Line 15: there is nothing at "days[9]" in the JSON.'), repr(out.stderr)

    # Zip files: packing files and folders, listing, unpacking.
    out = both(''.join([
               'use: zip\n'
               'use: folders\n'
               '\n'
               'genesis:\n'
               '  make the folder "box/inner"\n'
               '  inscribe "hello zip" into file "box/a.txt"\n'
               '  inscribe "deeper" into file "box/inner/b.txt"\n'
               '  inscribe "one more" into file "c.txt"\n'
               '  pack the zip with (a list of ("box", "c.txt"), "all.zip")\n'
               '  scrawl the files in the zip "all.zip"\n'
               '  unpack the zip with ("all.zip", "out")\n'
               '  scrawl contents of file "out/box/inner/b.txt", " ", contents of file "out/c.txt"\n'
               '  erase the folder "box"\n'
               '  erase the folder "out"\n'
               '  pack the zip with (a list of ("nothing.txt"), "x.zip")\n'
               'and the universe said i love you\n'
               ]))
    assert out.stdout == 'box/a.txt, box/inner/b.txt, c.txt\ndeeper one more\n', repr(out.stdout + out.stderr)
    assert out.stderr.startswith('Line 15: there is no file or folder called "nothing.txt".'), repr(out.stderr)

    out = both('use: zip\n\ngenesis:\n  inscribe "hello zip" into file "a.txt"\n  inscribe "one more" into file "c.txt"\n  pack the zip with (a list of ("a.txt", "c.txt"), "two.zip")\n  scrawl the files in the zip "two.zip"\n  unpack the zip with ("two.zip", "out")\n  scrawl contents of file "out/a.txt", " ", contents of file "out/c.txt"\nand the universe said i love you\n')  # without the folders library, so the web (node) packs and unpacks too
    assert out.stdout == "a.txt, c.txt\nhello zip one more\n", repr(out.stdout + out.stderr)

    # Email, to a server on this computer that keeps what it gets.
    mail = []
    smtp_catcher(47825, mail)
    out = both(''.join([
               'use: email\n'
               '\n'
               'genesis:\n'
               '  send an email with ("localhost:47825", "me@example.com", "", "you@example.com", "Hello", "first line" plus new line plus ".dotted line")\n'
               '  scrawl "sent"\n'
               '  try:\n'
               '    send an email with ("localhost", "", "", "you@example.com", "x", "y")\n'
               '  if that went wrong:\n'
               '    scrawl the wound\n'
               '  send an email with ("localhost:47825", "", "", "nobody", "x", "y")\n'
               'and the universe said i love you\n'
               ]))
    assert out.stdout == 'sent\na mail server is its address and port, like "smtp.gmail.com:587", not "localhost".\n', repr(out.stdout + out.stderr)
    assert out.stderr.startswith('Line 10: "nobody" isn\'t an email address.'), repr(out.stderr)
    assert len(mail) in ((1, 2, 3) if linux_skipped else (2, 3)) and all("Subject: Hello" in m and "first line\n..dotted line" in m for m in mail), mail

    # Desktop forms, acting by themselves from a script.
    form_script = Path(tempfile.mkdtemp()) / "form.script"
    form_script.write_text("type name Rex\nclick add\ntype name Tom\nclick add\nchoose pets Tom\ntick loud\nclick done\n", encoding="utf-8")
    os.environ["STELLANOVA_FORM_SCRIPT"] = str(form_script)
    out = both(''.join([
               'use: forms\n'
               '\n'
               'genesis:\n'
               '  open a form with ("Pets", 320, 240)\n'
               '  add a label with ("ask", "Name:", 10, 10, 60, 22)\n'
               '  add a field with ("name", "", 70, 10, 150, 22)\n'
               '  add a button with ("add", "Add", 230, 10, 80, 24)\n'
               '  add a list box with ("pets", 10, 44, 300, 120)\n'
               '  add a tick box with ("loud", "Shout it", 10, 174, 120, 22)\n'
               '  add a button with ("done", "Done", 230, 200, 80, 24)\n'
               '  set click to wait for a click\n'
               '  as long as click is "add":\n'
               '    put in the list with ("pets", the words in "name")\n'
               '    set the words in with ("name", "")\n'
               '    set click to wait for a click\n'
               '  scrawl "clicked ", click, ", chose ", the words in "pets", ", loud: ", is ticked "loud"\n'
               '  close the form\n'
               '  scrawl "[", wait for a click, "]"\n'
               'and the universe said i love you\n'
               ]))
    assert out.stdout == 'clicked done, chose Tom, loud: yes\n[]\n', repr(out.stdout + out.stderr)

    # Making sounds and .wav files.
    out = both(''.join([
               'use: sound making\n'
               '\n'
               'genesis:\n'
               '  scrawl round the pitch of the note "A4", " ", (the pitch of the note "C4") rounded to 2 decimal places, " ", (the pitch of the note "C#5") rounded to 2 decimal places\n'
               '  set beep to a tone with ("sine", 441, 0.01, 0.5)\n'
               '  scrawl the size of beep, " ", (item 26 of beep) rounded to 4 decimal places\n'
               '  set sq to a tone with ("square", 100, 0.02, 1)\n'
               '  scrawl item 1 of sq, " ", item 300 of sq\n'
               '  set both to mixed with (beep, sq)\n'
               '  scrawl the size of both, " ", the size of (followed by with (beep, sq))\n'
               '  scrawl (item 100 of faded with (sq, 0.01, 0)) rounded to 3 decimal places, " ", item 1 of louder with (sq, 0.5)\n'
               '  scrawl the size of echoed with (beep, 0.001, 0.5)\n'
               '  save the sound with (faded with (sq, 0.005, 0.005), "out.wav")\n'
               '  set back to the sound in the file "out.wav"\n'
               '  scrawl the size of back, " ", (item 441 of back) rounded to 3 decimal places\n'
               '  scrawl a tone with ("wobble", 1, 1, 1)\n'
               'and the universe said i love you\n'
               ]))
    assert out.stdout == "440 261.63 554.37\n441 0.5\n1 -1\n882 1323\n0.224 0.5\n617\n882 -1\n", repr(out.stdout)
    assert out.stderr.startswith('Line 16: there is no tone shape called "wobble".'), repr(out.stderr)

    # Animation: easing, tweens, waves, sprite sheet frames.
    out = both(''.join([
               'use: animation\n'
               '\n'
               'genesis:\n'
               '  for each style in a list of ("linear", "in", "out", "in out", "back", "overshoot", "bounce", "elastic"):\n'
               '    set shown to style plus ":"\n'
               '    for each k from 0 to 4:\n'
               '      set shown to shown plus " " plus ((eased with (style, k divided by 4)) rounded to 3 decimal places)\n'
               '    scrawl shown\n'
               '  scrawl tweened with (10, 20, 0.5, "linear"), " ", tweened with (0, 100, 0.25, "in out")\n'
               '  scrawl progress of with (2, 4, 3), " ", progress of with (2, 4, 9), " ", progress of with (2, 0, 1)\n'
               '  scrawl ping pong 0.25, " ", ping pong 1.5, " ", wave of with (1, 4)\n'
               '  scrawl sheet frame with (4, 8, 0.25), " ", sheet frame with (4, 8, 0.4), " ", sheet frame with (4, 8, 0.5)\n'
               '  scrawl tweened place with (0 horizontal 10 vertical 0 depth, 100 horizontal 20 vertical 4 depth, 0.5, "linear")\n'
               '  scrawl eased with ("wobbly", 0.5)\n'
               'and the universe said i love you\n'
               ]))
    assert out.stdout == ("linear: 0 0.25 0.5 0.75 1\nin: 0 0.016 0.125 0.422 1\nout: 0 0.578 0.875 0.984 1\nin out: 0 0.063 0.5 0.938 1\n"
                          "back: 0 -0.064 -0.088 0.183 1\novershoot: 0 0.817 1.088 1.064 1\nbounce: 0 0.473 0.766 0.973 1\n"
                          "elastic: 0 0.912 1.016 1.006 1\n15 6.25\n0.25 1 0\n0.25 0.5 0.5\n3 4 1\n50 horizontal 15 vertical 2 depth\n"), repr(out.stdout)
    assert out.stderr.startswith('Line 14: there is no easing called "wobbly".'), repr(out.stderr)

    # Getting and dropping libraries.
    with tempfile.TemporaryDirectory() as d:
        import zipfile
        words = 'to greeting for, given who (text), returning text = std::string("hello, ") + {who}\n  runs: "hello, " + {who}\n  web: "hello, " + {who}\n'
        (Path(d) / "greet.words").write_text(words, encoding="utf-8")
        with zipfile.ZipFile(Path(d) / "more.zip", "w") as z:
            z.writestr("project-main/libs/shout.words", words.replace("greeting for", "shout for"))
            z.writestr("../away.words", words.replace("greeting for", "away for"))
        say = lambda *a: subprocess.run([sys.executable, str(HERE / "stellanova.py"), *a], capture_output=True, text=True, encoding="utf-8", cwd=d).stdout
        assert "Got the library 'greet'" in say("get", "greet.words")
        assert "Got the library 'shout'" in say("get", "more.zip")
        assert sorted(p.name for p in Path(os.environ["STELLANOVA_GOT"]).glob("*.words")) == ["away.words", "greet.words", "shout.words"]
        assert "greet  (from file:" in say("got")
        (Path(d) / "greet.words").unlink()
        (Path(d) / "g.stella").write_text("use: greet\nuse: shout\ngenesis:\n  scrawl greeting for \"you\", \" \", shout for \"me\"\n" + END, encoding="utf-8")
        out = both((Path(d) / "g.stella").read_text(encoding="utf-8"))
        assert out.stdout == "hello, you hello, me\n", repr(out.stdout + out.stderr)
        assert "Dropped the library 'greet'" in say("drop", "greet")
        assert "There is no library called 'greet'" in say("check", "g.stella")

    # Commands alongside share names, taking turns with a lock.
    out = both(''.join([
               'the world remembers:\n'
               '  total (a number)\n'
               'and the universe said i love you\n'
               '\n'
               'to count up, given times (a number):\n'
               '  repeat times times:\n'
               '    holding the lock "total":\n'
               '      set total to total plus 1\n'
               'and the universe said i love you\n'
               '\n'
               'to take the lock:\n'
               '  holding the lock "total":\n'
               '    scrawl "the other one has it"\n'
               'and the universe said i love you\n'
               '\n'
               'genesis:\n'
               '  try:\n'
               '    holding the lock "total":\n'
               '      raise a test problem with "inside the lock"\n'
               '  if that went wrong:\n'
               '    scrawl the wound\n'
               '  meanwhile take the lock\n'
               '  wait for the others\n'
               '  meanwhile count up with 20000\n'
               '  meanwhile count up with 20000\n'
               '  meanwhile count up with 20000\n'
               '  wait for the others\n'
               '  scrawl total\n'
               'and the universe said i love you\n'
               ]))
    assert out.stdout == "inside the lock\nthe other one has it\n60000\n", repr(out.stdout + out.stderr)
    assert "can't leave it partway" in perr('to f:\n  holding the lock "a":\n    return\n' + END + 'genesis:\n  f\n' + END)[1]

    # A change never shows up in a copy.
    out = both('a dot has:\n  x (a number)\n  tags (a list of text)\n  inner (a list of numbers)\nand the universe said i love you\n\nto nudge, for a dot:\n  set x to x plus 1\n  add "n" to tags\nand the universe said i love you\n\nto grow, given xs (a list of numbers):\n  set mine to xs\n  add 99 to mine\n  scrawl "inside ", mine\nand the universe said i love you\n\ngenesis:\n  conjure a dot as d\n  add "a" to the tags of d\n  add 1 to the inner of d\n  set e to d\n  set the x of e to 5\n  add "b" to the tags of e\n  add 2 to the inner of e\n  scrawl the x of d, " ", the tags of d, " ", the inner of d\n  scrawl the x of e, " ", the tags of e, " ", the inner of e\n  set ds to a list of dots\n  add d to ds\n  add d to ds\n  set the x of item 1 of ds to 7\n  add "c" to the tags of item 2 of ds\n  scrawl the x of item 1 of ds, " ", the x of item 2 of ds, " ", the tags of item 1 of ds, " ", the tags of item 2 of ds, " ", the tags of d\n  for each p in ds:\n    set q to p\n    set the x of q to 100\n    add "z" to the tags of q\n    scrawl the tags of q, " ", the tags of p\n  scrawl the x of item 1 of ds, " ", the tags of item 1 of ds\n  nudge item 1 of ds\n  nudge d\n  scrawl the x of item 1 of ds, " ", the tags of item 1 of ds, " ", the x of item 2 of ds, " ", the tags of d\n  set xs to a list of (1, 2)\n  set ys to xs\n  grow xs\n  scrawl xs, " ", ys\n  set t to a table of lists of numbers\n  set entry "a" of t to xs\n  add 5 to entry "a" of t\n  set item 1 of entry "a" of t to 42\n  scrawl xs, " ", entry "a" of t\n  set u to t\n  add 6 to entry "a" of u\n  scrawl entry "a" of t, " ", entry "a" of u\n  set nest to a list of lists of numbers\n  add xs to nest\n  add xs to nest\n  add 8 to item 1 of nest\n  set item 1 of item 2 of nest to 0\n  scrawl nest, " ", xs\n  set copy to nest\n  for each row in copy:\n    set r to row\n    add 3 to r\n    scrawl r, " ", row\n  scrawl nest, " ", copy\nand the universe said i love you\n')
    assert out.stdout == '0 a 1\n5 a, b 1, 2\n7 0 a a, c a\na, z a\na, c, z a, c\n7 a\n8 a, n 0 a, n\ninside 1, 2, 99\n1, 2 1, 2\n1, 2 42, 2, 5\n42, 2, 5 42, 2, 5, 6\n(1, 2, 8), (0, 2) 1, 2\n1, 2, 8, 3 1, 2, 8\n0, 2, 3 0, 2\n(1, 2, 8), (0, 2) (1, 2, 8), (0, 2)' + chr(10), out.stdout
    out = both('genesis:\n  set t to a table of numbers\n  set entry "a" of t to 1\n  set u to t\n  set entry "a" of t to 2\n'
               '  set entry "a" of u to entry "a" of u plus 10\n  set x to entry "a" of t\n  set entry "a" of t to 3\n  scrawl t, " ", u, " ", x\n'
               '  set ts to a list of tables of numbers\n  add t to ts\n  set entry "a" of item 1 of ts to 9\n  scrawl t, " ", ts\n' + END)
    assert out.stdout == "a: 3 a: 11 2\na: 3 (a: 9)\n", out.stdout
    if compiler:  # threads making values while the collector runs often
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "busy.stella").write_text(
                'a pet has:\n  name (text)\n' + END + '\nto churn, given name (text):\n  set pets to a list of pets\n'
                '  for each n from 1 to 3000:\n    conjure a pet as p\n    set the name of p to name plus "-" plus (n as text)\n    add p to pets\n'
                '  holding the lock "screen":\n    scrawl name, " ", the name of last item of pets\n' + END
                + '\ngenesis:\n  meanwhile churn with "a"\n  meanwhile churn with "b"\n  churn with "c"\n  wait for the others\n' + END, encoding="utf-8")
            assert translate.build(Path(d) / "busy.stella", Path(d) / "busy.exe") is None
            ran = subprocess.run([str(Path(d) / "busy.exe")], capture_output=True, text=True, timeout=120,
                                 env=dict(os.environ, STELLANOVA_COLLECT_OFTEN="1"))
            assert sorted(ran.stdout.split()) == sorted("a a-3000 b b-3000 c c-3000".split()), ran

    # Lists of plain numbers: every list word works.
    out = both('genesis:\n  set xs to a list of numbers\n  for each n from 1 to 5:\n    add n times 2 to xs\n  insert 7 at 2 in xs\n'
               '  remove item 1 from xs\n  set item 1 of xs to 0.5\n'
               '  scrawl xs, " ", the size of xs, " ", item 3 of xs, " ", last item of xs, " ", sum of xs\n  set ys to xs\n  add 100 to ys\n'
               '  scrawl xs contains 100, " ", ys contains 100, " ", ys contains 8\n  remove 6 from xs\n  scrawl xs\n'
               '  scrawl xs changed by each n becomes n plus 1\n  scrawl xs kept by each n becomes n exceeds 5\n  set total to 0\n'
               '  for each x in ys:\n    set total to total plus x\n  scrawl total\n  set item 9 of xs to 1\n' + END)
    assert out.stdout == "0.5, 4, 6, 8, 10 5 6 10 28.5\nno yes yes\n0.5, 4, 8, 10\n1.5, 5, 9, 11\n8, 10\n128.5\n", repr(out.stdout)
    assert out.stderr == "Line 20: there is no item 9 in a list of 4 items. Items are counted from 1.\n", repr(out.stderr)

    # Text growing in place.
    out = both(''.join([
               'to shout, given words (text), returning text:\n'
               '  set said to words\n'
               '  set said to said plus "!"\n'
               '  return said\n'
               'and the universe said i love you\n'
               '\n'
               'genesis:\n'
               '  set s to "a"\n'
               '  set t to s\n'
               '  set s to s plus "b"\n'
               '  set s to s plus "c"\n'
               '  set xs to a list of text\n'
               '  add s to xs\n'
               '  set s to s plus "d"\n'
               '  set loud to shout with s\n'
               '  set s to s plus "e"\n'
               '  scrawl t, " ", item 1 of xs, " ", loud, " ", s\n'
               '  set s to s plus s\n'
               '  set u to "x"\n'
               '  for each n from 1 to 3:\n'
               '    set u to u plus n plus "-"\n'
               '  scrawl s, " ", u\n'
               'and the universe said i love you\n'
               ]))
    assert out.stdout == "a abc abcd! abcde\nabcdeabcde x1-2-3-\n", repr(out.stdout + out.stderr)

    # The network: TCP (with a server going alongside), UDP, and WebSockets.
    out = both(''.join([
               'use: network\n'
               '\n'
               'to echo once, given listener (a number):\n'
               '  set client to accept a connection on listener\n'
               '  set heard to receive a line from client\n'
               '  send a line on with (client, "you said: " plus heard)\n'
               '  close the connection client\n'
               'and the universe said i love you\n'
               '\n'
               'genesis:\n'
               '  set listener to listen on port 47811\n'
               '  meanwhile echo once with listener\n'
               '  set c to connect to with ("127.0.0.1", 47811)\n'
               '  send a line on with (c, "hello there")\n'
               '  scrawl receive a line from c\n'
               '  scrawl "[", receive from c, "]"\n'
               '  close the connection c\n'
               '  set u to open the udp port 47812\n'
               '  send udp with (u, "127.0.0.1", 47812, "a note to myself")\n'
               '  scrawl receive udp from u\n'
               '  try:\n'
               '    connect to with ("127.0.0.1", 1)\n'
               '  if that went wrong:\n'
               '    scrawl the wound\n'
               '  close the connection 99\n'
               'and the universe said i love you\n'
               ]))
    assert out.stdout == "you said: hello there\n[]\na note to myself\nI couldn't connect to 127.0.0.1 on port 1.\n", repr(out.stdout)
    assert out.stderr == "Line 25: there is no open connection 99.\n", repr(out.stderr)
    websocket_echo(47813)
    out = both(''.join([
               'use: network\n'
               '\n'
               'genesis:\n'
               '  set w to connect a websocket to "ws://127.0.0.1:47813/echo"\n'
               '  send on with (w, "hello")\n'
               '  scrawl receive from w\n'
               '  send on with (w, "two")\n'
               '  scrawl receive from w\n'
               '  close the connection w\n'
               'and the universe said i love you\n'
               ]))
    assert out.stdout == "echo: hello\necho: two\n", repr(out.stdout + out.stderr)

    # Python packages, when running directly: a word for each function.
    with tempfile.TemporaryDirectory() as d:
        script = Path(d) / "probe.stella"
        script.write_text('use python "statistics":\n  to middle of, given xs (a list of numbers), returning a number = median\n  to spread of, given xs (a list of numbers), returning a number = pstdev\nand the universe said i love you\n\nuse python "textwrap":\n  to wrapped, given words (text) and width (a number), returning a list of text = wrap\nand the universe said i love you\n\ngenesis:\n  scrawl middle of a list of (3, 1, 9, 4)\n  scrawl spread of a list of (2, 4, 4, 4, 5, 5, 7, 9)\n  scrawl wrapped with ("the quick brown fox jumps", 10)\nand the universe said i love you\n', encoding="utf-8")
        out = subprocess.run([sys.executable, str(HERE / "stellanova.py"), "run", str(script)], capture_output=True, text=True, encoding="utf-8")
        assert out.stdout == "3.5\n2\nthe quick, brown fox, jumps\n", repr(out.stdout + out.stderr)
        script.write_text('use python "no_such_package_here":\n  to nothing, returning a number = x\n' + END + 'genesis:\n  scrawl nothing\n' + END, encoding="utf-8")
        out = subprocess.run([sys.executable, str(HERE / "stellanova.py"), "run", str(script)], capture_output=True, text=True, encoding="utf-8")
        assert "Line 5: the Python package 'no_such_package_here' isn't installed" in out.stderr, repr(out.stderr)
        assert "only works when the program runs directly" in translate.build(script, Path(d) / "probe.exe")

    # C functions from any library (.dll): a word for each.
    if os.name == "nt":
        out = both(''.join([
                   'use the library "msvcrt.dll":\n'
                   '  to c square root, given x (a number), returning a number = double sqrt(double)\n'
                   '  to c length, given s (text), returning a number = unsigned long long strlen(text)\n'
                   '  to c number in, given s (text), returning a number = int atoi(text)\n'
                   '  to c find, given s (text) and letter (a number), returning text = text strchr(text, int)\n'
                   'and the universe said i love you\n'
                   '\n'
                   'use the library "kernel32.dll":\n'
                   '  to wide length, given s (text), returning a number = int lstrlenW(wide text)\n'
                   '  to the process number, returning a number = unsigned GetCurrentProcessId()\n'
                   'and the universe said i love you\n'
                   '\n'
                   'genesis:\n'
                   '  scrawl c square root with 2\n'
                   '  scrawl c length "héllo", " ", wide length "héllo"\n'
                   '  scrawl c number in "42abc" plus 1\n'
                   '  scrawl c find with ("hello world", 119)\n'
                   '  scrawl the process number exceeds 0\n'
                   'and the universe said i love you\n'
                   ]))
        assert out.stdout == "1.4142135623731\n6 5\n43\nworld\nyes\n", repr(out.stdout)
        out = both('use the library "kernel32.dll":\n  to nothing here, returning a number = int NoSuchFunction()\nand the universe said i love you\ngenesis:\n  scrawl nothing here\n' + END)
        assert out.stderr == 'Line 5: the library "kernel32.dll" has no function called NoSuchFunction.\n', repr(out.stderr)

    # Kinds for any kind.
    out = both(''.join([
               'a stack of anything has:\n'
               '  items (a list of anything)\n'
               'and the universe said i love you\n'
               '\n'
               'a pet has:\n'
               '  name (text)\n'
               'and the universe said i love you\n'
               '\n'
               'to push, for a stack of anything, given x (anything):\n'
               '  add x to items\n'
               'and the universe said i love you\n'
               '\n'
               'to top, for a stack of anything, returning anything:\n'
               '  return last item of items\n'
               'and the universe said i love you\n'
               '\n'
               'to pop, for a stack of anything:\n'
               '  remove item (the size of items) from items\n'
               'and the universe said i love you\n'
               '\n'
               'genesis:\n'
               '  conjure a stack of numbers as counts\n'
               '  push with (counts, 3)\n'
               '  push with (counts, 7)\n'
               '  scrawl top counts\n'
               '  pop counts\n'
               '  scrawl counts\n'
               '  set words to conjure a stack of text\n'
               '  push with (words, "hello")\n'
               '  scrawl top words\n'
               '  conjure a stack of pets as zoo\n'
               '  set rex to conjure a pet\n'
               '  set the name of rex to "Rex"\n'
               '  push with (zoo, rex)\n'
               '  scrawl the name of top zoo\n'
               '  set piles to a list of stacks of numbers\n'
               '  add counts to piles\n'
               '  scrawl the size of piles\n'
               'and the universe said i love you\n'
               ]))
    assert out.stdout == "7\na stack of numbers (items: 3)\nhello\nRex\n1\n", repr(out.stdout)

    # List maths, and stable sorting by a part.
    out = both('a pet has:\n  name (text)\n  age (a number)\n' + END +
               'genesis:\n  set xs to a list of (4, 1.5, 9, 2)\n  set sum to 1\n'
               '  scrawl sum of xs, " ", average of xs, " ", biggest of xs, " ", smallest of xs, " ", sum of a list of numbers, " ", sum\n'
               '  set pets to a list of (pet called with ("Rex", 3), pet called with ("Ann", 9), pet called with ("Bo", 3))\n'
               '  for each p in sorted pets by age: scrawl the name of p\n  scrawl sorted pets by name\n'
               '  scrawl average of a list of numbers\n' + END +
               'to pet called, given name (text) and age (a number), returning a pet:\n  set p to conjure a pet\n'
               '  set the name of p to name\n  set the age of p to age\n  return p\n' + END)
    assert out.stdout == ("16.5 4.125 9 1.5 0 1\nRex\nBo\nAnn\n"
                          "a pet (name: Ann, age: 9), a pet (name: Bo, age: 3), a pet (name: Rex, age: 3)\n"), repr(out.stdout)
    assert out.stderr == "Line 12: the list is empty, so it has no average.\n", repr(out.stderr)

    # save and load: the same both ways.
    out = both('a pet has:\n  name (text)\n  age (a number)\n  tricks (a list of text)\n' + END +
               'a home has:\n  owner (a pet)\n  pets (a list of pets)\n  spot (a place)\n' + END +
               'genesis:\n  set q to a quotation mark\n  set h to conjure a home\n'
               '  set the name of the owner of h to "Rex " plus q plus "the" plus q plus " dog\\" plus new line\n'
               '  add "sit" to the tricks of the owner of h\n  add the owner of h to the pets of h\n  set the spot of h to 1.5 horizontal -0 vertical 0.1 depth\n'
               '  save h to file "home.json"\n  scrawl contents of file "home.json"\n  set again to conjure a home\n'
               '  load again from file "home.json"\n  scrawl again is h\n'
               '  set xs to a list of (0.1, 1 divided by 100000, 1 divided by 10000, 123.25, 10000000000000000, 12345678901234567,'
               ' -1 divided by 100000, 1 divided by 3, 10000000000000000 times 1000, 7)\n'
               '  save xs to file "xs.json"\n  scrawl contents of file "xs.json"\n  set ys to a list of numbers\n  load ys from file "xs.json"\n'
               '  scrawl ys is xs\n  set t to a table of yes or no\n  set entry "b" of t to yes\n  set entry "a" of t to no\n'
               '  save t to file "t.json"\n  scrawl contents of file "t.json"\n'
               '  inscribe "{" plus q plus "name" plus q plus ": " plus q plus "Bo" plus q plus ", " plus q plus "tricks" plus q'
               ' plus ": [" plus q plus "\\u00e9\\ud83d\\ude00" plus q plus "], " plus q plus "age" plus q plus ": 2, "'
               ' plus q plus "age" plus q plus ": 3, " plus q plus "other" plus q plus ": null}" into file "p.json"\n'
               '  set p to conjure a pet\n  load p from file "p.json"\n  scrawl p\n'
               '  for each bad in a list of ("[1, 2", "[1, true]", "[[NaN]]", "[01]", "{}", "  [ ]  x", "[1.]", "[" plus q plus "a" plus q plus "]"):\n'
               '    inscribe bad into file "bad.json"\n    try:\n      load ys from file "bad.json"\n'
               '    if that went wrong:\n      scrawl the wound\n  inscribe "  [ 4 , 5e1, -0.5E+1 ]  " into file "ok.json"\n'
               '  load ys from file "ok.json"\n  scrawl ys\n  set zero to 0\n  set n to 1 divided by zero\n  save n to file "n.json"\n' + END)
    assert out.stdout == (
        '{"owner": {"name": "Rex \\"the\\" dog\\\\\\n", "age": 0, "tricks": ["sit"]}, "pets": [{"name": "Rex \\"the\\" dog\\\\\\n", '
        '"age": 0, "tricks": ["sit"]}], "spot": [1.5, 0, 0.1]}\n\nyes\n'
        '[0.1, 1e-05, 0.0001, 123.25, 1e+16, 1.2345678901234568e+16, -1e-05, 0.3333333333333333, 1e+19, 7]\n\nyes\n'
        '{"a": false, "b": true}\n\na pet (name: Bo, age: 3, tricks: é\U0001F600)\n'
        + 'the file "bad.json" doesn\'t hold a list of numbers.\n' * 8 + "4, 50, -5\n"), repr(out.stdout)
    assert out.stderr == "Line 49: I can't save infinity or not a number.\n", repr(out.stderr)
    assert perr("genesis:\n  set x to 1\n  load 5 from file \"a\"\n" + END)[1] == "'5' can't be changed, so I can't load into it."

    out = both('genesis:\n  scrawl "Hello ", 1 plus 1\n' + END)
    assert out.stdout == "Hello 2\n", repr(out.stdout)
    assert perr("genesis:\n  scrawl\n" + END)[1] == "'scrawl' needs something to show, like: scrawl \"hello\"."
    assert perr("genesis:\n  say 1\n" + END)[1] == "'say' is now 'scrawl', like: scrawl \"hello\"."

    # birth and existence.
    out = both('a ball has:\n  birth (a flat place)\n  speed (a number)\n' + END +
               'genesis:\n  set b to conjure a ball\n  set the birth of b to 10 horizontal 20 vertical\n'
               '  set the existence of b of horizontal to 99\n  scrawl b\n  set the birth of b to 1 horizontal 2 vertical\n'
               '  scrawl the existence of b\n  set balls to a list of balls\n  add b to balls\n'
               '  set the birth of item 1 of balls to 5 horizontal 5 vertical\n  scrawl item 1 of balls\n'
               '  set birth to 3 horizontal 3 vertical\n  set the existence of horizontal to 7\n  set birth to 4 horizontal 4 vertical\n'
               '  scrawl existence\n' + END)
    assert out.stdout == ("a ball (birth: 10 horizontal 20 vertical, existence: 99 horizontal 20 vertical, speed: 0)\n"
                          "1 horizontal 2 vertical\n"
                          "a ball (birth: 5 horizontal 5 vertical, existence: 5 horizontal 5 vertical, speed: 0)\n"
                          "4 horizontal 4 vertical\n"), repr(out.stdout)

    out = both('genesis:\n  set the text size to 20\n  set the text size to 600\n' + END)
    assert out.stderr == "Line 3: text can be from 1 to 500 dots high, not 600.\n", repr(out.stderr)
    assert perr("genesis:\n  draw a circle with 1, 1, 1, \"red\"\n" + END)[1].startswith("'draw' is now 'etch'")
    out = both('genesis:\n  open a world with "x", 50, 50\n  reveal the frame\n  reveal the frame\n'
               '  scrawl frame time exceeds 0.01 and frame time falls below 0.5\n  end the world\n' + END)
    assert out.stdout == "yes\n", repr(out.stdout)

    # Commands for a kind change the thing itself.
    out = both('a ball has:\n  birth (a flat place)\n  speed (a flat place)\n  bounces (a number)\nand the universe said i love you\n\nto bounce, for a ball:\n  set the speed of vertical to the speed of vertical times -1\n  set bounces to bounces plus 1\nand the universe said i love you\n\nto move along, for a ball, given steps (a number):\n  repeat steps times:\n    set existence to existence plus speed\nand the universe said i love you\n\nto how far, for a ball, returning a number:\n  return the size of (existence minus birth)\nand the universe said i love you\n\nto restart, for a ball:\n  set birth to 0 horizontal 0 vertical\n  set ball to ball\nand the universe said i love you\n\ngenesis:\n  set b to conjure a ball\n  set the birth of b to 10 horizontal 10 vertical\n  set the speed of b to 3 horizontal 4 vertical\n  move along with (b, 2)\n  bounce b\n  scrawl b\n  scrawl how far b\n  set balls to a list of balls\n  add b to balls\n  bounce item 1 of balls\n  restart item 1 of balls\n  scrawl item 1 of balls\nand the universe said i love you\n')
    assert out.stdout == ("a ball (birth: 10 horizontal 10 vertical, existence: 16 horizontal 18 vertical, "
                          "speed: 3 horizontal -4 vertical, bounces: 1)\n10\n"
                          "a ball (birth: 0 horizontal 0 vertical, existence: 0 horizontal 0 vertical, "
                          "speed: 3 horizontal 4 vertical, bounces: 2)\n"), repr(out.stdout)
    assert perr("a ball has:\n  speed (a number)\n" + END + "to bounce, for a ball:\n  set speed to 1\n" + END +
                'genesis:\n  bounce conjure a ball\n' + END)[1].startswith("'bounce' changes the ball it is given")
    assert perr('to bounce, for a rock:\n  cease\n' + END + 'genesis:\n  cease\n' + END)[1] == "There is no kind of thing called 'rock'."

    # A ball bounces off the world's edges, using radius.
    out = both('genesis:\n  open a world with "Bounce", 600, 400\n  set radius to 30\n  set birth to 300 horizontal 200 vertical\n  set speed to 7 horizontal 5 vertical\n  set side bounces to 0\n  set floor bounces to 0\n  repeat 300 times:\n    set existence to existence plus speed\n    if existence touches a side:\n      set the speed of horizontal to the speed of horizontal times -1\n      set side bounces to side bounces plus 1\n    if existence touches the top or bottom:\n      set the speed of vertical to the speed of vertical times -1\n      set floor bounces to floor bounces plus 1\n    consume the window with "black"\n    etch a circle with the existence of horizontal, the existence of vertical, radius, "purple"\n    reveal the frame\n  scrawl width of the world, " ", height of the world, " ", side bounces, " ", floor bounces\nand the universe said i love you\n')
    assert out.stdout == "600 400 4 4\n", repr(out.stdout)
    assert perr("genesis:\n  set birth to 1 horizontal 1 vertical\n  scrawl existence touches a side\n" + END)[1] == \
        "'touches a side' needs to know how big the thing is: set radius first, like 'set radius to 20'."

    # Touching: circles overlap.
    out = both('a ball has:\n  birth (a flat place)\n  radius (a number)\n' + END +
               'to near, for a ball, given other (a ball), returning a yes or no:\n  return existence touches other\n' + END +
               'genesis:\n  set c to conjure a ball\n  set b to conjure a ball\n  set the birth of c to 0 horizontal 0 vertical\n'
               '  set the birth of b to 25 horizontal 0 vertical\n  set the radius of c to 10\n  set the radius of b to 10\n'
               '  scrawl c touches b\n  set the radius of b to 15\n  scrawl c touches b\n  scrawl near with (c, b)\n'
               '  scrawl 0 horizontal 0 vertical touches b\n' + END)
    assert out.stdout == "no\nyes\nyes\nno\n", repr(out.stdout)
    assert perr("genesis:\n  scrawl 3 touches 4\n" + END)[1] == "'touches' needs a thing or a place, not a number."

    # Kinds of kinds.
    kinds = ('a pet has:\n  name (text)\n  age (a number)\n' + END + 'a dog is a kind of pet that has:\n  tricks (a list of text)\n' + END +
             'a puppy is a kind of dog:\n' + END + 'a cat is a kind of pet that also has:\n  lives (a number)\n' + END +
             'to speak, for a pet:\n  scrawl name, " makes a sound"\n' + END +
             'to speak, for a dog:\n  scrawl name, " says woof and knows ", the size of tricks, " tricks"\n' + END +
             'to grow, for a pet, given years (a number), returning a number:\n  set age to age plus years\n  return age\n' + END)
    out = both(kinds + 'genesis:\n  set p to conjure a pet\n  set the name of p to "Blob"\n  set d to conjure a dog\n  set the name of d to "Rex"\n'
               '  add "sit" to the tricks of d\n  set u to conjure a puppy\n  set the name of u to "Bit"\n  set c to conjure a cat\n'
               '  set the name of c to "Tom"\n  set the lives of c to 9\n  speak p\n  speak d\n  speak u\n  speak c\n'
               '  scrawl grow with (d, 3), " ", grow with (c, 2), " ", grow with (u, 1)\n  scrawl d\n  scrawl c\n  scrawl u\n' + END)
    assert out.stdout == ("Blob makes a sound\nRex says woof and knows 1 tricks\nBit says woof and knows 0 tricks\nTom makes a sound\n3 2 1\n"
                          "a dog (name: Rex, age: 3, tricks: sit)\na cat (name: Tom, age: 2, lives: 9)\na puppy (name: Bit, age: 1, tricks: (nothing))\n"), repr(out.stdout)
    # A dog used as a pet.
    out = both('a pet has:\n  name (text)\n  age (a number)\nand the universe said i love you\n\na dog is a kind of pet that has:\n  tricks (a list of text)\nand the universe said i love you\n\na puppy is a kind of dog:\nand the universe said i love you\n\nto show, given p (a pet):\n  scrawl "pet: ", p\nand the universe said i love you\n\nto oldest, given pets (a list of pets), returning a pet:\n  set best to conjure a pet\n  for each p in pets:\n    if the age of p exceeds the age of best: set best to p\n  return best\nand the universe said i love you\n\nto adopt, given name (text), returning a pet:\n  set d to conjure a dog\n  set the name of d to name\n  set the age of d to 2\n  return d\nand the universe said i love you\n\ngenesis:\n  set d to conjure a dog\n  set the name of d to "Rex"\n  set the age of d to 5\n  add "sit" to the tricks of d\n  show d\n  set u to conjure a puppy\n  set the name of u to "Bit"\n  set the age of u to 1\n  set shelter to a list of pets\n  add d to shelter\n  add u to shelter\n  add adopt with "Jo" to shelter\n  scrawl shelter\n  scrawl oldest with shelter\n  set p to conjure a pet\n  set p to u\n  scrawl p\n  set item 1 of shelter to u\n  scrawl item 1 of shelter\n  scrawl d\nand the universe said i love you\n')
    assert out.stdout == 'pet: a pet (name: Rex, age: 5)\na pet (name: Rex, age: 5), a pet (name: Bit, age: 1), a pet (name: Jo, age: 2)\na pet (name: Rex, age: 5)\na pet (name: Bit, age: 1)\na pet (name: Bit, age: 1)\na dog (name: Rex, age: 5, tricks: sit)\n', repr(out.stdout)
    assert perr(kinds + 'genesis:\n  set d to conjure a dog\n  set d to conjure a pet\n' + END)[1] == "'d' holds a dog, not a pet."
    assert perr('a dog is a kind of pet:\n' + END + 'genesis:\n  cease\n' + END)[1] == \
        "Describe what a pet has above the dog, so a dog can be a kind of pet."
    assert perr(kinds + 'a fish is a kind of pet that has:\n  age (a number)\n' + END + 'genesis:\n  cease\n' + END)[1] == \
        "A fish already has a part called 'age' (every pet has one)."
    assert perr(kinds + 'to speak, for a cat, given loud (yes or no):\n  cease\n' + END + 'genesis:\n  cease\n' + END)[1] == \
        "Every version of 'speak' must take the same inputs and return the same kind."

    # Commands as values.
    out = both('a button has:\n  label (text)\n  press (a command)\nand the universe said i love you\n\nto double, given x (a number), returning a number:\n  return x times 2\nand the universe said i love you\n\nto half, given x (a number), returning a number:\n  return x divided by 2\nand the universe said i love you\n\nto greet, given who (text):\n  scrawl "Hello, ", who\nand the universe said i love you\n\nto apply to all, given f (a command given a number returning a number) and items (a list of numbers), returning a list of numbers:\n  set out to a list of numbers\n  for each item in items: add invoke f with item to out\n  return out\nand the universe said i love you\n\nto chooser, given big (yes or no), returning a command given a number returning a number:\n  if big: return the command double\n  return the command half\nand the universe said i love you\n\ngenesis:\n  set f to the command double\n  scrawl invoke f with 21\n  scrawl apply to all with (the command half, a list of (1, 2, 3))\n  set steps to a list of (the command double, the command half, the command round)\n  for each step in steps: scrawl invoke step with 16\n  invoke the command greet with "Sam"\n  set g to the command greet\n  invoke g with "Jo"\n  scrawl invoke (chooser with yes) with 5, " ", invoke (chooser with no) with 5\n  scrawl f\n  set b to conjure a button\n  try:\n    invoke the press of b\n  if that went wrong:\n    scrawl the wound\n  set h to a list of commands given a number returning a number\n  scrawl the size of h\n  set p to the command power of\n  scrawl invoke p with (2, 10)\n  set the press of b to the command hi\n  invoke the press of b\n  scrawl b\nand the universe said i love you\n\nto hi:\n  scrawl "hi!"\nand the universe said i love you\n')
    assert out.stdout == "42\n0.5, 1, 1.5\n32\n8\n16\nHello, Sam\nHello, Jo\n10 2.5\na command\nthere is no command in it yet: set it to one first, like 'set f to the command double'.\n0\n1024\nhi!\na button (label: , press: a command)\n", repr(out.stdout)
    assert perr('to hi:\n  cease\n' + END + 'genesis:\n  scrawl the command hi is the command hi\n' + END)[1] == \
        'Comparing needs a number, but this is a command.'
    assert perr('genesis:\n  invoke 5\n' + END)[1] == "'invoke' needs a command, like 'invoke the command double with 4', not a number."
    assert perr('genesis:\n  set f to the command nothing\n' + END)[1] == "'the command' needs the name of a command after it, like 'the command double'."

    # a number names a table's entry by its written form: 3 is the entry "3"
    out = both('genesis:\n  set ages to a table of numbers\n  set the entry 3 of ages to 10\n  set the entry 2.5 of ages to 7\n'
               '  add 1 to the entry 3 of ages\n  scrawl ages\n  scrawl the entry "3" of ages, " ", ages contains 3, " ", ages contains 4\n'
               '  remove entry 2.5 from ages\n  scrawl the keys of ages\nand the universe said i love you\n')
    assert out.stdout == "2.5: 7, 3: 11\n11 yes no\n3\n", repr(out.stdout)
    assert perr('genesis:\n  set ages to a table of numbers\n  scrawl the entry yes of ages\n' + END)[1] == \
        "A table's entries are named with text or a number, but this is yes or no."

    # words in brackets inside text are filled in; a pattern's brackets stay
    out = both('a pet has:\n  name (text)\nand the universe said i love you\n\ngenesis:\n  set name to "Sam"\n  set count to 3\n'
               '  conjure a pet as rex\n  set the name of rex to "Rex"\n  scrawl "Hello, [name]! [count] coins, next [count plus 1]."\n'
               '  scrawl "[the name of rex] says hi", " and [0-9] [^B] [ ] [[kept]] stay"\nand the universe said i love you\n')
    assert out.stdout == "Hello, Sam! 3 coins, next 4.\nRex says hi and [0-9] [^B] [ ] [kept] stay\n", repr(out.stdout)
    assert perr('genesis:\n  scrawl "Hi [scroe]"\n' + END)[1].startswith("I don't know 'scroe'.")

    # depending on: one value, many choices (worked out once)
    out = both('to describe, given weather (text):\n  depending on weather:\n    "rain": scrawl "umbrella"\n    "snow", "hail":\n'
               '      scrawl "coat"\n      scrawl "boots"\n    anything else: scrawl "enjoy the [weather]"\nand the universe said i love you\n\n'
               'genesis:\n  for each w in a list containing ("rain", "hail", "sun"): describe with w\n'
               '  depending on 7 plus 1:\n    8: scrawl "eight"\nand the universe said i love you\n')
    assert out.stdout == "umbrella\ncoat\nboots\nenjoy the sun\neight\n", repr(out.stdout)
    assert perr('genesis:\n  depending on 1:\n    anything else: scrawl 1\n' + END)[1] == "Put at least one choice before 'anything else:'."

    # whenever / every
    out = both('genesis:\n  set ticks to 0\n  every 0.05 seconds:\n    set ticks to ticks plus 1\n    scrawl "tick [ticks]"\n'
               '  whenever ticks exceeds 2:\n    scrawl "past two"\n  whenever ticks is 4:\n    scrawl "bye"\n    end the program with 0\n'
               '  scrawl "watching"\nand the universe said i love you\n')
    assert out.stdout == "watching\ntick 1\ntick 2\ntick 3\npast two\ntick 4\nbye\n", repr(out.stdout)
    assert perr('genesis:\n  every banana:\n    scrawl 1\n' + END)[1] == "Write 'every 2 seconds:' or 'every frame:'."

    # stellanova watch
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "w.stella").write_text('genesis:\n  set coins to 3\n  if coins exceeds 2:\n    scrawl "rich"\n'
                                          '  for each n from 1 to 2:\n    add n to coins\nand the universe said i love you\n', encoding="utf-8")
        shown = subprocess.run([sys.executable, str(HERE / "stellanova.py"), "watch", "w.stella"], capture_output=True, text=True,
                               encoding="utf-8", cwd=d).stdout
    assert shown == ("\u25b8 line 2: set coins to 3\n    coins: 3\n\u25b8 line 3: if coins exceeds 2:   \u2192 yes\n\u25b8 line 4: scrawl \"rich\"\nrich\n"
                     "\u25b8 line 5: for each n from 1 to 2:\n\u25b8 line 6: add n to coins\n    coins: 4\n\u25b8 line 6: add n to coins\n    coins: 6\n"), repr(shown)

    # stellanova debug, and Studia's marked lines
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "d.stella").write_text('to double, given x (a number), returning a number:\n  set y to x times 2\n  return y\n'
                                          'and the universe said i love you\n\ngenesis:\n  set total to 0\n  for each n from 1 to 3:\n'
                                          '    set total to total plus double with n\n  scrawl total\nand the universe said i love you\n', encoding="utf-8")
        shown = subprocess.run([sys.executable, str(HERE / "stellanova.py"), "debug", "d.stella"], input="step\nstep\nstep\nlook x\nout\nover\ngo\n",
                               capture_output=True, text=True, encoding="utf-8", cwd=d).stdout
        stops = [l.replace("(debug) ", "") for l in shown.splitlines()[1:]]
        assert stops == ["\u25a0 line 7: set total to 0", "\u25a0 line 8: for each n from 1 to 3:", "\u25a0 line 9: set total to total plus double with n",
                         "\u25a0 line 2: set y to x times 2", "    x: 1", "\u25a0 line 9: set total to total plus double with n",
                         "\u25a0 line 9: set total to total plus double with n", "12"], stops
        shown = subprocess.run([sys.executable, str(HERE / "stellanova.py"), "debug", "--studia", "d.stella", "3"], input="go\nforget 3\ngo\n",
                               capture_output=True, text=True, encoding="utf-8", cwd=d).stdout
        marked = [json.loads(l[8:]) for l in shown.splitlines() if l.startswith("@@debug ")]
        assert [(m["line"], m["names"].get("y"), m["stops"]) for m in marked] == [(3, "2", [3]), (3, "4", [3]), (3, "4", [])], marked
        assert shown.splitlines()[-1] == "12", shown

    # stellanova profile
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "p.stella").write_text('to slow sum, given n (a number), returning a number:\n  set total to 0\n  for each k from 1 to n:\n'
                                          '    set total to total plus k times k\n  return total\nand the universe said i love you\n\n'
                                          'genesis:\n  scrawl slow sum with 300\n  scrawl slow sum with 300\nand the universe said i love you\n', encoding="utf-8")
        shown = subprocess.run([sys.executable, str(HERE / "stellanova.py"), "profile", "p.stella"], capture_output=True, text=True,
                               encoding="utf-8", cwd=d).stdout.splitlines()
    assert shown[:4] == ["9045050", "9045050", "", "Where the time went (the 20 slowest lines, by their own time):"], shown
    runs = {int(l.split()[0]): int(l.split()[1]) for l in shown[5:]}
    assert runs == {2: 2, 3: 2, 4: 600, 5: 2, 9: 1, 10: 1}, runs
    # stellanova wasm
    if node and (translate.machine.WASI / "wasi-sysroot-34.0").exists():
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "w.stella").write_text(
                'use: time\nuse: folders\n\na pet has:\n  name (text)\n  tricks (a list of text)\nand the universe said i love you\n\n'
                'to greet, given who (text), returning text:\n  return "Hello, [who]!"\nand the universe said i love you\n\n'
                'genesis:\n  ask "Name? " into name\n  scrawl greet with name\n  set k to 3\n'
                '  scrawl a list of (4, 9, 15) changed by each n becomes n times k\n'
                '  scrawl a list of (4, 9, 15) kept by each n becomes n exceeds 5\n'
                '  set pets to a list of pets\n  repeat 3 times:\n    conjure a pet as p\n    set the name of p to "Rex"\n    add p to pets\n'
                '  for each q in pets: scrawl the name of q, " knows: ", the tricks of q\n'
                '  make the folder "box/inner"\n  inscribe "hi" into file "box/a.txt"\n'
                '  scrawl files in the folder "box", " / ", folders in the folder "box"\n  erase the folder "box"\n'
                '  scrawl weekday of "2026-12-25"\n  scrawl item 9 of pets\nand the universe said i love you\n', encoding="utf-8")
            direct = subprocess.run([sys.executable, str(HERE / "stellanova.py"), "w.stella"], input="Sam\n", capture_output=True,
                                    text=True, encoding="utf-8", cwd=d)
            problem = translate.wasm(Path(d) / "w.stella")
            assert problem is None, problem
            made = subprocess.run([node, "w.mjs"], input="Sam\n", capture_output=True, text=True, encoding="utf-8", cwd=d,
                                  env=dict(os.environ, STELLANOVA_COLLECT_OFTEN="1"))
        assert direct.stdout.startswith("Name? Hello, Sam!\n12, 27, 45\n9, 15\nRex knows: (nothing)\n"), direct.stdout
        assert (made.stdout, made.stderr, made.returncode) == (direct.stdout, direct.stderr, direct.returncode), (made, direct)
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "m.stella").write_text('to count:\n  scrawl 1\nand the universe said i love you\n\ngenesis:\n  meanwhile count\n'
                                              'and the universe said i love you\n', encoding="utf-8")
            assert translate.wasm(Path(d) / "m.stella") is None  # 'meanwhile': each thread is a Node worker sharing the memory
            ran = subprocess.run([node, "m.mjs"], capture_output=True, text=True, cwd=d)
            assert (ran.stdout, ran.returncode) == ("1\n", 0), ran

    # stellanova check on a web program
    with tempfile.TemporaryDirectory() as d:
        page = 'use: page\n\ngenesis:\n  set the text with (the element "#count", "Hi")\nand the universe said i love you\n'
        (Path(d) / "c.stella").write_text(page, encoding="utf-8")
        said = subprocess.run([sys.executable, str(HERE / "stellanova.py"), "check", "c.stella"], capture_output=True, text=True,
                              encoding="utf-8", cwd=d).stdout
        assert said == "c.stella: no mistakes found.\n", said
        (Path(d) / "c.stella").write_text(page.replace('"Hi")', '"Hi")\n  scrawl nope'), encoding="utf-8")
        said = subprocess.run([sys.executable, str(HERE / "stellanova.py"), "check", "c.stella"], capture_output=True, text=True,
                              encoding="utf-8", cwd=d).stdout
        assert "nope" in said and "no mistakes" not in said, said
        # tidy: two spaces a step, no trailing spaces, line ends kept
        (Path(d) / "t.stella").write_bytes(b'to greet, given who (text):   \r\n    if who is "x":\r\n\t\tscrawl "hi   there"\r\n'
                                           b'    scrawl who\r\nand the universe said i love you\r\ngenesis:\r\n\r\n\r\n   greet with "x"\r\n' + END.encode() + b'\r\n\r\n')
        said = subprocess.run([sys.executable, str(HERE / "stellanova.py"), "tidy", "t.stella"], capture_output=True, text=True, cwd=d).stdout
        assert said == "t.stella: tidied.\n", said
        assert (Path(d) / "t.stella").read_bytes() == (b'to greet, given who (text):\r\n  if who is "x":\r\n    scrawl "hi   there"\r\n  scrawl who\r\n'
                                                       b'and the universe said i love you\r\n\r\ngenesis:\r\n\r\n  greet with "x"\r\n'
                                                       b'and the universe said i love you\r\n'), (Path(d) / "t.stella").read_bytes()
        said = subprocess.run([sys.executable, str(HERE / "stellanova.py"), "tidy", "t.stella"], capture_output=True, text=True, cwd=d).stdout
        assert said == "t.stella: already tidy.\n", said
        if node:  # the VS Code extension
            (Path(d) / "e.stella").write_text('to greet, given who (text):\n  scrawl who\n' + END + 'genesis:\n'
                                              '  scrawl days between with ("2026-01-01", "2026-01-03")\n  scrawl nope\n' + END, encoding="utf-8")
            said = subprocess.run([node, str(HERE / "editor" / "check_extension.js"), str(Path(d) / "e.stella")], capture_output=True,
                                  text=True, encoding="utf-8").stdout.splitlines()
            assert said[0].startswith("line 6: I don't know 'nope'.") and said[1].endswith("own: greet") and \
                said[2] == "days between, given first (text) and last (text), returning a number", said
            assert not list(Path(d).glob(".*.checking.stella")), "the copy being checked is left behind"

    # an if line counts every try
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "p.stella").write_text('genesis:\n  for each k from 1 to 10:\n    if k exceeds 8: scrawl k\nand the universe said i love you\n', encoding="utf-8")
        shown = subprocess.run([sys.executable, str(HERE / "stellanova.py"), "profile", "p.stella"], capture_output=True, text=True,
                               encoding="utf-8", cwd=d).stdout.splitlines()
    assert {int(l.split()[0]): int(l.split()[1]) for l in shown[5:]} == {2: 1, 3: 10}, shown

    # is one of
    out = both('genesis:\n  set answer to "y"\n  set sizes to a list containing (1, 2, 3)\n'
               '  scrawl answer is one of ("yes", "y", "sure"), " ", 2 is one of sizes, " ", 5 is not one of sizes, " ", answer is not one of ("y", "n")\n'
               '  if answer is one of ("yes", "y"): scrawl "agreed"\nand the universe said i love you\n')
    assert out.stdout == "yes yes yes no\nagreed\n", repr(out.stdout)
    assert perr('genesis:\n  scrawl 2 is one of ("a", "b")\n' + END)[1].startswith("'is one of' needs choices of the same kind")

    # a command with no inputs, then more words
    out = both('to greeting, returning text:\n  return "hi"\nand the universe said i love you\n\ngenesis:\n  scrawl greeting as saved text\n'
               'and the universe said i love you\n')
    assert out.stdout == '"hi"\n', repr(out.stdout)

    # inputs with usual values can be left out
    out = both('to greet, given name (text, usually "Friend") and count (a number, usually 1):\n  repeat count times:\n'
               '    scrawl "Hello, [name]!"\nand the universe said i love you\n\n'
               'to label, given n (a number) and unit (text, usually "cm"), returning text:\n  return "[n] [unit]"\nand the universe said i love you\n\n'
               'genesis:\n  greet\n  greet with "Sam"\n  greet with ("Jo", 2)\n'
               '  scrawl label with 5, " ", label with (5, "m"), " ", (label with 7) plus "!"\nand the universe said i love you\n')
    assert out.stdout == "Hello, Friend!\nHello, Sam!\nHello, Jo!\nHello, Jo!\n5 cm 5 m 7 cm!\n", repr(out.stdout)
    assert perr('to f, given a (a number, usually 1) and b (a number):\n  cease\n' + END)[1] == \
        "Inputs with a usual value go last, after the ones without."
    assert perr('to f, given a (a number, usually x):\n  cease\n' + END)[1].startswith("A usual value is written out")

    # a misspelt first word gets a guess
    assert perr('genesis:\n  scrwal 1\n' + END)[1] == "I don't know how to start a line with 'scrwal'. Did you mean 'scrawl'?"
    assert perr('genesis:\n  fro each n from 1 to 3: scrawl n\n' + END)[1] == \
        "I don't know how to start a line with 'fro each'. Did you mean 'for each'?"

    # list and text tools
    out = both('genesis:\n  set names to a list containing ("Ann", "Bo", "Cy", "Di", "Bo", "Ann")\n  scrawl items 2 to 4 of names\n'
               '  scrawl the first 2 of names, " / ", the last 3 of names, " / ", first 3 of "Stellanova", " / ", last 4 of "Stellanova"\n'
               '  scrawl unique names\n'
               '  scrawl the size of shuffled names, " ", the position of "Cy" in names, " ", the position of "Zed" in names\n'
               '  scrawl 1234567 with commas, " ", (-9876543.25) with commas, " ", 12 with commas\n'
               '  scrawl 7 padded to 3 digits, " ", (-4) padded to 2 digits, " ", 1234 padded to 2 digits\n'
               '  scrawl the first 10 of names\nand the universe said i love you\n')
    assert out.stdout == ("Bo, Cy, Di\nAnn, Bo / Di, Bo, Ann / Ste / nova\nAnn, Bo, Cy, Di\n6 3 0\n1,234,567 -9,876,543.25 12\n"
                          "007 -04 1234\nAnn, Bo, Cy, Di, Bo, Ann\n"), repr(out.stdout)

    # for each ... by
    out = both('genesis:\n  set out to ""\n  for each n from 0 to 20 by 5: set out to out plus n plus " "\n'
               '  for each n from 3 to 1 by -1: set out to out plus n plus " "\n  for each n from 0 to 1 by 0.25: set out to out plus n plus " "\n'
               '  for each n from 1 to 3 by 0: set out to out plus "never"\n  scrawl out\nand the universe said i love you\n')
    assert out.stdout == "0 5 10 15 20 3 2 1 0 0.25 0.5 0.75 1 \n", repr(out.stdout)

    # 'repeated N times' for text and lists, 'flattened' for a list of lists
    out = both('genesis:\n  scrawl "[", "ab" repeated 3 times, "] [", "x" repeated 0 times, "]"\n  set row to a list of (0, 1) repeated 2 times\n  scrawl row\n  set rows to a list of lists of numbers\n  add a list of (1, 2) to rows\n  add a list of (3) to rows\n  scrawl flattened rows, " ", the size of flattened rows\n  set names to flattened a list of (a list of ("a", "b"), a list of ("c"))\n  scrawl names\n  try:\n    scrawl "a" repeated (0 minus 1) times\n  if that went wrong:\n    scrawl the wound\nand the universe said i love you\n')
    assert out.stdout == "[ababab] []\n0, 1, 0, 1\n1, 2, 3 3\na, b, c\n'repeated' needs a whole number of times, 0 or more, not -1.\n", repr(out.stdout)

    # reversed, repeated and flattened on lists of things
    out = both('a pet has:\n  name (text)\nand the universe said i love you\n\ngenesis:\n  conjure a pet as rex\n  set the name of rex to "Rex"\n  conjure a pet as tom\n  set the name of tom to "Tom"\n  set pets to a list of pets\n  add rex to pets\n  add tom to pets\n  scrawl reversed pets\n  scrawl pets repeated 2 times\n  set groups to a list of lists of pets\n  add pets to groups\n  add reversed pets to groups\n  scrawl flattened groups\n  scrawl reversed a list of (1, 2, 3), " ", "ab" repeated 2 times, " ", flattened a list of (a list of (1), a list of (2, 3))\n  try:\n    scrawl pets repeated 0.5 times\n  if that went wrong:\n    scrawl the wound\nand the universe said i love you\n')
    assert out.stdout == "a pet (name: Tom), a pet (name: Rex)\na pet (name: Rex), a pet (name: Tom), a pet (name: Rex), a pet (name: Tom)\na pet (name: Rex), a pet (name: Tom), a pet (name: Tom), a pet (name: Rex)\n3, 2, 1 abab 1, 2, 3\n'repeated' needs a whole number of times, 0 or more, not 0.5.\n", repr(out.stdout)

    # 'for each' can borrow a name: each item in the loop, what it was after
    out = both('genesis:\n  set kind to "start"\n  for each kind in a list of ("a", "b"):\n    scrawl kind\n  scrawl kind\n  set n to 5\n  for each n from 1 to 2:\n    scrawl n\n  scrawl n\n  for each n in a list of ("x"):\n    scrawl n\n  scrawl n plus 1\nand the universe said i love you\n')
    assert out.stdout == 'a\nb\nstart\n1\n2\n5\nx\n6\n', repr(out.stdout)
    # sorted ..., biggest first (equal ones keep their order)
    out = both('a pet has:\n  name (text)\n  age (a number)\nand the universe said i love you\n\ngenesis:\n  set pets to a list of pets\n  for each n in a list of ("Rex", "Tom", "Bo", "Max"):\n    conjure a pet as p\n    set the name of p to n\n    set the age of p to the size of n\n    add p to pets\n  scrawl sorted pets by age, biggest first\n  scrawl sorted pets by age\n  scrawl sorted a list of (3, 1, 2), biggest first, " ", sorted a list of ("b", "a")\n  scrawl reversed a list of (1, 2)\nand the universe said i love you\n')
    assert out.stdout == 'a pet (name: Rex, age: 3), a pet (name: Tom, age: 3), a pet (name: Max, age: 3), a pet (name: Bo, age: 2)\na pet (name: Bo, age: 2), a pet (name: Rex, age: 3), a pet (name: Tom, age: 3), a pet (name: Max, age: 3)\n3, 2, 1 a, b\n2, 1\n', repr(out.stdout)
    # sorted by what each works out to
    out = both('a pet has:\n  name (text)\n  age (a number)\nand the universe said i love you\n\ngenesis:\n  set names to a list of ("Rex", "Al", "Tomas", "Bo", "Max")\n  scrawl sorted names by each n becomes the size of n\n  scrawl sorted names by each n becomes the size of n, biggest first\n  scrawl sorted a list of (3, -5, 1) by each x becomes x times x\n  set pets to a list of pets\n  for each n in names:\n    conjure a pet as p\n    set the name of p to n\n    set the age of p to the size of n\n    add p to pets\n  scrawl sorted pets by each p becomes letter 2 of the name of p\nand the universe said i love you\n')
    assert out.stdout == 'Al, Bo, Rex, Max, Tomas\nTomas, Rex, Max, Al, Bo\n1, 3, -5\na pet (name: Max, age: 3), a pet (name: Rex, age: 3), a pet (name: Al, age: 2), a pet (name: Tomas, age: 5), a pet (name: Bo, age: 2)\n', repr(out.stdout)
    # sorted text: long shared beginnings, shorter first, empty text, other alphabets
    out = both('genesis:\n  set names to a list of ("abcdefghij2", "abcdefghij1", "abcdefgh", "abcdefg", "", "abcdefghi", "b", "Ω", "a", "abcdefghij1")\n  scrawl sorted names\nand the universe said i love you\n')
    assert out.stdout == ', a, abcdefg, abcdefgh, abcdefghi, abcdefghij1, abcdefghij1, abcdefghij2, b, Ω\n', out.stdout
    out = both('a pet has:\n  name (text)\n  age (a number)\nand the universe said i love you\n\ngenesis:\n  set pets to a list of pets\n  for each n in a list of ("Rexington the 2nd", "Rexington the 1st", "Rexingto", "Bo"):\n    conjure a pet as p\n    set the name of p to n\n    set the age of p to the size of n\n    add p to pets\n  for each p in sorted pets by name: scrawl the name of p\n  scrawl sorted a list of ("xxxxxxxxB", "xxxxxxxxA", "y") by each w becomes w plus "!"\nand the universe said i love you\n')
    assert out.stdout == 'Bo\nRexingto\nRexington the 1st\nRexington the 2nd\nxxxxxxxxA, xxxxxxxxB, y\n', out.stdout
    # 'a plus b plus c' grows one new text; the names it reads stay as they were
    out = both('genesis:\n  set a to "x" plus 1 plus "y"\n  set b to a plus "z" plus a plus 2\n  set c to (a plus b) plus (b plus a)\n  set parts to a list of ("p", "q")\n  set d to (join parts with ",") plus "!" plus 3\n  scrawl a, " ", b, " ", c, " ", d, " ", parts\nand the universe said i love you\n')
    assert out.stdout == 'x1y x1yzx1y2 x1yx1yzx1y2x1yzx1y2x1y p,q!3 p, q\n', out.stdout
    # any alphabet and emoji
    out = both('use: letters\n\ngenesis:\n  set word to "Ünïcødé 😀 Ωμέγα"\n  scrawl the size of word\n  scrawl letter 9 of word, " ", letter 1 of word, " ", letters 11 to 15 of word\n  scrawl upper case of word\n  scrawl lower case of word\n  scrawl position of "😀" in word, " ", position of "Ω" in word\n  scrawl word contains "😀", " ", word begins with "Ün", " ", word ends with "γα"\n  scrawl replace "😀" with "🙂" in word\n  scrawl word split by " "\n  scrawl "[", "ñ" padded to 3 letters, "] ", "é" repeated 3 times\n  scrawl "[", trimmed "  ñ  ", "]"\n  scrawl the words of "à la carte"\n  scrawl code of the letter "😀", " ", the letter with code 937\n  scrawl sorted a list of ("é", "e", "z", "Ω")\n  scrawl "😀😀" is "😀😀", " ", the size of ""\n  for each n from 1 to 3:\n    scrawl letter n of "a😀b"\nand the universe said i love you\n')
    assert out.stdout == '15\n😀 Ü Ωμέγα\nÜNÏCØDÉ 😀 ΩΜΈΓΑ\nünïcødé 😀 ωμέγα\n9 11\nyes yes yes\nÜnïcødé 🙂 Ωμέγα\nÜnïcødé, 😀, Ωμέγα\n[ñ  ] ééé\n[ñ]\nà, la, carte\n128512 Ω\ne, z, é, Ω\nyes 0\na\n😀\nb\n', repr(out.stdout)
    # markup: a new <li>, <td> or <p> ends the one before it, as in browsers
    out = both('use: markup.stella\n\ngenesis:\n  set whole to read markup "<ul><li>One<li>Two<b>!</b><li>Three</ul><table><tr><td>a<td>b<tr><td>c</table><p>x<p>y"\n  for each ul in parts named with (whole, "ul"):\n    scrawl the size of the parts of ul, " items: ", join (the parts of ul changed by each li becomes all words in li) with ", "\n  for each tr in parts named with (whole, "tr"):\n    scrawl the size of the parts of tr, " cells: ", all words in tr\n  scrawl the size of parts named with (whole, "p")\nand the universe said i love you\n')
    assert out.stdout == '3 items: One, Two!, Three\n2 cells: ab\n1 cells: c\n2\n', repr(out.stdout)
    # big programs: a command written 'privately' is kept to its own script
    scripts = {'a.stella': 'to greet, privately:\n  scrawl "hi from a"\nand the universe said i love you\n\nto helper, privately, returning number:\n  return 1\nand the universe said i love you\n\nto from a:\n  greet\nand the universe said i love you\n', 'b.stella': 'to greet:\n  scrawl "hi from b"\nand the universe said i love you\n\nto helper, returning number:\n  return 2\nand the universe said i love you\n'}
    out = both('use: a.stella\nuse: b.stella\n\ngenesis:\n  greet\n  from a\nand the universe said i love you\n', others=scripts)
    assert out.stdout == 'hi from b\nhi from a\n', repr(out.stdout)
    def mistake(source, others):  # what running it directly says is wrong
        with tempfile.TemporaryDirectory() as d:
            for name, text_ in dict(others, **{'probe.stella': source}).items():
                (Path(d) / name).write_text(text_, encoding='utf-8')
            return subprocess.run([sys.executable, str(HERE / 'stellanova.py'), 'run', 'probe.stella'], cwd=d,
                                  capture_output=True, text=True, encoding='utf-8')
    out = mistake('use: a.stella\n\ngenesis:\n  scrawl helper\n' + END, scripts)
    assert "'helper' is kept to a.stella (it is written 'privately' there), so only a.stella can use it." in out.stdout + out.stderr, out
    out = mistake('use: a.stella\nuse: b.stella\n\ngenesis:\n  greet\n  from a\nand the universe said i love you\n', {'a.stella': 'to greet:\n  scrawl "hi from a"\nand the universe said i love you\n\nto helper, returning number:\n  return 1\nand the universe said i love you\n\nto from a:\n  greet\nand the universe said i love you\n', 'b.stella': 'to greet:\n  scrawl "hi from b"\nand the universe said i love you\n\nto helper, returning number:\n  return 2\nand the universe said i love you\n'})
    assert ("b.stella line 1: There are two commands called 'greet': this one, and one in a.stella line 1. "
            "Rename one, or write 'to greet, privately' in the script that only uses it there.") in out.stdout + out.stderr, out

    # text padded to a width
    out = both('genesis:\n  scrawl "[", "food" padded to 8 letters, "] [", "café" padded to 6 letters, "] [", "toolong" padded to 3 letters, "] [", 7 padded to 3 digits, "]"\n  try:\n    scrawl "a" padded to 1.5 letters\n  if that went wrong:\n    scrawl the wound\nand the universe said i love you\n')
    assert out.stdout == "[food    ] [café  ] [toolong] [007]\nI can't pad to 1.5 letters: it must be a whole number, 0 or more.\n", repr(out.stdout)

    # parts of a path, and when a file last changed
    out = both('use: folders\nuse: time\n\ngenesis:\n  for each p in a list of ("saves/slot 1.json", "notes", "a\\b\\.hidden", "x.tar.gz"):\n'
               '    scrawl "[", file name of p, "] [", extension of p, "] [", folder holding p, "]"\n'
               '  set gap to (seconds since 1970) minus last change of the file "f.txt"\n'
               '  scrawl gap is at least 0 and gap falls below 100, " ", bytes in the file "f.txt"\n'
               '  try:\n    scrawl last change of the file "nope.txt"\n  if that went wrong:\n    scrawl the wound\n' + END, others={"f.txt": b"hello"})
    assert out.stdout == ('[slot 1.json] [json] [saves]\n[notes] [] []\n[.hidden] [] [a\\b]\n[x.tar.gz] [gz] []\nyes 5\n'
                          'there is no file called "nope.txt".\n'), repr(out.stdout)

    # dates are text, with words in the time library
    out = both('use: time\n\ngenesis:\n  scrawl days between ("2026-11-13", "2026-12-25"), " ", days between ("2024-03-01", "2024-02-01")\n'
               '  scrawl date plus days ("2026-11-13", 30), " ", date plus days ("2024-03-01", -1), " ", date plus days ("1969-12-31", 1)\n'
               '  scrawl weekday of "2026-11-13", " ", weekday of "2000-01-01", " ", weekday of "1969-12-31"\n'
               '  scrawl (days until today) is 0\n  try:\n    scrawl weekday of "2026-02-30"\n  if that went wrong:\n    scrawl the wound\n'
               'and the universe said i love you\n')
    assert out.stdout == ("42 -29\n2026-12-13 2024-02-29 1970-01-01\nFriday Saturday Wednesday\nyes\n"
                          "'2026-02-30' isn't a date: dates are written like 2026-11-13.\n"), repr(out.stdout)
    out = both('use: time\n\ngenesis:\n  scrawl date in words "2026-11-16"\n'
               '  scrawl date plus months ("2026-01-31", 1), " ", date plus months ("2024-01-31", 1), " ", date plus months ("2026-03-15", -15)\n'
               '  set moment to seconds at ("2026-11-16", "14:05:09")\n'
               '  scrawl date at moment, " ", time at moment, " ", (seconds at ("2026-11-17", "14:05:09")) minus moment\n'
               '  try:\n    scrawl seconds at ("2026-11-16", "25:00:00")\n  if that went wrong:\n    scrawl the wound\n' + END)
    assert out.stdout == ("Monday 16 November 2026\n2026-02-28 2024-02-29 2024-12-15\n2026-11-16 14:05:09 86400\n"
                          "'25:00:00' isn't a time: times are written like 14:05:00.\n"), repr(out.stdout)

    # the spreadsheet library: CSV text <-> rows
    out = both('use: spreadsheet\n\ngenesis:\n  set rows to rows of the spreadsheet ("name,note" plus new line plus "Ann," plus a quotation mark '
               'plus "a, b" plus a quotation mark plus new line)\n  for each row in rows:\n    scrawl join row with " | "\n'
               '  add a list containing ("Bo", "x") to rows\n  scrawl the spreadsheet of rows\nand the universe said i love you\n')
    assert out.stdout == 'name | note\nAnn | a, b\nname,note\nAnn,"a, b"\nBo,x\n\n', repr(out.stdout)

    # the database library: SQLite, with ? for values
    out = both('use: database\n\ngenesis:\n  change the database ("shop.db", "create table if not exists items (name text, price real); delete from items")\n'
               '  change the database with values ("shop.db", "insert into items values (?, ?)", a list containing ("Bob' + "'" + 's cake", "12"))\n'
               '  change the database with values ("shop.db", "insert into items values (?, ?)", a list containing ("tea", "3.5"))\n'
               '  for each row in rows from the database ("shop.db", "select name, price from items order by price"):\n'
               '    scrawl join row with " costs "\n'
               '  scrawl item 1 of item 1 of rows from the database with values ("shop.db", "select count(*) from items where price > ?", a list containing "5")\n'
               '  try:\n    change the database ("shop.db", "select * from nowhere")\n  if that went wrong:\n    scrawl the wound\n'
               'and the universe said i love you\n')
    assert out.stdout == "tea costs 3.5\nBob's cake costs 12\n1\nthe database couldn't do it: there is no table called \"nowhere\", so make it first with CREATE TABLE (it said: no such table: nowhere).\n", repr(out.stdout)

    # JSON from web services
    q = "plus a quotation mark plus"
    out = both('a forecast has:\n  city (text)\n  temperature (a number)\n  wind speed (a number)\nand the universe said i love you\n\n'
               f'genesis:\n  set reply to "{{" {q} "city" {q} ": " {q} "Oslo" {q} ", " {q} "temperature" {q} ": null, " {q} "Wind_Speed" {q} '
               f'": 7, " {q} "extra" {q} ": [1, null]}}"\n'
               '  set f to conjure a forecast\n  load f from the text reply\n'
               '  scrawl the city of f, " ", the temperature of f, " ", the wind speed of f\nand the universe said i love you\n')
    assert out.stdout == "Oslo 0 7\n", repr(out.stdout)

    # check lines, and stellanova test
    out = both('genesis:\n  scrawl 1\n  check 1 plus 1 is 3\n  scrawl "not reached"\nand the universe said i love you\n')
    assert out.stdout == "1\n" and out.stderr == ("Line 3: this check failed: 1 plus 1 is 3\n"), (out.stdout, out.stderr)
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "t.stella").write_text('to double, given x (a number), returning a number:\n  return x times 2\nand the universe said i love you\n\n'
                                          'to test doubling:\n  check double with 2 is 4\nand the universe said i love you\n\n'
                                          'to test names:\n  set names to a list containing ("Ann", "Bo")\n  check the size of names is 3\n'
                                          'and the universe said i love you\n\ngenesis:\n  scrawl "genesis"\nand the universe said i love you\n', encoding="utf-8")
        tested = subprocess.run([sys.executable, str(HERE / "stellanova.py"), "test", "t.stella"], capture_output=True, text=True,
                                encoding="utf-8", cwd=d)
    assert (tested.stdout, tested.returncode) == ("\u2713 test doubling\n\u2717 test names: line 11: this check failed: the size of names is 3\n"
                                                  "2 tests: 1 passed, 1 failed.\n", 1), (tested.stdout, tested.returncode)

    # nothing
    out = both('an enemy has:\n  name (text)\n  health (a number)\nand the universe said i love you\n\nto the weakest, given enemies (a list of enemys), returning an enemy:\n  set best to no enemy\n  for each e in enemies:\n    if best is nothing or the health of e falls below the health of best:\n      set best to e\n  return best\nand the universe said i love you\n\ngenesis:\n  set foes to a list of enemys\n  scrawl the weakest with foes\n  scrawl (the weakest with foes) is nothing\n  conjure an enemy as orc\n  set the name of orc to "orc"\n  set the health of orc to 5\n  add orc to foes\n  set target to the weakest with foes\n  scrawl target is something, " ", the name of target\n  add no enemy to foes\n  scrawl foes\n  scrawl foes as saved text\n  set back to a list of enemys\n  load back from the text (foes as saved text)\n  scrawl back, " ", back is foes\n  set target to no enemy\n  try:\n    scrawl the health of target\n  if that went wrong:\n    scrawl the wound\n  set the health of target to 3\nand the universe said i love you\n')
    assert out.stdout == ("nothing\nyes\nyes orc\na enemy (name: orc, health: 5), nothing\n[{\"name\": \"orc\", \"health\": 5}, null]\n"
                          "a enemy (name: orc, health: 5), nothing yes\nthis enemy is nothing, so it has no health.\n"), repr(out.stdout)
    assert out.stderr == "Line 35: this enemy is nothing, so it has no health.\n", repr(out.stderr)

    # shared abilities
    out = both('a dog has:\n  name (text)\nand the universe said i love you\n\na robot has:\n  serial (a number)\nand the universe said i love you\n\na speaker is anything that can speak and shout twice.\n\nto speak, for a dog, returning text:\n  return "Woof, I am [the name of the dog]"\nand the universe said i love you\n\nto speak, for a robot, returning text:\n  return "Beep [the serial of the robot]"\nand the universe said i love you\n\nto shout twice, for a dog, given word (text):\n  scrawl word, " ", word, "!"\nand the universe said i love you\n\nto shout twice, for a robot, given word (text):\n  scrawl word, word\nand the universe said i love you\n\ngenesis:\n  conjure a dog as rex\n  set the name of rex to "Rex"\n  conjure a robot as robo\n  set the serial of robo to 42\n  set crowd to a list of speakers\n  add rex to crowd\n  add robo to crowd\n  for each s in crowd:\n    scrawl speak s\n    shout twice with (s, "hi")\n  scrawl crowd\n  set quiet to no speaker\n  scrawl quiet is nothing\n  set quiet to robo\n  scrawl speak quiet\n  set quiet to no speaker\n  scrawl speak quiet\nand the universe said i love you\n')
    assert out.stdout == ("Woof, I am Rex\nhi hi!\nBeep 42\nhihi\na dog (name: Rex), a robot (serial: 42)\nyes\nBeep 42\n"), repr(out.stdout)
    assert out.stderr == "Line 44: this speaker is nothing, so it can't speak.\n", repr(out.stderr)
    able = 'a dog has:\n  name (text)\nand the universe said i love you\n\na robot has:\n  serial (a number)\nand the universe said i love you\n\na speaker is anything that can speak and shout twice.\n\nto speak, for a dog, returning text:\n  return "Woof, I am [the name of the dog]"\nand the universe said i love you\n\nto speak, for a robot, returning text:\n  return "Beep [the serial of the robot]"\nand the universe said i love you\n\nto shout twice, for a dog, given word (text):\n  scrawl word, " ", word, "!"\nand the universe said i love you\n\nto shout twice, for a robot, given word (text):\n  scrawl word, word\nand the universe said i love you\n\n'
    assert perr(able + 'a cat has:\n  lives (a number)\n' + END + 'genesis:\n  conjure a cat as tom\n  set crowd to a list of speakers\n'
                '  add tom to crowd\n' + END)[1] == "This list holds speakers, so I can't add a cat to it."
    assert perr(able + 'genesis:\n  conjure a speaker as x\n' + END)[1] == \
        "A speaker is anything that can speak and shout twice, so conjure one of those instead (dog, robot)."
    assert perr(able + 'to purr, for a dog:\n  cease\n' + END + 'genesis:\n  set s to no speaker\n  purr s\n' + END)[1] == \
        "A speaker can only speak and shout twice, not 'purr'."

    # 'is a dog': which kind a thing really is (kinds of a dog count too)
    out = both(able + 'a puppy is a kind of dog that has:\n  toy (text)\n' + END + 'to speak, for a puppy, returning text:\n  return "Yip"\n' + END
               + 'to shout twice, for a puppy, given word (text):\n  scrawl word\n' + END
               + 'genesis:\n  conjure a dog as rex\n  conjure a robot as robo\n  conjure a puppy as bit\n  set crowd to a list of speakers\n'
               '  add rex to crowd\n  add robo to crowd\n  add bit to crowd\n  add no speaker to crowd\n'
               '  for each s in crowd:\n    scrawl s is a dog, " ", s is a robot, " ", s is not a puppy\n'
               '  scrawl rex is a dog, " ", bit is a dog, " ", rex is a puppy\n' + END)
    assert out.stdout == "yes no yes\nno yes yes\nyes no no\nno no yes\nyes yes no\n", repr(out.stdout)

    # hidden parts: only commands for that kind (and kinds of it) use them
    bank = ('an account has:\n  owner (text)\n  balance (a number, hidden)\n' + END + 'a savings is a kind of account that has:\n  rate (a number)\n' + END
            + 'to pay in, for an account, given amount (a number):\n  add amount to balance\n' + END
            + 'to grow, for a savings:\n  set the balance of the savings to the balance of the savings times (1 plus rate)\n' + END
            + 'to money in, for an account, returning a number:\n  return balance\n' + END)
    out = both(bank + 'genesis:\n  conjure a savings as s\n  set the rate of s to 0.5\n  pay in with (s, 10)\n  grow s\n  scrawl money in s\n  scrawl s\n' + END)
    assert out.stdout == "15\na savings (owner: , balance: 15, rate: 0.5)\n", repr(out.stdout)
    assert perr(bank + 'genesis:\n  conjure an account as acct\n  set the balance of acct to 5\n' + END)[1] == \
        "The balance of an account is hidden: only commands for an account can use it."

    # saving and loading speakers
    out = both('a dog has:\n  name (text)\nand the universe said i love you\n\na robot has:\n  serial (a number)\nand the universe said i love you\n\na speaker is anything that can speak and shout twice.\n\nto speak, for a dog, returning text:\n  return "Woof, I am [the name of the dog]"\nand the universe said i love you\n\nto speak, for a robot, returning text:\n  return "Beep [the serial of the robot]"\nand the universe said i love you\n\nto shout twice, for a dog, given word (text):\n  scrawl word, " ", word, "!"\nand the universe said i love you\n\nto shout twice, for a robot, given word (text):\n  scrawl word, word\nand the universe said i love you\n\na stage has:\n  title (text)\n  star (a speaker)\n  cast (a list of speakers)\nand the universe said i love you\n\ngenesis:\n  conjure a dog as rex\n  set the name of rex to "Rex"\n  conjure a robot as robo\n  set the serial of robo to 42\n  set crowd to a list of speakers\n  add rex to crowd\n  add robo to crowd\n  add no speaker to crowd\n  save crowd to file "crowd.json"\n  scrawl contents of file "crowd.json"\n  set back to a list of speakers\n  load back from file "crowd.json"\n  scrawl back is crowd\n  for each s in back:\n    if s is something: scrawl speak s\n  conjure a stage as show\n  set the title of show to "Tonight"\n  set the star of show to robo\n  set the cast of show to crowd\n  scrawl show as saved text\n  conjure a stage as again\n  load again from the text (show as saved text)\n  scrawl speak the star of again, " ", the size of the cast of again\n  scrawl rex as saved text\n  set odd to a list of speakers\n  try:\n    load odd from the text "[{[[]]}]"\n  if that went wrong:\n    scrawl the wound\nand the universe said i love you\n')
    assert out.stdout == ('[{"is a": "dog", "name": "Rex"}, {"is a": "robot", "serial": 42}, null]\n\nyes\nWoof, I am Rex\nBeep 42\n'
                          '{"title": "Tonight", "star": {"is a": "robot", "serial": 42}, "cast": [{"is a": "dog", "name": "Rex"}, '
                          '{"is a": "robot", "serial": 42}, null]}\nBeep 42 3\n{"name": "Rex"}\n'
                          "the text doesn't hold a list of speakers.\n"), repr(out.stdout)

    # freeing values while others live on
    out = both('a pet has:\n  name (text)\n  scores (a list of numbers)\nand the universe said i love you\n\n'
               'to make a pet, given n (a number), returning a pet:\n  conjure a pet as p\n  set the name of p to "pet " plus n\n'
               '  add n to the scores of p\n  return p\nand the universe said i love you\n\n'
               'genesis:\n  set pets to a list of pets\n  set names to a table of text values\n  set total to 0\n'
               '  for each n from 1 to 70000:\n    set scratch to a list containing (n, n plus 1, n plus 2)\n    set p to make a pet with n\n'
               '    add the sum of scratch to total\n    if the remainder of (n, 7000) is 0:\n      add p to pets\n'
               '      set the entry "k" plus n of names to the name of p\n'
               '  scrawl total, " ", the size of pets, " ", the name of the item at 10 in pets, " ", the scores of the item at 3 in pets\n'
               '  scrawl the entry "k70000" of names\nand the universe said i love you\n')
    assert out.stdout == "7350315000 10 pet 70000 21000\npet 70000\n", repr(out.stdout)

    # library threads calling a command
    out = both('use: burst\n\nto label, given n (a number), returning text:\n  set parts to a list containing (n, n plus 1, n times 2)\n'
               '  return "item " plus the sum of parts\nand the universe said i love you\n\n'
               'genesis:\n  scrawl burst with (20000, the command label)\nand the universe said i love you\n',
               others={"burst.words": 'note: test: C++ threads of its own calling a command\n\ncode:\n  #include <thread>\n  namespace burst\n  {\n  \tinline double go(double count, std::function<std::string(double)> f)\n  \t{\n  \t\tstd::vector<std::thread> ts; std::vector<double> sizes(4);\n  \t\tfor (int k = 0; k < 4; k++) ts.emplace_back([&, k] { for (double n = 1; n <= count; n++) sizes[k] += static_cast<double>(f(n).size()); });\n  \t\tfor (auto& t : ts) t.join();\n  \t\treturn sizes[0] + sizes[1] + sizes[2] + sizes[3];\n  \t}\n  }\n\npython:\n  def burst_go(count, f):\n      return 4 * sum(len(f(float(n))) for n in range(1, int(count) + 1))\n\nto burst with, given count (a number) and f (a command given a number returning text), returning a number = burst::go({count}, {f})\n  runs: burst_go({count}, {f})\n'})
    assert out.stdout == "788904\n", repr(out.stdout)

    # meanwhile: own names; a problem stops everything.
    out = both('to count up, given name (text) and delay (a number):\n  wait delay\n  inscribe name plus " done" into file name plus ".txt"\nand the universe said i love you\n\nto fail later:\n  wait 0.2 seconds\n  raise an error with "the helper broke"\nand the universe said i love you\n\ngenesis:\n  set started to seconds since the start\n  set names to a list of ("a", "b", "c")\n  for each who in names: meanwhile count up with who, 0.5\n  set names to a list of text\n  wait for the others\n  scrawl contents of file "a.txt", " ", contents of file "b.txt", " ", contents of file "c.txt"\n  scrawl seconds since the start minus started falls below 1.4\n  meanwhile count up with "d", 0.3\n  scrawl "main goes on"\n  meanwhile fail later\n  wait 1 seconds\n  scrawl "never"\nand the universe said i love you\n')
    assert (out.stdout, out.stderr) == ('a done b done c done\nyes\nmain goes on\n', 'Line 8: the helper broke\n'), repr((out.stdout, out.stderr))
    assert perr('genesis:\n  meanwhile 5\n' + END)[1] == "'meanwhile' starts a command going alongside the rest, like 'meanwhile count down with 10'."

    # The server library.
    out = both('to answer, given address (text), returning text:\n  if address is "/hello": return "Hello from Stellanova!"\n  return "You asked for " plus address\nand the universe said i love you\n\ngenesis:\n  meanwhile serve the web with (8765, the command answer)\n  wait 0.5\n  scrawl web page "http://127.0.0.1:8765/hello"\n  scrawl web page "http://127.0.0.1:8765/scores?top=3"\n  end the program with 0\nand the universe said i love you\n'.replace('genesis:\n', 'genesis:\n  scrawl the size of user name exceeds 0\n'))
    assert out.stdout == 'yes\nHello from Stellanova!\nYou asked for /scores?top=3\n', repr(out.stdout)
    # Folder files, request messages and addresses.
    out = both('to answer, given address (text), returning text:\n  if address begins with "/echo": return "got " plus the web message\n  if address is "/f": answer with the file "site/index.html"\n  return "page " plus web decoded (letters 2 to the size of address of address)\nand the universe said i love you\n\ngenesis:\n  make the folder "site"\n  inscribe "body {}" into file "site/look.css"\n  inscribe "<p>home</p>" into file "site/index.html"\n  meanwhile serve the web from the folder with (8766, "site", the command answer)\n  wait 0.5\n  scrawl web page "http://127.0.0.1:8766/look.css"\n  scrawl web page "http://127.0.0.1:8766/"\n  scrawl web page "http://127.0.0.1:8766/a%20b+c"\n  scrawl web page "http://127.0.0.1:8766/f"\n  scrawl send to the web page with ("http://127.0.0.1:8766/echo", "héllo there")\n  scrawl web encoded "a b/é", " ", web decoded (web encoded "a b/é")\n  end the program with 0\nand the universe said i love you\n')
    assert out.stdout == 'body {}\n<p>home</p>\npage a b c\n<p>home</p>\ngot héllo there\na%20b%2F%C3%A9 a b/é\n', repr(out.stdout)

    # Any web request, with its status.
    web_stub(8792)
    out = both('use: web\n\ngenesis:\n'
               '  scrawl ask the web with ("http://127.0.0.1:8792/a?b=1", "GET"), " ", the last web status\n'
               '  scrawl ask the web with ("http://127.0.0.1:8792/pets", "POST", "Rex"), " ", the last web status\n'
               '  scrawl ask the web with ("http://127.0.0.1:8792/pets/1", "PUT", "{}", "X-Pet: dog" plus new line plus '
               '"Content-Type: application/json"), " ", the last web status\n'
               '  scrawl ask the web with ("http://127.0.0.1:8792/missing", "DELETE"), " ", the last web status\n'
               '  try:\n    scrawl ask the web with ("http://127.0.0.1:1/", "GET")\n  if that went wrong:\n    scrawl the wound\n' + END)
    assert out.stdout == ('GET /a?b=1 [] [] [] 200\nPOST /pets [] [text/plain; charset=utf-8] [Rex] 201\n'
                          'PUT /pets/1 [dog] [application/json] [{}] 200\nDELETE /missing [] [] [] 404\n'
                          'I couldn\'t reach the web page "http://127.0.0.1:1/".\n'), repr(out.stdout)

    # the web server: how it was asked, a status for the answer
    out = both('use: server\nuse: web\n\nto answer, given address (text), returning text:\n  if address is "/gone":\n    answer with the status 404\n    return "no"\n  return the web way plus " " plus the web message\n' + END + 'genesis:\n  meanwhile serve the web with (8767, the command answer)\n  wait 0.5\n  scrawl ask the web with ("http://127.0.0.1:8767/", "PUT", "hi"), " ", the last web status\n  scrawl ask the web with ("http://127.0.0.1:8767/gone", "GET"), " ", the last web status\n  end the program with 0\n' + END)
    assert out.stdout == 'PUT hi 200\nno 404\n', repr(out.stdout)

    # request and answer headers
    out = both('use: server\nuse: web\n\nto answer, given address (text), returning text:\n  return "pet is " plus the web header "X-Pet" plus "; " plus the web header "x-none"\nand the universe said i love you\n\ngenesis:\n  meanwhile serve the web with (8768, the command answer)\n  wait 0.5\n  scrawl ask the web with ("http://127.0.0.1:8768/", "GET", "", "X-Pet: dog")\n  scrawl the last web header "content-type", " [", the last web header "X-Nothing", "] ", the last web header "Content-Length"\n  scrawl ask the web with ("http://127.0.0.1:8768/data", "GET")\n  end the program with 0\nand the universe said i love you\n')
    assert out.stdout == 'pet is dog; \ntext/html; charset=utf-8 [] 12\npet is ; \n', repr(out.stdout)

    # a slow visitor doesn't hold up others
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / 'sv.stella').write_text('use: server\n\nto answer, given address (text), returning text:\n  return "got " plus address\nand the universe said i love you\n\ngenesis:\n  serve the web with (8771, the command answer)\nand the universe said i love you\n', encoding='utf-8')
        (Path(d) / 'slow.py').write_text('"""A slow client holds a connection open; a quick one must still be answered."""\nimport socket, sys, time, urllib.request\nslow = socket.create_connection(("127.0.0.1", 8771))\nslow.sendall(b"GET /slow HTTP/1.1\\r\\nHost: x\\r\\n")  # never finishes its request\nt = time.time()\nsaid = urllib.request.urlopen("http://127.0.0.1:8771/quick", timeout=5).read().decode()\nprint(said, "quick" if time.time() - t < 2 else "slow")\nslow.close()\n', encoding='utf-8')
        ways = [[sys.executable, str(HERE / 'stellanova.py'), 'run', 'sv.stella']]
        if compiler and translate.build(Path(d) / 'sv.stella', Path(d) / 'sv.exe') is None:
            ways.append([str(Path(d) / 'sv.exe')])
        if node and translate.web(Path(d) / 'sv.stella') is None:
            ways.append([node, 'sv.js'])
        for how in ways:
            server = subprocess.Popen(how, cwd=d, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                time.sleep(2.5)
                said = subprocess.run([sys.executable, 'slow.py'], cwd=d, capture_output=True, text=True, timeout=20).stdout
                assert said == 'got /quick quick\n', (how, said)
            finally:
                server.kill()
                server.wait()

    # Saved text, both ways.
    out = both('a pet has:\n  name (text)\n  age (a number)\nand the universe said i love you\n\ngenesis:\n  set ages to a table of numbers\n  set entry "Rex" of ages to 3\n  set entry "Tom" of ages to 12.5\n  set words to ages as saved text\n  scrawl words\n  set back to a table of numbers\n  load back from the text words\n  scrawl back\n  set p to conjure a pet\n  set the name of p to "Rex " plus a quotation mark plus "the dog" plus a quotation mark\n  scrawl p as saved text\n  set q to conjure a pet\n  load q from the text "{" plus a quotation mark plus "name" plus a quotation mark plus ": " plus a quotation mark plus "Jo" plus a quotation mark plus ", " plus a quotation mark plus "age" plus a quotation mark plus ": 4}"\n  scrawl q\n  set nums to a list of numbers\n  load nums from the text "  [1, 2.5, -3]  "\n  scrawl nums\n  try:\n    load nums from the text "[1, oops]"\n  if that went wrong:\n    scrawl the wound\nand the universe said i love you\n')
    assert out.stdout == '{"Rex": 3, "Tom": 12.5}\nRex: 3, Tom: 12.5\n{"name": "Rex \\"the dog\\"", "age": 0}\na pet (name: Jo, age: 4)\n1, 2.5, -3\nthe text doesn\'t hold a list of numbers.\n', repr(out.stdout)

    # The letters library: the numbers behind letters.
    out = both('genesis:\n  scrawl code of the letter "A", " ", code of the letter "abc", " ", code of the letter "é", " ", code of the letter "😀"\n  scrawl the letter with code 72 plus the letter with code 105, " ", the letter with code 233, " ", the letter with code 128512\n  set secret to ""\n  for each c in a list of ("H", "A", "L"):\n    set secret to secret plus the letter with code (code of the letter c plus 1)\n  scrawl secret\n  try:\n    scrawl the letter with code -1\n  if that went wrong:\n    scrawl the wound\n  scrawl code of the letter ""\nand the universe said i love you\n')
    assert (out.stdout, out.stderr) == ('65 97 233 128512\nHi \u00e9 \U0001f600\nIBM\nthere is no letter with the code -1.\n',
                                        "Line 12: 'code of the letter' needs a letter, but the text is empty.\n"), repr((out.stdout, out.stderr))
    # Bytes: files as lists of numbers from 0 to 255.
    out = both('genesis:\n  fill the file with ("data.bin", a list of (0, 255, 10, 13, 65))\n  scrawl the bytes of the file "data.bin", " / ", bytes in the file "data.bin"\n  set all to the bytes of the file "data.bin"\n  add 66 to all\n  fill the file with ("data.bin", all)\n  scrawl contents of file "data.bin" ends with "AB"\n  try:\n    fill the file with ("bad.bin", a list of (1, 256))\n  if that went wrong:\n    scrawl the wound\n  scrawl file "bad.bin" exists\nand the universe said i love you\n')
    assert out.stdout == '0, 255, 10, 13, 65 / 5\nyes\na byte is a whole number from 0 to 255, not 256.\nno\n', repr(out.stdout)

    # random fraction: from 0 up to (not quite) 1.
    out = both('genesis:\n  set lowest to 1\n  set highest to 0\n  repeat 1000 times:\n    set r to random fraction\n'
               '    set lowest to smaller of lowest and r\n    set highest to larger of highest and r\n'
               '  scrawl lowest is at least 0 and lowest falls below 0.05 and highest falls below 1 and highest exceeds 0.95\n' + END)
    assert out.stdout == "yes\n", repr(out.stdout)

    # changed by / kept by.
    out = both('to double, given x (a number), returning a number:\n  return x times 2\nand the universe said i love you\n\nto big one, given x (a number), returning yes or no:\n  return x exceeds 3\nand the universe said i love you\n\nto shout, given word (text), returning text:\n  return upper case of word plus "!"\nand the universe said i love you\n\ngenesis:\n  set scores to a list of (1, 5, 2, 8)\n  scrawl scores changed by the command double\n  scrawl scores kept by the command big one\n  scrawl (scores kept by the command big one) changed by the command double\n  scrawl (the words of "hi there") changed by the command shout\n  scrawl the size of (a list of numbers kept by the command big one)\n  scrawl scores changed by the command round\nand the universe said i love you\n')
    assert out.stdout == '2, 10, 4, 16\n5, 8\n10, 16\nHI!, THERE!\n0\n1, 5, 2, 8\n', repr(out.stdout)
    assert perr('to half, given x (text), returning text:\n  return x\n' + END + 'genesis:\n  scrawl a list of (1, 2) changed by the command half\n' + END)[1] == \
        "'changed by' needs a command given a number returning something, not a command given text returning text."

    # Kept shapes, daylight, the pointer.
    out = both('use: window\n\ngenesis:\n  open a world with "Kept", 640, 480\n  start keeping the shapes as "land"\n  for each x from -5 to 5:\n    for each z from 0 to 10:\n      etch a cube with (x horizontal 0 vertical z depth, 1, "green")\n  etch a ball with (0 horizontal 2 vertical 4 depth, 0.7, "yellow")\n  stop keeping the shapes\n  try:\n    stop keeping the shapes\n  if that went wrong:\n    scrawl the wound\n  try:\n    etch the kept shapes "sea"\n  if that went wrong:\n    scrawl the wound\n  try:\n    set the daylight to 2\n  if that went wrong:\n    scrawl the wound\n  set frames to 0\n  as long as the world lives and frames falls below 5:\n    set frames to frames plus 1\n    place the eye at 0 horizontal 3 vertical -6 depth\n    aim the eye with (frames times 0.3, -15)\n    consume the window with "#87ceeb"\n    set the daylight to 1 minus frames divided by 200\n    etch the kept shapes "land"\n    etch words with "right " plus mouse right clicked plus " wheel " plus mouse wheel turned, 10, 10, "white"\n    reveal the frame\n  scrawl "moved ", (mouse moved across) is (mouse moved across), " ", (mouse moved down) is (mouse moved down)\n  forget the kept shapes "land"\n  try:\n    etch the kept shapes "land"\n  if that went wrong:\n    scrawl the wound\nand the universe said i love you\n')
    assert out.stdout == 'no shapes are being kept. Start with: start keeping the shapes as "land"\nthere are no shapes kept as "sea".\nthe daylight is from 0 (dark) to 1 (full), not 2.\nmoved yes yes\nthere are no shapes kept as "land".\n', repr(out.stdout)

    # Places can have negative parts written straight in.
    out = both('genesis:\n  scrawl 1 horizontal -2 vertical -3 depth, " / ", 5 horizontal -1 vertical\n  set x to 3\n'
               '  scrawl (1 horizontal 2 vertical) of horizontal - x\n' + END)
    assert out.stdout == "1 horizontal -2 vertical -3 depth / 5 horizontal -1 vertical\n-2\n", repr(out.stdout)

    # 3D: the eye, where places land on the screen, and the 3D shapes.
    out = both('genesis:\n  open a world with "x", 800, 600\n  place the eye at 0 horizontal 0 vertical 0 depth\n  aim the eye with (0, 0)\n'
               '  scrawl screen place of 0 horizontal 0 vertical 10 depth\n'
               '  set p to screen place of 1 horizontal 1 vertical 10 depth\n'
               '  scrawl p of horizontal rounded to 2 decimal places, " ", p of vertical rounded to 2 decimal places\n'
               '  scrawl screen place of 0 horizontal 0 vertical -5 depth\n'
               '  aim the eye with (90, 0)\n  scrawl screen place of 10 horizontal 0 vertical 0 depth\n'
               '  aim the eye with (0, 200)\n  set q to screen place of 0 horizontal 10 vertical 0.1 depth\n  scrawl q of vertical falls below 300\n'
               '  consume the window with "black"\n  etch the ground with ("green", "#00ff00")\n'
               '  etch a cube with (0 horizontal 0 vertical 5 depth, 1, "red")\n  etch a block with (2 horizontal 0 vertical 5 depth, 1, 2, 3, "blue")\n'
               '  etch a ball with (0 horizontal 1 vertical 3 depth, 0.5, "yellow")\n  etch words with "hi", 10, 10, "white"\n  reveal the frame\n'
               '  try:\n    etch a ball with (0 horizontal 1 vertical 3 depth, 0, "yellow")\n  if that went wrong:\n    scrawl the wound\n'
               '  end the world\n' + END)
    assert out.stdout == ("400 horizontal 300 vertical\n451.96 248.04\nnot a number horizontal not a number vertical\n"
                          "400 horizontal 300 vertical\nyes\na ball's radius must be more than 0.\n"), repr(out.stdout)

    # raise an error: a problem of your own, caught by try: like any other.
    out = both('to check fuel, given fuel (a number):\n  if fuel falls below 1: raise an error with "the tank is empty (" plus fuel plus ")"\n'
               '  scrawl "fuel ok"\n' + END + 'genesis:\n  check fuel with 5\n  try:\n    check fuel with 0\n  if that went wrong:\n'
               '    scrawl "caught: ", the wound\n  raise an error with "for real"\n' + END)
    assert (out.stdout, out.stderr) == ("fuel ok\ncaught: the tank is empty (0)\n", "Line 11: for real\n"), repr((out.stdout, out.stderr))
    assert perr("genesis:\n  raise an error with 5\n" + END)[1] == "'raise an error with' needs text saying what went wrong, not a number."

    # Text: trimmed, begins with, ends with.
    out = both('genesis:\n  scrawl "[" plus trimmed "  hi there  " plus "]", " [", trimmed "   ", "]"\n'
               '  scrawl "Dr Who" begins with "Dr", " ", "Dr Who" begins with "Who", " ", "Dr Who" ends with "Who", " ", "a" ends with "abc", " ", "x" begins with ""\n' + END)
    assert out.stdout == "[hi there] []\nyes no yes no yes\n", repr(out.stdout)

    # The computer library.
    out = both('genesis:\n  scrawl the size of the words given\n  scrawl the output of the command "echo hello there"\n'
               '  scrawl environment value of "OS"\n  scrawl the size of current folder exceeds 2\n  end the program with 3\n  scrawl "never"\n' + END)
    assert (out.stdout, out.returncode) == ("0\nhello there\n\n" + os.environ.get("OS", "") + "\nyes\n", 3), repr((out.stdout, out.returncode))
    # Programs running alongside.
    talker, sleeper = ("echo hello; echo oops 1>&2; exit 3", "sleep 30") if sys.platform.startswith("linux") else ("cmd /c echo hello& echo oops 1>&2& exit 3", "ping -n 30 127.0.0.1")
    out = both('use: computer\ngenesis:\n  set p to start the program with ("' + talker + '", "")\n'
               '  set said to ""\n  set problems to ""\n  as long as the program is running p:\n'
               '    set said to said plus latest output of the program p\n    set problems to problems plus latest errors of the program p\n'
               '  set said to said plus latest output of the program p\n  set problems to problems plus latest errors of the program p\n'
               '  scrawl trimmed said, " ", trimmed problems, " ", exit code of the program p\n'
               '  set q to start the program with ("' + sleeper + '", "")\n  stop the program q\n'
               '  as long as the program is running q:\n    set problems to ""\n  scrawl "stopped"\n  scrawl latest output of the program 9\n' + END)
    assert out.stdout == "hello oops 3\nstopped\n", repr(out.stdout)
    assert out.stderr == "Line 17: there is no program 9 (start one with 'start the program').\n", repr(out.stderr)

    # A kind holding a list of itself.
    tree = '[{"name": "a", "inside": [{"name": "b", "inside": [{}]}]}]'
    out = both('a spot has:\n  name (text)\n  inside (a list of spots)\n' + END + 'genesis:\n  set tree to a list of spots\n'
               '  load tree from file "tree.json"\n'
               '  scrawl the name of item 1 of (the inside of item 1 of tree), " ", tree as saved text\n' + END, others={"tree.json": tree})
    assert out.stdout == 'b [{"name": "a", "inside": [{"name": "b", "inside": [{"name": "", "inside": []}]}]}]\n', repr(out.stdout + out.stderr)
    out = both('genesis:\n  scrawl logarithm of 1000, " ", natural logarithm of e, " ", logarithm of -1\n'
               '  scrawl arc sine of 0.5 rounded to 6 decimal places, " ", arc cosine of 0, " ", arc tangent of 1, " ", arc sine of 2\n'
               '  scrawl whole part of -3.7, " ", whole part of 3.7\n' + END)
    assert out.stdout == "3 1 not a number\n30 90 45 not a number\n-3 3\n", repr(out.stdout)

    # The patterns library.
    out = both('genesis:\n  set line to "Sam is 31, Jo is 7 and Ann is 102."\n  scrawl the pattern fits with ("[0-9]+", line)\n'
               '  scrawl the pattern fits with ("^[0-9]", line)\n  scrawl matches of the pattern with ("[0-9]+", line)\n'
               '  scrawl pieces of the pattern with ("([A-Z][a-z]+) is ([0-9]+)", line)\n  scrawl the size of pieces of the pattern with ("zzz(z)", line)\n'
               '  scrawl replace the pattern with ("[0-9]+", line, "$$")\n  try:\n    scrawl the pattern fits with ("([a-z", line)\n'
               '  if that went wrong:\n    scrawl the wound\n' + END)
    assert out.stdout == 'yes\nno\n31, 7, 102\nSam, 31\n0\nSam is $$, Jo is $$ and Ann is $$.\nthe pattern "([a-z" isn\'t a pattern I understand.\n', repr(out.stdout)
    out = both('genesis:\n  scrawl the size of today, " ", the size of the time now, " ", seconds since 1970 exceeds 1000000\n' + END)
    assert out.stdout == "10 8 yes\n", repr(out.stdout)

    # The folders library.
    out = both('genesis:\n  make the folder "box/inner"\n  inscribe "hello" into file "box/a.txt"\n'
               '  copy the file with "box/a.txt", "box/b.txt"\n  move the file with "box/b.txt", "box/c.txt"\n'
               '  scrawl files in the folder "box", " / ", folders in the folder "box"\n'
               '  scrawl bytes in the file "box/c.txt", " ", folder "box/inner" exists, " ", folder "nope" exists\n'
               '  erase the file "box/a.txt"\n  scrawl files in the folder "box"\n  try:\n    erase the file "box/a.txt"\n'
               '  if that went wrong:\n    scrawl the wound\n  erase the folder "box"\n  scrawl folder "box" exists\n'
               '  scrawl files in the folder "nope"\n' + END)
    assert (out.stdout, out.stderr) == ('a.txt, c.txt / inner\n5 yes no\nc.txt\nI couldn\'t erase the file "box/a.txt".\nno\n',
                                        'Line 16: there is no folder called "nope".\n'), repr((out.stdout, out.stderr))

    out = both('genesis:\n  open a world with "x", 40, 40\n  etch a square with 20, 20, 5, "purple"\n  reveal the frame\n'
               '  end the world\n  scrawl "ok"\n' + END)
    assert out.stdout == "ok\n", repr(out.stdout)
    assert perr('genesis:\n  open a world with "x", 10, 10\n  etch a triangle with 1, 2\n' + END)[1] == (
        "I don't know 'etch a triangle with'. Words that start with 'etch': etch a ball, etch a block, etch a box, etch a circle, etch a cube, etch a line, "
        "etch a square, etch a triangle in space, etch the ground, etch the kept shapes, etch the model, etch the moving model, etch the picture, etch the picture in space, etch the picture turned, etch the sheet frame, etch words.")

    # within: close enough to touch.
    out = both('genesis:\n  set birth to 0 horizontal 0 vertical\n  set coin to 3 horizontal 4 vertical\n'
               '  scrawl existence is within 5 of coin, " ", existence is within 4.9 of coin, " ", 7 is within 2 of 5, " ",'
               ' 1 horizontal 1 vertical 1 depth is within 1 of 1 horizontal 1 vertical 2 depth, " ", not (10 is within 2 of 5)\n' + END)
    assert out.stdout == "yes no yes yes yes\n", repr(out.stdout)
    assert perr("genesis:\n  scrawl 1 is within 2 of 1 horizontal 2 vertical\n" + END)[1] == \
        "'within' compares two numbers or two places, not a number and a flat place."

    # Places, birth and existence.
    out = both('genesis:\n  set birth to 300 horizontal 200 vertical\n'
               '  set the existence of horizontal to the existence of horizontal plus 5\n  scrawl birth, " / ", existence\n'
               '  set existence to birth\n  scrawl existence\n  set gravity to 0 horizontal -0.5 vertical\n'
               '  set speed to gravity times 2 plus 1 horizontal 0 vertical\n  scrawl speed, " / ", round (sine of 30) times 10\n'
               '  set p to 3 horizontal 4 vertical 12 depth\n  set q to 1 horizontal 1 vertical 1 depth\n'
               '  scrawl p, " / ", the size of p, " / ", p plus q, " / ", -q, " / ", p divided by 2\n'
               '  set f to flat p\n  scrawl f, " / ", the size of f, " / ", direction of 0 horizontal 5 vertical, " / ",'
               ' p of horizontal plus p of depth\n'
               '  set p of vertical to 100\n  scrawl p, " / ", 1 horizontal 2 vertical 0 depth divided by 0\n'
               '  scrawl a list of (p, q)\n' + END)
    assert out.stdout == ("300 horizontal 200 vertical / 305 horizontal 200 vertical\n300 horizontal 200 vertical\n"
                          "1 horizontal -1 vertical / 0\n"
                          "3 horizontal 4 vertical 12 depth / 13 / 4 horizontal 5 vertical 13 depth / "
                          "-1 horizontal -1 vertical -1 depth / 1.5 horizontal 2 vertical 6 depth\n"
                          "3 horizontal 4 vertical / 5 / 90 / 15\n"
                          "3 horizontal 100 vertical 12 depth / infinity horizontal infinity vertical not a number depth\n"
                          "3 horizontal 100 vertical 12 depth, 1 horizontal 1 vertical 1 depth\n"), repr(out.stdout)
    # The old forms are gone.
    assert perr("genesis:\n  scrawl (1, 2)\n" + END)[1] == \
        "A place is written like 300 horizontal 200 vertical (and 5 depth, for a place with depth)."
    assert perr('to start:\n  cease\n' + END)[1] == "'to start:' is now 'genesis:'."
    assert perr("genesis:\n  set p to 1 horizontal 2 vertical\n  scrawl the x of p\n" + END)[1].startswith("I don't know 'x")
    assert perr("genesis:\n  set p to 1 horizontal 2 vertical\n  scrawl p of depth\n" + END)[1] != ""
    assert perr('to begin:\n  cease\n' + END)[1] == "A program needs a 'genesis:' command: that is where it begins."


    # Lists inside lists show in brackets.
    out = both('genesis:\n  set grid to a list of lists of numbers\n  add a list of (1, 2) to grid\n  add a list of numbers to grid\n'
               '  add a list of (3, 4) to grid\n  set item 1 of item 1 of grid to 9\n  scrawl grid, " / ", item 2 of item 3 of grid\n'
               '  set teams to a table of lists of text\n  set entry "red" of teams to a list of ("Ann", "Bo")\n  scrawl teams\n' + END)
    assert out.stdout == "(9, 2), (nothing), (3, 4) / 4\nred: (Ann, Bo)\n", repr(out.stdout)

    # Numbers and text shown the same both ways.
    out = both('genesis:\n  scrawl 1 divided by 3, " ", 10 divided by 4, " ", 2 times 0.1, " ", 1000000 times 1000000, " ", -0 times 1\n'
               '  scrawl the size of "héllo", " ", "a" plus 1 plus yes, " ", "x" is "x", " ", 3 is not 3\n'
               '  for each n from 1 to 4:\n    if n is 1: scrawl "one"\n    otherwise if n is 2:\n      scrawl "two"\n    otherwise: scrawl "many"\n'
               '  scrawl first big in a list of (1, 5, 9, 2)\n  count down with 3\n' + END +
               'to first big in, given xs (a list of numbers), returning a number:\n'
               '  for each x in xs:\n    if x exceeds 4: return x\n  return 0\n' + END +
               'to count down, given from (a number):\n  set left to from\n  as long as yes:\n    scrawl left\n'
               '    set left to left minus 1\n    if left is 0: cease\n' + END).stdout
    assert out == ("0.333333333333333 2.5 0.2 1000000000000 0\n5 a1yes yes no\none\ntwo\nmany\nmany\n5\n3\n2\n1\n"), repr(out)

    # Lists of things are copied when stored, the same both ways.
    out = both('a box has:\n  items (a list of numbers)\n' + END +
               'genesis:\n  set c to conjure a box\n  add 1 to the items of c\n  set b to c\n  add 2 to the items of b\n'
               '  set boxes to a list of (c, b)\n  add 3 to the items of item 1 of boxes\n  scrawl c, " ", b, " ", boxes\n'
               '  scrawl c is item 1 of boxes, " ", b is item 2 of boxes\n' + END).stdout
    assert out == ("a box (items: 1) a box (items: 1, 2) a box (items: 1, 3), a box (items: 1, 2)\nno yes\n"), repr(out)

    # Text and list tools; leaving loops early.
    out = both('genesis:\n  set s to "Héllo wörld, hello"\n'
               '  scrawl upper case of s, " | ", lower case of "ABC é", " | ", letter 2 of s, " | ", letters 7 to 11 of s\n'
               '  scrawl position of "llo" in s, " ", position of "zz" in s, " | ", replace "llo" with "LP" in s\n'
               '  set parts to s split by ", "\n  scrawl the size of parts, " ", item 2 of parts, " | ", join parts with "+"\n'
               '  scrawl sorted a list of (3, 1, 2), " | ", reversed a list of ("a", "b"), " | ", last item of parts, " | ", letters 3 to 2 of "abc", "."\n'
               '  for each n from 1 to 10:\n    if n is 2: move on\n    if n is 5: break free\n    scrawl n\n'
               '  repeat 3 times:\n    as long as yes: break free\n    scrawl "r"\n'
               '  scrawl letter 9 of "abc"\n' + END)
    assert out.stdout == ("HÉLLO WÖRLD, HELLO | abc é | é | wörld\n3 0 | HéLP wörld, heLP\n"
                          "2 hello | Héllo wörld+hello\n1, 2, 3 | b, a | hello | .\n1\n3\n4\nr\nr\nr\n"), repr(out.stdout)
    assert out.stderr == "Line 15: there is no letter 9 in text of 3 letters.\n", repr(out.stderr)
    assert perr('genesis:\n  break free\n' + END)[1] == "'break free' only works inside 'repeat', 'as long as' or 'for each'."

    # Tables.
    out = both('genesis:\n  set ages to a table of numbers\n  set entry "Rex" of ages to 3\n  set entry "Ann" of ages to 40\n'
               '  set entry "Rex" of ages to entry "Rex" of ages plus 1\n  scrawl ages, " | ", the size of ages, " | ", keys of ages\n'
               '  scrawl ages contains "Ann", " ", ages contains "Bob"\n  remove entry "Ann" from ages\n  scrawl ages\n'
               '  set pets to a table of lists of text\n  set entry "Rex" of pets to a list of text\n'
               '  add "sit" to entry "Rex" of pets\n  scrawl pets\n  for each name in keys of pets: scrawl name\n'
               '  scrawl entry "Bob" of ages\n' + END)
    assert out.stdout == "Ann: 40, Rex: 4 | 2 | Ann, Rex\nyes no\nRex: 4\nRex: (sit)\nRex\n", repr(out.stdout)
    assert out.stderr == 'Line 15: there is no entry "Bob" in the table.\n', repr(out.stderr)

    # Libraries.
    out = both('use: maths\nuse: time\ngenesis:\n  scrawl round (sine of 30 times 1000), " ", power of (2, 10), " ", remainder of (17, 5)\n'
               '  scrawl round 2.5, " ", round down -2.5, " ", round up 2.1, " ", round (pi times 100)\n'
               '  wait 0.01 seconds\n  scrawl seconds since the start exceeds 0, " ", the current year exceeds 2000\n' + END).stdout
    assert out == "500 1024 2\n3 -3 3 314\nyes yes\n", repr(out)

    # A window, the same both ways.
    out = both('use: window\ngenesis:\n  open a world with "Test ✓", 200, 100\n'
               '  scrawl the world lives, " ", mouse held, " ", key held "space"\n  repeat 3 times:\n'
               '    scrawl key pressed "space", " ", mouse clicked\n'
               '    consume the window with "black"\n    etch a box with 10, 10, 50, 20, "#ff8800"\n'
               '    etch a circle with 100, 50, 20, "blue"\n    etch a line with 0, 0, 200, 100, "white"\n'
               '    etch words with "héllo", 120, 10, "yellow"\n    reveal the frame\n  end the world\n'
               '  scrawl the world lives\n  etch a circle with 1, 1, 1, "red"\n  scrawl "ok"\n  etch a circle with 1, 1, 1, "reddish"\n' + END)
    assert out.stdout == "yes no no\nno no\nno no\nno no\nno\nok\n", repr(out.stdout)
    assert out.stderr == 'Line 17: I don\'t know the colour "reddish". Use a name like "red" or a code like "#ff8800".\n', repr(out.stderr)
    assert both('use: window\ngenesis:\n  reveal the frame\n' + END).stderr.startswith("Line 3: there is no window yet.")

    # Pictures: a tiny .png made here is read and drawn the same both ways.
    import struct
    import zlib

    def png(width, height):
        def chunk(kind, data):
            return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
        rows = b"".join(b"\0" + b"\xff\x00\x00" * width for _ in range(height))
        return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))
    out = both('use: window\ngenesis:\n  scrawl width of picture "red.png", " ", height of picture "red.png"\n'
               '  open a world with "Pictures", 100, 100\n  etch the picture with "red.png", 10, 10\n  reveal the frame\n'
               '  end the world\n  scrawl width of picture "red.png"\n  scrawl width of picture "none.png"\n' + END,
               others={"red.png": png(7, 3)})
    assert out.stdout == "7 3\n7\n", repr(out.stdout)
    assert out.stderr == 'Line 9: there is no picture called "none.png".\n', repr(out.stderr)
    out = both('genesis:\n  open a world with "Pictures", 100, 100\n  etch the picture turned with "red.png", 50, 50, 2, 30\n'
               '  reveal the frame\n  etch the picture turned with "red.png", 50, 50, 0, 30\n' + END, others={"red.png": png(7, 3)})
    assert out.stderr == "Line 5: a picture's size must be more than 0 and at most 100, not 0.\n", repr(out.stderr)

    # The web library, offline.
    out = both('use: web\ngenesis:\n  scrawl web page "http://localhost:1/"\n' + END)
    assert out.stderr == 'Line 3: I couldn\'t get the web page "http://localhost:1/".\n', repr(out.stderr)

    # Programs made of several scripts.
    shapes = ('use: maths\nuse: helpers.stella\na square has:\n  side (a number)\n' + END +
              'genesis:\n  scrawl "shapes on its own"\n' + END +
              'to area of, given s (a square), returning a number:\n  return power of (the side of s, 2)\n' + END +
              'to check, given s (a square):\n  if the side of s falls below 0: scrawl item 5 of a list of (1)\n' + END)
    helpers = 'use: shapes.stella\nto shout, given words (text):\n  scrawl upper case of words plus "!"\n' + END
    out = both('use: shapes.stella\nuse: helpers.stella\ngenesis:\n  set s to conjure a square\n  set the side of s to 3\n'
               '  scrawl area of s\n  shout with "hi"\n  check with s\n  set the side of s to -1\n  check with s\n' + END,
               others={"shapes.stella": shapes, "helpers.stella": helpers})
    assert out.stdout == "9\nHI!\n", repr(out.stdout)
    assert out.stderr == "shapes.stella line 13: there is no item 5 in a list of 1 item. Items are counted from 1.\n", repr(out.stderr)
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "bad.stella").write_text("to oops:\n  scrawl nothing here\n" + END, encoding="utf-8")
        (Path(d) / "main.stella").write_text("use: bad.stella\ngenesis:\n  oops\n" + END, encoding="utf-8")
        try:
            translate.read_script(Path(d) / "main.stella")
            raise AssertionError("expected a script error")
        except translate.ScriptError as e:
            assert translate.where(e.line) == "bad.stella line 2", translate.where(e.line)
    assert perr('use: missing.stella\ngenesis:\n  cease\n' + END)[1] == "There is no script called 'missing.stella' next to probe.stella."

    # Sound plays the same both ways.
    import io
    import wave
    silent = io.BytesIO()
    with wave.open(silent, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"\0\0" * 800)
    out = both('use: sound\ngenesis:\n  play the sound and wait with "quiet.wav"\n  play the sound with "quiet.wav"\n'
               '  play the sound with "quiet.wav"\n  play the sound again and again with "quiet.wav"\n'
               '  stop the sound\n  scrawl "played"\n  play the sound with "not a sound.wav"\n  play the sound with "nope.wav"\n' + END,
               others={"quiet.wav": silent.getvalue(), "not a sound.wav": b"hello"})
    assert out.stdout == "played\n", repr(out.stdout)
    assert out.stderr == "Line 9: I couldn't play \"not a sound.wav\" (it must be a .wav or .mp3 file).\n", repr(out.stderr)

    # Random items come from the list; an empty list is a plain error.
    out = both('genesis:\n  set xs to a list of (4, 4, 4)\n  scrawl a random item of xs, random item of a list of ("z")\n'
               '  scrawl random item of a list of numbers\n' + END)
    assert out.stdout == "4z\n", repr(out.stdout)
    assert out.stderr == "Line 4: the list is empty, so I can't pick a random item.\n", repr(out.stderr)

    # A command can call itself.
    out = both('genesis:\n  scrawl factorial of 10, " ", factorial of 20\n' + END +
               'to factorial of, given n (a number), returning a number:\n  if n is at most 1: return 1\n'
               '  return n times factorial of (n minus 1)\n' + END)
    assert out.stdout == "3628800 2432902008176640000\n", repr(out.stdout)

    # Lists, kinds, returning, files, errors.
    if True:
        ran = both('a pet has:\n  name (text)\n  ages (a list of numbers)\n' + END +
                          'genesis:\n  set p to conjure a pet\n  set the name of p to "Rex"\n  add 3 to the ages of p\n  add 4 to the ages of p\n'
                          '  scrawl p\n  scrawl total of the ages of p, " ", item 2 of the ages of p, " ", the size of the ages of p\n'
                          '  for each n from 1 to 3: add n times 10 to the ages of p\n  remove item 1 from the ages of p\n  scrawl the ages of p\n'
                          '  scrawl the ages of p contains 20, " ", "hello" contains "ell"\n'
                          '  inscribe "" into file "t.txt"\n  add "one" to file "t.txt"\n  add "two 2" to file "t.txt"\n  set got to lines of file "t.txt"\n'
                          '  scrawl got, " | ", the size of got, " | ", the words of item 2 of got, " | ", file "t.txt" exists, " ", file "nope.txt" exists\n'
                          '  scrawl (item 2 of the words of item 2 of got) as a number plus 1\n'
                          '  scrawl item 9 of the ages of p\n' + END +
                          'to total of, given xs (a list of numbers), returning a number:\n  set sum to 0\n'
                          '  for each x in xs: set sum to sum plus x\n  return sum\n' + END)
        assert ran.stdout == ("a pet (name: Rex, ages: 3, 4)\n7 4 2\n4, 10, 20, 30\nyes yes\n"
                              "one, two 2 | 2 | two, 2 | yes no\n3\n"), repr(ran.stdout)
        assert ran.stderr == "Line 22: there is no item 9 in a list of 4 items. Items are counted from 1.\n", repr(ran.stderr)
        assert ran.returncode == 1

    # Grammar: both forms mean the same.
    out = both('a notice has:\n  id (a number)\n  title (text)\n' + END +
               'to tell, use:\n  the title (text)\n  a count (a number)\n\n  conjure a notice as new notification\n'
               '  set the title of new notification to title\n  add count to the id of new notification\n'
               '  set kept notifications to a list containing new notification\n  scrawl the size of kept notifications, " ", kept notifications\n' + END +
               'to twice, returning a number, using:\n  x (a number)\n  return x times 2\n' + END +
               'genesis:\n  tell with "hi", 4\n  set count to 1\n  add 2 to count\n  add 5 to the count\n  scrawl count\n'
               '  set xs to a list containing (1, 2)\n  add twice with 3 to the item 2 of xs\n  scrawl xs\n' + END).stdout
    assert out == "1 a notice (id: 4, title: hi)\n8\n1, 8\n", repr(out)
    assert perr('genesis:\n  set xs to a list of (1, 2)\n  scrawl size of xs\n' + END)[1] == \
        "Write 'the size of', not 'size of': grammar is needed here for people reading it (the computer skips it)."
    assert perr('a pet has:\n  name (text)\n' + END + 'genesis:\n  conjure a pet as p\n  scrawl name of p\n' + END)[1].startswith("Write 'the name of'")
    assert perr('a pet has:\n  name (text)\n' + END + 'genesis:\n  conjure pet as p\n' + END)[1].startswith("Write 'conjure a pet' (or 'an')")
    assert perr('genesis:\n  set xs to list containing 1\n' + END)[1].startswith("Write 'a list containing ...'")
    assert perr('an apple has:\n  name (text)\n' + END + 'genesis:\n  conjure a apple as p\n' + END)[1] == "Write 'an apple', not 'a apple'."
    assert perr('genesis:\n  set a to 1\n' + END)[1].startswith("'a' is grammar, which the computer skips, so it can't be a name.")
    assert perr('to tell, use:\n  scrawl 1\n' + END + 'genesis:\n  tell\n' + END)[1].startswith("Under 'use:', list each input")
    assert perr('to tell, use:\n  x (a number)\n  scrawl x\n  y (text)\n' + END + 'genesis:\n  tell with 1\n' + END)[1].startswith(
        "'y (text)' looks like an input, but it is among the instructions.")
    assert perr('to tell, use:\n  x (a colour)\n  scrawl x\n' + END + 'genesis:\n  tell with 1\n' + END)[1].startswith("'a colour' isn't a kind")
    assert perr('genesis:\n  scrawl body\n' + END)[1] == \
        "I don't know 'body'. If it is a name, set it before this line (like 'set body to 0') or list it as an input of the command."
    assert perr('genesis:\n  set word to "x"\n  add 1 to word\n' + END)[1] == "'add ... to' needs a list or a number, but this is text."
    if node:
        print(f"(made for the web too: {web_runs[0]} programs; {len(web_skipped)} use words the web doesn't have yet)")
        if os.environ.get("STELLANOVA_TEST_WASM"):
            print(f"(made into WebAssembly too: {wasm_runs[0]} programs; {len(wasm_skipped)} use words it doesn't have yet)")
            if os.environ.get("STELLANOVA_SHOW_SKIPPED"):
                print("\n".join(sorted(set(wasm_skipped))))
        if os.environ.get("STELLANOVA_SHOW_SKIPPED"):
            print("\n".join(sorted(set(web_skipped))))


def plain_word_checks():
    """Mistakes use plain words."""
    import re
    jargon = re.compile(r"\b(std|nullptr|NoneType|None|null|undefined|NaN|int|float|double|bool|string|str|vector|dict|tuple|array|"
                        r"exception|errno|Traceback|pointer|segfault|boolean|integer|variable|argument|parameter|index|syntax|"
                        r"token|parse|runtime|struct|class|object|method|type)\b")
    files = [HERE / "stellanova.py", HERE / "machine.py", *(HERE / "libraries").glob("*.words"), *(HERE / "runtime").glob("*.[hcj]*")]
    found = []
    for path in files:
        for n, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            for m in re.finditer(r"(?:ScriptError|RunError|fail)\((?:[^,()]+,\s*)?(f?[\"'`].*)", line):
                said = "".join(re.findall(r"[\"'`]([^\"'`]*)[\"'`]", re.sub(r"\$?\{[^}]*\}", "", m.group(1))))
                if jargon.search(said) and "+ str(" not in m.group(1) and "std::to_string" not in m.group(1):
                    found.append(f"{path.name}:{n}: {said}")
    assert not found, "programmer words in mistake messages:\n" + "\n".join(found)


def main():
    plain_word_checks()
    for path in sorted(translate.LOGIC.glob("*.stella")):
        translate.translate(path)

    cpp = run("settings:\n  limit: 30 degrees\n\nto check, given goal (a place):\n  set gap to flat (goal minus centre of mass)\n"
              '  if the size of gap exceeds limit: cease\n  move turn rate toward 10 by at most 2 times frame time\n' + END)
    assert "constexpr double limit = 30.0;" in cpp, cpp
    assert "void ACreatureBody::Check(const FVector& goal)" in cpp, cpp
    assert "if ((gap).Size() > Stellanova_probe::limit)" in cpp, cpp
    assert "TurnRateDegS = FMath::Clamp(10.0, TurnRateDegS - " in cpp, cpp

    assert error("to check:\n  set turn rate to walk sped\n" + END) == (4, "I don't know 'walk sped'. Did you mean 'walk speed'?")
    assert error("to check:\n  set turn rate to fallen\n" + END) == (4, "'turn rate' holds a number, not yes or no.")
    assert error("to check:\n  set fallen to yes\n" + END) == (4, "'fallen' can't be changed by a script.")
    assert error('to check:\n  if turn rate: cease\n' + END)[1].startswith("'if' needs something that is yes or no")
    assert error("to check:\n  jump\n" + END)[1].startswith("I don't know how to start a line with 'jump'")
    closed = run('to check:\n  set turn rate to 1\n\nAnd the universe said I love you.\n\nto other:\n  cease\n' + END)
    assert "::Check()" in closed and "::Other()" in closed, closed
    assert error(END)[1].startswith("'and the universe said i love you' closes a command")
    assert error('to check:\n  cease\n')[1].startswith("The command 'to check' must end with the line 'and the universe said i love you'")
    assert error('to check:\n  cease\nto other:\n  cease\n' + END)[0] == 5
    called = run("to check:\n  set turn rate to half of 10\n  calm down with 2\n" + END +
                 "to half of, given x (a number), returning a number:\n  return x divided by 2\n" + END +
                 "to calm down, given by (a number):\n  set walk speed to walk speed minus by\n" + END)
    assert "TurnRateDegS = HalfOf(10.0);" in called and "\tCalmDown(2.0);" in called, called
    assert "//   double HalfOf(double x);" in called, called
    # Try-it mode.
    typed = iter(['set name to "Sam"', 'scrawl "Hi " plus name', "5 plus 3 times 2", "repeat 2 times:", "scrawl name", "",
                  "scrawl nme", "scrawl item 3 of a list of (1)", "use: maths", "round 2.6", "break free", "5 exceeds 3", "scrawl the size of today", "bye"])
    import contextlib
    import io
    screen = io.StringIO()
    with contextlib.redirect_stdout(screen):
        translate.try_it(read=lambda prompt: next(typed))
    shown = screen.getvalue().rstrip("\n").split("\n")[6:]
    assert shown == ["Hi Sam", "11", "Sam", "Sam", "I don't know 'nme'. Did you mean 'name'?",
                         "There is no item 3 in a list of 1 item. Items are counted from 1.",
                         "(the words of 'maths' can be used now)", "3",
                         "'break free' only works inside 'repeat', 'as long as' or 'for each'.", "yes", "10"], shown
    translate.THINGS = {}
    tutorial_checks()
    program_checks()
    built_run_checks()
    plugin_checks()
    course_checks()
    print("stellanova.py self-check passed")


def course_checks():
    """The course's lessons."""
    import subprocess
    said = {"01 hello": "Hello!\n", "02 names": "This is Sam.\nSam has 3 coins.\n", "03 choosing": "It's hot.\n",
            "05 lists": "I need 3 things: milk, eggs, bread\n- milk\n- eggs\n- bread\nDon't drop the eggs!\n",
            "07 things": "a pet (name: Rex, age: 3)\nRex is 3 years old.\n",
            "08 mistakes": "Grounded: not enough fuel (only 3)\nScore: 0\n"}
    go = lambda *a: subprocess.run([sys.executable, str(HERE / "stellanova.py"), *a], capture_output=True, text=True, encoding="utf-8")
    lessons = sorted((HERE / "course").glob("*.stella"))
    assert len(lessons) == 10, lessons
    for lesson in lessons:
        looked = go("check", str(lesson))
        if lesson.stem == "06 commands":
            assert "I don't know 'triple'" in looked.stdout, looked.stdout
        else:
            assert looked.returncode == 0, looked.stdout
        if lesson.stem in said:
            ran = go("run", str(lesson))
            assert ran.stdout == said[lesson.stem], (lesson.stem, ran.stdout, ran.stderr)
    with tempfile.TemporaryDirectory() as d:  # lesson 6, done
        done = Path(d) / "six.stella"
        done.write_text((HERE / "course" / "06 commands.stella").read_text(encoding="utf-8") +
                        "\nto triple, given x (a number), returning a number:\n  return x times 3\n" + END, encoding="utf-8")
        tested = go("test", str(done))
        assert tested.returncode == 0 and "1 passed" in tested.stdout, tested.stdout


def plugin_checks():
    """'stellanova plugin' (engines/host/host.cpp is a tiny engine)."""
    import subprocess
    clang = shutil.which("clang++") or r"C:\Program Files\LLVM\bin\clang++.exe"
    if not Path(clang).exists():
        return
    with tempfile.TemporaryDirectory() as d:
        script = Path(d) / "game.stella"
        script.write_text("use: engine\n\nto begin:\n  scrawl \"coin \", me, \" \", object name of me, \" at \", place of me\n" + END +
                          "\nto every frame, given seconds (a number):\n  turn the object with me, 90 times seconds\n"
                          "  move the object with me, 0 horizontal (frame time) vertical 0 depth\n" + END +
                          "\nto touched, given other (a number):\n  if object name of other is \"Player\":\n"
                          "    copy the object with me, place of me plus 0 horizontal 2 vertical 0 depth\n    remove the object me\n"
                          "  scrawl item 3 of a list of (1)\n" + END +
                          "\nto doubled, given x (a number), returning a number:\n  return x times 2\n" + END, encoding="utf-8")
        made = subprocess.run([sys.executable, str(HERE / "stellanova.py"), "plugin", str(script)], capture_output=True, text=True, cwd=d)
        assert made.returncode == 0, made.stdout + made.stderr
        lib = "game.so" if sys.platform.startswith("linux") else "game.dll"
        assert sorted(p.name for p in Path(d).iterdir()) == sorted(["game.stella", lib]), list(Path(d).iterdir())
        host = Path(d) / "host.exe"
        built = subprocess.run([clang, "-O1", str(HERE / "engines" / "host" / "host.cpp"), "-o", str(host)] +
                               (["-ldl"] if sys.platform.startswith("linux") else []), capture_output=True, text=True)
        assert built.returncode == 0, built.stderr
        ran = subprocess.run([str(host), str(Path(d) / lib)], capture_output=True, text=True, cwd=d)
        assert ran.stdout.splitlines() == [
            "start 0", "  [name 5]", "  [place 5]", "coin 5 Coin at 1 horizontal 2 vertical 3 depth", "begin 0",
            "  [turn by 5 45]", "  [frame time]", "  [move 5 0 0.5 0]", "every frame 0",
            "  [name 7]", "  [place 5]", "  [copy 5 1 4 3]", "  [remove 5]",
            "problem: Line 16: there is no item 3 in a list of 1 item. Items are counted from 1.", "touched 2",
            "doubled 0 1", "missing 1"], ran.stdout
        alone = subprocess.run([sys.executable, str(HERE / "stellanova.py"), "run", str(script)], capture_output=True, text=True, cwd=d)
        assert alone.returncode == 1 and "stellanova plugin game.stella" in alone.stdout, alone.stdout


def built_run_checks():
    """'stellanova x.stella' runs a kept built copy."""
    import subprocess
    if not shutil.which("clang++") and not Path(r"C:\Program Files\LLVM\bin\clang++.exe").exists():
        return
    env = {k: v for k, v in os.environ.items() if k != "STELLANOVA_DIRECT"}
    with tempfile.TemporaryDirectory() as d:
        script = Path(d) / "probe.stella"
        script.write_text('genesis:\n  scrawl "hi ", the words given\n  set x to item 5 of a list of (1)\n' + END, encoding="utf-8")
        go = lambda: subprocess.run([sys.executable, str(HERE / "stellanova.py"), "run", str(script), "a", "b"],
                                    capture_output=True, text=True, encoding="utf-8", cwd=d, env=env)
        for _ in range(2):  # built, then the kept copy
            done = go()
            assert (done.stdout, done.returncode) == ("hi a, b\n", 1) and "item 5" in done.stderr, (done.stdout, done.stderr, done.returncode)
        script.write_text('genesis:\n  scrawl "hi" plus\n' + END, encoding="utf-8")  # a mistake: said as before
        done = go()
        assert done.returncode == 1 and "line 2" in done.stdout, (done.stdout, done.stderr)


if __name__ == "__main__":
    main()
