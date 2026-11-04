"""Self-check for imagination.py. Run: py -3 test_imagination.py"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
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

    # Build and run a real program, if this computer has the C++ compiler.
    if not translate.find_vcvars():
        print("(skipped running a program: no C++ compiler found)")
        return
    import subprocess
    with tempfile.TemporaryDirectory() as d:
        script = Path(d) / "hello.imagine"
        script.write_text('to start:\n  ask "Name? " into name\n  ask "Age? " into age (a number)\n'
                          '  repeat 2 times: say "Hello, " plus name plus "!"\n'
                          '  say "Next year you are ", age plus 1, ". Grown up: ", age is at least 18\n' + END, encoding="utf-8")
        exe = Path(d) / "hello.exe"
        problem = translate.build(script, exe)
        assert problem is None, problem
        out = subprocess.run([str(exe)], input="Sam\nlots\n20.5\n", capture_output=True, text=True).stdout
        assert out == "Name? Age? Please type a number.\nAge? Hello, Sam!\nHello, Sam!\nNext year you are 21.5. Grown up: yes\n", repr(out)

        # Lists, kinds of things, giving back, files, and a plain error while running.
        script.write_text('a pet has:\n  name (text)\n  ages (a list of numbers)\n' + END +
                          'to start:\n  set p to a new pet\n  set name of p to "Rex"\n  add 3 to ages of p\n  add 4 to ages of p\n'
                          '  say p\n  say total of ages of p, " ", item 2 of ages of p, " ", size of ages of p\n'
                          '  for each n from 1 to 3: add n times 10 to ages of p\n  remove item 1 from ages of p\n  say ages of p\n'
                          '  say ages of p contains 20, " ", "hello" contains "ell"\n'
                          '  write "" to file "t.txt"\n  add "one" to file "t.txt"\n  add "two 2" to file "t.txt"\n  set got to lines of file "t.txt"\n'
                          '  say got, " | ", size of got, " | ", words of item 2 of got, " | ", file "t.txt" exists, " ", file "nope.txt" exists\n'
                          '  say (item 2 of words of item 2 of got) as a number plus 1\n'
                          '  say item 9 of ages of p\n' + END +
                          'to total of, given xs (a list of numbers), giving back a number:\n  set sum to 0\n'
                          '  for each x in xs: set sum to sum plus x\n  give back sum\n' + END, encoding="utf-8")
        assert translate.build(script, exe) is None
        ran = subprocess.run([str(exe)], capture_output=True, text=True, cwd=d)
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
