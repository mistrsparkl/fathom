# Learning Stellanova

This walks through Stellanova from the very first line to a small game. Every program here really works: the self-check runs each one and compares what it prints with what is written under it.

To run a program, save it in a file ending in `.stella` (for example `hello.stella`) and type:

```
stellanova hello.stella
```

## 1. Saying something

```stellanova
genesis:
  scrawl "Hello!"
and the universe said i love you
```

```output
Hello!
```

A program is made of **commands**. `genesis:` is where every program begins (`genesis:` means the same). The lines that belong to it are indented (moved right) under it, and it ends with the line `and the universe said i love you`.

`scrawl` shows something on the screen. Text goes between quote marks.

Words in square brackets inside text are filled in with what they hold:

```stellanova
genesis:
  set name to "Sam"
  set coins to 3
  scrawl "Hello, [name]! You have [coins] coins, and [coins plus 1] after this one."
and the universe said i love you
```

```output
Hello, Sam! You have 3 coins, and 4 after this one.
```

Only brackets holding words are filled in, so a pattern like `"[0-9]"` stays as it is. To show brackets around words, double them: `"[[NaN]]"` shows `[NaN]`.

## 2. Remembering things

```stellanova
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

`set ... to ...` remembers a value under a name. A name can be several words, like `best score`. `scrawl` can show several things one after another, with commas between them.

## 3. Choosing

```stellanova
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

`if` does its indented lines only when the thing after it is yes. `otherwise if` and `otherwise` are tried in turn when the ones above them were no.

When the choice is about one value, `depending on` reads better:

```stellanova
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

Each line under it is a value (or several, with commas), a `:`, then what to do. `anything else:` is for every other value.

### Testing your commands

A `check` line says something that should be so. Put checks in commands whose names start with `test`:

```stellanova
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

`stellanova test maths.stella` runs every test (not genesis) and shows which passed:

```
✓ test doubling
1 test: 1 passed, 0 failed.
```

A check that isn't so says which line and what failed: `✗ test doubling: line 7: this check failed: double with 0 is 1`.

### Watching a program run

`stellanova watch` runs a program and shows each line as it happens, with the names it changed:

```
> stellanova watch hot.stella
▸ line 2: set temperature to 31
    temperature: 31
▸ line 3: if temperature exceeds 30:   → yes
▸ line 4: scrawl "It's hot."
It's hot.
```

## 4. Doing things again

```stellanova
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

`repeat` does its lines a number of times. `for each n from 1 to 5` does them once for each number, with `n` being that number. There is also `as long as ...:`, which keeps going while something is yes.

### Whenever and every

A command can say what to do whenever something happens, and every so often. Those lines start once the command's other lines are done, and go on until the program ends:

```stellanova
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

In a game, `every frame:` holds what happens each frame (moving, drawing), and `whenever key pressed "space":` what a key does. The frame is shown after each round on its own, and it all stops when the window is closed.

## 5. Lists

```stellanova
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

A list keeps several values in order. Items are counted from 1.

## 6. Your own commands

```stellanova
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

A command can take **inputs** (after `given`, each with its kind in brackets) and can **return** an answer. Putting a job in its own command gives it a name, so the program reads like a list of what happens.

### Usual values

An input can have a usual value. Leave it out when calling, and the command gets that value:

```stellanova
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

Inputs with a usual value go last. The value is written out: text, a number, `yes` or `no`.

## 7. Your own kinds of things

```stellanova
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

`a pet has:` describes a new kind of thing and its parts. After that, `conjure a pet` makes one, and `the name of rex` is one of its parts.

## 8. Asking

Programs can ask the person using them a question:

```
genesis:
  ask "What's your name? " into name
  ask "How old are you? " into age (a number)
  scrawl "Hi ", name, "! In ten years you'll be ", age plus 10, "."
and the universe said i love you
```

`ask` shows the question and waits for an answer. With `(a number)` it keeps asking until a number is typed.

## 9. When things go wrong

A mistake in the script is found before it runs, and explained in plain words:

```
guess.stella line 4: I don't know 'scroe'. Did you mean 'score'?
```

A problem while it runs stops it with the line where it happened. To carry on instead, use `try:`:

```stellanova
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

Your own commands can go wrong on purpose with `raise an error`, and `try:` catches that the same way:

```stellanova
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

Programs can open a world (a window) and etch in it. This is a whole game: a ball you move with the arrow keys.

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

`300 horizontal 200 vertical` is a place on the screen: 300 across, 200 down. `birth` is where the ball starts, and `existence` is where it is now. `the existence of horizontal` is how far across it is, and `the existence of vertical` how far down. Space sends it back to its birth (a small white dot). `consume the window` paints over everything etched before, ready for the next picture, and `reveal the frame` puts the picture on the screen (60 times a second).

Setting `birth` also makes `existence` start at the same place.

The window words come from a **library**, a set of extra words. Libraries load by themselves when you use their words.

`examples/dodge.stella` is a bigger game: dodge the falling balls.

## 11. Kinds of kinds

A dog is a kind of pet: it has everything a pet has, and more. A command for pets works on dogs too, unless dogs have their own version:

```stellanova
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

`the command double` is the command itself, not its answer. You can keep it, give it to another command, and do it later with `invoke`:

```stellanova
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

`meanwhile` starts a command and carries straight on. `wait for the others` waits until they are all done:

```stellanova
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

Websites and other programs often speak JSON. `as saved text` writes anything as JSON, and `load ... from the text` reads it back. `patterns` find text by its shape:

```stellanova
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

The `web` library gets and sends pages (`web page`, `send to the web page`), `server` makes your program a web server, `folders` works with files and folders, and `computer` runs other programs (`the output of the command "dir"`). LANGUAGE.md has them all.

## 15. Grammar for people

Stellanova is written for people to read, so it asks for grammar in a few places: `the` before a part
(`the size of`, `the title of`), and `a` or `an` after `conjure` and before `list containing`.
The computer checks it is there, then skips it: `the`, `a` and `an` change nothing.
A command's inputs can also go on their own lines, under `use:`:

```stellanova
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

Leave out `the` in `scrawl size of kept notices` and Stellanova says: Write 'the size of', not 'size of'.

## 16. Tidy programs

```stellanova
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

`sorted costs by amount` puts the smallest first; `, biggest first` turns it round. `by each n becomes ...` sorts by anything worked out from each item, and things that come out the same keep their order. `padded to 6 letters` puts spaces after text so columns line up. Text words count letters, not bytes, so `upper case of` works in every alphabet. `folder "saves" exists`, like `file "notes.txt" exists`, is yes or no.

Two more for bigger programs. A part written `amount (a number, hidden)` can only be used by the commands for that kind (`to pay, for a cost, ...:`), so nothing else can change it by mistake. And in a program made of several scripts, `to tidy, privately:` keeps a command to the script it is in: other scripts can't use it, and can have a `tidy` of their own.

## Where next

- `LANGUAGE.md` lists everything the language can do.
- Type `stellanova` on its own to try lines out one at a time.
- `stellanova build game.stella` makes a program into an `.exe` that runs on its own and fast.
