"""Tries Stellanova in Godot itself: makes a project, sets it up, plays a scene where a ball falls into a coin.
Run: py -3 engines/godot/check/check.py   (needs Godot 4.4 or later: winget install GodotEngine.GodotEngine; not in the test suite)"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOME = HERE.parents[2]
found = shutil.which("godot") or next(iter(sorted(
    (Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages").glob("GodotEngine.GodotEngine_*/*_console.exe"))), None)
if not found:
    sys.exit("Godot isn't installed: winget install GodotEngine.GodotEngine")
project = Path(tempfile.mkdtemp(prefix="stellanova_godot_")) / "Check"
shutil.copytree(HERE, project, ignore=shutil.ignore_patterns("check.py", "__pycache__"))
subprocess.run([sys.executable, str(HOME / "stellanova.py"), "godot", str(project)], check=True)
godot = lambda *a: subprocess.run([str(found), "--headless", "--path", str(project), *a], capture_output=True, text=True,
                                  errors="replace", timeout=300, stdin=subprocess.DEVNULL)
imported = godot("--import")
assert imported.returncode == 0, imported.stdout[-3000:] + imported.stderr[-3000:]
ran = godot("-s", "check.gd")
said = [line for line in ran.stdout.splitlines() if line.startswith(("coin ", "CHECK"))]
print("\n".join(said))
assert ran.returncode == 0 and "ERROR" not in ran.stderr, ran.stdout[-3000:] + ran.stderr[-3000:]
assert said[:1] == ["coin Coin at 0 horizontal 0 vertical 0 depth"], said
copy = [s for s in said[1:] if s.startswith("coin ")]
assert copy and " vertical " in copy[0] and float(copy[0].split(" at 0 horizontal ")[1].split()[0]) > 2, said  # the copy began 2 higher
print("Godot check passed")
shutil.rmtree(project.parent, ignore_errors=True)
