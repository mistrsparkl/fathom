# Learning Fathom

This goes from your first line all the way to a small game. Every program in here actually runs. The tests run each one and check it prints what's written underneath.

Save a program in a file that ends in `.fathom`, like `hello.fathom`, and run it with:

```
fathom hello.fathom
```

## 1. Saying something

```fathom
genesis:
  scrawl "Hello!"
and the universe said i love you
```

```output
Hello!
```

Programs are made of commands. Every program starts at `genesis:`. The lines that belong to it are pushed in two spaces, and it finishes with `and the universe said i love you`.

`scrawl` puts something on the screen. Text goes in quote marks.

If you put a name in square brackets inside some text, you get whatever that name holds:

```fathom
genesis:
  set name to "Sam"
  set coins to 3
  scrawl "Hello, [name]! You have [coins] coins, and [coins plus 1] after this one."
and the universe said i love you
```

```output
Hello, Sam! You have 3 coins, and 4 after this one.
```

It only does that when there are words in the brackets, so something like `"[0-9]"` is left alone. If you really want brackets around a word, double them up. `"[[NaN]]"` shows `[NaN]`.

## 2. Remembering things

```fathom
genesis:
  set name to "Sam"
  set age to 11
  scrawl "This is ", name, "."
  scrawl "Next year ", name, " will be ", age plus 1, "."
and the universe said i love you
```

```output
This is Sam.
Next year Sam will be 12.
```

`set ... to ...` stores a value under a name. Names can be more than one word, like `best score`. You can give `scrawl` a few things at once with commas between them.

## 3. Choosing

```fathom
genesis:
  set temperature to 31
  if temperature exceeds 30:
    scrawl "It's hot."
  otherwise if temperature falls below 10:
    scrawl "It's cold."
  otherwise:
    scrawl "It's nice."
and the universe said i love you
```

```output
It's hot.
```

`if` only runs its pushed-in lines when what comes after it is true. If it isn't, Fathom tries the `otherwise if`, and then the `otherwise`.

When you're choosing based on one value, `depending on` is nicer:

```fathom
genesis:
  set weather to "snow"
  depending on weather:
    "rain": scrawl "Take an umbrella."
    "snow", "hail":
      scrawl "Wear a coat."
      scrawl "And boots."
    anything else: scrawl "Enjoy the day."
and the universe said i love you
```

```output
Wear a coat.
And boots.
```

Each line under it has a value, or a few with commas, then a `:` and what to do. `anything else:` catches the rest.

### Testing your commands

A `check` line says something that ought to be true. Put your checks in commands whose names start with `test`:

```fathom
to double, given x (a number), returning a number:
  return x times 2
and the universe said i love you

to test doubling:
  check double with 2 is 4
  check double with 0 is 0
and the universe said i love you

genesis:
  scrawl double with 21
and the universe said i love you
```

```output
42
```

`fathom test maths.fathom` runs the tests instead of genesis and tells you how they went:

```
✓ test doubling
1 test: 1 passed, 0 failed.
```

When a check fails you get the line and what went wrong, like `✗ test doubling: line 7: this check failed: double with 0 is 1`.

### Watching a program run

`fathom watch` runs a program one line at a time and shows you the names that change:

```
> fathom watch hot.fathom
▸ line 2: set temperature to 31
    temperature: 31
▸ line 3: if temperature exceeds 30:   → yes
▸ line 4: scrawl "It's hot."
It's hot.
```

## 4. Doing things again

```fathom
genesis:
  repeat 3 times:
    scrawl "Hip hip hooray!"
  for each n from 1 to 5:
    scrawl n, " times 7 is ", n times 7
and the universe said i love you
```

```output
Hip hip hooray!
Hip hip hooray!
Hip hip hooray!
1 times 7 is 7
2 times 7 is 14
3 times 7 is 21
4 times 7 is 28
5 times 7 is 35
```

`repeat` runs its lines a set number of times. `for each n from 1 to 5` runs them once per number, and `n` is the number it's on. `as long as ...:` keeps going for as long as something stays true.

### Whenever and every

You can tell a command what to do whenever something happens, or every so often. Those lines kick in after the rest of the command is done and keep going until the program ends:

```fathom
genesis:
  set ticks to 0
  every 0.1 seconds:
    set ticks to ticks plus 1
    scrawl "tick [ticks]"
  whenever ticks is 3:
    scrawl "That's three."
    end the program with 0
  scrawl "Waiting..."
and the universe said i love you
```

```output
Waiting...
tick 1
tick 2
tick 3
That's three.
```

Games use this a lot. `every frame:` is where moving and drawing go, and `whenever key pressed "space":` is what a key does. The frame gets shown after each round by itself, and it all stops when someone closes the window.

## 5. Lists

```fathom
genesis:
  set shopping to a list of ("milk", "eggs")
  add "bread" to shopping
  scrawl "I need ", the size of shopping, " things: ", shopping
  for each thing in shopping:
    scrawl "- ", thing
  if shopping contains "eggs": scrawl "Don't drop the eggs!"
  scrawl "The first thing is ", item 1 of shopping, "."
and the universe said i love you
```

