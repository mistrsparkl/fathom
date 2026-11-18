# Stellanova

A programming language written in plain English words.

```
genesis:
  scrawl "I'm thinking of a number from 1 to 100."
  set secret to random number from 1 to 100
  set guess to 0
  as long as guess is not secret:
    ask "Your guess? " into guess (a number)
    if guess falls below secret: scrawl "Too low."
    if guess exceeds secret: scrawl "Too high."
  scrawl "You got it!"
and the universe said i love you
```

- `stellanova game.stella` runs a program. Nothing else is needed but Python 3. With LLVM, it runs as fast machine code: the first run after a change takes about half a second longer.
- `stellanova build game.stella` makes it into a fast `.exe` of machine code (needs LLVM: `winget install LLVM.LLVM`).
- `stellanova wasm game.stella` makes the same machine code as WebAssembly: `node game.mjs` runs it (see LANGUAGE.md).
- `stellanova unity <project>`, `stellanova unreal <project>` or `stellanova godot <project>` lets that game engine run Stellanova programs (`use: engine`; see `libraries/engine.words`).
- `stellanova` on its own lets you try lines out one at a time.
- `stellanova check game.stella` looks for mistakes without running it.
- `stellanova tidy game.stella` puts its spacing right: two spaces for each step in, one empty line between parts.
- `stellanova test game.stella` runs its `to test ...:` commands and shows which `check` lines failed.
- `stellanova watch game.stella` runs it line by line, showing each line and the names it changes.

Start with **TUTORIAL.md**. **LANGUAGE.md** lists everything the language can do. The examples are in `examples/`, and the libraries (maths, time, window, sound, web, computer, folders, letters, patterns, server) are in `libraries/`.

**Stellanova Studia** (`editor/studia`) is a place to write programs, like Visual Studio Code but only for Stellanova, and it is written in Stellanova too: `screens.stella` is the editing box, tabs, files, words and output, and `system.stella` reads and writes files, looks for mistakes and runs programs. Start it with `npm install` once, then `npm start` in `editor/studia`.

**Visual Studio Code**: `py -3 editor/make_vsix.py`, then `code --install-extension editor/stellanova.vsix`. It colours `.stella` files, shows mistakes while you type, completes words and explains a word when the mouse is on it. The setting `stellanova.home` is the folder with `stellanova.py`, if it has moved since the extension was made.

Checking Stellanova itself: `py -3 test_stellanova.py` runs every test program both ways (directly and built) and checks they print exactly the same.

`stellanova build game.stella` makes an .exe with LLVM (install it: `winget install LLVM.LLVM`). The runtime is `runtime/machine.cpp`.
