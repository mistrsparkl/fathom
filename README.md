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

- `stellanova game.stella` runs a program. Nothing else is needed but Python 3.
- `stellanova build game.stella` makes it into a fast `.exe` of machine code (needs LLVM: `winget install LLVM.LLVM`).
- `stellanova` on its own lets you try lines out one at a time.
- `stellanova check game.stella` looks for mistakes without running it.
- `stellanova test game.stella` runs its `to test ...:` commands and shows which `check` lines failed.
- `stellanova watch game.stella` runs it line by line, showing each line and the names it changes.

Start with **TUTORIAL.md**. **LANGUAGE.md** lists everything the language can do. The examples are in `examples/`, and the libraries (maths, time, window, sound, web, computer, folders, letters, patterns, server) are in `libraries/`.

Checking Stellanova itself: `py -3 test_stellanova.py` runs every test program both ways (directly and built) and checks they print exactly the same.

`stellanova build game.stella` makes machine code: Stellanova writes LLVM code for the program and LLVM's clang
turns it into an .exe (install LLVM: `winget install LLVM.LLVM`). What every program needs is in `runtime/machine.cpp`,
compiled once, and it frees values a program no longer uses. A library word's own C++ is compiled into a small
function the machine code calls; the program's own code never becomes C++.
