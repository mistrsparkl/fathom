# Cosmonova

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

- `cosmonova game.cosmos` runs a program. Nothing else is needed but Python 3.
- `cosmonova build game.cosmos` makes it into a fast `.exe` (needs Visual Studio's C++ compiler).
- `cosmonova` on its own lets you try lines out one at a time.
- `cosmonova check game.cosmos` looks for mistakes without running it.

Start with **TUTORIAL.md**. **LANGUAGE.md** lists everything the language can do. The examples are in `examples/`, and the libraries (maths, time, window, sound, web, computer, folders, letters, patterns, server) are in `libraries/`.

Checking Cosmonova itself: `py -3 test_cosmonova.py` runs every test program both ways (directly and built) and checks they print exactly the same.
