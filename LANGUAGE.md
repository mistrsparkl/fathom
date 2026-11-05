# Cosmonova

Cosmonova is a programming language written in plain English words. Scripts end in `.cosmos`. There are two sorts of script:

- **A program** stands on its own and begins at its `genesis:` command. Run it with:

  ```
  cosmonova examples/guess.cosmos
  ```

  Cosmonova reads the script and does what it says, line by line. Nothing is translated and no compiler is needed. (`cosmonova` is `cosmonova.bat` in this folder, short for `py -3 cosmonova.py`.)

  To make a program into an `.exe` that runs fast and on its own, build it. This turns it into C++ and needs Visual Studio's C++ compiler:

  ```
  cosmonova build examples/guess.cosmos
  ```

  A program does exactly the same thing either way. The self-check runs its test programs both ways and compares what they print.
- **A program for a web page** is made into JavaScript instead: `cosmonova web examples/pets.cosmos site` writes `site/pets.js` and Cosmonova's runtime `site/cosmonova.js`. Load both in a page (`<script src="cosmonova.js"></script><script src="pets.js"></script>`), or run the program with `node pets.js`. It does the same as the other two ways (the self-check runs its programs with node too). See *Programs for web pages* below.
- **A part of something else** starts with `this is part of: <thing>`, e.g. Unreal code for a creature. Turn a the folder of these into C++ (`<name>.cosmos.cpp`, which you never edit) with:

  ```
  py -3 cosmonova.py <scripts folder> <output folder>
  ```

- **Checking for mistakes** without running: `cosmonova check examples/guess.cosmos`.
- **Trying things out:** type just `cosmonova` for a prompt. Each line you type is done straight away, and names are kept from line to line. Type a value on its own (`5 plus 3`) to see it. A line ending in `:` takes the indented lines after it, finished with an empty line. `bye` finishes.

A mistake stops with a plain message, such as:

```
follow.cosmos line 31: I don't know 'walk sped'. Did you mean 'walk speed'?
```

Working examples: `examples/guess.cosmos` (a guessing game), `examples/pets.cosmos` (lists, kinds of things, commands that return answers), `examples/clock.cosmos` (libraries), `examples/dodge.cosmos` (a game in a window) and `examples/follow.cosmos` (how a deer follows the player, part of a creature).

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

## Commands that return an answer

Add `returning <kind>` to the first line, and leave with `return ...`:

```
to total age of, given pets (a list of pets), returning a number:
  set total to 0
  for each pet in pets: set total to total plus the age of pet
  return total
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

**Commands as values.** `the command double` is the command itself, not its answer. Keep it in a name, a list or a part of a thing, give it to another command, or give it back from one. `invoke` does it:

```
to apply to all, given f (a command given a number returning a number) and items (a list of numbers), returning a list of numbers:
  set out to a list of numbers
  for each item in items: add invoke f with item to out
  return out
and the universe said i love you

genesis:
  scrawl apply to all with (the command double, a list of (1, 2, 3))
  set steps to a list of (the command double, the command round)
  invoke the command greet with "Sam"
