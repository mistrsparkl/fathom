# Stellanova: a programming language you can read out loud

I've always thought code should read like what it does. Stellanova is my attempt at that. You write programs in plain English words, and the same script can run straight away, become a fast `.exe`, turn into WebAssembly, or become JavaScript for a web page. This post walks through the whole language, term by term, with small examples you can copy.

Grab a coffee. It's a long one.

## Getting started

A Stellanova script is a text file ending in `.stella`. Here's the smallest useful program:

```
genesis:
  scrawl "Hello, world!"
and the universe said i love you
```

Save it as `hello.stella` and run it:

```
stellanova hello.stella
```

That's it. No compiler, no project file. Stellanova reads the script and does what it says, line by line.

Two words in there deserve an explanation right away:

- **`genesis:`** is where a program begins. Every program has exactly one.
- **`and the universe said i love you`** ends a block. Every command, every description of a kind of thing, and every `the world remembers:` block finishes with this line, unindented. Leaving it out is an error. Yes, it's a little sentimental. I like it.

### The ways to run a program

| Command | What it does |
|---|---|
| `stellanova game.stella` | Runs it right now. |
| `stellanova build game.stella` | Turns it into machine code: a real `.exe` (or a Linux program, if you build on Linux). Needs LLVM. |
| `stellanova wasm game.stella` | Builds WebAssembly, plus a small `.mjs` file so `node` can run it. |
| `stellanova web game.stella site` | Turns it into JavaScript for a web page. |
| `stellanova check game.stella` | Looks for mistakes without running anything. |
| `stellanova test maths.stella` | Runs every command whose name starts with `test`, and tells you which passed. |
| `stellanova debug game.stella 12 30` | Runs it and stops before lines 12 and 30 so you can look around. |
| `stellanova profile game.stella` | Runs it, then shows which lines took the most time. |
| `stellanova watch game.stella` | Shows each line as it runs, with the names it changed. |
| `stellanova` on its own | A prompt where every line you type runs straight away. Type `bye` to leave. |

A program does exactly the same thing whichever way you run it. The test suite checks this by running every test program both directly and built, and comparing what they print.

How fast is it? Built programs run at the same speed as C++ for number crunching, commands calling each other, and lists of numbers. Running directly is closer to Python's speed. So try things out directly, and build when you want speed.

### When you make a mistake

Stellanova tells you in plain words, with the line number:

```
follow.stella line 31: I don't know 'walk sped'. Did you mean 'walk speed'?
```

Mistakes found while running look the same:

```
Line 22: there is no item 9 in a list of 4 items. Items are counted from 1.
```

## The kinds of values

Every value has a kind, and a name keeps holding the same kind once you've set it.

| Kind | What it looks like |
|---|---|
| **a number** | `60`, `2.5`, `30 degrees` (words after a number like `degrees` are just for you) |
| **yes or no** | `yes`, `no`, `speed exceeds 10` |
| **text** | `"hello"`, `"Hi " plus name` |
| **a place** | `1 horizontal 2 vertical 3 depth`: a point in space, across, down and deep |
| **a flat place** | `300 horizontal 200 vertical`: across and down only, like a spot on the screen |
| **a list of ...** | `a list of numbers` (empty), `a list of (3, 5, 7)`. One kind of thing, in order. |
| **a table of ...** | `a table of numbers`. Looks values up by a name, like a phone book. |
| **your own kind** | `conjure a pet`, once you've described what a pet has |

Mixing kinds is caught for you. If `turn rate` holds a number, then `set turn rate to fallen` says: `'turn rate' holds a number, not yes or no.`

Lists and tables can hold other lists and tables. `a list of lists of numbers` is a grid, and `item 2 of item 3 of grid` reaches inside it.

## Names

You keep values under names, and names can be several words long:

```
set braking speed to 12
set player name to "Sam"
```

The first `set` makes the name. After that, `set` changes it.

A few words belong to the language, so they can't be names: `and`, `or`, `not`, `if`, `set`, `to`, `of`, `is`, `plus`, `minus`, `times` and friends. Stellanova tells you if you trip over one.

A name you set inside a command belongs to that command alone. To share names across the whole program, list them in a **`the world remembers:`** block at the top level:

```
the world remembers:
  score (a number)
  players (a list of text)
and the universe said i love you
```

