# Imagination

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

- `imagine game.imagine` runs a program. Nothing else is needed but Python 3.
- `imagine build game.imagine` makes it into a fast `.exe` (needs Visual Studio's C++ compiler).
- `imagine` on its own lets you try lines out one at a time.
- `imagine check game.imagine` looks for mistakes without running it.

Start with **TUTORIAL.md**. **LANGUAGE.md** lists everything the language can do. The examples are in `examples/`, and the libraries (maths, time, window, sound, web, computer, folders, patterns) are in `libraries/`.

Checking Imagination itself: `py -3 test_imagination.py` runs every test program both ways (directly and built) and checks they print exactly the same.
