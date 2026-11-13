"""Self-check for stellanova.py. Run: py -3 test_stellanova.py"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import stellanova as translate
translate.LOGIC = Path(__file__).resolve().parent / "examples"


END = "and the universe said i love you\n"


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
    assert perr('use: nothing here\ngenesis:\n  cease\n' + END)[1].startswith("There is no library called 'nothing here'. Libraries: computer, folders, letters, maths, page, patterns, screen, server, sound, time, web, window")

    # Run real programs both ways: directly, and built into machine code (if LLVM is there).
    # Both must print exactly the same, so the two halves of every piece of the language agree.
    import subprocess
    try:
        compiler = None if os.environ.get("STELLANOVA_NO_BUILD") else translate.machine.find_clang()
    except RuntimeError:
        compiler = None
    if not compiler:
        print("(only running directly: no LLVM found)")
    node = shutil.which("node") if not os.environ.get("STELLANOVA_NO_WEB") else None
    web_skipped, web_runs = [], [0]

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
                assert problem is None, problem
                built = subprocess.run([str(exe)], input=typed, capture_output=True, text=True, encoding="utf-8", cwd=d)
                assert (built.stdout, built.stderr, built.returncode) == (direct.stdout, direct.stderr, direct.returncode), \
                    f"built: {built.stdout!r} {built.stderr!r} {built.returncode}\ndirect: {direct.stdout!r} {direct.stderr!r} {direct.returncode}"
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

    # try: / if that went wrong: catches problems the same both ways, even from inside commands and libraries.
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

    # List maths, and sorting things by one of their parts (ties keep their order).
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

    # save ... to file / load ... from file: every kind, written exactly the same both ways.
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
               '  for each bad in a list of ("[1, 2", "[1, true]", "[NaN]", "[01]", "{}", "  [ ]  x", "[1.]", "[" plus q plus "a" plus q plus "]"):\n'
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

    # Things with a birth get an existence; setting birth (of a thing, or on its own) moves existence there.
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

    # Commands for a kind of thing change the thing itself, even one inside a list.
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

    # Two things touch when their circles (existence and radius) overlap; a place uses the radius in reach.
    out = both('a ball has:\n  birth (a flat place)\n  radius (a number)\n' + END +
               'to near, for a ball, given other (a ball), returning a yes or no:\n  return existence touches other\n' + END +
               'genesis:\n  set c to conjure a ball\n  set b to conjure a ball\n  set the birth of c to 0 horizontal 0 vertical\n'
               '  set the birth of b to 25 horizontal 0 vertical\n  set the radius of c to 10\n  set the radius of b to 10\n'
               '  scrawl c touches b\n  set the radius of b to 15\n  scrawl c touches b\n  scrawl near with (c, b)\n'
               '  scrawl 0 horizontal 0 vertical touches b\n' + END)
    assert out.stdout == "no\nyes\nyes\nno\n", repr(out.stdout)
    assert perr("genesis:\n  scrawl 3 touches 4\n" + END)[1] == "'touches' needs a thing or a place, not a number."

    # Kinds of kinds: a dog has all of a pet's parts and does a pet's commands, unless it has its own version.
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
    # A dog can go where a pet goes (inputs, lists, names, return) as a pet: a copy with just a pet's parts.
    out = both('a pet has:\n  name (text)\n  age (a number)\nand the universe said i love you\n\na dog is a kind of pet that has:\n  tricks (a list of text)\nand the universe said i love you\n\na puppy is a kind of dog:\nand the universe said i love you\n\nto show, given p (a pet):\n  scrawl "pet: ", p\nand the universe said i love you\n\nto oldest, given pets (a list of pets), returning a pet:\n  set best to conjure a pet\n  for each p in pets:\n    if the age of p exceeds the age of best: set best to p\n  return best\nand the universe said i love you\n\nto adopt, given name (text), returning a pet:\n  set d to conjure a dog\n  set the name of d to name\n  set the age of d to 2\n  return d\nand the universe said i love you\n\ngenesis:\n  set d to conjure a dog\n  set the name of d to "Rex"\n  set the age of d to 5\n  add "sit" to the tricks of d\n  show d\n  set u to conjure a puppy\n  set the name of u to "Bit"\n  set the age of u to 1\n  set shelter to a list of pets\n  add d to shelter\n  add u to shelter\n  add adopt with "Jo" to shelter\n  scrawl shelter\n  scrawl oldest with shelter\n  set p to conjure a pet\n  set p to u\n  scrawl p\n  set item 1 of shelter to u\n  scrawl item 1 of shelter\n  scrawl d\nand the universe said i love you\n')
    assert out.stdout == 'pet: a pet (name: Rex, age: 5)\na pet (name: Rex, age: 5), a pet (name: Bit, age: 1), a pet (name: Jo, age: 2)\na pet (name: Rex, age: 5)\na pet (name: Bit, age: 1)\na pet (name: Bit, age: 1)\na dog (name: Rex, age: 5, tricks: sit)\n', repr(out.stdout)
    assert perr(kinds + 'genesis:\n  set d to conjure a dog\n  set d to conjure a pet\n' + END)[1] == "'d' holds a dog, not a pet."
    assert perr('a dog is a kind of pet:\n' + END + 'genesis:\n  cease\n' + END)[1] == \
        "Describe what a pet has above the dog, so a dog can be a kind of pet."
    assert perr(kinds + 'a fish is a kind of pet that has:\n  age (a number)\n' + END + 'genesis:\n  cease\n' + END)[1] == \
        "A fish already has a part called 'age' (every pet has one)."
    assert perr(kinds + 'to speak, for a cat, given loud (yes or no):\n  cease\n' + END + 'genesis:\n  cease\n' + END)[1] == \
        "Every version of 'speak' must take the same inputs and return the same kind."

    # Commands as values: kept in names, lists and parts, given to and given back by commands, done with 'invoke'.
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

    # freeing values: over 262144 values are made, so built programs free some while others (kept in lists, tables, things) must live on
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

    # a library's own C++ threads calling a command: each thread joins the collector the first time it runs machine code
    out = both('use: burst\n\nto label, given n (a number), returning text:\n  set parts to a list containing (n, n plus 1, n times 2)\n'
               '  return "item " plus the sum of parts\nand the universe said i love you\n\n'
               'genesis:\n  scrawl burst with (20000, the command label)\nand the universe said i love you\n',
               others={"burst.words": 'note: test: C++ threads of its own calling a command\n\ncode:\n  #include <thread>\n  namespace burst\n  {\n  \tinline double go(double count, std::function<std::string(double)> f)\n  \t{\n  \t\tstd::vector<std::thread> ts; std::vector<double> sizes(4);\n  \t\tfor (int k = 0; k < 4; k++) ts.emplace_back([&, k] { for (double n = 1; n <= count; n++) sizes[k] += static_cast<double>(f(n).size()); });\n  \t\tfor (auto& t : ts) t.join();\n  \t\treturn sizes[0] + sizes[1] + sizes[2] + sizes[3];\n  \t}\n  }\n\npython:\n  def burst_go(count, f):\n      return 4 * sum(len(f(float(n))) for n in range(1, int(count) + 1))\n\nto burst with, given count (a number) and f (a command given a number returning text), returning a number = burst::go({count}, {f})\n  runs: burst_go({count}, {f})\n'})
    assert out.stdout == "788904\n", repr(out.stdout)

    # meanwhile: commands going alongside the rest, each with its own copy of the names; a problem in one stops everything.
    out = both('to count up, given name (text) and delay (a number):\n  wait delay\n  inscribe name plus " done" into file name plus ".txt"\nand the universe said i love you\n\nto fail later:\n  wait 0.2 seconds\n  raise an error with "the helper broke"\nand the universe said i love you\n\ngenesis:\n  set started to seconds since the start\n  set names to a list of ("a", "b", "c")\n  for each who in names: meanwhile count up with who, 0.5\n  set names to a list of text\n  wait for the others\n  scrawl contents of file "a.txt", " ", contents of file "b.txt", " ", contents of file "c.txt"\n  scrawl seconds since the start minus started falls below 1.4\n  meanwhile count up with "d", 0.3\n  scrawl "main goes on"\n  meanwhile fail later\n  wait 1 seconds\n  scrawl "never"\nand the universe said i love you\n')
    assert (out.stdout, out.stderr) == ('a done b done c done\nyes\nmain goes on\n', 'Line 8: the helper broke\n'), repr((out.stdout, out.stderr))
    assert perr('genesis:\n  meanwhile 5\n' + END)[1] == "'meanwhile' starts a command going alongside the rest, like 'meanwhile count down with 10'."

    # The server library: a web server whose pages come from a command (with the computer and web libraries in the same program).
    out = both('to answer, given address (text), returning text:\n  if address is "/hello": return "Hello from Stellanova!"\n  return "You asked for " plus address\nand the universe said i love you\n\ngenesis:\n  meanwhile serve the web with (8765, the command answer)\n  wait 0.5\n  scrawl web page "http://127.0.0.1:8765/hello"\n  scrawl web page "http://127.0.0.1:8765/scores?top=3"\n  end the program with 0\nand the universe said i love you\n'.replace('genesis:\n', 'genesis:\n  scrawl the size of user name exceeds 0\n'))
    assert out.stdout == 'yes\nHello from Stellanova!\nYou asked for /scores?top=3\n', repr(out.stdout)
    # Files from a folder, what was sent with a request, and text inside addresses.
    out = both('to answer, given address (text), returning text:\n  if address begins with "/echo": return "got " plus the web message\n  if address is "/f": answer with the file "site/index.html"\n  return "page " plus web decoded (letters 2 to the size of address of address)\nand the universe said i love you\n\ngenesis:\n  make the folder "site"\n  inscribe "body {}" into file "site/look.css"\n  inscribe "<p>home</p>" into file "site/index.html"\n  meanwhile serve the web from the folder with (8766, "site", the command answer)\n  wait 0.5\n  scrawl web page "http://127.0.0.1:8766/look.css"\n  scrawl web page "http://127.0.0.1:8766/"\n  scrawl web page "http://127.0.0.1:8766/a%20b+c"\n  scrawl web page "http://127.0.0.1:8766/f"\n  scrawl send to the web page with ("http://127.0.0.1:8766/echo", "héllo there")\n  scrawl web encoded "a b/é", " ", web decoded (web encoded "a b/é")\n  end the program with 0\nand the universe said i love you\n')
    assert out.stdout == 'body {}\n<p>home</p>\npage a b c\n<p>home</p>\ngot héllo there\na%20b%2F%C3%A9 a b/é\n', repr(out.stdout)

    # Saved text: any value as JSON text, and back (for the web, or other programs).
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

    # changed by / kept by: a command done to every item of a list, or picking items.
    out = both('to double, given x (a number), returning a number:\n  return x times 2\nand the universe said i love you\n\nto big one, given x (a number), returning yes or no:\n  return x exceeds 3\nand the universe said i love you\n\nto shout, given word (text), returning text:\n  return upper case of word plus "!"\nand the universe said i love you\n\ngenesis:\n  set scores to a list of (1, 5, 2, 8)\n  scrawl scores changed by the command double\n  scrawl scores kept by the command big one\n  scrawl (scores kept by the command big one) changed by the command double\n  scrawl (the words of "hi there") changed by the command shout\n  scrawl the size of (a list of numbers kept by the command big one)\n  scrawl scores changed by the command round\nand the universe said i love you\n')
    assert out.stdout == '2, 10, 4, 16\n5, 8\n10, 16\nHI!, THERE!\n0\n1, 5, 2, 8\n', repr(out.stdout)
    assert perr('to half, given x (text), returning text:\n  return x\n' + END + 'genesis:\n  scrawl a list of (1, 2) changed by the command half\n' + END)[1] == \
        "'changed by' needs a command given a number returning something, not a command given text returning text."

    # Kept shapes (etched once, drawn every frame), daylight, and the pointer's words.
    out = both('use: window\n\ngenesis:\n  open a world with "Kept", 640, 480\n  start keeping the shapes as "land"\n  for each x from -5 to 5:\n    for each z from 0 to 10:\n      etch a cube with (x horizontal 0 vertical z depth, 1, "green")\n  etch a ball with (0 horizontal 2 vertical 4 depth, 0.7, "yellow")\n  stop keeping the shapes\n  try:\n    stop keeping the shapes\n  if that went wrong:\n    scrawl the wound\n  try:\n    etch the kept shapes "sea"\n  if that went wrong:\n    scrawl the wound\n  try:\n    set the daylight to 2\n  if that went wrong:\n    scrawl the wound\n  set frames to 0\n  as long as the world lives and frames falls below 5:\n    set frames to frames plus 1\n    place the eye at 0 horizontal 3 vertical -6 depth\n    aim the eye with (frames times 0.3, -15)\n    consume the window with "#87ceeb"\n    set the daylight to 1 minus frames divided by 200\n    etch the kept shapes "land"\n    etch words with "right " plus mouse right clicked plus " wheel " plus mouse wheel turned, 10, 10, "white"\n    reveal the frame\n  scrawl "moved ", mouse moved across, " ", mouse moved down\n  forget the kept shapes "land"\n  try:\n    etch the kept shapes "land"\n  if that went wrong:\n    scrawl the wound\nand the universe said i love you\n')
    assert out.stdout == 'no shapes are being kept. Start with: start keeping the shapes as "land"\nthere are no shapes kept as "sea".\nthe daylight is from 0 (dark) to 1 (full), not 2.\nmoved 0 0\nthere are no shapes kept as "land".\n', repr(out.stdout)

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

    # The computer library: commands' output, the environment, ending with an exit number; maths words.
    out = both('genesis:\n  scrawl the size of the words given\n  scrawl the output of the command "echo hello there"\n'
               '  scrawl environment value of "OS"\n  scrawl the size of current folder exceeds 2\n  end the program with 3\n  scrawl "never"\n' + END)
    assert (out.stdout, out.returncode) == ("0\nhello there\n\nWindows_NT\nyes\n", 3), repr((out.stdout, out.returncode))
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
               '  scrawl bytes in the file "box/c.txt", " ", there is a folder "box/inner", " ", there is a folder "nope"\n'
               '  erase the file "box/a.txt"\n  scrawl files in the folder "box"\n  try:\n    erase the file "box/a.txt"\n'
               '  if that went wrong:\n    scrawl the wound\n  erase the folder "box"\n  scrawl there is a folder "box"\n'
               '  scrawl files in the folder "nope"\n' + END)
    assert (out.stdout, out.stderr) == ('a.txt, c.txt / inner\n5 yes no\nc.txt\nI couldn\'t erase the file "box/a.txt".\nno\n',
                                        'Line 16: there is no folder called "nope".\n'), repr((out.stdout, out.stderr))

    out = both('genesis:\n  open a world with "x", 40, 40\n  etch a square with 20, 20, 5, "purple"\n  reveal the frame\n'
               '  end the world\n  scrawl "ok"\n' + END)
    assert out.stdout == "ok\n", repr(out.stdout)
    assert perr('genesis:\n  open a world with "x", 10, 10\n  etch a triangle with 1, 2\n' + END)[1] == (
        "I don't know 'etch a triangle with'. Words that start with 'etch': etch a ball, etch a block, etch a box, etch a circle, etch a cube, etch a line, "
        "etch a square, etch the ground, etch the kept shapes, etch the picture, etch the picture turned, etch words.")

    # within: close enough to touch.
    out = both('genesis:\n  set birth to 0 horizontal 0 vertical\n  set coin to 3 horizontal 4 vertical\n'
               '  scrawl existence is within 5 of coin, " ", existence is within 4.9 of coin, " ", 7 is within 2 of 5, " ",'
               ' 1 horizontal 1 vertical 1 depth is within 1 of 1 horizontal 1 vertical 2 depth, " ", not (10 is within 2 of 5)\n' + END)
    assert out.stdout == "yes no yes yes yes\n", repr(out.stdout)
    assert perr("genesis:\n  scrawl 1 is within 2 of 1 horizontal 2 vertical\n" + END)[1] == \
        "'within' compares two numbers or two places, not a number and a flat place."

    # Places: horizontal, vertical and depth. Setting birth makes existence start there too.
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


    # Lists of lists and tables of lists: the inner ones are shown in brackets.
    out = both('genesis:\n  set grid to a list of lists of numbers\n  add a list of (1, 2) to grid\n  add a list of numbers to grid\n'
               '  add a list of (3, 4) to grid\n  set item 1 of item 1 of grid to 9\n  scrawl grid, " / ", item 2 of item 3 of grid\n'
               '  set teams to a table of lists of text\n  set entry "red" of teams to a list of ("Ann", "Bo")\n  scrawl teams\n' + END)
    assert out.stdout == "(9, 2), (nothing), (3, 4) / 4\nred: (Ann, Bo)\n", repr(out.stdout)

    # Numbers and text shown the same way both ways; if / otherwise chains; stop and return inside loops.
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
    assert out.stdout == ("HéLLO WöRLD, HELLO | abc é | é | wörld\n3 0 | HéLP wörld, heLP\n"
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

    # A window: opens, draws, shows frames and closes the same both ways (it flashes up for a moment).
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

    # The web library, without needing the internet: a page that can't be reached fails the same both ways.
    out = both('use: web\ngenesis:\n  scrawl web page "http://localhost:1/"\n' + END)
    assert out.stderr == 'Line 3: I couldn\'t get the web page "http://localhost:1/".\n', repr(out.stderr)

    # Programs made of several scripts: used scripts bring their kinds and commands (not their start),
    # are read once even when used twice, and errors name the script they are in.
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

    # Sound: a short silent .wav plays (and waits) the same both ways; a missing file is a plain error.
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

    # Lists, kinds of things, returning, files, and a plain error while running.
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

    # Grammar: needed where English needs it, then skipped, so both forms mean the same.
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
        if os.environ.get("STELLANOVA_SHOW_SKIPPED"):
            print("\n".join(sorted(set(web_skipped))))


def main():
    for path in sorted(translate.LOGIC.glob("*.stella")):
        translate.translate(path)

    cpp = run("settings:\n  limit: 30 degrees\n\nto check, given goal (a place):\n  set gap to flat (goal minus centre of mass)\n"
              '  if the size of gap exceeds limit: cease\n  move turn rate toward 10 by at most 2 times frame time\n' + END)
    assert "constexpr double limit = 30.0;" in cpp, cpp
    assert "void ATerranovaCreatureBody::Check(const FVector& goal)" in cpp, cpp
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
    # Try-it mode: each typed line is done straight away; names are kept; blocks end with an empty line.
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
    print("stellanova.py self-check passed")


if __name__ == "__main__":
    main()
