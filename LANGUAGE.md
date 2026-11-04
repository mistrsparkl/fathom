# Imagination

Imagination is a programming language written in plain English words. Scripts end in `.imagine`. There are two sorts of script:

- **A program** stands on its own and begins at its `genesis:` command. Run it with:

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

- **Checking for mistakes** without running: `imagine check examples/guess.imagine`.
- **Trying things out:** type just `imagine` for a prompt. Each line you type is done straight away, and names are kept from line to line. Type a value on its own (`5 plus 3`) to see it. A line ending in `:` takes the indented lines after it, finished with an empty line. `bye` finishes.

A mistake stops with a plain message, such as:

```
follow.imagine line 31: I don't know 'walk sped'. Did you mean 'walk speed'?
```

Working examples: `examples/guess.imagine` (a guessing game), `examples/pets.imagine` (lists, kinds of things, commands that give back answers), `examples/clock.imagine` (libraries), `examples/dodge.imagine` (a game in a window) and `examples/follow.imagine` (how a deer follows the player, part of a creature).

## A program, top to bottom

```
genesis:
  ask "What's your name? " into name
  greet with name
and the universe said i love you

to greet, given who (text):
  scrawl "Hello, " plus who plus "!"
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

Then use it like any value: `scrawl "Ages added up: ", total age of shelter`. A command with one input takes it right after its name (`with` is optional). With two or more inputs, put them in brackets: `pet called with ("Rex", 3)`.

**Commands for a kind of thing.** `to bounce, for a ball:` makes a command that belongs to balls. Inside it, the ball's parts are used by their own names, and changing them changes the ball it was given, not a copy:

```
to bounce, for a ball:
  set speed to speed times -1
  set bounces to bounces plus 1
and the universe said i love you
```

Call it with the ball: `bounce b`, or `bounce item 1 of balls`. More inputs come after `given`, as usual: `to move along, for a ball, given steps (a number):`, called as `move along with b, 2`. Inside, the whole ball is `ball`.

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
| `set rex to conjure a pet` | A new pet: its numbers are 0, its text is empty, its lists are empty. |
| `name of rex` | One of its parts. `set name of rex to "Rex"` changes it. |
| `given friend (a pet)`, `(a list of pets)` | A pet as an input, or a list of them. |
| `scrawl rex` | Shows `a pet (name: Rex, age: 3, tricks: sit)`. |

**Kinds of kinds.** A kind of thing can be a kind of another one. It has all of the other's parts, and more of its own:

```
a dog is a kind of pet that has:
  tricks (a list of text)
and the universe said i love you

a puppy is a kind of dog:
and the universe said i love you
```

A dog has a name and an age (because every pet has) and tricks. Commands for a pet (`to speak, for a pet:`) work on dogs and puppies too. A dog can have its own version, `to speak, for a dog:`, which dogs (and puppies) use instead; every version takes the same other inputs. Elsewhere a dog stays a dog: an input `(a pet)` or a list of pets can't hold one.

## A part of something else, top to bottom

```
whisper: Anything after "note:" is for people; the computer ignores it.

this is part of: creature body

settings:
  look limit: 30 degrees
  turn slew: 20 degrees per second squared

to steer toward, given goal (a place) and running (yes or no):
  set wandering to no
  if fallen: cease
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
| yes or no | `yes`, `no`, `fallen`, `speed exceeds 10` |
| a place | `1 horizontal 2 vertical 3 depth`, `centre of mass`, `goal` (a point in space: across, down and deep) |
| a flat place | `300 horizontal 200 vertical`, `flat (goal minus centre of mass)` (across and down only) |
| text | `"hello"`, `name`, `"Hi " plus name` (words between quote marks) |
| a list of ... | `a list of numbers` (empty), `a list of (3, 5, 7)`, `a list of pets`. Holds one kind of thing, in order. |
| a table of ... | `a table of numbers` (empty). Looks things up by a name (text), like a phone book. |

**birth and existence.** `set birth to 300 horizontal 200 vertical` says where something starts, and puts `existence` (where it is now) at the same place. Move `existence`, and `set existence to birth` sends it back.