They start empty (0, no, "", an empty list), and every command can read and change them.

## Showing things and asking questions

**`scrawl`** prints things, one after another, then starts a new line:

```
scrawl "Score: ", score
```

Text can fill itself in. Words in square brackets inside text are replaced by what they hold:

```
scrawl "Hello, [name]! [count plus 1] left."
```

If you need real square brackets, double them: `[[like this]]` shows `[like this]`.

**`ask`** shows a question and keeps what the person types:

```
ask "What's your name? " into name
ask "How old are you? " into age (a number)
ask "Play again? " into again (yes or no)
```

When you ask for a number, it keeps asking until it gets one. For yes or no, it accepts `yes`, `y`, `no` or `n`.

## Working things out

### Arithmetic

`a plus b`, `a minus b`, `a times b` and `a divided by b` do what they say. The symbols `+ - * /` work too. A minus in front gives the negative: `-look limit`.

`2 to the power 10` raises a number to a power, and it comes before `times` and `plus` the way it does in maths. So `3 times 2 to the power 3` is 24.

More number words:

- `square root of x`
- `smaller of a and b`, `larger of a and b`
- `clamp x between low and high` keeps x inside a range
- `random number from 1 to 100` gives a whole number, both ends included
- `random fraction` gives a number from 0 up to, but never quite, 1
- `(price times 1.2) rounded to 2 decimal places` (halves go up, away from zero)
- `1234567 with commas` gives "1,234,567"
- `7 padded to 3 digits` gives "007", and `"food" padded to 8 letters` gives "food    ", for lining up columns
- `upper case of "straße ω"` gives "STRAßE Ω": every alphabet, not just A to Z
- `12 bitwise and 10`, `bitwise or`, `bitwise exclusive or`, `1 shifted left by 4`, `shifted right by` work on the bits of whole numbers

### Comparing

These all give yes or no:

- `a exceeds b` (greater than)
- `a falls below b` (less than)
- `a is at least b`, `a is at most b`
- `a is b`, `a is not b`
- `answer is one of ("yes", "y", "sure")`, and `is not one of`
- `existence is within 30 of coin` asks whether two places or numbers are 30 or less apart
- `ball touches coin` asks whether two things' circles overlap

Combine them with `and`, `or` and `not`.

### Text

- `"Hi " plus name` joins text. Numbers and yes or no are written out for you, so `"Score: " plus 5` works.
- `the size of name` is how many letters it has.
- `letter 2 of name`, `letters 2 to 4 of name` (counted from 1)
- `upper case of name`, `lower case of name`
- `trimmed line` drops spaces and line breaks from both ends
- `name begins with "Dr"`, `name ends with ".txt"`, `name contains "ell"`
- `position of "lo" in name` is where it first appears, or 0 if it isn't there
- `replace "a" with "b" in name`
- `line split by ", "` cuts text into a list
- `lines of text`, `the words of text`
- `answer as a number` turns `"42"` into 42, and `score as text` goes the other way
- `a quotation mark` and `new line` are how you put those two characters inside text

### Lists

Make them:

```
set scores to a list of numbers
set primes to a list of (2, 3, 5, 7)
set kept to a list containing new notification
```

Change them:

| Line | What it does |
|---|---|
| `add 5 to scores` | Puts 5 at the end. |
| `insert 5 at 2 in scores` | Puts 5 in second place and moves the rest along. |
| `remove item 2 from scores` | Takes out the second item. |
| `remove 5 from scores` | Takes out the first 5. |
| `set item 2 of scores to 9` | Changes one item. |

Read them:

- `item 2 of scores` (items are counted from 1, the way people count)
- `last item of scores`, `a random item of scores`
- `items 2 to 5 of scores`, `first 3 of scores`, `last 3 of scores`
- `the size of scores`
- `scores contains 5`
- `sum of scores`, `average of scores`, `biggest of scores`, `smallest of scores`
- `sorted scores`, `reversed scores`, `unique names`, `shuffled names` (each gives a new list)
- `join names with ", "` makes one piece of text
- `position of "Bo" in names`
- `sorted pets by age` sorts your own things by one of their parts, and `sorted pets by age, biggest first` turns it round
- `sorted names by each n becomes the size of n` sorts by anything worked out from each item (shortest name first, here)

### Tables

