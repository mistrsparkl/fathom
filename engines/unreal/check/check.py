"""Tries Stellanova in Unreal itself: builds a small project, sets it up, plays a scene where a ball falls onto a coin.
Run: py -3 engines/unreal/check/check.py   (needs Unreal Engine 5.8; not in the test suite)"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOME = HERE.parents[2]
ENGINE = Path(r"C:\Program Files\Epic Games\UE_5.8\Engine")
if not ENGINE.exists():
    sys.exit("Unreal Engine 5.8 isn't installed (the Epic Games Launcher installs it).")
project = Path(tempfile.mkdtemp(prefix="stellanova_unreal_")) / "Check"
shutil.copytree(HERE / "Project", project)
subprocess.run([sys.executable, str(HOME / "stellanova.py"), "unreal", str(project)], check=True)
shutil.copy(HERE / "coin.stella", project / "Stellanova")
built = subprocess.run([str(ENGINE / "Build" / "BatchFiles" / "Build.bat"), "CheckEditor", "Win64", "Development",
                        f"-Project={project / 'Check.uproject'}", "-WaitMutex"], capture_output=True, text=True, stdin=subprocess.DEVNULL)
assert built.returncode == 0, built.stdout[-3000:]
ran = subprocess.run([str(ENGINE / "Binaries" / "Win64" / "UnrealEditor-Cmd.exe"), str(project / "Check.uproject"), "/Engine/Maps/Entry",
                      "-game", "-nullrhi", "-nosound", "-unattended", "-nosplash", "-stdout", "-FullStdOutLogOutput"],
                     capture_output=True, text=True, errors="replace", timeout=900, stdin=subprocess.DEVNULL)
said = [line.split("LogStellanova: ", 1)[1] for line in ran.stdout.splitlines() if "LogStellanova: " in line]
print("\n".join(said))
print((project / "check.txt").read_text() if (project / "check.txt").exists() else "(no check.txt)")
assert said[:1] == ["coin Coin at 0 horizontal 0 vertical 0 depth"], said
assert len([s for s in said if s.startswith("coin Coin at")]) >= 2 and not any(s.startswith("Error") for s in said), said  # the coin's copy began too
print("Unreal check passed")
shutil.rmtree(project.parent, ignore_errors=True)
