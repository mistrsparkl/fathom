"""Plays words.stella in Godot, then in an exported game. Run: py -3 engines/godot/check/check.py"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOME = HERE.parents[2]
sys.path.insert(0, str(HOME / "engines" / "check"))
import check  # noqa: E402  (what every engine check shares)

found = shutil.which("godot") or next(iter(sorted(
    (Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages").glob("GodotEngine.GodotEngine_*/*_console.exe"))), None)
if not found:
    sys.exit("Godot isn't installed: winget install GodotEngine.GodotEngine")
project = Path(tempfile.mkdtemp(prefix="stellanova_godot_")) / "Check"
shutil.copytree(HERE, project, ignore=shutil.ignore_patterns("check.py", "__pycache__"))
shutil.copy(check.PROGRAM, project)
subprocess.run([sys.executable, str(HOME / "stellanova.py"), "godot", str(project)], check=True)


def run(program, *a):
    done = subprocess.run([str(program), "--headless", *a], capture_output=True, text=True, errors="replace", timeout=300,
                          stdin=subprocess.DEVNULL, cwd=Path(program).parent)
    return done


def play(program, *a, engine):
    done = run(program, *a)
    said, objects, problems = [], {}, []
    for line in done.stdout.splitlines():
        if line.startswith("CHECK "):
            name, h, v, d, turn, colour = line[6:].split("|")
            objects[name] = ((float(h), float(v), float(d)), float(turn), None if colour == "none" else colour)
        elif line.strip() and not line.startswith("Godot Engine"):
            said.append(line)
    for line in done.stderr.splitlines():
        if line.startswith("ERROR: Stellanova: "):
            problems.append("problem: " + line[len("ERROR: Stellanova: "):])
        elif line.startswith(("ERROR", "SCRIPT ERROR")):
            sys.exit(f"{engine}: Godot said: {line}\n{done.stderr[-3000:]}")
    print(f"{engine}:\n  " + "\n  ".join(said + problems))
    assert done.returncode == 0, done.stderr[-3000:]
    check.check_said(said + problems, engine)
    check.check_scene(objects, engine)


assert run(found, "--path", str(project), "--import").returncode == 0
play(found, "--path", str(project), engine="Godot editor")
(project / "exported").mkdir()
exported = run(found, "--path", str(project), "--export-debug", "Windows Desktop", str(project / "exported" / "Check.exe"))
made = sorted(p.name for p in (project / "exported").iterdir()) if (project / "exported").exists() else []
assert exported.returncode == 0 and "words.dll" in made, f"export made {made}\n" + exported.stdout[-2000:] + exported.stderr[-2000:]
game = shutil.move(project / "exported", project.parent / "game")  # (away from the project, which it mustn't need)
shutil.rmtree(project)
play(Path(game) / "Check.console.exe", engine="exported Godot game")
print("Godot check passed")
shutil.rmtree(project.parent, ignore_errors=True)
