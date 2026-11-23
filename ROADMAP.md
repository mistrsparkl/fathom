# Roadmap

Everything here has to work three ways (run straight from the script, built into an .exe, and on the web) unless it says otherwise. It also needs tests in `test_fathom.py` and a write-up in LANGUAGE.md.

## Done

The language
- [x] `insert x at 2 in xs`
- [x] Commands written right where you use them (`each x becomes x times 2`)
- [x] Kinds that hold any kind (`a pair of (a number, text)`, `a stack of anything`)
- [x] Powers, bitwise maths, and whole numbers of any size
- [x] Bytes (`the bytes of the file`, `the text of the bytes`)
- [x] Kinds of problem (`raise a fuel problem with ...`, `if that went wrong with a fuel problem:`)
- [x] Commands for a kind of thing kept as values
- [x] `if s is a dog:`
- [x] Hidden parts (`balance (a number, hidden)`)
- [x] Commands kept to their own script (`to tidy, privately:`)

Reaching other stuff
- [x] Calling C libraries and DLLs
- [x] Calling Python packages (only when running straight from the script)
- [x] Sockets: TCP, UDP and WebSockets
- [x] Threads that share things, with locks
- [x] `fathom get <library>`

Libraries
- [x] Animation, physics, sound making, pictures
- [x] 3D: models (.obj, .gltf, .glb with bones and motions), textures, shaders, lights, cameras
- [x] Zip, hashing, encryption, JSON paths, email
- [x] Desktop forms
- [x] Dates, XML and HTML, command-line options
- [x] File facts and path parts (`last change of the file`, `file name of path`)
- [x] `"ab" repeated 3 times`, `flattened xs`
- [x] Any web request (`ask the web with (address, "POST", message, headers)`) and headers
- [x] A web server that can answer more than one person at a time
- [x] Every library word works on the web too, apart from C libraries and Python packages

Tools
- [x] Debugger and profiler, in Studia and on the command line
- [x] WebAssembly, `meanwhile` included
- [x] Linux, with windows, sound, forms and pictures
- [x] VS Code: mistakes while you type, word suggestions, help when you hover
- [x] `fathom tidy`
- [x] Every whole program in LANGUAGE.md gets checked by the tests
- [x] Mistake messages never show C++, Python or JavaScript words

Things real programs needed (from writing `todo.fathom`, `guestbook.fathom` and `spending.fathom`)
- [x] `folder "saves" exists`
- [x] Output shows up straight away, even when it's going to a file
- [x] `sorted totals by amount, biggest first`, and sorting by anything (`by each n becomes ...`)
- [x] `"food" padded to 12 letters`
- [x] `the web way` and `answer with the status 404` in the web server
- [x] Text in any alphabet, and emoji
- [x] Database errors that say what went wrong in plain words

Speed
- [x] Built lists of numbers hold plain numbers
- [x] Number loops as fast as C++
- [x] Lists of text and of things (faster than Python; sorting 1M texts takes a fifth of the time)

## Not done

- [ ] macOS. It needs a Mac to test on.

Big games (as well as small ones)
- [ ] As fast as C++ when making many values: numbers and small things kept inside lists and other things, not each on its own
- [ ] Control over memory where it matters: values a program frees itself, and blocks of things laid out side by side
- [ ] Finding slow parts: a built program says where its time went
- [ ] A debugger: stop at a line, look at names, go on line by line
- [ ] Large programs: many files built quickly, only the changed ones again
- [ ] Consoles. They need the makers' kits to build and test on.
