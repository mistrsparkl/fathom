"""Makes dist/fathom-linux.tar.gz for install.sh. Runs inside Linux (make_release.py starts it in WSL)."""
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
electron = json.loads((HOME / "editor" / "studio" / "node_modules" / "electron" / "package.json").read_text())["version"]

with tempfile.TemporaryDirectory() as d:
    src = Path(d) / "src"
    src.mkdir()
    archive = subprocess.run(["git", "archive", "HEAD"], cwd=HOME, capture_output=True, check=True).stdout
    tarfile.open(fileobj=io.BytesIO(archive)).extractall(src, filter="tar")
    studio = src / "editor" / "studio"
    subprocess.run([sys.executable, str(src / "fathom.py"), "web", "screens.fathom", "ui"], cwd=studio, check=True)
    subprocess.run([sys.executable, str(src / "fathom.py"), "build", "system.fathom"], cwd=studio, check=True)
    later = time.time() + 60  # (newer than their .fathom files, so Studio doesn't rebuild them)
    for f in (studio / "system", studio / "ui" / "screens.js", studio / "ui" / "fathom.js"):
        os.utime(f, (later, later))
    for skip in ("tutorial", "unreal", "blog"):
        shutil.rmtree(src / skip, ignore_errors=True)
    shutil.rmtree(src / "runtime" / "built", ignore_errors=True)

    url = f"https://github.com/electron/electron/releases/download/v{electron}/electron-v{electron}-linux-x64.zip"
    print("getting", url)
    window = src / "studio-window"
    with zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(url).read())) as z:
        for info in z.infolist():
            z.extract(info, window)
            mode = info.external_attr >> 16
            if mode:
                (window / info.filename).chmod(mode & 0o777)
    shutil.copy(HOME / "installer" / "uninstall.sh", src / "uninstall.sh")
    (src / "uninstall.sh").chmod(0o755)
    (src / "fathom").chmod(0o755)
    (src / "VERSION").write_text(VERSION)

    out = HOME / "dist" / "fathom-linux.tar.gz"
    out.parent.mkdir(exist_ok=True)
    with tarfile.open(out, "w:gz") as t:
        for f in sorted(src.iterdir()):
            t.add(f, f.name)
print(f"{out} ({out.stat().st_size // 1_000_000} MB)")