```
set ages to a table of numbers
set entry "Rex" of ages to 3
scrawl entry "Rex" of ages
remove entry "Rex" from ages
```

`keys of ages` gives the names in alphabetical order, `ages contains "Rex"` checks for one, and `the size of ages` counts them. A number works as a name too, so `the entry 3 of ages` is the entry "3".

### Places

Places are for games and anything that moves. `p of horizontal`, `p of vertical` and `p of depth` read one part, and `set p of horizontal to 5` changes it. You can add places, take them away, and multiply or divide them by a number. `flat (place)` drops the height, `direction of flat place` gives a compass angle in degrees, and `angle from a to b` gives the turn between two angles, from -180 to 180.

**`birth` and `existence`** are two special names for where something starts and where it is now. `set birth to 300 horizontal 200 vertical` sets both at once. Move `existence` around, and `set existence to birth` sends it home.

### How `of` groups things

`of` takes everything after it, up to a word like `is`, `and`, `between` or `by`. Parts and items are the exception: `the age of rex plus 1` means `(the age of rex) plus 1`. Words that change a whole value, like `as text` or `rounded to`, apply to everything before them. When in doubt, use brackets.

## Making choices

```
if fallen: cease
```

The part after the colon runs only when the test is yes. For longer choices, put the lines underneath:

```
if score exceeds 100:
  scrawl "Amazing!"
otherwise if score exceeds 50:
  scrawl "Nice."
otherwise:
  scrawl "Keep going."
```

When you're choosing based on one value, **`depending on`** is tidier:

```
depending on weather:
  "rain": scrawl "Umbrella!"
  "sun", "heat": scrawl "Sunscreen!"
  anything else: scrawl "Just a jacket."
```

## Loops

| Loop | Runs |
|---|---|
| `repeat 10 times:` | 10 times. |
| `as long as guess is not secret:` | While the test is yes. |
| `for each score in scores:` | Once for every item, with `score` holding it. |
| `for each n from 1 to 10:` | For each whole number from 1 to 10. |
| `for each n from 0 to 100 by 5:` | Counting in steps. A negative step counts down. |

Inside any loop, **`break free`** leaves the loop and **`move on`** skips to the next round.

There are also loops that run on their own once a command's other lines are done:

- **`whenever ticks exceeds 2:`** runs its lines each time the test turns yes.
- **`every 2 seconds:`** runs its lines every two seconds.
- **`every frame:`** runs once per frame in a game window.

## Commands

A command is a named set of lines. You make one with `to`:

```
to greet, given who (text):
  scrawl "Hello, " plus who plus "!"
and the universe said i love you
```

And use it by name:

```
greet with "Sam"
```

**`given`** lists the inputs, each with its kind in brackets. Join several with `and`. A command with no inputs is just its name: `greet`. With one input, `with` is optional. With two or more, put them in brackets: `pet called with ("Rex", 3)`.

If you have a lot of inputs, you can list them under the first line instead:

```
to tell, use:
  app name (text)
  title (text)
  quiet delivery (yes or no)

  scrawl title
and the universe said i love you
```

### Commands that give an answer

Add **`returning`** and the kind, then leave with **`return`**:

```
to double, given x (a number), returning a number:
  return x times 2
and the universe said i love you
```

Now `double with 4` is a value you can use anywhere. `return whether x is 3` reads nicely too; `whether` changes nothing.

**`cease`** leaves a command early, for commands that don't return anything.

### Commands as values

`the command double` is the command itself, not its answer. You can keep it in a name or a list, hand it to another command, and run it later with **`invoke`**:

```
set steps to a list of (the command double, the command round)
scrawl invoke the command double with 5
```

The kind of a command value says what it takes and gives: `a command`, `a command given text`, or `a command given a number and text returning yes or no`.

You can also write a small command right where you need it with **`each ... becomes`**:

```
scrawl scores changed by each s becomes s times 2
scrawl scores kept by each s becomes s exceeds 10
set add tax to each price (a number) becomes price times 1.2
```

**`changed by`** makes a new list with the command applied to every item. **`kept by`** keeps only the items the command says yes to. A command written this way keeps a copy of any name it uses, as it was when the command was made.

## Your own kinds of things

Describe what a kind of thing has, one part per line:

```
a pet has:
  name (text)
  age (a number)
  tricks (a list of text)
and the universe said i love you
```

Then:

