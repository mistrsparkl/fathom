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
- [ ] Messages for every mistake say the line and the fix (a test for each message in LANGUAGE.md)

## 7. Libraries
- [x] Dates and moments: `date in words`, `date plus months`, `seconds at`, `date at`, `time at` (dates stay text, so they sort and save)
- [ ] XML and HTML reading (`use: markup`)
- [ ] Command-line tools: options and flags from `the words given` (`use: options`)
