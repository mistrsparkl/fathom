# The tutorial video

This makes a video that goes through the whole language in Fathom Studia, with a voice and captions. It finishes by building a platform game (`lessons/files/hop.fathom`). Each lesson is a script, and the recorder plays it in Studia (typing, running, zooming in) and films it.

You'll need Studia's Electron (`cd editor/studia && npm install`), ffmpeg, and `py -3 -m pip install edge-tts`. The voice is Edge's online `en-US-AndrewNeural`, so new lines need the internet. Lines it's already spoken are saved in `out/voice`.

```
py -3 check_lessons.py lessons/*.lesson          # try the lessons' programs without filming (-v shows each zoom's lines)
cd ../editor/studia
npx electron ../../tutorial/recorder.js ../../tutorial/lessons/*.lesson    # films out/parts/<lesson>.mp4
cd ../../tutorial
py -3 join.py                                     # out/Fathom Tutorial.mp4, a chapter per lesson
```

`py -3 make_hop_lesson.py` writes `lessons/17-platformer.lesson` from the game itself, so the line numbers stay right when the game changes. Games film themselves. The window library has a demo mode (`FATHOM_DEMO_FRAMES`, `FATHOM_DEMO_KEYS`) that saves every frame and presses keys from a list like `lessons/files/hop.keys`.

## Lesson scripts

One step per line, written `what: value`. Steps with a block (`type`, `type fast`, `paste`, `say` and `keys`) put it on the lines underneath, pushed in two spaces. If the block starts with an empty line, it starts a new line first. `#` is a note.

| Step | Does |
|---|---|
| `title: Lists` | The lesson's name (its chapter in the joined film). |
| `files: a.fathom, b.txt` | Copies these from `lessons/files` into the studia's folder first. |
| `say: ...` | Says it, with captions. Later steps carry on while it talks, but anything other than `say`, `pause` and `until ...` waits for the voice to finish. |
| `wait`, `pause: 2` | Wait for the voice to finish, or a number of seconds. |
| `card: kicker \| title \| words`, `uncard` | A title card over everything, and taking it away. |
| `new: hello.fathom`, `open: hello.fathom`, `open library: time` | Make a file, open one, or open a library's own file. |
| `clear`, `type:`, `type fast:`, `paste:` | Empty the file; type (slowly or quickly) or paste text where the caret is. |
| `line: 5`, `select: 3-5`, `keys: ctrl+end backspace enter` | Put the caret at the end of a line, select whole lines, press keys. |
| `zoom: lines 2-6`, `zoom: output`, `zoom: out` | Move the camera onto lines or an element, or back. |
| `spot: line 3`, `spot: lines 3-4`, `spot: off` | A frame around lines, to point at them. |
| `point: #run`, `click: #run`, `hide cursor` | Move the pointer there, click there, hide it. |
| `run`, `watch`, `test`, `build`, `web`, `wasm`, `profile`, `debug` | Press that button and wait until it finishes, or (debugging) pauses (`run: and keep going` doesn't wait; anything else after the colon is a note). |
| `stop at: 4`, `until paused` | Click beside a line's number to put a stop there (or take it away), and wait until the program pauses or ends. |
| `answer: Sam`, `until finished`, `focus` | Type an answer for `ask`, wait for the program to finish, give the code back the keys. |
| `game: hop.fathom \| hop.keys \| Hop!` | Play the game (filmed ahead with those keys) in a window over the studia; the lesson goes on meanwhile, and `until game ends` waits for it. |
