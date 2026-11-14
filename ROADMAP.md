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
- [ ] The web build gets the words it lacks (database included)

## 4. Tools
- [ ] Debugger: stop at a line, step, look at names (studio)
- [ ] Profiler: which lines take the time
- [ ] WebAssembly output; building for other systems