Your own kinds of things can have them too. Give the kind a `birth` part and it gets an `existence` part by itself:

```
a ball has:
  birth (a flat place)
  speed (a number)
and the universe said i love you
```

`set birth of ball to 100 horizontal 50 vertical` puts the ball's existence there too. Then move `existence of ball`, and `(existence of ball) of horizontal` is how far across it is.

Lists and tables can hold other lists and tables: `a list of lists of numbers` is a grid, and `item 2 of item 3 of grid` reaches inside it. When shown, the inner ones are in brackets: `(1, 2), (3, 4)`.
| your own kind | `conjure a pet` (see above) |

Mixing kinds is an error: `set turn rate to fallen` says "'turn rate' holds a number, not yes or no."

## Lines inside a command

| Line | Means |
|---|---|
| `set gap to goal minus centre of mass` | Remember a value under a name. A new name is made the first time it is set. |
| `move turn rate toward 20 by at most 5` | Change a number toward a goal, but by no more than the step. |
| `if fallen: cease` | Do the part after the colon only when it is yes. |
| `if ...:` / `otherwise if ...:` / `otherwise:` | With indented lines below, for longer choices. |
| `scrawl "Score: ", score` | Show things on the screen, one after another, then start a new line. |
| `ask "Your name? " into name` | Show the question and keep what the person types, as text. |
| `ask "Your age? " into age (a number)` | The same, as a number. It asks again until a number is typed. |
| `ask "Again? " into again (yes or no)` | The same, as yes or no (`yes`, `y`, `no` or `n`). |
| `echo 10 times:` | Do the indented lines below 10 times. |
| `as long as guess is not secret:` | Keep doing the indented lines below while it is yes. |
| `greet with name, 3` | Do your own command `greet`, giving it its inputs in order. A command without inputs is just its name: `greet`. |
| `for each score in scores:` | Do the indented lines once for every item of a list, with `score` being that item. |
| `for each n from 1 to 10:` | The same for each whole number from 1 to 10. |
| `gather 5 into scores` | Put an item at the end of a list. |
| `banish item 2 from scores` / `banish 5 from scores` | Take out the second item / the first 5. |
| `set item 2 of scores to 9` | Change one item. Items are counted from 1. |
| `set entry "Rex" of ages to 3` | Put a value in a table under a name (replacing what was there). |
| `banish entry "Rex" from ages` | Take a name and its value out of a table. |
| `give back total` | Leave the command, giving back an answer. |
| `shatter with "the tank is empty"` | Stop with a problem of your own. `try:` catches it like any other, and `the wound` is its text. |
| `break free` | Leave the `echo`, `as long as` or `for each` it is inside, and carry on after it. |
| `move on` | Go straight to the next round of the loop it is inside. |
| `inscribe "hello" into file "notes.txt"` | Make or replace a file with this text. |
| `gather "a line" into file "log.txt"` | Add a line to the end of a file (making it if needed). |
| `cease` | Leave the command now (only in commands that don't give back anything). |
| `beep with 440, 0.5` | A word from a library (see Libraries). |
| `whisper: ...` | A note for people. |

## Working things out

| Write | Gives |
|---|---|
| `a plus b`, `a minus b`, `a times b`, `a divided by b` (or `+ - * /`) | arithmetic |
| `-look limit` | the negative |
| `smaller of a and b`, `larger of a and b` | the smaller or larger number |
| `clamp x between low and high` | x, kept inside the range |
| `square root of x` | the square root |
| `size of x` | a number without its sign, the distance of a place from 0 horizontal 0 vertical 0 depth, the length of a (flat) place, or how many letters text has |
| `random number from 1 to 100` | a random whole number, both ends included |
| `item 2 of scores` | one item of a list (counted from 1) |
| `a random item of scores` | one item of a list, picked at random |
| `size of scores` | how many items a list has |
| `scores contains 5`, `name contains "ell"` | yes or no: is it in the list / in the text |
| `contents of file "notes.txt"` | everything in a file, as text |
| `lines of file "notes.txt"` | the file's lines, as a list of text |
| `file "notes.txt" exists` | yes or no |
| `lines of text`, `words of text` | text split into lines or words, as a list of text |
| `answer as a number` | text turned into a number (`"42"` gives 42) |
| `score as text` | a number or yes or no written out as text |
| `(price times 1.2) rounded to 2 places` | a number rounded to that many decimal places (halves go up, away from zero) |
| `letter 2 of name`, `letters 2 to 4 of name` | one letter, or some letters, of text (counted from 1) |
| `upper case of name`, `lower case of name` | text in CAPITALS / small letters (A to Z only) |
| `trimmed line` | text without the spaces, tabs and line breaks at its start and end |
| `name begins with "Dr"`, `name ends with ".txt"` | yes or no |
| `position of "lo" in name` | where it first appears, counted from 1 (0 if it isn't there) |
| `replace "a" with "b" in name` | text with every "a" changed to "b" |
| `line split by ", "` | text cut into a list of text at every ", " |
| `join names with ", "` | a list made into one text, with ", " between the items |
| `sorted scores`, `reversed scores` | a copy of a list, smallest first / back to front |
| `last item of scores` | the last item of a list |
| `sum of scores`, `average of scores`, `biggest of scores`, `smallest of scores` | worked out from a list of numbers |
| `sorted pets by age` | a copy of a list of things, smallest part first (things with the same part keep their order) |
| `entry "Rex" of ages` | the value a table keeps under that name |
| `keys of ages` | a table's names, as a list of text in alphabetical order |
| `ages contains "Rex"`, `size of ages` | yes or no: does the table have that name / how many names it has |
| `"Hi " plus name` | text joined together (numbers and yes or no are written out, e.g. `"Score: " plus 5`) |
| `p of horizontal`, `p of vertical`, `p of depth` | one part of a place: across, down (on a screen, down is more), deep. `set p of horizontal to 5` changes it. |
| `p plus q`, `p minus q`, `p times 2`, `p divided by 2`, `-p` | places added, taken away, made bigger or smaller |
| `flat (place)` | the place without its height |
| `direction of flat place` | its compass angle in degrees |
| `angle from a to b` | the turn from angle a to angle b, -180 to 180 degrees |
| `a exceeds b`, `falls below`, `is at least`, `is at most`, `is`, `is not` | yes or no |
| `existence is within 30 of coin` | yes or no: are two places (or numbers) 30 or less apart? Good for things touching. |
| `ball touches coin` | yes or no: do two things' circles overlap? Each needs a `birth` (giving it an `existence`) and a `radius`. A place on its own counts as a dot (or uses `radius`, inside a thing's command). |
| `x and y`, `x or y`, `not x` | combining yes or no |

`of` takes everything after it until a word like `is`, `and`, `between` or `by`, except for parts and items (`age of rex plus 1` is `(age of rex) plus 1`). Use brackets to say exactly what belongs together: `(size of gap) minus stop distance`.

## Names

Names can be several words (`turn needed`, `braking speed`). They can't use the language's own words: and, angle, as, ask, at, banish, between, by, cease, clamp, conjure, contains, depth, direction, divided, each, echo, empty, exceeds, falls, file, flat, for, from, gather, horizontal, if, in, inscribe, into, is, larger, least, less, list, minus, more, most, move, new, no, not, note, of, or, otherwise, plus, random, remove, repeat, root, scrawl, set, size, smaller, square, stop, than, times, to, toward, try, vertical, while, whisper, with, wound, write, yes. Some phrases are the language's too, so avoid names that start them: `entry`, `keys of`, `sum of`, `average of`, `biggest of`, `smallest of`, `rounded to`, `letter`, `letters`, `upper case`, `lower case`, `position of`, `replace`, `join`, `sorted`, `reversed`, `last item of`, `split by`.

## Adding words

A script can only use words its thing knows. New words (another part of the deer's state, a new ability) are added to the `.words` file; a new physical ability (jumping, a gallop) needs C++ underneath first, then it gets a word.

In a part of something else, commands can call each other too; the top of the C++ it makes lists what the class's header must declare. New kinds of things can only be described inside programs for now.

## Programs made of several scripts

A program can use another script's commands and kinds of things:

```
use: shapes.imagine
```

The other script is looked for next to this one. It can have its own `genesis:` (so it can be run and tried by itself); that part is left out when it is used. A script used more than once, even by scripts it uses itself, is read once. A mistake in a used script names it, like `shapes.imagine line 13: ...`.

## Libraries

A library gives a program more words. A library loads by itself as soon as the program uses one of its words; `use: <library>` near the top says so out loud:

```
use: time
use: maths

genesis:
  wait 2 seconds
  scrawl "Sine of 30 is ", sine of 30
and the universe said i love you
```

| Library | Words |
|---|---|
| `maths` | `pi`, `sine of`, `cosine of`, `tangent of` (degrees), `round`, `round down`, `round up`, `whole part of`, `power of (2, 10)`, `remainder of (17, 5)`, `e`, `logarithm of` (base 10), `natural logarithm of`, `arc sine of`, `arc cosine of`, `arc tangent of` (degrees) |
| `time` | `wait 2 seconds`, `seconds since start`, `hour now`, `minute now`, `second now`, `day of the month`, `month now`, `year now`, `today` (like `2026-11-04`), `the time now` (like `14:05:09`), `day of the week` (like `Wednesday`), `seconds since 1970` |
| `window` | A window to etch in, for games and pictures. See below. |
| `web` | `web page "https://example.com"` (gives back the page as text), `download with "https://example.com/cat.png", "cat.png"` (into a file), `send to the web page with (address, message)` (sends text, gives back the answer) |
| `sound` | `play the sound with "boom.wav"`, `play the sound and wait with "boom.wav"`, `play the sound again and again with "music.wav"`, `stop the sound` (stops them all). Sounds play on top of each other, so a game can have many at once. .wav or .mp3 files. |
| `computer` | `beep with 440, 0.5` (pitch, seconds), `run the command "dir"` (gives back its exit number), `open "notes.txt"` (opens a file or web address), `user name`, `output of the command "dir"` (what it printed, as text), `the words given` (a list of the words typed after the program's name: `imagine game.imagine easy 3`), `environment value of "PATH"`, `current folder`, `end the program with 0` (stops at once, giving that exit number) |
| `folders` | `files in the folder "saves"`, `folders in the folder "saves"` (lists of names, in order), `there is a folder "saves"`, `make the folder "saves/old"`, `erase the file "a.txt"`, `erase the folder "old"` (and everything in it), `move the file with "a.txt", "b.txt"` (moves or renames), `copy the file with "a.txt", "b.txt"`, `bytes in the file "a.txt"` |
| `patterns` | Finding text by its shape (`"[0-9]+"` is one or more digits, `"."` any letter, `"(...)"` a piece to keep): `the pattern fits with ("[0-9]+", line)` (yes or no), `matches of the pattern with ("[0-9]+", line)` (every match, as a list of text), `pieces of the pattern with ("([a-z]+)=([0-9]+)", line)` (the bracketed pieces of the first match), `replace the pattern with ("[0-9]+", line, "#")` |

### The window library

```
use: window

genesis:
  open a world with "My game", 800, 600
  set x to 400
  as long as the world lives:
    if key held "right": set x to x plus 5
    consume the window with "black"
    etch a circle with x, 300, 20, "orange"
    reveal the frame
and the universe said i love you
```

Places are counted in dots (pixels) from the top left corner: `x` goes right, `y` goes down.

| Words | Means |
|---|---|
| `open a world with "Title", 800, 600` | Open a window this wide and high. |
| `etch the picture turned with "ship.png", 300, 200, 2, 45` | The picture with its middle at 300, 200, twice as big, turned 45 degrees clockwise. (Running directly, this needs Pillow: `py -3 -m pip install pillow`.) |
| `frame time` | How many seconds the last frame took (about 0.0167 at 60 frames a second). Moving by `speed times frame time times 60` keeps things the same speed even when the computer is slow. |
| `width of the world`, `height of the world` | How big the window is, in dots. |
| `existence touches a side`, `existence touches the top or bottom` | yes or no: is a thing this place is the middle of touching (or past) the window's left or right edge, or its top or bottom? It uses `radius` for how far the thing reaches from its middle, so `set radius to 20` first, and etch the circle with `radius` too. |
| `etch a square with 300, 200, 20, "purple"` | A square with its middle at 300, 200, reaching 20 from its middle to each side (like a circle's radius). |
| `set the text size to 32` | Words etched after this are 32 dots high (16 at first). |
| `consume the window with "black"` | Fill the whole window with one colour. |
| `etch a box with x, y, width, height, "red"` | A filled box, from its top left corner. |
| `etch a circle with x, y, radius, "blue"` | A filled circle around a middle point. |
| `etch a line with x, y, to x, to y, "white"` | A line from one place to another. |
| `etch words with "Score: " plus score, x, y, "yellow"` | Words, from their top left corner. |
| `etch the picture with "ship.png", x, y` | A picture (.png or .gif), at its own size, from its top left corner. |
| `width of picture "ship.png"`, `height of picture "ship.png"` | A picture's size in dots. |
| `reveal the frame` | Show what was etched, then wait so the window shows 60 frames a second. |
| `the world lives` | yes or no: becomes no when the person closes the window. |
| `key held "left"` | yes or no: is that key held down? Keys: letters, digits, `left`, `right`, `up`, `down`, `space`, `enter`, `escape`, `shift`, `control`, `tab`, `backspace`. |
| `consume the window with "black"` | The same as `consume the window with`. |
| `mouse x`, `mouse y`, `mouse held` | Where the mouse is, and whether its left button is held down. |
| `key pressed "space"`, `mouse clicked` | yes or no: was the key pressed (or the mouse button clicked) since the frame before? Yes for one frame only, so one press does one thing. |
| `end the world` | Close it yourself. |

Colours are names (`black`, `white`, `red`, `green`, `blue`, `yellow`, `orange`, `purple`, `pink`, `brown`, `grey`) or codes like `"#ff8800"` (red, green and blue, each from 00 to ff).

### Making a library

A library is a `.words` file, in `libraries/` or next to your program. Each word says what it means in C++ (for `build`) and, on an indented `runs:` line, in Python (for running directly). Anything C++ or Python can do can get an English word this way: windows, sound, the internet, games. Here is a word from `libraries/time.words`:

```
to wait, given seconds (a number) = std: : this_thread: : sleep_for(std: : chrono: : duration<double>({seconds}))
  runs: time.sleep(max(0.0, {seconds}))
```

`{seconds}` stands for the input, and `{line}` in the C++ is the number of the line using the word (for error messages). Other lines a library can have are `include: <header>` (a C++ header), `link: name` (a system library), `code:` and `python:` (helper code, indented below), and values like `pi = 3.14159, number, read only` (with their own `runs:` line). Use each input only once in the C++ line. A word without a `runs:` line only works in built programs.

## Saving and loading

`save` keeps any value in a file, and `load` puts it back, so a game can remember high scores or where the player was:

```
save high scores to file "scores.json"
...
set high scores to a table of numbers
load high scores from file "scores.json"
```

`load` needs a name that already holds the right kind of value (here, a table of numbers). Lists, tables, places and your own kinds of things all work, even inside each other. A thing whose file lacks one of its parts gets that part empty, so adding a part to a kind of thing doesn't spoil old saves. If the file holds something else, the problem is `the file "scores.json" doesn't hold a table of numbers.` Use `try:` to carry on instead.

The file is JSON, which other programs can read too. To write text holding a quote mark, use the word `quote mark` (and `new line` for a line break): `scrawl "She said " plus quote mark plus "hi" plus quote mark`.

## When something goes wrong while running

The program stops with the line and a plain reason, such as `Line 22: there is no item 9 in a list of 4 items. Items are counted from 1.`

To carry on instead, put the lines that might go wrong under `try:`, and what to do instead under `if that went wrong:` (at the same indent, right after). Inside it, `the wound` is the reason, as text:

```
try:
  set notes to contents of file "notes.txt"
if that went wrong:
  scrawl "I couldn't read the notes: ", the wound
  set notes to ""
```

The lines under `try:` stop at the first problem, even one deep inside a command they use.

Checking the translator itself: `py -3 test_imagination.py`.
