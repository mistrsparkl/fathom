"""Tries Stellanova in Unity itself: makes a project, sets it up, plays a scene where a ball falls onto a coin.
Run: py -3 engines/unity/check/check.py   (needs Unity 6 and Unity Hub signed in; not in the test suite)"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOME = HERE.parents[2]
editors = sorted(Path(r"C:\Program Files\Unity\Hub\Editor").glob("*/Editor/Unity.exe"))
if not editors:
    sys.exit("Unity isn't installed: get it with Unity Hub.")
unity = str(editors[-1])
project = Path(tempfile.mkdtemp(prefix="stellanova_unity_")) / "Check"
log = project.parent / "unity.log"
run = lambda *a: subprocess.run([unity, "-batchmode", "-nographics", *a, "-logFile", str(log)], timeout=900).returncode
assert run("-createProject", str(project), "-quit") == 0, log.read_text(errors="replace")[-3000:]
subprocess.run([sys.executable, str(HOME / "stellanova.py"), "unity", str(project)], check=True)
shutil.copy(HERE / "coin.stella", project / "Assets")
(project / "Assets" / "Editor").mkdir()
shutil.copy(HERE / "PlayCheck.cs", project / "Assets" / "Editor")
code = run("-projectPath", str(project), "-executeMethod", "PlayCheck.Run")
said = (project / "check.txt").read_text() if (project / "check.txt").exists() else ""
print(said)
assert code == 0 and "Log: coin Coin at 0 horizontal 0 vertical 0 depth" in said, log.read_text(errors="replace")[-3000:]
assert "player colour RGBA(1.000, 0.000, 0.000, 1.000)" in said and said.count("Log: coin Coin") >= 2, said
print("Unity check passed")
shutil.rmtree(project.parent, ignore_errors=True)
