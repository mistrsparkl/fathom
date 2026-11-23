"""Starts Fathom: runs a kept built copy if nothing changed, else fathom.py."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = Path.home() / ".fathom" / "runs"  # built copies of scripts that were run, and what each was built from


def stamp(path):
    s = path.stat()
    return [str(path), s.st_mtime_ns, s.st_size]


def install_stamp():
    """Fathom's own files: when any changes, every script is built again."""
    files = [HERE / "fathom.py", HERE / "machine.py"] + [HERE / "runtime" / f for f in ("machine.cpp", "machine.h", "fathom.h")]
    files += sorted(p for p in (HERE / "libraries").rglob("*") if p.is_file())
    if os.environ.get("FATHOM_GOT"):
        files += sorted(p for p in Path(os.environ["FATHOM_GOT"]).rglob("*") if p.is_file())
    return [stamp(p) for p in files]


def note_of(script):
    """The note for a script's built copy."""
    return RUNS / (hashlib.sha256(str(script.resolve()).encode("utf-8")).hexdigest()[:24] + ".json")


def kept_copy(script):
    """The built copy, if still current (or None)."""
    try:
        note = json.loads(note_of(script).read_text(encoding="utf-8"))
        exe = RUNS / note["exe"]
        if exe.exists() and note["stamp"] == install_stamp() and all(stamp(Path(p)) == [p, t, n] for p, t, n in note["sources"]):
            return exe
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def main(argv):
    args = argv[1:]
    if args[:1] == ["run"]:
        args = args[1:]
    if args and args[0].lower().endswith(".fathom") and not os.environ.get("FATHOM_DIRECT"):
        exe = kept_copy(Path(args[0]))
        if exe:
            try:
                return subprocess.run([str(exe), *args[1:]]).returncode
            except KeyboardInterrupt:
                return 130
    import fathom  # (imported, not run, so Python keeps it ready-made)
    return fathom.main(argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