```output
I need 3 things: milk, eggs, bread
- milk
- eggs
- bread
Don't drop the eggs!
The first thing is milk.
```

A list holds a bunch of values in order. The first item is item 1, not 0.

## 6. Your own commands

```fathom
genesis:
  greet with "Sam"
  greet with "Ann"
  scrawl "Double 21 is ", double 21
and the universe said i love you

to greet, given who (text):
  scrawl "Hello, ", who, "!"
and the universe said i love you

to double, given x (a number), returning a number:
  return x times 2
and the universe said i love you
```

```output
Hello, Sam!
Hello, Ann!
Double 21 is 42
```

Commands can take inputs. They go after `given`, with what kind they are in brackets. A command can also hand back an answer with `return`. Splitting your program into commands means genesis ends up reading like a list of what happens.

### Usual values

You can give an input a usual value. If you leave it out when you call the command, it uses that:

```fathom
to greet, given name (text, usually "friend") and count (a number, usually 1):
  repeat count times:
    scrawl "Hello, [name]!"
and the universe said i love you

genesis:
  greet
  greet with "Sam"
  greet with ("Jo", 2)
and the universe said i love you
```

```output
Hello, friend!
Hello, Sam!
Hello, Jo!
Hello, Jo!
```

Inputs with usual values have to go last, and the value has to be written out: some text, a number, `yes` or `no`.

## 7. Your own kinds of things

```fathom
a pet has:
  name (text)
  age (a number)
and the universe said i love you

genesis:
  set rex to conjure a pet
  set the name of rex to "Rex"
  set the age of rex to 3
  scrawl rex
  scrawl the name of rex, " is ", the age of rex, " years old."
and the universe said i love you
```

```output
a pet (name: Rex, age: 3)
Rex is 3 years old.
```

`a pet has:` makes up a new kind of thing and lists its parts. Then `conjure a pet` makes one, and `the name of rex` gets at one of its parts.

## 8. Asking

A program can ask whoever's using it a question:

```
genesis:
  ask "What's your name? " into name
  ask "How old are you? " into age (a number)
  scrawl "Hi ", name, "! In ten years you'll be ", age plus 10, "."
and the universe said i love you
```

`ask` shows the question and waits. Add `(a number)` and it'll keep asking until it gets one.

## 9. When things go wrong

Mistakes in your script get caught before it runs, and the message tries to say what to do about it:

```
guess.fathom line 4: I don't know 'scroe'. Did you mean 'score'?
```

If something goes wrong while it's running, it stops and tells you the line. Wrap it in `try:` if you'd rather keep going:

```fathom
genesis:
  try:
    scrawl contents of file "missing.txt"
  if that went wrong:
    scrawl "No luck: ", the wound
  scrawl "Still going."
and the universe said i love you
```

```output
No luck: there is no file called "missing.txt" (or it can't be opened).
Still going.
```

You can make your own commands fail on purpose with `raise an error`, and `try:` catches those too:

```fathom
to fly, given fuel (a number):
  if fuel falls below 10: raise an error with "not enough fuel (only " plus fuel plus ")"
  scrawl "Up we go!"
and the universe said i love you

genesis:
  try:
    fly with 3
  if that went wrong:
    scrawl "Grounded: ", the wound
and the universe said i love you
```

```output
Grounded: not enough fuel (only 3)
```

## 10. A game

A program can open a window, which Fathom calls a world, and draw in it. Here's a whole game. It's a ball you move around with the arrow keys:

```
genesis:
  open a world with "Ball", 600, 400
  set birth to 300 horizontal 200 vertical
  as long as the world lives:
    if key held "left": set the existence of horizontal to the existence of horizontal minus 5
    if key held "right": set the existence of horizontal to the existence of horizontal plus 5
    if key held "up": set the existence of vertical to the existence of vertical minus 5
    if key held "down": set the existence of vertical to the existence of vertical plus 5
    if key pressed "space": set existence to birth
    consume the window with "black"
    etch a circle with the birth of horizontal, the birth of vertical, 4, "white"
    etch a circle with the existence of horizontal, the existence of vertical, 20, "orange"
    reveal the frame
and the universe said i love you
```

`300 horizontal 200 vertical` is a spot on the screen, 300 across and 200 down. `birth` is where the ball starts and `existence` is where it is right now. Setting `birth` puts `existence` there too. `the existence of horizontal` is how far across the ball is, and `the existence of vertical` is how far down.

Space sends the ball back to where it started, which is the little white dot. `consume the window` paints over the last frame so you can draw the next one, and `reveal the frame` puts it on screen. That happens 60 times a second.

The window words come from a library, which is just a set of extra words. You don't have to load it. Using one of its words is enough.

For a bigger game, look at `examples/dodge.fathom`. You dodge falling balls.

## 11. Kinds of kinds

A dog is a kind of pet. It has everything a pet has, plus some more. Any command that works on pets works on dogs too, unless you've written a dog version:

