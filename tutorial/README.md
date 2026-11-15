# The Stellanova tutorial film

A film that goes through every part of the language, in Stellanova Studio, with a spoken voice and captions, and ends
by making a platform game (`lessons/files/hop.stella`). Each lesson is a script; the recorder plays it in the studio
(typing, running, zooming in) and films it.

Needs: Node with the studio's Electron (`cd editor/studio && npm install`), ffmpeg, and `py -3 -m pip install edge-tts`
(the voice is Microsoft Edge's online voice `en-US-AndrewNeural`, so speaking new lines needs the internet; spoken lines
are kept in `out/voice` and only new or changed ones are sent).

```
py -3 check_lessons.py lessons/*.lesson          # try the lessons' programs without filming (-v shows each zoom's lines)
cd ../editor/studio
npx electron ../../tutorial/recorder.js ../../tutorial/lessons/*.lesson    # films out/parts/<lesson>.mp4
cd ../../tutorial
py -3 join.py                                     # out/Stellanova Tutorial.mp4, a chapter per lesson
```

`py -3 make_hop_lesson.py` writes `lessons/16-platformer.lesson` from the game itself (and the `records.stella` script it uses), so its line numbers stay right
when the game changes. Games are filmed by the game itself: the window library's demo mode (`STELLANOVA_DEMO_FRAMES`,
`STELLANOVA_DEMO_KEYS`) writes every frame and presses keys from a list like `lessons/files/hop.keys`.

## Lesson scripts

One step per line, `what: value`. Blocks (for `type`, `type fast`, `paste`, `say` and `keys`) go on the lines below,
indented two spaces; a block starting with an empty line starts a new line first. `#` starts a note.

| Step | Does |
|---|---|
| `title: Lists` | The lesson's name (its chapter in the joined film). |
| `files: a.stella, b.txt` | Copies these from `lessons/files` into the studio's folder first. |
| `say: ...` | Speaks it, with captions. The steps after it go on while it is spoken, but every step except `say`, `pause` and `until ...` waits for the voice to finish first. |
| `wait`, `pause: 2` | Wait for the voice to finish, or a number of seconds. |
| `card: kicker \| title \| words`, `uncard` | A title card over everything, and taking it away. |
| `new: hello.stella`, `open: hello.stella`, `open library: time` | Make a file, open one, or open a library's own file. |
| `clear`, `type:`, `type fast:`, `paste:` | Empty the file; type (slowly or quickly) or paste text where the caret is. |
| `line: 5`, `select: 3-5`, `keys: ctrl+end backspace enter` | Put the caret at the end of a line, select whole lines, press keys. |
| `zoom: lines 2-6`, `zoom: output`, `zoom: out` | Move the camera onto lines or an element, or back. |
| `spot: line 3`, `spot: lines 3-4`, `spot: off` | A frame around lines, to point at them. |
| `point: #run`, `click: #run`, `hide cursor` | Move the pointer there, click there, hide it. |
| `run`, `watch`, `test`, `build`, `web`, `wasm`, `profile`, `debug` | Press that button and wait until it finishes, or (debugging) pauses (`run: and keep going` doesn't wait; anything else after the colon is a note). |
| `stop at: 4`, `until paused` | Click beside a line's number to put a stop there (or take it away), and wait until the program pauses or ends. |
| `answer: Sam`, `until finished`, `focus` | Type an answer for `ask`, wait for the program to finish, give the code back the keys. |
| `game: hop.stella \| hop.keys \| Hop!` | Play the game (filmed ahead with those keys) in a window over the studio; the lesson goes on meanwhile, and `until game ends` waits for it. |
