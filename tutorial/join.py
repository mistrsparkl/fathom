"""Joins the filmed lessons (out/parts/NN-name.mp4, in order) into one film, out/Stellanova Tutorial.mp4, with a
chapter for each lesson (named by its 'title:' line), so players can jump between them.

    py -3 join.py
"""
import subprocess
from pathlib import Path

HERE = Path(__file__).parent
PARTS = HERE / "out" / "parts"
FILM = HERE / "out" / "Stellanova Tutorial.mp4"


def seconds_of(film):
    said = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(film)],
                          capture_output=True, text=True, check=True)
    return float(said.stdout.strip())


def title_of(lesson):
    for line in lesson.read_text(encoding="utf-8").splitlines():
        if line.startswith("title:"):
            return line[6:].strip()
    return lesson.stem


lessons = sorted((HERE / "lessons").glob("[0-9][0-9]-*.lesson"))
films = [PARTS / f"{l.stem}.mp4" for l in lessons]
missing = [f.name for f in films if not f.exists()]
if missing:
    raise SystemExit("not filmed yet: " + ", ".join(missing))

chapters, at = [";FFMETADATA1", "title=Stellanova: every part of the language"], 0.0
for lesson, film in zip(lessons, films):
    length = seconds_of(film)
    chapters += ["[CHAPTER]", "TIMEBASE=1/1000", f"START={int(at * 1000)}", f"END={int((at + length) * 1000)}", f"title={title_of(lesson)}"]
    at += length
meta = HERE / "out" / "chapters.txt"
meta.write_text("\n".join(chapters) + "\n", encoding="utf-8")

inputs = []
for f in films:
    inputs += ["-i", str(f)]
n = len(films)
joined = "".join(f"[{k}:v][{k}:a]" for k in range(n)) + f"concat=n={n}:v=1:a=1[v][a]"
subprocess.run(["ffmpeg", "-v", "error", "-stats", "-y", *inputs, "-i", str(meta), "-filter_complex", joined,
                "-map", "[v]", "-map", "[a]", "-map_metadata", str(n), "-map_chapters", str(n),
                "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30",
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(FILM)], check=True)
print(f"made {FILM.name}: {at / 60:.1f} minutes, {n} chapters")
