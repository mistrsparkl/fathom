# Imagination

Imagination is a programming language written in plain English words. Scripts end in `.imagine`. There are two sorts of script:

- **A program** stands on its own and begins at its `to start:` command. Run it with:

  ```
  imagine examples/guess.imagine
  ```

  Imagination reads the script and does what it says, line by line. Nothing is translated and no compiler is needed. (`imagine` is `imagine.bat` in this folder, short for `py -3 imagination.py`.)

  To make a program into an `.exe` that runs fast and on its own, build it. This turns it into C++ and needs Visual Studio's C++ compiler:

  ```
  imagine build examples/guess.imagine
  ```

  A program does exactly the same thing either way. The self-check runs its test programs both ways and compares what they print.
- **A part of something else** starts with `this is part of: <thing>`, e.g. Unreal code for a creature. Turn a folder of these into C++ (`<name>.imagine.cpp`, which you never edit) with:

  ```
  py -3 imagination.py <scripts folder> <output folder>
  ```

A mistake stops with a plain message, such as:

```
follow.imagine line 31: I don't know 'walk sped'. Did you mean 'walk speed'?
```

Working examples: `examples/guess.imagine` (a guessing game), `examples/pets.imagine` (lists, kinds of things, commands that give back answers), `examples/clock.imagine` (libraries), `examples/dodge.imagine` (a game in a window) and `examples/follow.imagine` (how a deer follows the player, part of a creature).

## A program, top to bottom

```
to start:
  ask "What's your name? " into name
  greet with name
and the universe said i love you

to greet, given who (text):
  say "Hello, " plus who plus "!"
and the universe said i love you
```

## Commands that give back an answer

Add `giving back <kind>` to the first line, and leave with `give back ...`:

```
to total age of, given pets (a list of pets), giving back a number:
  set total to 0
  for each pet in pets: set total to total plus age of pet
  give back total
and the universe said i love you
```

Then use it like any value: `say "Ages added up: ", total age of shelter`. A command with one input takes it right after its name (`with` is optional). With two or more inputs, put them in brackets: `pet called with ("Rex", 3)`.

## Your own kinds of things

Describe what a kind of thing has, one part per line, then use it as a kind anywhere:

```
a pet has:
  name (text)
  age (a number)
  tricks (a list of text)
and the universe said i love you
```

| Write | Means |
|---|---|
| `set rex to a new pet` | A new pet: its numbers are 0, its text is empty, its lists are empty. |
| `name of rex` | One of its parts. `set name of rex to "Rex"` changes it. |
| `given friend (a pet)`, `(a list of pets)` | A pet as an input, or a list of them. |
| `say rex` | Shows `a pet (name: Rex, age: 3, tricks: sit)`. |

## A part of something else, top to bottom

```
note: Anything after "note:" is for people; the computer ignores it.

this is part of: creature body

settings:
  look limit: 30 degrees
  turn slew: 20 degrees per second squared

to steer toward, given goal (a place) and running (yes or no):
  set wandering to no
  if fallen: stop
  ...
and the universe said i love you
```

1. **`this is part of:`** (the first line, after notes) names the thing the script belongs to. Its words (what it already knows, like `fallen` or `walk speed`) are listed in `<name>.words` next to the script, e.g. `examples/creature body.words`.
2. **`settings:`** are named numbers you can tune. Anything after the number (`degrees`, `cm per second`) is a description for you.
3. **`to ...:`** is a command. Its lines are indented under it. After `given` come its inputs, each with its kind in brackets.
4. **`and the universe said i love you`** must follow every command's last indented line, unindented. It marks where the command ends; leaving it out is an error.

## Kinds of things

| Kind | Examples |
|---|---|
| a number | `60`, `2.5`, `walk speed`, `30 degrees` |
| yes or no | `yes`, `no`, `fallen`, `speed is more than 10` |
| a place | `centre of mass`, `goal` (a point in the world) |
| a flat place | `flat (goal minus centre of mass)` (a place with its height dropped) |
| text | `"hello"`, `name`, `"Hi " plus name` (words between quote marks) |
| a list of ... | `a list of numbers` (empty), `a list of (3, 5, 7)`, `a list of pets`. Holds one kind of thing, in order. |
| a table of ... | `a table of numbers` (empty). Looks things up by a name (text), like a phone book. |
| your own kind | `a new pet` (see above) |

Mixing kinds is an error: `set turn rate to fallen` says "'turn rate' holds a number, not yes or no."

## Lines inside a command

