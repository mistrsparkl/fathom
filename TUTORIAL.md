# Learning Imagination

This walks through Imagination from the very first line to a small game. Every program here really works: the self-check runs each one and compares what it prints with what is written under it.

To run a program, save it in a file ending in `.imagine` (for example `hello.imagine`) and type:

```
imagine hello.imagine
```

## 1. Saying something

```imagination
genesis:
  say "Hello!"
and the universe said i love you
```

```output
Hello!
```

A program is made of **commands**. `genesis:` is where every program begins (`to start:` means the same). The lines that belong to it are indented (moved right) under it, and it ends with the line `and the universe said i love you`.

`say` shows something on the screen. Text goes between quote marks.

## 2. Remembering things

```imagination
genesis:
  set name to "Sam"
  set age to 11
  say "This is ", name, "."
  say "Next year ", name, " will be ", age plus 1, "."
and the universe said i love you
```

```output
This is Sam.
Next year Sam will be 12.
```

`set ... to ...` remembers a value under a name. A name can be several words, like `best score`. `say` can show several things one after another, with commas between them.

## 3. Choosing

```imagination
genesis:
  set temperature to 31
  if temperature is more than 30:
    say "It's hot."
  otherwise if temperature is less than 10:
    say "It's cold."
  otherwise:
    say "It's nice."
and the universe said i love you
```

```output
It's hot.
```

`if` does its indented lines only when the thing after it is yes. `otherwise if` and `otherwise` are tried in turn when the ones above them were no.

## 4. Doing things again

```imagination
genesis:
  repeat 3 times:
    say "Hip hip hooray!"
  for each n from 1 to 5:
    say n, " times 7 is ", n times 7
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

`repeat` does its lines a number of times. `for each n from 1 to 5` does them once for each number, with `n` being that number. There is also `while ...:`, which keeps going while something is yes.

## 5. Lists

```imagination
genesis:
  set shopping to a list of ("milk", "eggs")
  add "bread" to shopping
  say "I need ", size of shopping, " things: ", shopping
  for each thing in shopping:
    say "- ", thing
  if shopping contains "eggs": say "Don't drop the eggs!"
  say "The first thing is ", item 1 of shopping, "."
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

```imagination
genesis:
  greet with "Sam"
  greet with "Ann"
  say "Double 21 is ", double 21
and the universe said i love you

to greet, given who (text):
  say "Hello, ", who, "!"
and the universe said i love you

to double, given x (a number), giving back a number:
  give back x times 2
and the universe said i love you
```

```output
Hello, Sam!
Hello, Ann!
Double 21 is 42
```

A command can take **inputs** (after `given`, each with its kind in brackets) and can **give back** an answer. Putting a job in its own command gives it a name, so the program reads like a list of what happens.

## 7. Your own kinds of things

```imagination
a pet has:
  name (text)
  age (a number)
and the universe said i love you

genesis:
  set rex to a new pet
  set name of rex to "Rex"
  set age of rex to 3
  say rex
  say name of rex, " is ", age of rex, " years old."
and the universe said i love you
```

```output
a pet (name: Rex, age: 3)
Rex is 3 years old.
```

`a pet has:` describes a new kind of thing and its parts. After that, `a new pet` makes one, and `name of rex` is one of its parts.

## 8. Asking

Programs can ask the person using them a question:

```
genesis:
  ask "What's your name? " into name
  ask "How old are you? " into age (a number)
  say "Hi ", name, "! In ten years you'll be ", age plus 10, "."
and the universe said i love you
```

`ask` shows the question and waits for an answer. With `(a number)` it keeps asking until a number is typed.

## 9. When things go wrong

A mistake in the script is found before it runs, and explained in plain words:

```
guess.imagine line 4: I don't know 'scroe'. Did you mean 'score'?
```

A problem while it runs stops it with the line where it happened. To carry on instead, use `try:`:

```imagination
genesis:
  try:
    say contents of file "missing.txt"
  if that went wrong:
    say "No luck: ", the problem
  say "Still going."
and the universe said i love you
```

```output
No luck: there is no file called "missing.txt" (or it can't be opened).
Still going.
```

## 10. A game

Programs can open a window and draw in it. This is a whole game: a ball you move with the arrow keys.

```
genesis:
  open a window with "Ball", 600, 400
  set birth to (300, 200)
  while the window is open:
    if key held "left": set birth of x to birth of x minus 5
    if key held "right": set birth of x to birth of x plus 5
    if key held "up": set birth of y to birth of y minus 5
    if key held "down": set birth of y to birth of y plus 5
    consume the window with "black"
    draw a circle with birth of x, birth of y, 20, "orange"
    show the frame
and the universe said i love you
```

`(300, 200)` is a place on the screen: 300 across, 200 down. `birth of x` is its across part and `birth of y` its down part. `consume the window` paints over everything drawn before, ready for the next picture, and `show the frame` puts the picture on the screen (60 times a second).

The window words come from a **library**, a set of extra words. Libraries load by themselves when you use their words.

`examples/dodge.imagine` is a bigger game: dodge the falling balls.

## Where next

- `LANGUAGE.md` lists everything the language can do.
- Type `imagine` on its own to try lines out one at a time.
- `imagine build game.imagine` makes a program into an `.exe` that runs on its own and fast.