- **`conjure a pet`** makes a new one, with every part empty. `conjure a pet as rex` says the same thing the other way round.
- **`the name of rex`** reads a part, and `set the name of rex to "Rex"` changes it.
- **`scrawl rex`** shows `a pet (name: Rex, age: 3, tricks: sit)`.

### Commands for a kind of thing

```
to bounce, for a ball:
  set speed to speed times -1
  set bounces to bounces plus 1
and the universe said i love you
```

**`for a ball`** means the command belongs to balls. Inside it, the ball's parts are plain names, and changing them changes the real ball you gave it. Call it with `bounce b`. Inside, the whole ball is called `ball`.

### Kinds of kinds

```
a dog is a kind of pet that has:
  tricks (a list of text)
and the universe said i love you
```

A dog has everything a pet has, plus its own parts. Commands for pets work on dogs, and a dog can have its own version of a command that it uses instead. A dog can go anywhere a pet is wanted. It goes there as a pet, with just a pet's parts.

### Kinds for any kind

**`anything`** lets you describe a kind once for every kind it might hold:

```
a stack of anything has:
  items (a list of anything)
and the universe said i love you
```

Now `a stack of numbers` and `a stack of text` both exist.

### Shared abilities

```
a speaker is anything that can speak.
```

Any kind of thing with its own `to speak, for a ...:` command is now a speaker. A list of speakers can hold dogs and robots together, and `speak s` does it the way each one's own kind does.

### Nothing

A name for a kind of thing can hold nothing: `set best to no enemy`. Ask with `if best is nothing` or `if best is something`. Reading a part of nothing stops with a clear message, like `this enemy is nothing, so it has no health.`

### Hidden parts, and asking what kind

A part written `balance (a number, hidden)` can only be used by the commands for that kind of thing, so nothing else can reach in and change it. And `s is a dog` asks what kind of thing something really is (a puppy is a dog too).

## Files and saving

- **`inscribe "hello" into file "notes.txt"`** makes or replaces a file.
- **`add "a line" to file "log.txt"`** adds a line to the end.
- **`contents of file "notes.txt"`** reads the whole file as text.
- **`lines of file "notes.txt"`** reads it as a list of lines.
- **`file "notes.txt" exists`** is yes or no, and so is **`folder "saves" exists`**.

**`save`** and **`load`** keep any value in a JSON file:

```
save high scores to file "scores.json"
set high scores to a table of numbers
load high scores from file "scores.json"
```

`load` needs a name that already holds the right kind. If you add a part to a kind of thing later, old saves still load; the new part just starts empty.

**`scores as saved text`** gives the same JSON without a file, and **`load scores from the text reply`** reads it back. That's how you talk to web services: describe the parts you want as a kind of thing and load the answer into it. Stellanova even matches `windSpeed`, `wind_speed` and `Wind-Speed` to your part called `wind speed`.

## When things go wrong

Put risky lines under **`try:`**, and what to do instead under **`if that went wrong:`**. Inside, **`the wound`** is the reason, as text:

```
try:
  set notes to contents of file "notes.txt"
if that went wrong:
  scrawl "I couldn't read the notes: ", the wound
  set notes to ""
```

You can raise problems of your own:

- **`raise an error with "the tank is empty"`** stops with your message.
- **`raise a fuel problem with "the tank is empty"`** gives the problem a kind. Then `if that went wrong with a fuel problem:` catches only those.

**`check`** is the quick version for tests: `check double with 2 is 4` stops with `this check failed: double with 2 is 4` if it isn't true.

## Doing things at the same time

**`meanwhile`** starts a command running on its own, and the next line carries on straight away:

```
meanwhile download with ("https://example.com/a.png", "a.png")
scrawl "Downloading in the background..."
wait for the others
```

**`wait for the others`** waits for everything started with `meanwhile`. Each one gets its own copy of every name, so they can't spoil each other's values. When they do need to share names from `the world remembers:`, they take turns with a lock:

```
holding the lock "total":
  set total to total plus 1
```

## Notes and grammar

**`whisper:`** writes a note for people. The computer ignores it.

Grammar is mostly for you. Stellanova skips `the`, `a` and `an` before reading a line, so `set the notices to kept` and `set notices to kept` are the same. A few places need them, though:

