"""Tries Stellanova in Unity itself: makes a project, sets it up, plays engines/check/words.stella in the editor, then builds
the game and plays that too. Run: py -3 engines/unity/check/check.py   (needs Unity 6 and Unity Hub signed in; not in the test suite)"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOME = HERE.parents[2]
sys.path.insert(0, str(HOME / "engines" / "check"))
import check  # noqa: E402  (what every engine check shares)

editors = sorted(Path(r"C:\Program Files\Unity\Hub\Editor").glob("*/Editor/Unity.exe"))
if not editors:
    sys.exit("Unity isn't installed: get it with Unity Hub.")
unity = str(editors[-1])
project = Path(tempfile.mkdtemp(prefix="stellanova_unity_")) / "Check"
log = project.parent / "unity.log"
run = lambda *a: subprocess.run([unity, "-batchmode", "-nographics", *a, "-logFile", str(log)], timeout=1800).returncode
assert run("-createProject", str(project), "-quit") == 0, log.read_text(errors="replace")[-3000:]
subprocess.run([sys.executable, str(HOME / "stellanova.py"), "unity", str(project)], check=True)
shutil.copy(check.PROGRAM, project / "Assets")
shutil.copy(HERE / "CheckReport.cs", project / "Assets")
(project / "Assets" / "Editor").mkdir()
shutil.copy(HERE / "PlayCheck.cs", project / "Assets" / "Editor")


def read(report, engine):
    text = report.read_text(encoding="utf-8") if report.exists() else ""
    said, objects = [], {}
    for line in text.splitlines():
        if line.startswith("SAID "):
            said.append(line[5:])
        elif line.startswith("CHECK "):
            name, h, v, d, turn, colour = line[6:].split("|")
            objects[name] = ((float(h), float(v), float(d)), float(turn), None if colour == "none" else colour)
        elif line.startswith("BAD "):
            sys.exit(f"{engine}: Unity said: {line}")
    print(f"{engine}:\n  " + "\n  ".join(said))
    assert said, f"{engine}: no check.txt\n" + log.read_text(errors="replace")[-3000:]
    check.check_said(said, engine)
    check.check_scene(objects, engine)


assert run("-projectPath", str(project), "-executeMethod", "PlayCheck.Run") == 0, log.read_text(errors="replace")[-3000:]
read(project / "check.txt", "Unity editor")
assert run("-projectPath", str(project), "-executeMethod", "PlayCheck.Build") == 0, log.read_text(errors="replace")[-3000:]
game = Path(shutil.move(project / "game", project.parent / "game"))  # (away from the project, which it mustn't need)
shutil.rmtree(project)
played = subprocess.run([str(game / "Check.exe"), "-batchmode", "-nographics", "-logFile", str(game / "player.log")], timeout=300)
assert played.returncode == 0, (game / "player.log").read_text(errors="replace")[-3000:]
read(game / "check.txt", "built Unity game")
print("Unity check passed")
shutil.rmtree(project.parent, ignore_errors=True)
