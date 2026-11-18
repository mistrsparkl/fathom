"""What every engine check shares: words.stella's lines and the scene it must leave behind."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROGRAM = HERE / "words.stella"
EXPECTED = (HERE / "expected.txt").read_text(encoding="utf-8").splitlines()


def check_said(said, engine):
    """said: the program's lines in order, problems as 'problem: ...' (engines may show those apart from the rest).
    Begin's lines come first, in order; each line comes once."""
    plain = [s for s in said if not s.startswith("problem: ")]
    assert plain[:11] == EXPECTED[:11], f"{engine}: begin said\n" + "\n".join(said)
    assert sorted(said) == sorted(EXPECTED), f"{engine}: expected\n" + "\n".join(EXPECTED) + "\nbut it said\n" + "\n".join(said)


def check_scene(objects, engine):
    """objects: name -> (place (h, v, d) or None, turn, colour name or None) as the engine sees them at the end."""
    mover = objects["Mover"]
    assert all(abs(a - b) < 0.01 for a, b in zip(mover[0], (5, 5, 6))) and abs(mover[1] - 90) < 0.5, f"{engine}: Mover {mover}"
    assert objects["Box"][2] == "blue" and objects["Player"][2] == "red", f"{engine}: {objects}"
    assert len(objects) == 4, f"{engine}: the copy wasn't removed: {sorted(objects)}"