and the universe said i love you
```

The kind says what the command takes and returns: `a command` (nothing either way), `a command given text`, `a command given a number and text returning yes or no`. Library words work too (`the command round`). Commands for a kind of thing can't be kept this way, and commands can't be compared or saved.

**At the same time.** `meanwhile download with ("https://example.com/a.png", "a.png")` starts a command going on its own, and the next line carries on straight away. `wait for the others` waits until every command started with `meanwhile` has finished (a program also waits for them before it ends). Each one gets its own copy of every name as it was when it started, so they can't spoil each other's values; they can share files and the screen. A problem in any of them stops the whole program. `meanwhile invoke f` works too.

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
| `conjure a pet as rex` | The same, said the other way round. |
| `the name of rex` | One of its parts. `set the name of rex to "Rex"` changes it. |
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

A dog has a name and an age (because every pet has) and tricks. Commands for a pet (`to speak, for a pet:`) work on dogs and puppies too. A dog can have its own version, `to speak, for a dog:`, which dogs (and puppies) use instead; every version takes the same other inputs. A dog can also go anywhere a pet is wanted: an input `(a pet)`, a list of pets, a name holding a pet, or `return` in a command returning a pet. It goes there as a pet: a copy with just a pet's parts (its tricks stay behind). A pet can't go where a dog is wanted.

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

`set the birth of ball to 100 horizontal 50 vertical` puts the ball's existence there too. Then move `the existence of ball`, and `(the existence of ball) of horizontal` is how far across it is.

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
| `repeat 10 times:` | Do the indented lines below 10 times. |
| `as long as guess is not secret:` | Keep doing the indented lines below while it is yes. |
| `greet with name, 3` | Do your own command `greet`, giving it its inputs in order. A command without inputs is just its name: `greet`. |
| `for each score in scores:` | Do the indented lines once for every item of a list, with `score` being that item. |
| `for each n from 1 to 10:` | The same for each whole number from 1 to 10. |
| `add 5 to scores` | Put an item at the end of a list. |
| `remove item 2 from scores` / `remove 5 from scores` | Take out the second item / the first 5. |
| `set item 2 of scores to 9` | Change one item. Items are counted from 1. |
| `set entry "Rex" of ages to 3` | Put a value in a table under a name (replacing what was there). |
| `remove entry "Rex" from ages` | Take a name and its value out of a table. |
| `return total` | Leave the command, returning an answer. |
| `raise an error with "the tank is empty"` | Stop with a problem of your own. `try:` catches it like any other, and `the wound` is its text. |
| `break free` | Leave the `repeat`, `as long as` or `for each` it is inside, and carry on after it. |
| `move on` | Go straight to the next round of the loop it is inside. |
| `inscribe "hello" into file "notes.txt"` | Make or replace a file with this text. |
| `add "a line" to file "log.txt"` | Add a line to the end of a file (making it if needed). |
| `cease` | Leave the command now (only in commands that don't return anything). |
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
| `the size of x` | a number without its sign, the distance of a place from 0 horizontal 0 vertical 0 depth, the length of a (flat) place, or how many letters text has |
| `random number from 1 to 100` | a random whole number, both ends included |
| `random fraction` | a random number from 0 up to (but never quite) 1, like 0.7302 |
| `item 2 of scores` | one item of a list (counted from 1) |
| `a random item of scores` | one item of a list, picked at random |
| `the size of scores` | how many items a list has |
| `scores contains 5`, `name contains "ell"` | yes or no: is it in the list / in the text |
| `contents of file "notes.txt"` | everything in a file, as text |
| `lines of file "notes.txt"` | the file's lines, as a list of text |
| `file "notes.txt" exists` | yes or no |
| `lines of text`, `the words of text` | text split into lines or words, as a list of text |
| `answer as a number` | text turned into a number (`"42"` gives 42) |
| `score as text` | a number or yes or no written out as text |
| `(price times 1.2) rounded to 2 decimal places` | a number rounded to that many decimal places (halves go up, away from zero) |
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
| `scores changed by the command double` | a new list: the command done to every item (see Commands as values) |
| `scores kept by the command big one` | a new list of just the items the command says yes to |
| `sorted pets by age` | a copy of a list of things, smallest part first (things with the same part keep their order) |
| `entry "Rex" of ages` | the value a table keeps under that name |
| `keys of ages` | a table's names, as a list of text in alphabetical order |
| `ages contains "Rex"`, `the size of ages` | yes or no: does the table have that name / how many names it has |
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

`of` takes everything after it until a word like `is`, `and`, `between` or `by`, except for parts and items (`the age of rex plus 1` is `(the age of rex) plus 1`). Words that change a whole value (`as text`, `as a number`, `as saved text`, `rounded to`, `changed by`, `kept by`) belong to everything before them: `item 2 of scores as text` is `(item 2 of scores) as text`, and `round x as text` is `(round x) as text`. Use brackets to say exactly what belongs together: `(the size of gap) minus stop distance`.

## Names

Names can be several words (`turn needed`, `braking speed`). They can't use the language's own words: and, angle, as, ask, at, begins, between, by, cease, changed, clamp, conjure, contains, depth, direction, divided, each, empty, ends, exceeds, falls, file, flat, for, from, horizontal, if, in, inscribe, into, invoke, is, kept, larger, least, less, list, meanwhile, minus, more, most, move, new, no, not, of, or, otherwise, plus, raise, random, remove, repeat, return, returning, root, scrawl, set, size, smaller, square, stop, than, times, to, touches, toward, trimmed, try, vertical, whether, while, whisper, with, wound, write, yes. Some phrases are the language's too, so avoid names that start them: `entry`, `keys of`, `sum of`, `average of`, `biggest of`, `smallest of`, `rounded to`, `letter`, `letters`, `upper case`, `lower case`, `position of`, `replace`, `join`, `sorted`, `reversed`, `last item of`, `split by`.

## Adding words

A script can only use words its thing knows. New words (another part of the deer's state, a new ability) are added to the `.words` file; a new physical ability (jumping, a gallop) needs C++ underneath first, then it gets a word.

In a part of something else, commands can call each other too; the top of the C++ it makes lists what the class's header must declare. New kinds of things can only be described inside programs for now.

## Names the whole program shares

A name set inside a command belongs to that command. Names every command shares go in a `the world remembers:` block, at the top level of the script:

```
the world remembers:
  score (a number)
  players (a list of text)