```fathom
a pet has:
  name (text)
and the universe said i love you

a dog is a kind of pet that has:
  tricks (a list of text)
and the universe said i love you

to speak, for a pet:
  scrawl name, " makes a sound."
and the universe said i love you

to speak, for a dog:
  scrawl name, " barks and knows ", the size of tricks, " tricks."
and the universe said i love you

genesis:
  set tom to conjure a pet
  set the name of tom to "Tom"
  set rex to conjure a dog
  set the name of rex to "Rex"
  add "sit" to the tricks of rex
  speak tom
  speak rex
and the universe said i love you
```

```output
Tom makes a sound.
Rex barks and knows 1 tricks.
```

## 12. Commands as values

`the command double` gives you the command itself instead of running it. You can store it, pass it to another command, and run it later with `invoke`:

```fathom
to double, given x (a number), returning a number:
  return x times 2
and the universe said i love you

to do twice, given f (a command given a number returning a number) and x (a number), returning a number:
  return invoke f with (invoke f with x)
and the universe said i love you

genesis:
  scrawl do twice with (the command double, 5)
  set steps to a list of (the command double, the command round)
  for each step in steps: scrawl invoke step with 2.6
and the universe said i love you
```

```output
20
5.2
3
```

## 13. Two things at once

`meanwhile` starts a command and moves on without waiting for it. `wait for the others` waits until they've all finished:

```fathom
to note down, given name (text):
  inscribe "hello from " plus name into file name plus ".txt"
and the universe said i love you

genesis:
  meanwhile note down with "first"
  meanwhile note down with "second"
  wait for the others
  scrawl contents of file "first.txt", " / ", contents of file "second.txt"
and the universe said i love you
```

```output
hello from first / hello from second
```

## 14. Talking to other programs

A lot of websites and programs talk in JSON. `as saved text` turns anything into JSON, and `load ... from the text` reads it back in. Patterns let you find bits of text by what they look like:

```fathom
genesis:
  set scores to a table of numbers
  set entry "Sam" of scores to 31
  set entry "Jo" of scores to 7
  set words to scores as saved text
  scrawl words
  set again to a table of numbers
  load again from the text words
  scrawl entry "Sam" of again
  scrawl matches of the pattern with ("[0-9]+", "Sam is 31, Jo is 7")
and the universe said i love you
```

```output
{"Jo": 7, "Sam": 31}
31
31, 7
```

There's more in the libraries. `web` fetches and sends pages, `server` turns your program into a web server, `folders` deals with files and folders, and `computer` runs other programs, like `the output of the command "dir"`. LANGUAGE.md covers all of them.

## 15. Grammar for people

Fathom is meant to be read by people, so it wants proper grammar in a few spots. You need `the` before a part, as in `the size of` or `the title of`. You need `a` or `an` after `conjure` and before `list containing`.
The computer checks they're there and then ignores them. They don't change what the program does.
If a command has a lot of inputs, you can put them on their own lines under `use:`:

```fathom
a notice has:
  title (text)
and the universe said i love you

the world remembers:
  total (a number)
and the universe said i love you

to tell, use:
  title (text)
  count (a number)

  conjure a notice as new notification
  set the title of new notification to title
  set kept notices to a list containing new notification
  add count to the total
  scrawl the size of kept notices, " ", the title of new notification
and the universe said i love you

genesis:
  tell with "hello", 2
  tell with "again", 3
  scrawl the total
and the universe said i love you
```

```output
1 hello
1 again
5
```

Write `scrawl size of kept notices` without the `the` and Fathom will tell you: Write 'the size of', not 'size of'.

## 16. Tidy programs

```fathom
a cost has:
  kind (text)
  amount (a number)
and the universe said i love you

to cost of, given kind (text) and amount (a number), returning a cost:
  conjure a cost as c
  set the kind of c to kind
  set the amount of c to amount
  return c
and the universe said i love you

genesis:
  set costs to a list of (cost of with ("food", 20.75), cost of with ("rent", 700), cost of with ("fun", 20))
  for each c in sorted costs by amount, biggest first:
    scrawl the kind of c padded to 6 letters, the amount of c
  scrawl sorted a list of ("Tomas", "Al", "Rex") by each n becomes the size of n
  scrawl upper case of "café", " ", folder "saves" exists
and the universe said i love you
```

```output
rent  700
food  20.75
fun   20
Al, Rex, Tomas
CAFÉ no
```

`sorted costs by amount` puts the smallest first, and adding `, biggest first` flips it. You can sort by anything you work out from each item with `by each n becomes ...`. Items that tie stay in the order they were in.

`padded to 6 letters` adds spaces after some text so your columns line up. Text words count letters, not bytes, so `upper case of` works with any alphabet. `folder "saves" exists` is yes or no, and so is `file "notes.txt" exists`.

Two things that help with bigger programs. If you write a part as `amount (a number, hidden)`, only that kind's own commands (like `to pay, for a cost, ...:`) can touch it, so nothing else changes it by accident. And if your program is split over several scripts, `to tidy, privately:` keeps the command inside its own script. Other scripts can't use it, and they can have their own `tidy`.

## Where next

LANGUAGE.md has everything the language can do. Type `fathom` by itself to try lines out one at a time. And `fathom build game.fathom` turns your program into an `.exe` that runs fast and on its own.
