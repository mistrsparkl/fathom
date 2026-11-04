"""Self-check for anything.py. Run: py -3 test_anything.py"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import anything as translate
translate.LOGIC = Path(__file__).resolve().parent / "examples"


def run(body):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "probe.any"
        p.write_text("this is part of: creature body\n\n" + body, encoding="utf-8")
        return translate.translate(p)


def error(body):
    try:
        run(body)
    except translate.ScriptError as e:
        return e.line, e.message
    raise AssertionError("expected a script error")


def main():
    for path in sorted(translate.LOGIC.glob("*.any")):
        translate.translate(path)

    cpp = run("settings:\n  limit: 30 degrees\n\nto check, given goal (a place):\n  set gap to flat (goal minus centre of mass)\n"
              "  if size of gap is more than limit: stop\n  move turn rate toward 10 by at most 2 times frame time\n")
    assert "constexpr double limit = 30.0;" in cpp, cpp
    assert "void ATerranovaCreatureBody::Check(const FVector& goal)" in cpp, cpp
    assert "if ((gap).Size() > Any_probe::limit)" in cpp, cpp
    assert "TurnRateDegS = FMath::Clamp(10.0, TurnRateDegS - " in cpp, cpp

    assert error("to check:\n  set turn rate to walk sped\n") == (4, "I don't know 'walk sped'. Did you mean 'walk speed'?")
    assert error("to check:\n  set turn rate to fallen\n") == (4, "'turn rate' holds a number, not yes or no.")
    assert error("to check:\n  set fallen to yes\n") == (4, "'fallen' can't be changed by a script.")
    assert error("to check:\n  if turn rate: stop\n")[1].startswith("'if' needs something that is yes or no")
    assert error("to check:\n  jump\n")[1].startswith("I don't know how to start a line with 'jump'")
    closed = run("to check:\n  set turn rate to 1\n\nAnd the universe said I love you.\n\nto other:\n  stop\nand the universe said i love you\n")
    assert "::Check()" in closed and "::Other()" in closed, closed
    assert error("and the universe said i love you\n")[1].startswith("'and the universe said i love you' closes a command")
    print("anything.py self-check passed")


if __name__ == "__main__":
    main()