and the universe said i love you
```

They start empty (0, no, "", an empty list), and any command can read and set them. A program made of several scripts can have one such block in each.

## Programs made of several scripts

A program can use another script's commands and kinds of things:

```
use: shapes.cosmos
```

The other script is looked for next to this one. It can have its own `genesis:` (so it can be run and tried by itself); that part is left out when it is used. A script used more than once, even by scripts it uses itself, is read once. A mistake in a used script names it, like `shapes.cosmos line 13: ...`.

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
| `time` | `wait 2 seconds`, `seconds since the start`, `the current hour`, `the current minute`, `the current second`, `the day of the month`, `the current month`, `the current year`, `today` (like `2026-11-04`), `the time now` (like `14:05:09`), `the day of the week` (like `Wednesday`), `seconds since 1970` |
| `window` | A window to etch in, for games and pictures. See below. |
| `web` | `web page "https://example.com"` (returns the page as text), `download with "https://example.com/cat.png", "cat.png"` (into a file), `send to the web page with (address, message)` (sends text, returns the answer) |
| `sound` | `play the sound with "boom.wav"`, `play the sound and wait with "boom.wav"`, `play the sound again and again with "music.wav"`, `stop the sound` (stops them all). Sounds play on top of each other, so a game can have many at once. .wav or .mp3 files. |
| `computer` | `beep with 440, 0.5` (pitch, seconds), `run the command "dir"` (returns its exit number), `open "notes.txt"` (opens a file or web address), `user name`, `the output of the command "dir"` (what it printed, as text), `the words given` (a list of the words typed after the program's name: `cosmonova game.cosmos easy 3`), `environment value of "PATH"`, `current folder`, `end the program with 0` (stops at once, giving that exit number) |
| `folders` | `files in the folder "saves"`, `folders in the folder "saves"` (lists of names, in order), `there is a folder "saves"`, `make the folder "saves/old"`, `erase the file "a.txt"`, `erase the folder "old"` (and everything in it), `move the file with "a.txt", "b.txt"` (moves or renames), `copy the file with "a.txt", "b.txt"`, `bytes in the file "a.txt"`, `the bytes of the file "cat.png"` (the file as a list of numbers from 0 to 255, for files that aren't text), `fill the file with ("out.bin", numbers)` (the other way) |
| `letters` | `code of the letter "A"` (65: the number behind a letter), `the letter with code 233` ("é") |
| `patterns` | Finding text by its shape (`"[0-9]+"` is one or more digits, `"."` any letter, `"(...)"` a piece to keep): `the pattern fits with ("[0-9]+", line)` (yes or no), `matches of the pattern with ("[0-9]+", line)` (every match, as a list of text), `pieces of the pattern with ("([a-z]+)=([0-9]+)", line)` (the bracketed pieces of the first match), `replace the pattern with ("[0-9]+", line, "#")` |
| `server` | `serve the web with (8080, the command answer)` makes the program a web server for this computer: open `http://127.0.0.1:8080/hello` in a browser and `answer` (a command given text returning text) is given `"/hello"` and returns the page. It serves until the program ends, so start it with `meanwhile` to do other things too. `serve the web from the folder with (8080, "site", the command answer)` also sends the files in that folder (`/` is `index.html`), and asks `answer` only about addresses that aren't files. Inside `answer`, `the web message` is what a form or `fetch` sent along (empty for a plain visit), `answer with the file "song.mp3"` sends a file from anywhere instead of the text given back, and `web decoded "a%20b"` ("a b") and `web encoded` turn addresses into text and back. The Tidal OS system side uses these. |

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
| `mouse x`, `mouse y`, `mouse held` | Where the mouse is, and whether its left button is held down. |
| `key pressed "space"`, `mouse clicked` | yes or no: was the key pressed (or the mouse button clicked) since the frame before? Yes for one frame only, so one press does one thing. |
| `mouse right held`, `mouse right clicked` | The same for the right button. |
| `mouse wheel turned` | How many notches the wheel turned since the frame before: more than 0 away from you, less than 0 toward you. |
| `hold the pointer`, `let go of the pointer` | Hide the pointer and keep it in the window, for looking around in a 3D game. While it is held, `mouse moved across` and `mouse moved down` say how far the mouse moved since the frame before. |
| `colour from (255, 136, 0)` | The colour with that much red, green and blue (each 0 to 255), as `"#ff8800"`. Good for colours that change, like a sky at dusk. |
| `end the world` | Close it yourself. |