- `the` before a part: `the size of xs`, `the name of rex`
- `a` or `an` after `conjure`: `conjure a pet`
- `a` before `list containing`
- `a` before consonants and `an` before vowels, as in English

And `add` reads both ways: `add 1 to count` makes a number bigger, while `add item to collection` puts an item at the end of a list.

## Programs made of several scripts

```
use: shapes.stella
```

That brings in another script's commands and kinds of things. The other script can have its own `genesis:` so you can run it alone; that part is skipped when it's used.

Two scripts can't both have a command with the same name: Stellanova tells you where each one is. A helper only its own script needs can be written `to tidy, privately:`, and then other scripts can't see it (and can have a `tidy` of their own).

## Libraries

A library gives you more words. It loads by itself as soon as you use one of its words, and `use: time` at the top says so out loud. Here's what comes with Stellanova.

| Library | What it gives you |
|---|---|
| `maths` | `pi`, `e`, `sine of`, `cosine of`, `tangent of` (in degrees), their `arc` versions, `round`, `round down`, `round up`, `whole part of`, `power of`, `remainder of`, `logarithm of`, `natural logarithm of` |
| `time` | `wait 2 seconds`, `seconds since the start`, `today`, `the time now`, `the day of the week`, `days between`, `days until`, `date plus days`, `weekday of`, and the current hour, minute, second, day, month and year |
| `window` | A window for games and pictures, in 2D and 3D (more on this below) |
| `sound` | `play the sound with "boom.wav"`, `play the sound and wait`, `play the sound again and again`, `stop the sound`. Plays .wav and .mp3, many at once. |
| `sound making` | Builds sounds from scratch: `a tone with ("sine", 440, 0.5, 0.8)`, `the pitch of the note "C#5"`, `mixed with`, `followed by with`, `louder with`, `faded with`, `echoed with`, `save the sound with`, and `record the sound 3` from the microphone |
| `pictures` | Edit pictures dot by dot: `a blank picture with`, `the picture in the file`, `the dot at with`, `colour the dot with`, `the dots of the picture`, `save the picture with` |
| `forms` | Desktop forms with buttons, fields, labels, lists and tick boxes. `open a form with`, `add a button with`, `wait for a click`, `the words in "name"`, `is ticked "loud"` |
| `web` | `web page "https://..."` reads a page, `download with` saves a file, `send to the web page with` posts text |
| `server` | Turns your program into a web server: `serve the web with (8080, the command answer)`. Inside `answer`, `the web way` says how it was asked ("GET", "POST"...), `the web header "Cookie"` reads a header, and `answer with the status 404` says a page isn't there. Many people can ask at once |
| `network` | TCP (`connect to with`, `listen on port`, `send on with`, `receive from`), UDP and WebSockets |
| `email` | `send an email with (...)` over TLS |
| `database` | SQLite: `change the database with`, `rows from the database with`, with `?` placeholders so typed text can't break your queries |
| `spreadsheet` | Reads and writes CSV |
| `json` | Reaches into JSON with paths like `"weather.days[2].high"` |
| `computer` | Runs other programs and reads what they print, reads environment values, opens files, beeps, and ends the program with an exit number |
| `folders` | Lists, makes, moves, copies and erases files and folders, and reads files as bytes |
| `zip` | Packs and unpacks .zip files |
| `encryption` | `encrypted with (message, password)` and `decrypted with`, plus `a random code of 16` |
| `hashing` | sha256, sha512, sha1 and md5 fingerprints, and HMAC signatures |
| `patterns` | Regular expressions in plain words: `the pattern fits with`, `matches of the pattern with`, `pieces of the pattern with`, `replace the pattern with` |
| `letters` | Text to UTF-8 bytes and back, and the number behind a letter |
| `animation` | Smooth movement: `eased with`, `tweened with`, `ping pong`, `wave of with`, `sheet frame with` |
| `big numbers` | Whole numbers of any size, kept as text |
| `physics.stella` | Boxes that fall, slide, land and bounce, written in Stellanova itself |
| `page` | For web programs: find and change page elements, listen for clicks, animate, draw on a canvas, play media |
| `screen` | A full-screen surface with see-through colours, rounded shapes, real fonts and frosted glass, for building whole desktops |

### The window library

This one deserves its own section, because it's where Stellanova is the most fun.

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

Places are counted in dots from the top left corner. `x` goes right and `y` goes down.