| Line | Means |
|---|---|
| `set gap to goal minus centre of mass` | Remember a value under a name. A new name is made the first time it is set. |
| `move turn rate toward 20 by at most 5` | Change a number toward a goal, but by no more than the step. |
| `if fallen: stop` | Do the part after the colon only when it is yes. |
| `if ...:` / `otherwise if ...:` / `otherwise:` | With indented lines below, for longer choices. |
| `say "Score: ", score` | Show things on the screen, one after another, then start a new line. |
| `ask "Your name? " into name` | Show the question and keep what the person types, as text. |
| `ask "Your age? " into age (a number)` | The same, as a number. It asks again until a number is typed. |
| `repeat 10 times:` | Do the indented lines below 10 times. |
| `while guess is not secret:` | Keep doing the indented lines below while it is yes. |
| `greet with name, 3` | Do your own command `greet`, giving it its inputs in order. A command without inputs is just its name: `greet`. |
| `for each score in scores:` | Do the indented lines once for every item of a list, with `score` being that item. |
| `for each n from 1 to 10:` | The same for each whole number from 1 to 10. |
| `add 5 to scores` | Put an item at the end of a list. |
| `remove item 2 from scores` / `remove 5 from scores` | Take out the second item / the first 5. |
| `set item 2 of scores to 9` | Change one item. Items are counted from 1. |
| `set entry "Rex" of ages to 3` | Put a value in a table under a name (replacing what was there). |
| `remove entry "Rex" from ages` | Take a name and its value out of a table. |
| `give back total` | Leave the command, giving back an answer. |
| `stop the loop` | Leave the `repeat`, `while` or `for each` it is inside, and carry on after it. |
| `skip to the next one` | Go straight to the next round of the loop it is inside. |
| `write "hello" to file "notes.txt"` | Make or replace a file with this text. |
| `add "a line" to file "log.txt"` | Add a line to the end of a file (making it if needed). |
| `stop` | Leave the command now (only in commands that don't give back anything). |
| `beep with 440, 0.5` | A word from a library (see Libraries). |
| `note: ...` | A note for people. |

## Working things out

| Write | Gives |
|---|---|
| `a plus b`, `a minus b`, `a times b`, `a divided by b` (or `+ - * /`) | arithmetic |
| `-look limit` | the negative |
| `smaller of a and b`, `larger of a and b` | the smaller or larger number |
| `clamp x between low and high` | x, kept inside the range |
| `square root of x` | the square root |
| `size of x` | a number without its sign, the length of a (flat) place, or how many letters text has |
| `random number from 1 to 100` | a random whole number, both ends included |
| `item 2 of scores` | one item of a list (counted from 1) |
| `size of scores` | how many items a list has |
| `scores contains 5`, `name contains "ell"` | yes or no: is it in the list / in the text |
| `contents of file "notes.txt"` | everything in a file, as text |
| `lines of file "notes.txt"` | the file's lines, as a list of text |
| `file "notes.txt" exists` | yes or no |
| `lines of text`, `words of text` | text split into lines or words, as a list of text |
| `answer as a number` | text turned into a number (`"42"` gives 42) |
| `score as text` | a number or yes or no written out as text |
| `letter 2 of name`, `letters 2 to 4 of name` | one letter, or some letters, of text (counted from 1) |
| `upper case of name`, `lower case of name` | text in CAPITALS / small letters (A to Z only) |
| `position of "lo" in name` | where it first appears, counted from 1 (0 if it isn't there) |
| `replace "a" with "b" in name` | text with every "a" changed to "b" |
| `line split by ", "` | text cut into a list of text at every ", " |
| `join names with ", "` | a list made into one text, with ", " between the items |
| `sorted scores`, `reversed scores` | a copy of a list, smallest first / back to front |
| `last item of scores` | the last item of a list |
| `entry "Rex" of ages` | the value a table keeps under that name |
| `keys of ages` | a table's names, as a list of text in alphabetical order |
| `ages contains "Rex"`, `size of ages` | yes or no: does the table have that name / how many names it has |
| `"Hi " plus name` | text joined together (numbers and yes or no are written out, e.g. `"Score: " plus 5`) |
| `flat (place)` | the place without its height |
| `direction of flat place` | its compass angle in degrees |
| `angle from a to b` | the turn from angle a to angle b, -180 to 180 degrees |
| `a is more than b`, `is less than`, `is at least`, `is at most`, `is`, `is not` | yes or no |
| `x and y`, `x or y`, `not x` | combining yes or no |

`of` takes everything after it until a word like `is`, `and`, `between` or `by`, except for parts and items (`age of rex plus 1` is `(age of rex) plus 1`). Use brackets to say exactly what belongs together: `(size of gap) minus stop distance`.

## Names

Names can be several words (`turn needed`, `braking speed`). They can't use the language's own words: set, to, if, otherwise, stop, note, and, or, not, is, more, less, than, at, least, most, plus, minus, times, divided, by, clamp, between, smaller, larger, of, square, root, size, flat, direction, angle, from, yes, no, move, toward, say, ask, into, repeat, while, with, random, for, each, in, contains, list, empty, new, remove, file, write, as. Some phrases are the language's too, so avoid names that start them: `entry`, `keys of`, `letter`, `letters`, `upper case`, `lower case`, `position of`, `replace`, `join`, `sorted`, `reversed`, `last item of`, `split by`.

## Adding words

A script can only use words its thing knows. New words (another part of the deer's state, a new ability) are added to the `.words` file; a new physical ability (jumping, a gallop) needs C++ underneath first, then it gets a word.

Commands can only call each other, and new kinds of things can only be described, inside programs for now.

## Programs made of several scripts

A program can use another script's commands and kinds of things:

```
use: shapes.imagine
```

The other script is looked for next to this one. It can have its own `to start:` (so it can be run and tried by itself); that part is left out when it is used. A script used more than once, even by scripts it uses itself, is read once. A mistake in a used script names it, like `shapes.imagine line 13: ...`.

## Libraries

A library gives a program more words. Put `use: <library>` near the top of the program:

```
use: time
use: maths

to start:
  wait 2 seconds
  say "Sine of 30 is ", sine of 30
and the universe said i love you
```

| Library | Words |
|---|---|
| `maths` | `pi`, `sine of`, `cosine of`, `tangent of` (degrees), `round`, `round down`, `round up`, `power of (2, 10)`, `remainder of (17, 5)` |
| `time` | `wait 2 seconds`, `seconds since start`, `hour now`, `minute now`, `second now`, `day of the month`, `month now`, `year now` |
| `window` | A window to draw in, for games and pictures. See below. |
| `web` | `web page "https://example.com"` (gives back the page as text) |
| `computer` | `beep with 440, 0.5` (pitch, seconds), `run the command "dir"` (gives back its exit number), `open "notes.txt"` (opens a file or web address), `user name` |

### The window library

```
use: window

to start:
  open a window with "My game", 800, 600
  set x to 400
  while the window is open:
    if key held "right": set x to x plus 5
    clear the window with "black"
    draw a circle with x, 300, 20, "orange"
    show the frame
and the universe said i love you
```

Places are counted in dots (pixels) from the top left corner: `x` goes right, `y` goes down.

| Words | Means |
|---|---|
| `open a window with "Title", 800, 600` | Open a window this wide and high. |
| `clear the window with "black"` | Fill the whole window with one colour. |
| `draw a box with x, y, width, height, "red"` | A filled box, from its top left corner. |
| `draw a circle with x, y, radius, "blue"` | A filled circle around a middle point. |
| `draw a line with x, y, to x, to y, "white"` | A line from one place to another. |
| `draw words with "Score: " plus score, x, y, "yellow"` | Words, from their top left corner. |
| `show the frame` | Show what was drawn, then wait so the window shows 60 frames a second. |
| `the window is open` | yes or no: becomes no when the person closes the window. |
| `key held "left"` | yes or no: is that key held down? Keys: letters, digits, `left`, `right`, `up`, `down`, `space`, `enter`, `escape`, `shift`, `control`, `tab`, `backspace`. |
| `mouse x`, `mouse y`, `mouse held` | Where the mouse is, and whether its left button is held down. |
| `close the window` | Close it yourself. |

Colours are names (`black`, `white`, `red`, `green`, `blue`, `yellow`, `orange`, `purple`, `pink`, `brown`, `grey`) or codes like `"#ff8800"` (red, green and blue, each from 00 to ff).

### Making a library

A library is a `.words` file, in `libraries/` or next to your program. Each word says what it means in C++ (for `build`) and, on an indented `runs:` line, in Python (for running directly). Anything C++ or Python can do can get an English word this way: windows, sound, the internet, games. Here is a word from `libraries/time.words`:

```
to wait, given seconds (a number) = std::this_thread::sleep_for(std::chrono::duration<double>({seconds}))
  runs: time.sleep(max(0.0, {seconds}))
```

`{seconds}` stands for the input, and `{line}` in the C++ is the number of the line using the word (for error messages). Other lines a library can have are `include: <header>` (a C++ header), `link: name` (a system library), `code:` and `python:` (helper code, indented below), and values like `pi = 3.14159, number, read only` (with their own `runs:` line). Use each input only once in the C++ line. A word without a `runs:` line only works in built programs.

## When something goes wrong while running

The program stops with the line and a plain reason, such as `Line 22: there is no item 9 in a list of 4 items. Items are counted from 1.`

Checking the translator itself: `py -3 test_imagination.py`.
