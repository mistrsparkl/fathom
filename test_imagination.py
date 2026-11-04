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
    assert perr("use: nothing here\nto start:\n  stop\n" + END)[1].startswith("There is no library called 'nothing here'. Libraries: computer, maths, time")

    # Run real programs both ways: directly, and built with the C++ compiler (if there is one).
    # Both must print exactly the same, so the two halves of every piece of the language agree.
    import subprocess
    compiler = translate.find_vcvars()
    if not compiler:
        print("(only running directly: no C++ compiler found)")

    def both(source, typed=""):
        with tempfile.TemporaryDirectory() as d:
            script = Path(d) / "probe.imagine"
            script.write_text(source, encoding="utf-8")
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

    # Libraries.
    out = both('use: maths\nuse: time\nto start:\n  say round (sine of 30 times 1000), " ", power of (2, 10), " ", remainder of (17, 5)\n'
               '  say round 2.5, " ", round down -2.5, " ", round up 2.1, " ", round (pi times 100)\n'
               '  wait 0.01 seconds\n  say seconds since start is more than 0, " ", year now is more than 2000\n' + END).stdout
    assert out == "500 1024 2\n3 -3 3 314\nyes yes\n", repr(out)

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
    program_checks()
    print("imagination.py self-check passed")


if __name__ == "__main__":
    main()
