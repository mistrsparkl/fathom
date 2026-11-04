"""Self-check for imagination.py. Run: py -3 test_imagination.py"""
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import imagination as translate
translate.LOGIC = Path(__file__).resolve().parent / "examples"


END = "and the universe said i love you\n"


def run(body, part_of="this is part of: creature body\n\n"):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "probe.imagine"
        p.write_text(part_of + body, encoding="utf-8")
        return translate.translate(p)


def error(body, part_of="this is part of: creature body\n\n"):
    try:
        run(body, part_of)
    except translate.ScriptError as e:
        return e.line, e.message
    raise AssertionError("expected a script error")


def tutorial_checks():
    """Every program in TUTORIAL.md has no mistakes, and the ones with an output block print exactly that."""
    import re
    import subprocess
    doc = (HERE / "TUTORIAL.md").read_text(encoding="utf-8")
    blocks = re.findall(r"```(\w*)\n(.*?)```", doc, re.S)
    ran = 0
    for k, (fence, body) in enumerate(blocks):
        if CLOSING_LINE not in body:
            continue
        with tempfile.TemporaryDirectory() as d:
            script = Path(d) / "tutorial.imagine"
            script.write_text(body, encoding="utf-8")
            translate.LOGIC = Path(d)
            translate.read_script(script)  # raises on any mistake
            if fence == "imagination":
                assert blocks[k + 1][0] == "output", f"a program in TUTORIAL.md has no output block after it:\n{body}"
                out = subprocess.run([sys.executable, str(HERE / "imagination.py"), "run", str(script)],
                                     capture_output=True, text=True, encoding="utf-8", cwd=d)
                assert out.stdout == blocks[k + 1][1] and not out.stderr, f"TUTORIAL.md:\n{body}\nprinted:\n{out.stdout}{out.stderr}"
                ran += 1
    assert ran >= 8, ran
    translate.LOGIC = HERE / "examples"


CLOSING_LINE = "and the universe said i love you"


