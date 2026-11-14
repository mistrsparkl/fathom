"""Speaks lines with a natural voice (Microsoft Edge's online voices) and keeps each as an .mp3 next to a .json of
when each word is said. Lines already spoken are kept, so only new or changed lines are sent.

    py -3 voice.py lines.json      lines.json: a list of texts; prints a list of {"file", "seconds", "words"}
"""
import asyncio
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import edge_tts

VOICE = "en-US-AndrewNeural"
RATE = "+0%"
HERE = Path(__file__).parent
KEPT = HERE / "out" / "voice"


def spoken(text):
    """How the voice should say it: Stellanova's own words are read the way a person would read them."""
    return text.replace("stellanova.py", "stellanova dot p y").replace(".stella", " dot stella").replace(".exe", " dot e x e")


async def speak(text, mp3, timing):
    talk = edge_tts.Communicate(spoken(text), VOICE, rate=RATE, boundary="WordBoundary")
    words = []
    with open(mp3, "wb") as out:
        async for piece in talk.stream():
            if piece["type"] == "audio":
                out.write(piece["data"])
            elif piece["type"] == "WordBoundary":
                words.append({"at": piece["offset"] / 1e7, "for": piece["duration"] / 1e7, "word": piece["text"]})
    timing.write_text(json.dumps(words), encoding="utf-8")


def seconds_of(mp3):
    said = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(mp3)],
                          capture_output=True, text=True)
    return float(said.stdout.strip())


def voice_all(texts):
    KEPT.mkdir(parents=True, exist_ok=True)
    made = []
    for text in texts:
        name = hashlib.sha1((VOICE + RATE + spoken(text)).encode("utf-8")).hexdigest()[:16]
        mp3, timing = KEPT / f"{name}.mp3", KEPT / f"{name}.json"
        for attempt in range(4):
            if mp3.exists() and timing.exists() and mp3.stat().st_size > 0:
                break
            try:
                asyncio.run(speak(text, mp3, timing))
            except Exception as problem:  # the service sometimes drops a request: try again
                print(f"(voice: trying again after {problem})", file=sys.stderr)
        try:
            seconds = seconds_of(mp3)
        except ValueError:  # a broken file from a dropped request: say it again
            mp3.unlink()
            asyncio.run(speak(text, mp3, timing))
            seconds = seconds_of(mp3)
        made.append({"file": str(mp3), "seconds": seconds, "words": json.loads(timing.read_text(encoding="utf-8"))})
    return made


if __name__ == "__main__":
    print(json.dumps(voice_all(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")))))
