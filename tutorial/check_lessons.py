"""Checks lessons without filming. py -3 check_lessons.py lessons/*.lesson"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
HOME = HERE.parent
WORK = HERE / "out" / "checking"


def read(file):
    lines = file.read_text(encoding="utf-8").replace("\r", "").split("\n")
    steps, files, i = [], [], 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.startswith("#"):
            i += 1
            continue
        m = re.match(r"^([a-z ]+?):\s?(.*)$", line) or re.match(r"^([a-z ]+)$", line)
        if not m:
            raise SystemExit(f"{file.name} line {i + 1}: I don't understand {line!r}")
        what, rest = m.group(1), (m.group(2) if m.lastindex and m.lastindex > 1 else "") or ""
        if what == "files":
            files = [f.strip() for f in rest.split(",") if f.strip()]
        elif what in ("type", "type fast", "paste", "say", "keys") and rest == "":
            block = []
            while i + 1 < len(lines) and (lines[i + 1].startswith("  ") or (lines[i + 1] == "" and (lines[i + 2] if i + 2 < len(lines) else "").startswith("  "))):
                i += 1
                block.append(lines[i][2:])
            rest = " ".join(block) if what == "say" else "\n".join(block)
            steps.append((what, rest, i + 1))
        else:
            steps.append((what, rest, i + 1))
        i += 1
    return files, steps


class Editor:
    def __init__(self):
        self.text, self.at, self.chosen = "", 0, None

    def start_of(self, n):
        rows = self.text.split("\n")
        return sum(len(r) + 1 for r in rows[: n - 1])

    def put(self, words):
        if self.chosen:
            a, b = self.chosen
            self.text, self.at, self.chosen = self.text[:a] + self.text[b:], a, None
        self.text = self.text[: self.at] + words + self.text[self.at:]
        self.at += len(words)


def run(how, file, answers):
    py = ["py", "-3", str(HOME / "fathom.py")]
    call = py + ([file.name] if how == "run" else [how, file.name])
    said = subprocess.run(call, cwd=WORK, input="\n".join(answers) + "\n", capture_output=True, text=True, encoding="utf-8", timeout=300)
    return said.returncode, (said.stdout + said.stderr).rstrip()


def check(lesson, verbose):
    files, steps = read(lesson)
    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True)
    for f in files:
        shutil.copy(HERE / "lessons" / "files" / f, WORK / Path(f).name)
    ed, current, problems = Editor(), None, 0
    words_said = 0
    for k, (what, value, line) in enumerate(steps):
        if what == "say":
            words_said += len(value.split())
        elif what == "new":
            current = WORK / value
            ed = Editor()
        elif what == "open":
            current = WORK / value
            ed = Editor()
            ed.text = current.read_text(encoding="utf-8").replace("\r", "")
        elif what == "open library":
            current = None
            ed = Editor()
            ed.text = (HOME / "libraries" / f"{value}.words").read_text(encoding="utf-8").replace(chr(13), "")
        elif what == "clear":
            ed = Editor()
        elif what in ("type", "type fast", "paste"):
            ed.put(value)
        elif what == "line":
            n = int(value)
            rows = ed.text.split("\n")
            ed.at, ed.chosen = ed.start_of(n) + len(rows[n - 1]), None
        elif what == "select":
            a, b = (int(x) for x in (value.split("-") + [value])[:2])
            ed.chosen = (ed.start_of(a), ed.start_of(b + 1))
        elif what == "keys":
            for key in value.split():
                if key == "ctrl+end":
                    ed.at = len(ed.text)
                elif key == "enter":
                    ed.put("\n")
                elif key == "end":
                    ed.at = ed.text.find("\n", ed.at) if "\n" in ed.text[ed.at:] else len(ed.text)
                elif key == "backspace":
                    ed.text, ed.at = ed.text[: ed.at - 1] + ed.text[ed.at:], ed.at - 1
                elif key in ("ctrl+s", "escape"):
                    pass
                else:
                    print(f"  ({lesson.name} line {line}: the checker doesn't follow '{key}')")
        elif what == "zoom" and verbose:
            m = re.match(r"lines? (\d+)(?:\s*-\s*(\d+))?$", value)
            if m:
                a, b = int(m.group(1)), int(m.group(2) or m.group(1))
                rows = ed.text.split("\n")
                print(f"  zoom {a}-{b}: " + " | ".join(r.strip() for r in rows[a - 1: b]))
        elif what in ("run", "test", "watch", "build", "web", "wasm", "profile", "debug", "save"):
            if current:
                current.write_text(ed.text, encoding="utf-8")
            if what == "save":
                continue
            answers = [v for w, v, _ in steps[k + 1:] if w == "answer"]
            nxt = [w for w, _, _ in steps[k + 1:] if w in ("run", "test", "watch", "build")]
            if nxt:  # only the answers before the next run
                stop = next(i for i, s in enumerate(steps[k + 1:]) if s[0] in ("run", "test", "watch", "build"))
                answers = [v for w, v, _ in steps[k + 1: k + 1 + stop] if w == "answer"]
            code, out = run(what, current, answers)
            mark = "" if code == 0 else f"   <-- ended with {code}"
            print(f"  [{what} {current.name}, line {line}]{mark}")
            for o in out.split("\n")[:25]:
                print("     " + o)
            problems += code != 0 and "expect" not in value
    print(f"{lesson.name}: about {words_said / 150:.1f} minutes of talking")
    return problems


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    verbose = "-v" in sys.argv
    total = sum(check(Path(f), verbose) for f in sys.argv[1:] if f.endswith(".lesson"))
    print("problems:", total)
