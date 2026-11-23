# Fathom: a programming language you can read out loud

I wanted a language where the code just says what it does, in normal words. Fathom is what I ended up with. You can run a script straight away, build it into a fast `.exe`, turn it into WebAssembly, or turn it into JavaScript for a web page. This post goes through most of it with small examples.

## Hello

A Fathom program is a text file ending in `.fathom`:

```
genesis:
  scrawl "Hello, world!"
and the universe said i love you
```

Run it with `fathom hello.fathom`. There's no project file and no compile step you have to think about.

Every program starts at `genesis:`. Every block, whether it's genesis, a command or a kind of thing, ends with `and the universe said i love you`. It's a bit sentimental, I know. I like it.

The other ways to run things:

```
fathom build game.fathom          a real .exe (or a Linux program if you're on Linux)
fathom wasm game.fathom           WebAssembly, plus a .mjs so node can run it
fathom web game.fathom site       JavaScript for a web page
fathom check game.fathom          look for mistakes without running
fathom test maths.fathom          run the commands whose names start with test
fathom debug game.fathom 12 30    stop before lines 12 and 30 so you can poke around
fathom profile game.fathom        see which lines are slow
fathom watch game.fathom          show each line as it runs
fathom                            type lines and they run right away (bye to leave)
```

Whichever way you run a program, it does the same thing. The tests make sure of that by running everything both ways and comparing the output.

On speed: built programs keep up with C++ for number crunching, function calls and lists of numbers. Running straight from the script is more like Python. So mess around without building, and build when you want it fast.

When you get something wrong, it tells you in plain words:

```
follow.fathom line 31: I don't know 'walk sped'. Did you mean 'walk speed'?
```

## Values

Every value has a kind. Once a name holds a number, it holds a number for good. The kinds are numbers (`60`, `2.5`, `30 degrees`, where `degrees` is just there for you to read), yes or no, text, places (`1 horizontal 2 vertical 3 depth`), flat places (`300 horizontal 200 vertical`, like a spot on the screen), lists, tables, and whatever kinds you make up yourself.

If you mix them up it catches it. Say `turn rate` holds a number and you write `set turn rate to fallen`. You'll get `'turn rate' holds a number, not yes or no.`

Names can be several words:

```
set braking speed to 12
set player name to "Sam"
```

The first `set` makes the name and later ones change it. A name you make inside a command only exists in that command. If you want something every command can see, put it in `the world remembers:`:

```
the world remembers:
  score (a number)
  players (a list of text)
and the universe said i love you
```

## Talking to people

`scrawl` prints, and text fills itself in from square brackets:

```
scrawl "Hello, [name]! [count plus 1] left."
```

`ask` asks a question and keeps the answer:

```
ask "What's your name? " into name
ask "How old are you? " into age (a number)
ask "Play again? " into again (yes or no)
```

If you ask for a number it keeps asking until it gets one. Yes or no takes `yes`, `y`, `no` or `n`.

## Working things out

Maths is `plus`, `minus`, `times` and `divided by`, though `+ - * /` work too. `2 to the power 10` does powers. There's a pile of other number words: `square root of x`, `smaller of a and b`, `clamp x between low and high`, `random number from 1 to 100`, `(price times 1.2) rounded to 2 decimal places`, `1234567 with commas`, `7 padded to 3 digits`.

Comparing reads like English. `a exceeds b` is bigger than, `a falls below b` is smaller than, and there's `is at least`, `is at most`, `is`, `is not`, and `answer is one of ("yes", "y", "sure")`. For games there's `existence is within 30 of coin` and `ball touches coin`.

Text has the stuff you'd expect: `"Hi " plus name`, `the size of name`, `letters 2 to 4 of name`, `upper case of name`, `name begins with "Dr"`, `replace "a" with "b" in name`, `line split by ", "`. `upper case of "straße ω"` gives "STRAßE Ω", so it isn't stuck on A to Z.

## Lists and tables

```
set scores to a list of numbers
set primes to a list of (2, 3, 5, 7)
add 5 to scores
insert 5 at 2 in scores
remove item 2 from scores
set item 2 of scores to 9
```

Items count from 1, like people count. You can read them with `item 2 of scores`, `last item of scores`, `items 2 to 5 of scores` and `first 3 of scores`. There's also `sum of scores`, `average of scores`, `biggest of scores`, `sorted scores`, `reversed scores`, `shuffled names` and `join names with ", "`. `sorted pets by age, biggest first` sorts your own things by one of their parts.

Tables look things up by name, kind of like a phone book:

