"""Makes dist/stellanova-linux.tar.gz for install.sh. Runs inside Linux (make_release.py starts it in WSL)."""
import io
import os
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

HOME = Path(__file__).resolve().parents[1]
VERSION = sys.argv[1] if len(sys.argv) > 1 else "dev"
electron = json.loads((HOME / "editor" / "studia" / "node_modules" / "electron" / "package.json").read_text())["version"]

with tempfile.TemporaryDirectory() as d:
    src = Path(d) / "src"
    src.mkdir()
    archive = subprocess.run(["git", "archive", "HEAD"], cwd=HOME, capture_output=True, check=True).stdout
    tarfile.open(fileobj=io.BytesIO(archive)).extractall(src, filter="tar")
    studia = src / "editor" / "studia"
    subprocess.run([sys.executable, str(src / "stellanova.py"), "web", "screens.stella", "ui"], cwd=studia, check=True)
    subprocess.run([sys.executable, str(src / "stellanova.py"), "build", "system.stella"], cwd=studia, check=True)
    later = time.time() + 60  # (newer than their .stella files, so Studia doesn't rebuild them)
    for f in (studia / "system", studia / "ui" / "screens.js", studia / "ui" / "stellanova.js"):
        os.utime(f, (later, later))
    for skip in ("tutorial", "unreal", "blog"):
        shutil.rmtree(src / skip, ignore_errors=True)
    shutil.rmtree(src / "runtime" / "built", ignore_errors=True)

    url = f"https://github.com/electron/electron/releases/download/v{electron}/electron-v{electron}-linux-x64.zip"
    print("getting", url)
    window = src / "studia-window"
    with zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(url).read())) as z:
        for info in z.infolist():
            z.extract(info, window)
            mode = info.external_attr >> 16
            if mode:
                (window / info.filename).chmod(mode & 0o777)
    shutil.copy(HOME / "installer" / "uninstall.sh", src / "uninstall.sh")
    (src / "uninstall.sh").chmod(0o755)
    (src / "stellanova").chmod(0o755)
    (src / "VERSION").write_text(VERSION)

    out = HOME / "dist" / "stellanova-linux.tar.gz"
    out.parent.mkdir(exist_ok=True)
    with tarfile.open(out, "w:gz") as t:
        for f in sorted(src.iterdir()):
            t.add(f, f.name)
print(f"{out} ({out.stat().st_size // 1_000_000} MB)")
