# Fathom

Fathom is a programming language you write in plain English. Here's a guessing game:

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

## Installing

Windows, in PowerShell:

```
irm https://raw.githubusercontent.com/mistrsparkl/fathom/main/install.ps1 | iex
```

Linux:

```
curl -fsSL https://raw.githubusercontent.com/mistrsparkl/fathom/main/install.sh | sh
```

That gets you the `fathom` command and Fathom Studia, the editor. It'll grab Python if you don't have it, and the compiler stuff that makes programs fast. Open Studia and hit Learn if you're new.

You can uninstall it from Apps & features on Windows, or with `sh ~/.local/share/fathom/uninstall.sh` on Linux.

If you'd rather not use the installer, clone this repo and put the folder on your PATH. You only need Python 3.

## Commands

```
fathom game.fathom          run it
fathom                      try lines out one at a time
fathom check game.fathom    find mistakes without running
fathom tidy game.fathom     fix the spacing
fathom test game.fathom     run its tests
fathom watch game.fathom    step through it line by line
fathom build game.fathom    make an .exe
fathom wasm game.fathom     make WebAssembly
```

Programs get built into machine code when LLVM is around, which is a lot faster. The first run after you change something takes about half a second longer while it builds.

You can also use Fathom inside Unity, Unreal and Godot. Run `fathom unity <project>` (or `unreal`, or `godot`) and it sets the project up. There's more in `libraries/engine.words`.

## Where things are

New? Read TUTORIAL.md. LANGUAGE.md has everything. There are example programs in `examples/` and the libraries are in `libraries/`.

Studia lives in `editor/studia`, and it's written in Fathom too. To run it from the repo: `npm install` once, then `npm start`.

There's also a VS Code extension: `py -3 editor/make_vsix.py`, then `code --install-extension editor/fathom.vsix`.

`py -3 test_fathom.py` runs the tests.