def program_checks():
    """Programs of their own: text, say, ask, loops, calling commands."""
    prog = lambda body: run(body, "")
    perr = lambda body: error(body, "")
    cpp = prog('to start:\n  ask "Name? " into name\n  repeat 3 times:\n    greet with name, 2\nand the universe said i love you\n\n'
               'to greet, given who (text) and times (a number):\n  say "Hi " plus who, "! x", times\n' + END)
    assert "void Greet(const std::string& who, double times);" in cpp, cpp
    assert 'name = imagine::ask_text(std::string("Name? "));' in cpp, cpp
    assert "Greet(name, 2.0);" in cpp, cpp
    assert "int main()" in cpp, cpp
    assert perr("to begin:\n  stop\n" + END)[1].startswith("A program needs a 'to start:' command")
    assert perr("to start:\n  greet with 1\n" + END)[1].startswith("I don't know how to start a line with 'greet'")
    assert perr("to start:\n  hi with 1\n" + END + "to hi, given who (text):\n  stop\n" + END) == (2, "Input 1 of 'hi' must be text, not a number.")
    assert perr("to start:\n  hi\n" + END + "to hi, given who (text):\n  stop\n" + END) == (2, "'hi' needs 1 input, but this gives it 0.")
    assert perr('to start:\n  say "oops\n' + END)[1].startswith("This text has no closing")
    assert perr('to start:\n  set x to "a" minus 1\n' + END)[1] == "I can't subtract a number from text."
    assert perr('to start:\n  while 5:\n    stop\n' + END)[1].startswith("'while' needs something that is yes or no")
    assert perr('to start:\n  repeat "x" times:\n    stop\n' + END)[1].startswith("'repeat' needs a number of times")

    # Giving back, lists, kinds of things, files: the plain errors.
    assert perr("to start:\n  stop\n" + END + "to twice, given x (a number), giving back a number:\n  give back \"no\"\n" + END) \
        == (5, "This command gives back a number, not text.")
    assert perr("to start:\n  give back 1\n" + END)[1].startswith("'give back' only works in a command that says")
    assert perr("to start:\n  stop\n" + END + "to two, giving back a number:\n  stop\n" + END)[1].startswith("This command gives back a number, so leave it")
    assert perr("to start:\n  set x to hello\n" + END + "to hello:\n  stop\n" + END)[1] == "'hello' doesn't give back anything, so it can't be used as a value."
    assert perr("to start:\n  set s to a list of numbers\n  add \"x\" to s\n" + END)[1] == "This list holds numbers, so I can't add text to it."
    assert perr("to start:\n  set s to a list of (1, \"a\")\n" + END)[1] == "A list holds one kind of thing, but this mixes a number and text."
    assert perr("to start:\n  for each n in 5:\n    stop\n" + END)[1] == "'for each ... in' needs a list, but this is a number."
    assert perr("a pet has:\n  name (text)\n" + END + "to start:\n  set p to a new pet\n  say age of p\n" + END)[1].startswith("I don't know 'age")
    assert perr("a pet has:\n  name (text)\n" + END + "to start:\n  set p to a new dog\n" + END)[1].startswith("There is no kind of thing called 'dog'")
    assert perr("a pet has:\n  best friend (a pet)\n" + END + "to start:\n  stop\n" + END)[1].startswith("A pet can't hold a whole pet")
    assert perr("a pet has:\n  name (text)\n\nto start:\n  stop\n" + END)[1].startswith("The description of 'pet' must end with")
    assert perr("to start:\n  set n to 5 as a number\n" + END)[1] == "'as a number' turns text into a number, but this is a number."

    assert perr("to start:\n  otherwise: stop\n" + END)[1] == "'otherwise' needs an 'if' line just above it, at the same indent."
    assert perr("use: nothing here\nto start:\n  stop\n" + END)[1].startswith("There is no library called 'nothing here'. Libraries: computer, maths, sound, time, web, window")

    # Run real programs both ways: directly, and built with the C++ compiler (if there is one).
    # Both must print exactly the same, so the two halves of every piece of the language agree.
    import subprocess
    compiler = translate.find_vcvars()
    if not compiler:
        print("(only running directly: no C++ compiler found)")

    def both(source, typed="", others=None):
        with tempfile.TemporaryDirectory() as d:
            script = Path(d) / "probe.imagine"
            script.write_text(source, encoding="utf-8")
            for name, other in (others or {}).items():
                if isinstance(other, bytes):
                    (Path(d) / name).write_bytes(other)
                else:
                    (Path(d) / name).write_text(other, encoding="utf-8")
            direct = subprocess.run([sys.executable, str(HERE / "imagination.py"), "run", str(script)],
                                    input=typed, capture_output=True, text=True, encoding="utf-8", cwd=d)
            if compiler:
                exe = Path(d) / "probe.exe"
                problem = translate.build(script, exe)
                assert problem is None, problem
                built = subprocess.run([str(exe)], input=typed, capture_output=True, text=True, encoding="utf-8", cwd=d)
                assert (built.stdout, built.stderr, built.returncode) == (direct.stdout, direct.stderr, direct.returncode), \
                    f"built: {built.stdout!r} {built.stderr!r} {built.returncode}\ndirect: {direct.stdout!r} {direct.stderr!r} {direct.returncode}"
            return direct

    out = both('to start:\n  ask "Name? " into name\n  ask "Age? " into age (a number)\n'
               '  repeat 2 times: say "Hello, " plus name plus "!"\n'
               '  say "Next year you are ", age plus 1, ". Grown up: ", age is at least 18\n' + END, "Sam\nlots\n20.5\n").stdout
    assert out == "Name? Age? Please type a number.\nAge? Hello, Sam!\nHello, Sam!\nNext year you are 21.5. Grown up: yes\n", repr(out)

    out = both('to start:\n  ask "Again? " into again (yes or no)\n  say again\n  ask "Sure? " into again\n  say not again\n' + END,
               "maybe\n YES \nn\n").stdout
    assert out == "Again? Please type yes or no.\nAgain? yes\nSure? yes\n", repr(out)

    # try: / if that went wrong: catches problems the same both ways, even from inside commands and libraries.
    out = both('use: web\nto start:\n  for each n from 1 to 3:\n    try:\n      say item n of a list of (10, 20)\n'
               '    if that went wrong:\n      say "Oops: ", the problem\n  try:\n    set x to contents of file "nope.txt"\n'
               '    say "not here"\n  if that went wrong:\n    say the problem\n  try:\n    risky\n  if that went wrong:\n'
               '    say "caught ", the problem\n  try:\n    say web page "http://localhost:1/"\n  if that went wrong:\n'
               '    say "no web"\n  say item 7 of a list of (1)\n' + END +
               'to risky:\n  say "before"\n  say letter 5 of "abc"\n  say "after"\n' + END)
    assert out.stdout == ("10\n20\nOops: there is no item 3 in a list of 2 items. Items are counted from 1.\n"
                          'there is no file called "nope.txt" (or it can\'t be opened).\n'
                          "before\ncaught there is no letter 5 in text of 3 letters.\nno web\n"), repr(out.stdout)
    assert out.stderr == "Line 21: there is no item 7 in a list of 1 item. Items are counted from 1.\n", repr(out.stderr)
    assert perr("to start:\n  try:\n    stop\n  say 1\n" + END)[1].startswith("'try:' needs an 'if that went wrong:' line")
    assert perr("to start:\n  if that went wrong:\n    stop\n" + END)[1].startswith("'if that went wrong:' goes right after")

    out = both('to start:\n  say (2 divided by 3) rounded to 2 places, " ", 2.675 rounded to 2 places, " ", 1234.5 rounded to 0 places,'
               ' " ", -1.25 rounded to 1 place\n  say 1 rounded to 1.5 places\n' + END)
    assert out.stdout == "0.67 2.68 1235 -1.3\n", repr(out.stdout)
    assert out.stderr == "Line 3: I can round to 0 to 15 places, not 1.5.\n", repr(out.stderr)

    # Places in programs.
    out = both('to start:\n  set p to a place at (3, 4, 12)\n  set q to a place at (1, 1, 1)\n'
               '  say p, " ", size of p, " ", p plus q, " ", p minus q times 2, " ", -q, " ", p divided by 2\n'
               '  set f to flat p\n  say f, " ", size of f, " ", direction of a flat place at (0, 5), " ", x of p plus z of p\n'
               '  set y of p to 100\n  say p, " ", a place at (1, 2, 0) divided by 0\n  set route to a list of (p, q)\n'
               '  say route\n' + END)
    assert out.stdout == ("(3, 4, 12) 13 (4, 5, 13) (1, 2, 10) (-1, -1, -1) (1.5, 2, 6)\n(3, 4) 5 90 15\n"
                          "(3, 100, 12) (infinity, infinity, not a number)\n(3, 100, 12), (1, 1, 1)\n"), repr(out.stdout)
    assert perr("to start:\n  say a place at (1, 2)\n" + END)[1] == "A place has 3 numbers, like a place at (1, 2, 3)."

    # Numbers and text shown the same way both ways; if / otherwise chains; stop and give back inside loops.
    out = both('to start:\n  say 1 divided by 3, " ", 10 divided by 4, " ", 2 times 0.1, " ", 1000000 times 1000000, " ", -0 times 1\n'
               '  say size of "héllo", " ", "a" plus 1 plus yes, " ", "x" is "x", " ", 3 is not 3\n'
               '  for each n from 1 to 4:\n    if n is 1: say "one"\n    otherwise if n is 2:\n      say "two"\n    otherwise: say "many"\n'
               '  say first big in a list of (1, 5, 9, 2)\n  count down with 3\n' + END +
               'to first big in, given xs (a list of numbers), giving back a number:\n'
               '  for each x in xs:\n    if x is more than 4: give back x\n  give back 0\n' + END +
               'to count down, given from (a number):\n  set left to from\n  while yes:\n    say left\n'
               '    set left to left minus 1\n    if left is 0: stop\n' + END).stdout
    assert out == ("0.333333333333333 2.5 0.2 1000000000000 0\n5 a1yes yes no\none\ntwo\nmany\nmany\n5\n3\n2\n1\n"), repr(out)

    # Lists of things are copied when stored, the same both ways.
    out = both('a box has:\n  items (a list of numbers)\n' + END +
               'to start:\n  set a to a new box\n  add 1 to items of a\n  set b to a\n  add 2 to items of b\n'
               '  set boxes to a list of (a, b)\n  add 3 to items of item 1 of boxes\n  say a, " ", b, " ", boxes\n'
               '  say a is item 1 of boxes, " ", b is item 2 of boxes\n' + END).stdout
    assert out == ("a box (items: 1) a box (items: 1, 2) a box (items: 1, 3), a box (items: 1, 2)\nno yes\n"), repr(out)

    # Text and list tools; leaving loops early.
    out = both('to start:\n  set s to "Héllo wörld, hello"\n'
               '  say upper case of s, " | ", lower case of "ABC é", " | ", letter 2 of s, " | ", letters 7 to 11 of s\n'
               '  say position of "llo" in s, " ", position of "zz" in s, " | ", replace "llo" with "LP" in s\n'
               '  set parts to s split by ", "\n  say size of parts, " ", item 2 of parts, " | ", join parts with "+"\n'
               '  say sorted a list of (3, 1, 2), " | ", reversed a list of ("a", "b"), " | ", last item of parts, " | ", letters 3 to 2 of "abc", "."\n'
               '  for each n from 1 to 10:\n    if n is 2: skip to the next one\n    if n is 5: stop the loop\n    say n\n'
               '  repeat 3 times:\n    while yes: stop the loop\n    say "r"\n'
               '  say letter 9 of "abc"\n' + END)
    assert out.stdout == ("HéLLO WöRLD, HELLO | abc é | é | wörld\n3 0 | HéLP wörld, heLP\n"
                          "2 hello | Héllo wörld+hello\n1, 2, 3 | b, a | hello | .\n1\n3\n4\nr\nr\nr\n"), repr(out.stdout)
    assert out.stderr == "Line 15: there is no letter 9 in text of 3 letters.\n", repr(out.stderr)
    assert perr("to start:\n  stop the loop\n" + END)[1] == "'stop the loop' only works inside 'repeat', 'while' or 'for each'."

    # Tables.
    out = both('to start:\n  set ages to a table of numbers\n  set entry "Rex" of ages to 3\n  set entry "Ann" of ages to 40\n'
               '  set entry "Rex" of ages to entry "Rex" of ages plus 1\n  say ages, " | ", size of ages, " | ", keys of ages\n'
               '  say ages contains "Ann", " ", ages contains "Bob"\n  remove entry "Ann" from ages\n  say ages\n'
               '  set pets to a table of lists of text\n  set entry "Rex" of pets to a list of text\n'
               '  add "sit" to entry "Rex" of pets\n  say pets\n  for each name in keys of pets: say name\n'
               '  say entry "Bob" of ages\n' + END)
    assert out.stdout == "Ann: 40, Rex: 4 | 2 | Ann, Rex\nyes no\nRex: 4\nRex: sit\nRex\n", repr(out.stdout)
    assert out.stderr == 'Line 15: there is no entry "Bob" in the table.\n', repr(out.stderr)

    # Libraries.
    out = both('use: maths\nuse: time\nto start:\n  say round (sine of 30 times 1000), " ", power of (2, 10), " ", remainder of (17, 5)\n'
               '  say round 2.5, " ", round down -2.5, " ", round up 2.1, " ", round (pi times 100)\n'
               '  wait 0.01 seconds\n  say seconds since start is more than 0, " ", year now is more than 2000\n' + END).stdout
    assert out == "500 1024 2\n3 -3 3 314\nyes yes\n", repr(out)

    # A window: opens, draws, shows frames and closes the same both ways (it flashes up for a moment).
    out = both('use: window\nto start:\n  open a window with "Test ✓", 200, 100\n'
               '  say the window is open, " ", mouse held, " ", key held "space"\n  repeat 3 times:\n'
               '    say key pressed "space", " ", mouse clicked\n'
               '    clear the window with "black"\n    draw a box with 10, 10, 50, 20, "#ff8800"\n'
               '    draw a circle with 100, 50, 20, "blue"\n    draw a line with 0, 0, 200, 100, "white"\n'
               '    draw words with "héllo", 120, 10, "yellow"\n    show the frame\n  close the window\n'
               '  say the window is open\n  draw a circle with 1, 1, 1, "red"\n  say "ok"\n  draw a circle with 1, 1, 1, "reddish"\n' + END)
    assert out.stdout == "yes no no\nno no\nno no\nno no\nno\nok\n", repr(out.stdout)
    assert out.stderr == 'Line 17: I don\'t know the colour "reddish". Use a name like "red" or a code like "#ff8800".\n', repr(out.stderr)
    assert both('use: window\nto start:\n  show the frame\n' + END).stderr.startswith("Line 3: there is no window yet.")

    # Pictures: a tiny .png made here is read and drawn the same both ways.
    import struct
    import zlib

    def png(width, height):
        def chunk(kind, data):
            return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
        rows = b"".join(b"\0" + b"\xff\x00\x00" * width for _ in range(height))
        return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))
    out = both('use: window\nto start:\n  say width of picture "red.png", " ", height of picture "red.png"\n'
               '  open a window with "Pictures", 100, 100\n  draw the picture with "red.png", 10, 10\n  show the frame\n'
               '  close the window\n  say width of picture "red.png"\n  say width of picture "none.png"\n' + END,
               others={"red.png": png(7, 3)})
    assert out.stdout == "7 3\n7\n", repr(out.stdout)
    assert out.stderr == 'Line 9: there is no picture called "none.png".\n', repr(out.stderr)

    # The web library, without needing the internet: a page that can't be reached fails the same both ways.
    out = both('use: web\nto start:\n  say web page "http://localhost:1/"\n' + END)
    assert out.stderr == 'Line 3: I couldn\'t get the web page "http://localhost:1/".\n', repr(out.stderr)

    # Programs made of several scripts: used scripts bring their kinds and commands (not their start),
    # are read once even when used twice, and errors name the script they are in.
    shapes = ('use: maths\nuse: helpers.imagine\na square has:\n  side (a number)\n' + END +
              'to start:\n  say "shapes on its own"\n' + END +
              'to area of, given s (a square), giving back a number:\n  give back power of (side of s, 2)\n' + END +
              'to check, given s (a square):\n  if side of s is less than 0: say item 5 of a list of (1)\n' + END)
    helpers = 'use: shapes.imagine\nto shout, given words (text):\n  say upper case of words plus "!"\n' + END
    out = both('use: shapes.imagine\nuse: helpers.imagine\nto start:\n  set s to a new square\n  set side of s to 3\n'
               '  say area of s\n  shout with "hi"\n  check with s\n  set side of s to -1\n  check with s\n' + END,
               others={"shapes.imagine": shapes, "helpers.imagine": helpers})
    assert out.stdout == "9\nHI!\n", repr(out.stdout)
    assert out.stderr == "shapes.imagine line 13: there is no item 5 in a list of 1 item. Items are counted from 1.\n", repr(out.stderr)
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "bad.imagine").write_text("to oops:\n  say nothing here\n" + END, encoding="utf-8")
        (Path(d) / "main.imagine").write_text("use: bad.imagine\nto start:\n  oops\n" + END, encoding="utf-8")
        try:
            translate.read_script(Path(d) / "main.imagine")
            raise AssertionError("expected a script error")
        except translate.ScriptError as e:
            assert translate.where(e.line) == "bad.imagine line 2", translate.where(e.line)
    assert perr("use: missing.imagine\nto start:\n  stop\n" + END)[1] == "There is no script called 'missing.imagine' next to probe.imagine."

    # Sound: a short silent .wav plays (and waits) the same both ways; a missing file is a plain error.
    import io
    import wave
    silent = io.BytesIO()
    with wave.open(silent, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"\0\0" * 800)
    out = both('use: sound\nto start:\n  play the sound and wait with "quiet.wav"\n  play the sound with "quiet.wav"\n'
               '  stop the sound\n  say "played"\n  play the sound with "nope.wav"\n' + END, others={"quiet.wav": silent.getvalue()})
    assert out.stdout == "played\n", repr(out.stdout)
    assert out.stderr == 'Line 7: there is no sound file called "nope.wav".\n', repr(out.stderr)

    # Random items come from the list; an empty list is a plain error.
    out = both('to start:\n  set xs to a list of (4, 4, 4)\n  say a random item of xs, random item of a list of ("z")\n'
               '  say random item of a list of numbers\n' + END)
    assert out.stdout == "4z\n", repr(out.stdout)
    assert out.stderr == "Line 4: the list is empty, so I can't pick a random item.\n", repr(out.stderr)

    # A command can call itself.
    out = both('to start:\n  say factorial of 10, " ", factorial of 20\n' + END +
               'to factorial of, given n (a number), giving back a number:\n  if n is at most 1: give back 1\n'
               '  give back n times factorial of (n minus 1)\n' + END)
    assert out.stdout == "3628800 2432902008176640000\n", repr(out.stdout)

    # Lists, kinds of things, giving back, files, and a plain error while running.
    if True:
        ran = both('a pet has:\n  name (text)\n  ages (a list of numbers)\n' + END +
                          'to start:\n  set p to a new pet\n  set name of p to "Rex"\n  add 3 to ages of p\n  add 4 to ages of p\n'
                          '  say p\n  say total of ages of p, " ", item 2 of ages of p, " ", size of ages of p\n'
                          '  for each n from 1 to 3: add n times 10 to ages of p\n  remove item 1 from ages of p\n  say ages of p\n'
                          '  say ages of p contains 20, " ", "hello" contains "ell"\n'
                          '  write "" to file "t.txt"\n  add "one" to file "t.txt"\n  add "two 2" to file "t.txt"\n  set got to lines of file "t.txt"\n'
                          '  say got, " | ", size of got, " | ", words of item 2 of got, " | ", file "t.txt" exists, " ", file "nope.txt" exists\n'
                          '  say (item 2 of words of item 2 of got) as a number plus 1\n'
                          '  say item 9 of ages of p\n' + END +
                          'to total of, given xs (a list of numbers), giving back a number:\n  set sum to 0\n'
                          '  for each x in xs: set sum to sum plus x\n  give back sum\n' + END)
        assert ran.stdout == ("a pet (name: Rex, ages: 3, 4)\n7 4 2\n4, 10, 20, 30\nyes yes\n"
                              "one, two 2 | 2 | two, 2 | yes no\n3\n"), repr(ran.stdout)
        assert ran.stderr == "Line 22: there is no item 9 in a list of 4 items. Items are counted from 1.\n", repr(ran.stderr)
        assert ran.returncode == 1