**3D.** The window can show a 3D world too. Places are across (`horizontal`), up (`vertical`, more is higher, unlike flat window places) and away (`depth`). The picture is seen from **the eye**:

| Words | Means |
|---|---|
| `place the eye at 0 horizontal 1.6 vertical -10 depth` | Where the picture is seen from. |
| `aim the eye with (turn, tilt)` | Which way the eye looks, in degrees: turn 0 looks along depth, 90 looks along horizontal (to the right); tilt up is more, from -89 to 89. Walking forward at a turn is `(sine of turn) horizontal 0 vertical (cosine of turn) depth`. |
| `etch the ground with ("green", "#2a7a2a")` | A checkered floor at vertical 0 around the eye, in two colours. It is always under everything else. |
| `etch a cube with (middle, size, "red")` | A cube around a middle place. Its sides are shaded by the light. |
| `etch a block with (middle, width, height, depth, "brown")` | A box of any size. |
| `etch a ball with (middle, radius, "yellow")` | A ball. |
| `the graphics card draws` | yes or no: are the 3D shapes drawn by the graphics card? |
| `set the daylight to 0.3` | How bright the 3D world is, from 0 (dark) to 1 (full, at first). It dims every 3D shape, not the words etched on top. |
| `start keeping the shapes as "house"` … `stop keeping the shapes` | The 3D shapes etched in between aren't drawn now: they are kept under that name. `etch the kept shapes "house"` then draws them all at once, every frame, far faster than etching each one again, so worlds of many thousands of blocks stay smooth. Keeping under the same name again replaces them, and `forget the kept shapes "house"` lets them go. |
| `screen place of 3 horizontal 1 vertical 5 depth` | Where a place shows on the window, as a flat place (`not a number` when it is behind the eye). |

3D shapes are drawn just before anything flat is etched or the frame is revealed, so words etched after them (a score) stay on top. They are drawn by the **graphics card** (OpenGL, which every Windows has): things hide behind each other properly and balls are smoothly lit. Running directly, this also needs Pillow (`py -3 -m pip install pillow`). Without them, the same shapes are drawn far ones first instead, which looks a little plainer. `the graphics card draws` is yes or no (once a world is open), and setting the environment value `COSMONOVA_NO_GPU` to 1 turns the graphics card off. `consume the window with "#87ceeb"` makes a sky. `examples/walk3d.cosmos` is a small 3D game. `examples/driftstone.cosmos` is a bigger one: an island of blocks to dig, build on and craft with, with day and night (left button digs, right button places, 1 to 9 or the wheel choose, C opens the workbench, K keeps the island).

Colours are names (`black`, `white`, `red`, `green`, `blue`, `yellow`, `orange`, `purple`, `pink`, `brown`, `grey`) or codes like `"#ff8800"` (red, green and blue, each from 00 to ff).

### Making a library

