# Roadmap: making Stellanova limitless

Each item works running directly, built (.exe) and on the web unless it says otherwise, has tests in
`test_stellanova.py`, and is in LANGUAGE.md. When all are done: a tutorial chapter for each group, and the tutorial's
platformer (`tutorial/lessons/files/hop.stella`) rewritten to use everything the tutorial teaches.

## 1. The language itself
- [x] `insert x at 2 in xs`
- [x] Commands written where they're used (`each x becomes x times 2`, for `changed by`, `kept by`, `sorted ... by`, inputs)
- [x] Kinds for any kind (`a pair of (a number, text)`, `a stack of anything`): kinds with a kind as an input
- [x] Numbers: `to the power`, bitwise `and`/`or`/`exclusive or`/shifts, whole numbers of any size
- [x] Bytes: lists of numbers from 0 to 255 (`the bytes of the file`, `fill the file`, `the bytes of the text`, `the text of the bytes`)
- [x] Kinds of problem: `raise a <kind> with ...`, `if that went wrong with a <kind>:`
- [x] Commands for a kind of thing kept as values

## 2. Reaching everything else
- [x] Call any C library / DLL from a program (`use the library "user32.dll"` and a word for each function)
- [x] Call any Python package when running directly (`use python: numpy`)
- [x] Sockets: TCP, UDP, WebSockets (`use: network`)
- [x] Threads that share things, with locks (`holding the lock "x":`)
- [x] A package manager: `stellanova get <library>`

## 3. Libraries
- [x] Animation: easing, tweens, sprite sheets (`use: animation`, `etch the sheet frame`)
- [x] Physics: bodies, collisions, gravity (`use: physics.stella`, written in Stellanova)
- [x] Sound making: tones, effects, recording (`use: sound making`)
- [x] Pictures: load, change dots, save (`use: pictures`)
- [x] 3D models (.obj), textures, shaders, lights and cameras (window library: models, pictures in space, shader commands, light, eye view)
- [x] Compression (zip), hashing, encryption, JSON paths, email (`use: zip`, `hashing`, `encryption`, `json`, `email`)
- [x] Desktop forms: buttons, fields, lists in a window
- [x] The web build gets the words it lacks (database included): every library word works on the web (C libraries and Python packages can't)

## 4. Tools
- [x] Debugger: stop at a line, step, look at names (studio): `stellanova debug`, and Debug in the studio
- [x] Profiler: which lines take the time (`stellanova profile`)
- [x] WebAssembly output (`stellanova wasm`: WASI, run by node or wasmtime; the libraries that use Windows itself, and `meanwhile`, not yet)
- [x] Linux: `stellanova build` run on Linux (WSL Ubuntu, clang) makes a Linux program; the language passes the built-vs-direct checks
- [x] Linux libraries without a screen: computer, database, email, network, server, web
- [x] Linux libraries with a screen or speakers: sound, sound making, window (X11, FreeType, libpng, GLX)
- [x] Linux: forms (GTK 3), pictures (libpng), screen (Tkinter + Pillow)
- [x] Speed: built lists of numbers hold plain numbers; direct runs write each command as one Python function (`STELLANOVA_NO_FAST=1` runs them the old way)
- [ ] macOS: needs its sysroot, and a Mac to test on

# Roadmap 2: easier to write, bigger programs

## 5. The language
- [x] Asking which kind a thing is: `if s is a dog:` (kinds of a dog count too)
- [x] Parts only a kind's own commands can use: `balance (a number, hidden)`

## 6. Writing programs
- [x] VS Code: mistakes shown while typing, word completion and help on hover (`editor/vscode/extension.js`)
- [x] `stellanova tidy`: puts a script's spacing and indenting right
- [x] Every whole program in LANGUAGE.md (one with `genesis:`) is checked for mistakes by the tests, as TUTORIAL.md's are

## 7. Libraries
- [x] Dates and moments: `date in words`, `date plus months`, `seconds at`, `date at`, `time at` (dates stay text, so they sort and save)
- [x] XML and HTML reading (`use: markup.stella`)
- [x] Command-line tools: `--loud` and `--size=3` from `the words given` (`use: options.stella`)

# Roadmap 3: everyday jobs, in plain words

Every word added here must read plainly to someone who has never programmed: one obvious way to do each thing,
a one-line example in LANGUAGE.md, and a mistake message that says how to fix it.

## 8. Files and folders
- [x] Facts about a file: `bytes in the file "notes.txt"` (it was there already), `last change of the file "notes.txt"` (a moment)
- [x] Parts of a path: `file name of path`, `extension of path`, `folder holding path`

## 9. Text and lists
- [x] `"ab" repeated 3 times`
- [x] `flattened xs`: a list of lists as one list

## 10. The web
- [x] Any web request: `ask the web with (address, "POST", message, headers)` gives the answer; `the last web status` is its number (library words can now have inputs that are usually left out)

## 11. Reading easily
- [x] Mistake messages checked for plain words: no C++, Python or JavaScript words reach the person writing (`plain_word_checks` in the tests)

# Roadmap 4: what real programs needed

From writing `examples/todo.stella`, `guestbook.stella` and `spending.stella`. Simple and readable first.

- [x] One way to ask whether something is there: `folder "saves" exists`, like `file "notes.txt" exists` (`there is a folder` goes)
- [x] Output shows straight away, even when it goes to a file or another program
- [x] `for each` can use a name the command already has: each item inside the loop, what it was after it
- [x] `sorted totals by amount, biggest first` (and `sorted scores, biggest first`)
- [x] Text padded to a width: `"food" padded to 12 letters`
- [x] The web server: `the web way` says how it was asked ("GET", "POST"...), `answer with the status 404` says a page isn't there, and saved text goes as data, not as a page

# Roadmap 5: the rest (speed last)

- [x] Sorting by a worked-out value: `sorted names by each n becomes the size of n`
- [x] Headers: `the web header "X-Pet"` in a server's answer, `the last web header "Content-Type"` after `ask the web`
- [x] The web server answers several people at once (reading and sending side by side; `answer` one at a time, so no locks are needed)
- [x] Markup: `<li>`, `<p>`, `<td>` and the like end when the next one starts, as browsers do
- [x] Every library word works on the web, apart from C libraries and Python packages (they all did; the 3 skipped test programs use C libraries or a test library made without web lines)
- [x] `meanwhile` in WebAssembly (built for wasm32-wasip1-threads; the runner starts a Node worker for each thread)
- [x] Text in any language and emoji: every text word counts letters, not bytes (they did; `upper case of` now changes every alphabet, not only a to z)
- [ ] Big programs: commands kept to their own script (`to ..., privately:`), clear messages when two scripts use the same name
- [ ] Messages from databases, mail servers and the system start with plain words saying what failed
- [ ] The VS Code extension tried in VS Code itself
- [ ] The tutorial teaches what roadmaps 2 to 4 added; BLOG.md brought up to date
- [ ] Speed: lists of text and things, and direct runs, measured and made faster