def main():
    for path in sorted(translate.LOGIC.glob("*.imagine")):
        translate.translate(path)

    cpp = run("settings:\n  limit: 30 degrees\n\nto check, given goal (a place):\n  set gap to flat (goal minus centre of mass)\n"
              "  if size of gap is more than limit: stop\n  move turn rate toward 10 by at most 2 times frame time\n" + END)
    assert "constexpr double limit = 30.0;" in cpp, cpp
    assert "void ATerranovaCreatureBody::Check(const FVector& goal)" in cpp, cpp
    assert "if ((gap).Size() > Imagine_probe::limit)" in cpp, cpp
    assert "TurnRateDegS = FMath::Clamp(10.0, TurnRateDegS - " in cpp, cpp

    assert error("to check:\n  set turn rate to walk sped\n" + END) == (4, "I don't know 'walk sped'. Did you mean 'walk speed'?")
    assert error("to check:\n  set turn rate to fallen\n" + END) == (4, "'turn rate' holds a number, not yes or no.")
    assert error("to check:\n  set fallen to yes\n" + END) == (4, "'fallen' can't be changed by a script.")
    assert error("to check:\n  if turn rate: stop\n" + END)[1].startswith("'if' needs something that is yes or no")
    assert error("to check:\n  jump\n" + END)[1].startswith("I don't know how to start a line with 'jump'")
    closed = run("to check:\n  set turn rate to 1\n\nAnd the universe said I love you.\n\nto other:\n  stop\n" + END)
    assert "::Check()" in closed and "::Other()" in closed, closed
    assert error(END)[1].startswith("'and the universe said i love you' closes a command")
    assert error("to check:\n  stop\n")[1].startswith("The command 'to check' must end with the line 'and the universe said i love you'")
    assert error("to check:\n  stop\nto other:\n  stop\n" + END)[0] == 5
    called = run("to check:\n  set turn rate to half of 10\n  calm down with 2\n" + END +
                 "to half of, given x (a number), giving back a number:\n  give back x divided by 2\n" + END +
                 "to calm down, given by (a number):\n  set walk speed to walk speed minus by\n" + END)
    assert "TurnRateDegS = HalfOf(10.0);" in called and "\tCalmDown(2.0);" in called, called
    assert "//   double HalfOf(double x);" in called, called
    # Try-it mode: each typed line is done straight away; names are kept; blocks end with an empty line.
    typed = iter(['set name to "Sam"', 'say "Hi " plus name', "5 plus 3 times 2", "repeat 2 times:", "say name", "",
                  "say nme", "say item 3 of a list of (1)", "use: maths", "round 2.6", "stop the loop", "bye"])
    import contextlib
    import io
    screen = io.StringIO()
    with contextlib.redirect_stdout(screen):
        translate.try_it(read=lambda prompt: next(typed))
    shown = screen.getvalue().rstrip("\n").split("\n")[6:]
    assert shown == ["Hi Sam", "11", "Sam", "Sam", "I don't know 'nme'. Did you mean 'name'?",
                         "There is no item 3 in a list of 1 item. Items are counted from 1.",
                         "(the words of 'maths' can be used now)", "3",
                         "'stop the loop' only works inside 'repeat', 'while' or 'for each'."], shown
    translate.THINGS = {}
    tutorial_checks()
    program_checks()
    print("imagination.py self-check passed")


if __name__ == "__main__":
    main()
