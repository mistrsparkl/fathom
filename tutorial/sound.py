"""Makes a lesson's sound track: each spoken line placed at the second it started in the film.

    py -3 sound.py placed.json out.wav      placed.json: {"seconds": total, "placed": [[start seconds, mp3], ...]}
"""
import array
import json
import subprocess
import sys
import wave

RATE = 48000


def samples(mp3):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", mp3, "-f", "s16le", "-ac", "1", "-ar", str(RATE), "-"],
                         capture_output=True, check=True).stdout
    return array.array("h", raw)


def main(placed_file, wav_file):
    plan = json.load(open(placed_file, encoding="utf-8"))
    track = array.array("h", bytes(2 * int(plan["seconds"] * RATE + RATE)))
    for start, mp3 in plan["placed"]:
        at = int(start * RATE)
        for k, v in enumerate(samples(mp3)):
            if at + k < len(track):
                track[at + k] = max(-32768, min(32767, track[at + k] + v))
    with wave.open(wav_file, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(RATE)
        out.writeframes(track.tobytes())


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