```
set ages to a table of numbers
set entry "Rex" of ages to 3
scrawl entry "Rex" of ages
remove entry "Rex" from ages
```

## Choosing and looping

```
if score exceeds 100:
  scrawl "Amazing!"
otherwise if score exceeds 50:
  scrawl "Nice."
otherwise:
  scrawl "Keep going."
```

If you're choosing on one value, `depending on` is tidier:

```
depending on weather:
  "rain": scrawl "Umbrella!"
  "sun", "heat": scrawl "Sunscreen!"
  anything else: scrawl "Just a jacket."
```

Loops are `repeat 10 times:`, `as long as guess is not secret:`, `for each score in scores:`, `for each n from 1 to 10:` and `for each n from 0 to 100 by 5:`. `break free` gets you out of one and `move on` skips to the next go.

There are also ones that run by themselves once a command's other lines are done. `whenever ticks exceeds 2:` runs each time that turns true, `every 2 seconds:` runs on a timer, and `every frame:` runs once per frame in a game.

## Commands

```
to greet, given who (text):
  scrawl "Hello, " plus who plus "!"
and the universe said i love you
```

Then `greet with "Sam"`. With two or more inputs you put them in brackets, like `pet called with ("Rex", 3)`. Add `returning` and the command can give back an answer:

```
to double, given x (a number), returning a number:
  return x times 2
and the universe said i love you
```

`the command double` is the command itself, so you can store it or pass it around and run it later with `invoke`.

## Your own kinds of things

```
a pet has:
  name (text)
  age (a number)
  tricks (a list of text)
and the universe said i love you
```

`conjure a pet` makes one. `the name of rex` reads a part and `set the name of rex to "Rex"` changes it. `scrawl rex` shows the whole thing: `a pet (name: Rex, age: 3, tricks: sit)`.

Commands can belong to a kind:

```
to bounce, for a ball:
  set speed to speed times -1
  set bounces to bounces plus 1
and the universe said i love you
```

Inside, the ball's parts are plain names, and changing them changes the actual ball. You call it with `bounce b`.

You can also do kinds of kinds (`a dog is a kind of pet that has:`), kinds that hold any kind (`a stack of anything has:`), and shared abilities (`a speaker is anything that can speak.`). A part written `balance (a number, hidden)` can only be touched by that kind's own commands. A name can hold nothing, as in `set best to no enemy`, and you check it with `if best is nothing`.

## Files

```
inscribe "hello" into file "notes.txt"
add "a line" to file "log.txt"
scrawl contents of file "notes.txt"
save high scores to file "scores.json"
load high scores from file "scores.json"
```

`save` and `load` work on any value and use JSON. If you add a part to a kind later, your old saves still load. The new part just starts out empty. `scores as saved text` gives you the JSON without a file, which is handy for web services. It'll even match `windSpeed` or `wind_speed` to a part you called `wind speed`.

## When things go wrong

```
try:
  set notes to contents of file "notes.txt"
if that went wrong:
  scrawl "I couldn't read the notes: ", the wound
  set notes to ""
```

`the wound` is what went wrong. You can raise your own with `raise an error with "the tank is empty"`. You can also give it a kind, like `raise a fuel problem with ...`, and catch only those with `if that went wrong with a fuel problem:`.

## Two things at once

```
meanwhile download with ("https://example.com/a.png", "a.png")
scrawl "Downloading in the background..."
wait for the others
```

Everything started with `meanwhile` gets its own copy of every name, so they can't mess each other up. When they do need to share something, they take turns:

```
holding the lock "total":
  set total to total plus 1
```

## Games

This is the part I have the most fun with.

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

`consume the window` clears it and `etch` draws circles, boxes, lines, words and pictures. `reveal the frame` shows what you drew and keeps things at 60 frames a second. For keys there's `key held "left"` and `key pressed "space"`, and the mouse has `mouse x`, `mouse clicked` and so on. It does 3D as well, with cubes, balls, models, lights and a camera you can move.

There are libraries for lots more: sound, pictures, physics, animation, databases, web pages, web servers, sockets, zip files, JSON, email. They load by themselves when you use one of their words. If you need something they don't have, you can call a C library or (when running straight from the script) a Python package.

## The web

`fathom web game.fathom site` turns a program into a web page. Window games just work there, since the window turns into a canvas. You can also deal with the page directly:

```
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

## That's most of it

If you want to keep going, look in the examples folder. `guess.fathom` is a guessing game, `pets.fathom` has lists and kinds of things, `dodge.fathom` and `pong.fathom` are window games, and `driftstone.fathom` is an island made of blocks that you can dig, build on and craft with. LANGUAGE.md has everything else.