**Opening, drawing and showing:**

- `open a world with "Title", 800, 600` opens a window.
- `consume the window with "black"` fills it with one colour.
- `etch a box with x, y, width, height, "red"`, `etch a circle with x, y, radius, "blue"`, `etch a square with x, y, half width, "purple"` and `etch a line with x, y, to x, to y, "white"` draw shapes.
- `etch words with "Score: " plus score, x, y, "yellow"` draws text, and `set the text size to 32` makes it bigger.
- `etch the picture with "ship.png", x, y` draws a .png or .gif. `etch the picture turned with` adds size and angle, and `etch the sheet frame with` draws one frame of a sprite sheet.
- `reveal the frame` shows what you drew, then waits so the game runs at 60 frames a second.
- `the world lives` turns to no when the person closes the window, and `end the world` closes it yourself.
- `frame time` is how long the last frame took, so movement can stay smooth on slow computers.

**Keys and the mouse:**

- `key held "left"` is yes while a key is down. `key pressed "space"` is yes for one frame only, so one press does one thing.
- `mouse x`, `mouse y`, `mouse held`, `mouse clicked`, `mouse right held`, `mouse right clicked` and `mouse wheel turned` cover the mouse.
- `hold the pointer` hides the pointer and keeps it in the window for 3D games. Then `mouse moved across` and `mouse moved down` tell you how far it moved.

**Colours** are names (`black`, `white`, `red`, `green`, `blue`, `yellow`, `orange`, `purple`, `pink`, `brown`, `grey`) or codes like `"#ff8800"`. `colour from (255, 136, 0)` builds one from numbers.

**3D.** The same window shows a 3D world, seen from **the eye**:

- `place the eye at 0 horizontal 1.6 vertical -10 depth` and `aim the eye with (turn, tilt)` set the camera.
- `etch the ground with ("green", "#2a7a2a")` draws a checkered floor.
- `etch a cube with`, `etch a block with`, `etch a ball with` and `etch a triangle in space with` draw shapes.
- `etch the model with ("ship.obj", middle, 2, 45, "")` loads a 3D model.
- `etch the picture in space with` lays a picture on the world like a texture.
- `shine the light from`, `set the daylight to 0.3` and `set the eye view to 90` set the mood.
- `start keeping the shapes as "house"` and `etch the kept shapes "house"` let you draw thousands of blocks every frame without slowing down.
- `shade the shapes with the command tint` gives each shape a colour from your own command.

The graphics card draws the 3D shapes, so things hide behind each other properly and balls are smoothly lit.

### Making your own library

A library is a `.words` file. Each word says what it means in C++ (for built programs) and, on a `runs:` line, in Python (for running directly):

```
to wait, given seconds (a number) = std::this_thread::sleep_for(std::chrono::duration<double>({seconds}))
  runs: time.sleep(max(0.0, {seconds}))
```

`{seconds}` stands for the input. A `web:` line adds the JavaScript version. Libraries can also bring headers (`include:`), system libraries (`link:`), and helper code (`code:`, `python:`, `javascript:`).

You can also borrow words without writing a library:

- **`use python "statistics":`** gives words for Python functions (when running directly).
- **`use the library "user32.dll":`** gives words for C functions in any `.dll` or `.so`.
- **`stellanova get user/project`** fetches someone else's library from GitHub. Only get libraries from people you trust, since a library can run any code.

## Programs for web pages

`stellanova web` turns a program into JavaScript. With the `page` library, it can run a real web page:

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

Window games work in a browser as they are: the window becomes a canvas in the page.

## Wrapping up

That's the whole language. To recap the shape of things:

- A program starts at `genesis:`, and every block ends with `and the universe said i love you`.
- `set` keeps values, `scrawl` shows them, and `ask` takes them from people.
- `to` makes commands, `returning` gives them answers, and `for a pet` gives them to a kind of thing.
- `a pet has:` describes your own kinds, and `conjure` makes them.
- `try:` and `if that went wrong:` handle problems.
- Libraries add everything else, from windows and sound to databases and web servers.

The examples folder is the best place to go next. `guess.stella` is a guessing game, `pets.stella` shows lists and kinds of things, `dodge.stella` and `pong.stella` are games in a window, and `driftstone.stella` is an island of blocks you can dig, build on and craft with, all in plain English.

Happy writing.
