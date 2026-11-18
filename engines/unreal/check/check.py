"""Plays words.stella in Unreal, then in a packaged game. Run: py -3 engines/unreal/check/check.py"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOME = HERE.parents[2]
sys.path.insert(0, str(HOME / "engines" / "check"))
import check  # noqa: E402  (what every engine check shares)

ENGINE = Path(r"C:\Program Files\Epic Games\UE_5.8\Engine")
if not ENGINE.exists():
    sys.exit("Unreal Engine 5.8 isn't installed (the Epic Games Launcher installs it).")
project = Path(tempfile.mkdtemp(prefix="stellanova_unreal_")) / "Check"
shutil.copytree(HERE / "Project", project)
subprocess.run([sys.executable, str(HOME / "stellanova.py"), "unreal", str(project)], check=True)
shutil.copy(check.PROGRAM, project / "Stellanova")
quiet = dict(capture_output=True, text=True, errors="replace", stdin=subprocess.DEVNULL)


def read(report, engine, output):
    text = report.read_text(encoding="utf-8-sig") if report.exists() else ""
    said, objects = [], {}
    for line in text.splitlines():
        if line.startswith("SAID "):
            said.append(line[5:])
        elif line.startswith("CHECK "):
            name, h, v, d, turn, colour = line[6:].split("|")
            objects[name] = ((float(h), float(v), float(d)), float(turn), None if colour == "none" else colour)
        elif line.startswith("BAD "):
            sys.exit(f"{engine}: Unreal said: {line}")
    print(f"{engine}:\n  " + "\n  ".join(said))
    assert said, f"{engine}: no check.txt\n" + output[-3000:]
    check.check_said(said, engine)
    check.check_scene(objects, engine)


built = subprocess.run([str(ENGINE / "Build" / "BatchFiles" / "Build.bat"), "CheckEditor", "Win64", "Development",
                        f"-Project={project / 'Check.uproject'}", "-WaitMutex"], **quiet)
assert built.returncode == 0, built.stdout[-3000:]
ran = subprocess.run([str(ENGINE / "Binaries" / "Win64" / "UnrealEditor-Cmd.exe"), str(project / "Check.uproject"), "/Engine/Maps/Entry",
                      "-game", "-nullrhi", "-nosound", "-unattended", "-nosplash", "-stdout", "-FullStdOutLogOutput"], timeout=900, **quiet)
read(project / "check.txt", "Unreal editor", ran.stdout)
(project / "Stellanova" / "words.dll").unlink()  # (packaging makes it again)
archive = project.parent / "game"
packaged = subprocess.run([str(ENGINE / "Build" / "BatchFiles" / "RunUAT.bat"), "BuildCookRun", f"-project={project / 'Check.uproject'}",
                           "-noP4", "-platform=Win64", "-clientconfig=Development", "-build", "-cook", "-stage", "-pak", "-archive",
                           f"-archivedirectory={archive}", "-unattended", "-utf8output"], timeout=5400, **quiet)
assert packaged.returncode == 0, packaged.stdout[-5000:]
shutil.rmtree(project)  # (the packaged game mustn't need it)
game = next(archive.rglob("Check.exe"))
played = subprocess.run([str(game), "-nullrhi", "-nosound", "-unattended", "-nosplash"], timeout=600, **quiet)
read(game.parent / "Check" / "check.txt", "packaged Unreal game", played.stdout + played.stderr)
print("Unreal check passed")
shutil.rmtree(project.parent, ignore_errors=True)
