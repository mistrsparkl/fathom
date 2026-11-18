"""Makes dist/stellanova-windows.zip for install.ps1. Upload: py -3 installer/make_release.py v0.1.0"""
import os
import subprocess
import sys
import time
import zipfile
from pathlib import Path

HOME = Path(__file__).resolve().parents[1]
STUDIA = HOME / "editor" / "studia"
WINDOW = STUDIA / "node_modules" / "electron" / "dist"
VERSION = sys.argv[1] if len(sys.argv) > 1 else "dev"

if not WINDOW.exists():
    sys.exit("Electron is missing: run npm install in editor/studia first.")
py = [sys.executable, str(HOME / "stellanova.py")]
subprocess.run(py + ["web", "screens.stella", "ui"], cwd=STUDIA, check=True)
subprocess.run(py + ["build", "system.stella"], cwd=STUDIA, check=True)
made = [STUDIA / "system.exe", STUDIA / "ui" / "screens.js", STUDIA / "ui" / "stellanova.js"]
now = time.time() + 60  # (newer than their .stella files, so Studia doesn't rebuild them)
for f in made:
    os.utime(f, (now, now))

tracked = subprocess.run(["git", "ls-files"], cwd=HOME, capture_output=True, text=True, check=True).stdout.split("\n")
out = HOME / "dist" / "stellanova-windows.zip"
out.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6, strict_timestamps=False) as z:
    for name in tracked:
        if name and not name.startswith(("tutorial/", "unreal/", "blog/")) and (HOME / name).is_file():
            z.write(HOME / name, name)
    for f in made:
        z.write(f, f.relative_to(HOME).as_posix())
    for f in WINDOW.rglob("*"):
        if f.is_file():
            z.write(f, "studia-window/" + f.relative_to(WINDOW).as_posix())
    z.write(HOME / "installer" / "uninstall.ps1", "uninstall.ps1")
    z.writestr("VERSION", VERSION)
print(f"{out} ({out.stat().st_size // 1_000_000} MB)")

if VERSION != "dev":
    gh = r"C:\Program Files\GitHub CLI\gh.exe"
    subprocess.run([gh, "release", "create", VERSION, str(out), "--title", f"Stellanova {VERSION}",
                    "--notes", "Install: irm https://raw.githubusercontent.com/mistrsparkl/stellanova/main/install.ps1 | iex"],
                   cwd=HOME, check=True)