A library is a `.words` file, in `libraries/` or next to your program. Each word says what it means in C++ (for `build`) and, on an indented `runs:` line, in Python (for running directly). Anything C++ or Python can do can get an English word this way: windows, sound, the internet, games. Here is a word from `libraries/time.words`:

```
to wait, given seconds (a number) = std: : this_thread: : sleep_for(std: : chrono: : duration<double>({seconds}))
  runs: time.sleep(max(0.0, {seconds}))
```

`{seconds}` stands for the input, and `{line}` in the C++ is the number of the line using the word (for error messages). Other lines a library can have are `include: <header>` (a C++ header), `link: name` (a system library), `code:` and `python:` (helper code, indented below), and values like `pi = 3.14159, number, read only` (with their own `runs:` line). Use each input only once in the C++ line. A word without a `runs:` line only works in built programs.

For programs made for the web, a word gets an indented `web:` line too: what it means in JavaScript (`{seconds}` and `{line}` work the same way). Helper code for those goes in a `javascript:` block, which only web programs get (and `code:`, `include:` and `link:` only built ones). A library whose words only make sense on a web page starts with the line `web only`; its words have no ` = C++` part, and using one in a program that isn't made for the web says so.

## Programs for web pages

`cosmonova web` makes a program into JavaScript, so it can be the inside of a web page or an app made with Electron. The `page` library gives it the page:

```
use: page

the world remembers:
  clicks (a number)
and the universe said i love you

to pressed, given event (a number):
  set clicks to clicks plus 1
  set the text with (the element "#count", "Clicks: " plus clicks)
and the universe said i love you

genesis:
  listen for an event with (the element "button", "click", the command pressed)
and the universe said i love you
```

Every the element of the page is a number (0 means there isn't one), so elements fit in names, lists and kinds of things. `the element "#count"` finds one by its CSS selector, and `listen for an event` gives a command each event the person makes, as a number that the event words read. Commands answering the page run one after another, and `wait`, `web page` and the words that wait (like `play the media`) let the page carry on meanwhile.

| Words (library `page`) | Means |
|---|---|
| `the element "sel"`, `elements matching "sel"`, `the element within with (el, "sel")`, `elements within`, `the nearest matching element with (el, "sel")`, `parent of the element`, `the element at with (x, y)` | Finding elements (`the nearest matching element` looks at the element and the ones around it, like CSS `closest`). `the whole window`, `the page`, `the page body` and `the focused element` are elements too. |
| `the element made from "<li>new</li>"`, `insert as a child with (el, parent)`, `insert as the first child`, `insert before`, `remove the element`, `empty the element` | Making elements from markup and putting them in the page. |
| `set the text with (el, "text")`, `set the markup`, `words in the element`, `safe markup of words` | What an element holds. `safe markup of` turns `<` and `&` into markup that shows them, for words a person typed. |
| `value of the element`, `set the value`, `the element is ticked`, `tick the element`, `enable the element`, `focus on the element`, `select all in the element`, `the selected words` | Fields, ticks and buttons. |
| `set the attribute with (el, "name", "value")`, `drop the attribute`, `the attribute value`, `apply the appearance with (el, "open")`, `remove the appearance`, `toggle the appearance with (el, "open", yes)`, `the element has the appearance`, `set the style with (el, "width", "20px")`, `the style value` | Attributes, looks (CSS classes) and styles. |
| `the left edge of`, `top of`, `width of`, `height of`, `width of the window`, `height of the window`, `scroll into view`, `scroll to the end` | Where things are, in dots from the top left of the window. |
| `listen for an event with (el, "click", the command c)`, `the pointer x coordinate of e`, `the pointer y coordinate of`, `key of the event`, `button of the event`, `wheel of the event`, `the target of`, `control held in the event`, `shift held in the event`, `alt held in the event`, `hold back the event`, `stop the event spreading`, `capture the pointer with (el, e)` | Answering the person. |
| `after with (2, the command c)`, `every with (0.5, the command c)`, `wait for the next frame` | Later, and again and again. |
| `animate with (el, "opacity", "0", "1", 0.3, "ease-out")`, `animate and wait` | Moving smoothly from one value to another (any CSS easing). |
| `start drawing on with (canvas, 1)`, `drawing width`, `drawing height`, `clear the drawing`, `begin a shape`, `shape point with (x, y)`, `fill the shape`, `fill the shape fading`, `trace the shape`, `fill a dot`, `fill a box`, `fill the drawing fading`, `fill the drawing glowing` | Drawing on a canvas element (the second input of `start drawing on` is how sharp: 1 is every dot of the screen). |
| `play the media`, `pause the media`, `the media is playing`, `media time of`, `media length of`, `set the media time`, `set the media loudness`, `local copy of address`, `loudness bands of with (el, 24)` | Sound and video elements: `local copy of` fetches a whole file into the page, and `loudness bands of` says how loud each band of pitches is (0 to 1), for a visualiser. |

The `web`, `time`, `maths`, `letters`, `patterns`, `computer` and `server` words that make sense in a page work there too (`web page` fetches, `wait` waits without stopping the page). Tidal OS (in its own folder, `..\TidalOS`) has screens written this way: its desktop, windows and apps are all Cosmonova.

## Saving and loading

`save` keeps any value in a file, and `load` puts it back, so a game can remember high scores or where the player was:

```
save high scores to file "scores.json"
...
set high scores to a table of numbers
load high scores from file "scores.json"
```

`load` needs a name that already holds the right kind of value (here, a table of numbers). Lists, tables, places and your own kinds of things all work, even inside each other. A thing whose file lacks one of its parts gets that part empty, so adding a part to a kind of thing doesn't spoil old saves. If the file holds something else, the problem is `the file "scores.json" doesn't hold a table of numbers.` Use `try:` to carry on instead.

`scores as saved text` gives the same JSON as text, without a file, and `load scores from the text reply` reads it back, so a program can talk to websites and other programs that use JSON (`load` fails with `the text doesn't hold a list of numbers.` if it doesn't fit). The file is JSON, which other programs can read too. To write text holding a quotation mark, use the word `a quotation mark` (and `new line` for a line break): `scrawl "She said " plus a quotation mark plus "hi" plus a quotation mark`.

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

Checking the translator itself: `py -3 test_cosmonova.py`.

## Reading like English

- `genesis:` just above a definition (`to ...:`, `a ... has:`, `the world remembers:`) only marks where it begins;
  the program still starts at the one `genesis:` whose lines are commands.
- Grammar is for people, and the computer skips it: `the`, `a` and `an` are left out before a line is read,
  so `if the size of kept notifications falls below 60:` is read as `if size of kept notifications falls below 60:`.
  Words inside quote marks, notes and names that hold an article themselves (`the page`, `open a world`) are kept.
- Grammar is **needed** in these places, and a line without it is a mistake:
  - `the` before a part of something: `the size of xs`, `the name of rex`, `the id of new notification`.
  - `a` or `an` after `conjure`: `conjure a notice as new notification`.
  - `a` before `list containing`: `set kept to a list containing new notification` (several items: `a list containing (1, 2, 3)`).
  - `a` before a consonant and `an` before a, e or i: `an apple`, not `a apple` (`an hour`, `a unit` and `an orange` are fine).
- Anywhere else `the`, `a` and `an` are up to you: `set the notices to kept notifications` and `set notices to kept notifications` are the same line.
- So `a`, `an` and `the` can't be names on their own.
- `add 1 to count` makes a number bigger; `add item to collection` puts an item at the end of a list.
- A command's inputs can be listed under it, after `use:` or `using:` (or `utilize:`), one per line, before its instructions:

  ```
  to tell, use:
    app name (text)
    title (text)
    quiet delivery (yes or no)

    conjure a notice as new notification
    set the title of new notification to title
  and the universe said i love you
  ```

  The first line that isn't `name (kind)` starts the instructions; an input-looking line among the instructions is a mistake.
  It is the same command as `to tell, given app name (text) and title (text) and quiet delivery (yes or no):`.
- `return x` leaves a command with x; a command that returns says so in its first line: `to double, given x (a number), returning a number:`.
- `raise an error with "no fuel"` is a problem of your own, caught by `try:` like any other.
- `return whether x is 3`: `whether` just reads well; it changes nothing.
- `the item at 2 in names` is `item 2 of names`; `x rounded to 1 decimal place`; `a quotation mark`; `a list of text values`.
