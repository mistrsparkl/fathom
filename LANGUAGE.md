# Stellanova

This is the full reference. If you're just starting, TUTORIAL.md is friendlier.

Scripts end in `.stella`. Most of them are programs: they start at `genesis:` and you run them like this:

```
stellanova examples/guess.stella
```

That runs the script as it is. To get a fast `.exe` that runs on its own, build it. You'll need LLVM for that (`winget install LLVM.LLVM`, or `sudo apt install clang` on Linux):

```
stellanova build examples/guess.stella
```

The program does the same thing either way. The tests check that by running everything both ways and comparing the output.

There are a few other ways to run a script:

- `stellanova wasm examples/pets.stella` builds WebAssembly. You get `pets.wasm`, and `pets.mjs` so you can run it with `node pets.mjs` (`wasmtime --dir . pets.wasm` works too). It can use files in its folder, ask and print, use hashing, encryption and zip, and `meanwhile` works. It can't use C libraries, Python packages, or the libraries that need the operating system (window, sound, forms, web, network, database, computer, email, pictures). It needs the WASI sysroot. Get `wasi-sysroot-34.0.tar.gz` and `libclang_rt-34.0.tar.gz` from the wasi-sdk-34 release on github.com/WebAssembly/wasi-sdk and unpack them into `~/.stellanova/wasi`.
- `stellanova web examples/pets.stella site` turns it into JavaScript. You get `site/pets.js` plus `site/stellanova.js`. Put both in a page with `<script src="stellanova.js"></script><script src="pets.js"></script>`, or run it with `node pets.js`. There's more on this under Programs for web pages.
- A script can also be part of something else, like Unreal code for a creature. Those start with `this is part of: <thing>`. `py -3 stellanova.py <scripts folder> <output folder>` turns a folder of them into C++ (`<name>.stella.cpp`, which you don't edit).

And some tools:

- `stellanova check examples/guess.stella` looks for mistakes without running anything.
- `stellanova test examples/maths.stella` runs every `to test ...:` command instead of genesis and tells you which passed. A line like `check double with 2 is 4` fails with `this check failed: double with 2 is 4` if it isn't true. You can use `check` anywhere, not just in tests.
- `stellanova debug examples/guess.stella 12 30` stops before lines 12 and 30. Leave the numbers off and it stops before the first line. When it stops, Enter (or `step`) runs one line, `over` runs the line and whatever commands it calls, `out` runs until the current command finishes, and `go` runs to the next stop. `names` shows everything, `look score` shows one name, `stop at 40` and `forget 12` change the stops, and `quit` ends it. In Studia, click next to a line number to put a stop there and press Debug.
- `stellanova profile examples/pong.stella` runs the program and then lists the 20 slowest lines. For each one you get how many times it ran, its own time, its share of the total, and its time including the commands it called.
- `stellanova watch examples/guess.stella` shows each line as it runs, the names it changed, and which way each `if` went.
- `stellanova` by itself lets you type lines and run them one at a time. Names stick around between lines. Type a value like `5 plus 3` to see it. A line ending in `:` takes the pushed-in lines after it, until an empty line. `bye` quits.

When there's a mistake, the message tells you where and tries to tell you how to fix it:

```
follow.stella line 31: I don't know 'walk sped'. Did you mean 'walk speed'?
```

Some examples to look at: `examples/guess.stella` is a guessing game, `examples/pets.stella` uses lists and kinds of things, `examples/clock.stella` uses libraries, `examples/dodge.stella` is a window game, and `examples/follow.stella` is a script that's part of a creature, which makes a deer follow the player.

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

Then you can use it anywhere a value goes, like `scrawl "Ages added up: ", total age of shelter`. If a command takes one input, it goes right after the name, and `with` is optional. If it takes two or more, put them in brackets: `pet called with ("Rex", 3)`.

**Commands for a kind of thing.** `to bounce, for a ball:` makes a command that belongs to balls. Inside it you use the ball's parts by their names, and changing them changes the actual ball you passed in, not a copy:

```
to bounce, for a ball:
  set speed to speed times -1
  set bounces to bounces plus 1
and the universe said i love you
```

You call it with the ball, like `bounce b` or `bounce item 1 of balls`. Other inputs go after `given` like normal, so `to move along, for a ball, given steps (a number):` gets called as `move along with b, 2`. Inside the command, the whole ball is called `ball`.

**Commands as values.** `the command double` is the command itself, not what it gives back. You can store it in a name, a list or a part of a thing, pass it to another command, or return it from one. `invoke` runs it:

```
to apply to all, given f (a command given a number returning a number) and items (a list of numbers), returning a list of numbers:
  set out to a list of numbers
  for each item in items: add invoke f with item to out
  return out
and the universe said i love you

to double, given x (a number), returning a number:
  return x times 2
and the universe said i love you

to greet, given name (text):
  scrawl "Hi ", name
and the universe said i love you

genesis:
  scrawl apply to all with (the command double, a list of (1, 2, 3))
  set steps to a list of (the command double, the command round)
  invoke the command greet with "Sam"
and the universe said i love you
```

**Commands written where you use them.** `each x becomes x times 2` is a command too. You write it right where you need it, with the inputs before `becomes` (joined with `and` if there's more than one) and the answer after. Each input needs its kind in brackets, unless it's obvious from where it's going, like in `scores changed by each s becomes s times 2` or `scores kept by each s becomes s exceeds 10`. Otherwise you write it out: `set add tax to each price (a number) becomes price times 1.2`, or `each left (text) and right (text) becomes left plus right`. It remembers the names it uses as they were when you made it. So if you `set k to 3`, then `set add k to each x (a number) becomes x plus k`, then `set k to 100`, it still adds 3.

The kind of a command says what it takes and what it gives back. `a command` takes and gives nothing, then there's `a command given text`, `a command given a number and text returning yes or no`, and so on. Library words work too, like `the command round`. You can't store commands that belong to a kind of thing this way, and you can't compare or save commands.

**At the same time.** `meanwhile download with ("https://example.com/a.png", "a.png")` starts a command running by itself and goes straight on to the next line. `wait for the others` waits until everything you started with `meanwhile` is done. A program waits for them before it ends anyway. Each one gets its own copy of every name, as it was when it started, so they can't mess up each other's values. They do share files and the screen. If any of them hits a problem, the whole program stops. `meanwhile invoke f` works too.

**Sharing, with locks.** Commands running at the same time all share the names in `the world remembers:`. Only their own names are copies. If several of them change the same one, they need to take turns or changes get lost:

```
holding the lock "total":
  set total to total plus 1
```

Only one command at a time can be inside a lock with a given name. The rest wait. A command can take the same lock again inside itself, though not on the web yet. You can't leave partway through with `return`, `break free` or `move on`, and if something goes wrong inside, the lock gets let go.

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

**Commands for a kind of thing, as values.** You can store one of these too. `set older to the command grow` keeps `to grow, for a pet, given years (a number):` as a value of kind `a command given a pet and a number returning a pet`. It changes a copy of the pet and gives that copy back, so you'd write `set tom to invoke older with (tom, 3)` to keep the change. If the command returns something itself, like `to summary, for a pet, returning text:`, you get that instead.

**Python packages.** When a program runs directly (`stellanova program.stella`), it can use any Python package, with a word for each function:

```
use python "statistics":
  to middle of, given xs (a list of numbers), returning a number = median
and the universe said i love you
```

After the `=` goes the function's name in the package, or something like `linalg.norm` if it's inside part of the package. Inputs get passed to Python as they are, so lists become lists and tables become dictionaries, and the answer gets turned into whatever kind the word returns. If the package isn't installed, the message tells you how to get it. These words only work when running straight from the script, not built or on the web.

**Getting libraries.** `stellanova get <address>` downloads a library someone else made and keeps it, so any of your programs can `use:` it. The address can be a `.words` file (online or on your computer), a `.zip` of `.words` files, or a GitHub project written as `user/project`. `stellanova got` lists what you've got and where each one came from, and `stellanova drop <name>` gets rid of one. A library can run any code it likes on your computer, so only get them from people you trust.

**C functions from any library.** A program can call the functions in any C library (a `.dll` on Windows, `.so` elsewhere), with a word for each:

```
use the library "user32.dll":
  to message box, given owner (a number) and message (text) and title (text) and style (a number), returning a number = int MessageBoxA(pointer, text, text, int)
and the universe said i love you
```

After the `=` goes the C function: what it returns, its name, and the C type of each input. The types are `int`, `unsigned`, `long long`, `unsigned long long`, `double`, `float` and `pointer`, which are all numbers in Stellanova. Then there's `text` (a UTF-8 `char*`), `wide text` (a `wchar_t*`, for Windows' `...W` functions), `yes or no` (a `bool`), and `void` if it returns nothing. This works when running directly and when built, but not on the web. You can put the same words in a library of your own (`mine.words`, next to the script) after a `c library: user32.dll` line, writing each as `... = c: int MessageBoxA(pointer, text, text, int)`.

**Kinds for any kind.** A kind of thing can be described once for every kind it may hold, with `anything` standing for that kind:

```
a stack of anything has:
  items (a list of anything)
and the universe said i love you

to push, for a stack of anything, given x (anything):
  add x to items
and the universe said i love you

to top, for a stack of anything, returning anything:
  return last item of items
and the universe said i love you
```

Now `conjure a stack of numbers`, `a stack of text` and `a list of stacks of pets` all work, and each one is its own kind. It's like the description gets written out again with `anything` swapped for a number, or text, or a pet. The commands come along too, so `push with (counts, 3)` and `top words` work on whatever stack you give them.

**Kinds of kinds.** A kind of thing can be a kind of another one. It has all of the other's parts, and more of its own:

```
a dog is a kind of pet that has:
  tricks (a list of text)
and the universe said i love you

a puppy is a kind of dog:
and the universe said i love you
```

A part written like `balance (a number, hidden)` is hidden. Only that kind's own commands, and those of kinds made from it, can use or change it. Anywhere else, `the balance of acct` is a mistake. That way the kind gets to decide how it changes.

A dog has a name and an age, since every pet does, and it has tricks too. Commands for pets, like `to speak, for a pet:`, work on dogs and puppies as well. A dog can have its own version, `to speak, for a dog:`, and dogs and puppies will use that one instead. Every version has to take the same other inputs. You can also use a dog anywhere a pet is wanted: as a `(a pet)` input, in a list of pets, in a name holding a pet, or returned from a command that returns a pet. It goes in as a pet, though, so it's a copy with only a pet's parts and its tricks get left behind. It doesn't work the other way. A pet can't go where a dog is wanted.

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

1. **`this is part of:`** goes on the first line (after any notes) and says what thing the script belongs to. The words that thing already knows, like `fallen` or `walk speed`, are listed in `<name>.words` next to the script. See `examples/creature body.words`.
2. **`settings:`** are numbers with names, for tuning. Whatever comes after the number (`degrees`, `cm per second`) is just for you to read.
3. **`to ...:`** is a command, with its lines pushed in under it. Its inputs come after `given`, each with its kind in brackets.
4. **`and the universe said i love you`** has to come after every command, not pushed in. It's how Stellanova knows the command is over, and leaving it out is a mistake.

## Kinds of things

| Kind | Examples |
|---|---|
| a number | `60`, `2.5`, `walk speed`, `30 degrees` |
| yes or no | `yes`, `no`, `fallen`, `speed exceeds 10` |
| a place | `1 horizontal 2 vertical 3 depth`, `centre of mass`, `goal` (a point in space: across, down and deep) |
| a flat place | `300 horizontal 200 vertical`, `flat (goal minus centre of mass)` (across and down only) |
| text | `"hello"`, `name`, `"Hi " plus name` (words between quote marks) |
| a list of ... | `a list of numbers` (empty), `a list of (3, 5, 7)`, `a list of pets`. Holds one kind of thing, in order. |
| a table of ... | `a table of numbers` (empty). Looks things up by a name (text), like a phone book. A number works as a name too: `the entry 3 of ages` is the entry "3". |

**birth and existence.** `set birth to 300 horizontal 200 vertical` says where something starts, and puts `existence` (where it is right now) in the same spot. Then you move `existence` around, and `set existence to birth` sends it back.

Your own kinds of things can have them too. Give the kind a `birth` part and it gets an `existence` part by itself:

```
a ball has:
  birth (a flat place)
  speed (a number)
and the universe said i love you
```

`set the birth of ball to 100 horizontal 50 vertical` puts the ball's existence there too. Then you move `the existence of ball`, and `(the existence of ball) of horizontal` tells you how far across it is.

Lists and tables can hold other lists and tables. `a list of lists of numbers` is a grid, and `item 2 of item 3 of grid` gets something out of it. When you print one, the inner lists are shown in brackets: `(1, 2), (3, 4)`.
| your own kind | `conjure a pet` (see above) |

Mixing kinds is an error: `set turn rate to fallen` says "'turn rate' holds a number, not yes or no."

## Lines inside a command

| Line | Means |
|---|---|
| `set gap to goal minus centre of mass` | Remember a value under a name. A new name is made the first time it is set. |
| `move turn rate toward 20 by at most 5` | Change a number toward a goal, but by no more than the step. |
| `if fallen: cease` | Do the part after the colon only when it is yes. |
| `if ...:` / `otherwise if ...:` / `otherwise:` | With indented lines below, for longer choices. |
| `whenever ticks exceeds 2:` | With indented lines below: they run each time it turns yes. Checked again and again once the command's other lines are done. |
| `every 2 seconds:` | With indented lines below: they run every 2 seconds, once the command's other lines are done. |
| `every frame:` | With indented lines below: they run once a frame while the world lives (the frame is revealed after them on its own). `whenever key pressed "space":` works alongside it. |
| `if answer is one of ("yes", "y", "sure"):` | Whether a value is any of these (or in a list: `if 3 is one of sizes`). `is not one of` is the opposite. |
| `depending on weather:` | Choices about one value. Each indented line is a value (or several, with commas), `:`, and what to do, like `"rain": scrawl "Umbrella!"`. The last can be `anything else: ...`. The value is worked out once. |
| `scrawl "Hello, [name]! [count plus 1] left."` | Words in square brackets inside text are filled in with what they hold. Brackets holding anything but words (a pattern's `[0-9]`) stay as they are; `[[like this]]` shows `[like this]`. |
| `scrawl "Score: ", score` | Show things on the screen, one after another, then start a new line. |
| `ask "Your name? " into name` | Show the question and keep what the person types, as text. |
| `ask "Your age? " into age (a number)` | The same, as a number. It asks again until a number is typed. |
| `ask "Again? " into again (yes or no)` | The same, as yes or no (`yes`, `y`, `no` or `n`). |
| `repeat 10 times:` | Do the indented lines below 10 times. |
| `as long as guess is not secret:` | Keep doing the indented lines below while it is yes. |
| `greet with name, 3` | Do your own command `greet`, giving it its inputs in order. A command without inputs is just its name: `greet`. |
| `for each score in scores:` | Do the indented lines once for every item of a list, with `score` being that item. If `score` already had a value, it has that value again after the loop. |
| `for each n from 1 to 10:` | The same for each whole number from 1 to 10. |
| `for each n from 0 to 100 by 5:` | Counting in steps: 0, 5, 10 ... 100. A step below 0 counts down (`from 10 to 1 by -1`). |
| `add 5 to scores` | Put an item at the end of a list. |
| `insert 5 at 2 in scores` | Put an item in a list at that place, moving the ones after it along (`at` the size plus 1 puts it at the end). |
| `remove item 2 from scores` / `remove 5 from scores` | Take out the second item / the first 5. |
| `set item 2 of scores to 9` | Change one item. Items are counted from 1. |
| `set entry "Rex" of ages to 3` | Put a value in a table under a name (replacing what was there). |
| `remove entry "Rex" from ages` | Take a name and its value out of a table. |
| `return total` | Leave the command, returning an answer. |
| `raise an error with "the tank is empty"` | Stop with a problem of your own. `try:` catches it like any other, and `the wound` is its text. |
| `raise a fuel problem with "the tank is empty"` | A kind of problem, named in your own words. After a `try:`, `if that went wrong with a fuel problem:` takes only those. Several can follow one `try:`, and a plain `if that went wrong:` (last) takes the rest. A problem nothing takes goes on, as if there were no `try:`. |
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
| `2 to the power 10` | a number to a power (before `times` and `plus`, as in maths: `3 times 2 to the power 3` is 24) |
| `12 bitwise and 10`, `bitwise or`, `bitwise exclusive or`, `1 shifted left by 4`, `shifted right by` | the bits of whole numbers (smaller than 9007199254740992, either way): 8, 14, 6, 16 |
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
| `upper case of name`, `lower case of name` (any alphabet: `upper case of "straße ω"` is "STRAßE Ω". Letters with no single capital, like ß, stay) | text in CAPITALS / small letters |
| `trimmed line` | text without the spaces, tabs and line breaks at its start and end |
| `name begins with "Dr"`, `name ends with ".txt"` | yes or no |
| `position of "lo" in name` | where it first appears, counted from 1 (0 if it isn't there); in a list, which item it is (`position of "Bo" in names`) |
| `replace "a" with "b" in name` | text with every "a" changed to "b" |
| `line split by ", "` | text cut into a list of text at every ", " |
| `join names with ", "` | a list made into one text, with ", " between the items |
| `sorted scores`, `reversed scores` | a copy of a list, smallest first / back to front. `sorted scores, biggest first` the other way |
| `"ab" repeated 3 times`, `a list of (0) repeated 10 times` | the text or list that many times over (`"ababab"`) |
| `flattened rows` | a list of lists as one list: `flattened a list of (a list of (1, 2), a list of (3))` is 1, 2, 3 |
| `last item of scores` | the last item of a list |
| `items 2 to 5 of scores` | a list of those items |
| `first 3 of scores`, `last 3 of scores` | the first or last few items of a list (or letters of text); all of them when there are fewer |
| `unique names`, `shuffled names` | a copy without repeats (first ones kept) / in a random order |
| `1234567 with commas` | "1,234,567" |
| `7 padded to 3 digits`, `"food" padded to 8 letters` | "007", and "food    " (spaces after it, for lining things up) |
| `sum of scores`, `average of scores`, `biggest of scores`, `smallest of scores` | worked out from a list of numbers |
| `scores changed by the command double` | a new list: the command done to every item (see Commands as values) |
| `scores kept by the command big one` | a new list of just the items the command says yes to |
| `sorted pets by age` | a copy of a list of things, smallest part first (things with the same part keep their order); `sorted pets by age, biggest first` the other way |
| `sorted names by each n becomes the size of n` | a copy of a list in order of what each item works out to (a number or text): here, shortest name first. `, biggest first` works here too |
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

`of` grabs everything after it until it hits a word like `is`, `and`, `between` or `by`. Parts and items are different: `the age of rex plus 1` means `(the age of rex) plus 1`. Words that change a whole value (`as text`, `as a number`, `as saved text`, `rounded to`, `changed by`, `kept by`) apply to everything before them. So `item 2 of scores as text` means `(item 2 of scores) as text`, and `round x as text` means `(round x) as text`. If you're not sure, use brackets: `(the size of gap) minus stop distance`.

## Names

Names can be several words (`turn needed`, `braking speed`). They can't use the language's own words: and, angle, as, ask, at, begins, between, by, cease, changed, clamp, conjure, contains, depth, direction, divided, each, empty, ends, exceeds, falls, file, flat, for, from, horizontal, if, in, inscribe, into, invoke, is, kept, larger, least, less, list, meanwhile, minus, more, most, move, new, no, not, of, or, otherwise, plus, raise, random, remove, repeat, return, returning, root, scrawl, set, size, smaller, square, stop, than, times, to, touches, toward, trimmed, try, vertical, whether, while, whisper, with, wound, write, yes. Some phrases are the language's too, so avoid names that start them: `entry`, `keys of`, `sum of`, `average of`, `biggest of`, `smallest of`, `rounded to`, `letter`, `letters`, `upper case`, `lower case`, `position of`, `replace`, `join`, `sorted`, `reversed`, `last item of`, `split by`, `items`, `first`, `last`, `unique`, `shuffled`, `with commas`, `padded to`.

## Adding words

A script can only use the words its thing knows. New words, like another part of the deer's state or a new ability, go in the `.words` file. Something physical that's new, like jumping or galloping, needs C++ written for it first, and then it can get a word.

In a part of something else, commands can call each other too. The top of the C++ it makes lists what the class's header has to declare. For now, you can only describe new kinds of things inside programs.

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
use: shapes.stella
```

Stellanova looks for the other script next to this one. It can have its own `genesis:` so you can run it by itself to try it out, and that part gets skipped when another script uses it. If a script gets used more than once, even by scripts it uses itself, it's only read once. Mistakes in a used script say which script they're in, like `shapes.stella line 13: ...`.

If only the script itself needs a command, you can keep it private with `to tidy up, privately:` (or `to tidy up, privately, given ...:`). Other scripts can't use it, and they can have a `tidy up` of their own. If two scripts both have a command with the same name and neither is private, that's a mistake, and the message tells you where both of them are.

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
| `database` | SQLite files: `change the database ("shop.db", "create table items (name text, price real)")`, `rows from the database ("shop.db", "select name from items")` (a list of rows, each a list of text). With a `?` where each value goes, so text from people can't change the command: `change the database with values ("shop.db", "insert into items values (?, ?)", a list containing (name, price as text))`, `rows from the database with values (...)`. On the web it works with node. |
| `sound making` | Making sounds. A sound is a list of numbers from -1 to 1, 44100 for each second. `a tone with ("sine", 440, 0.5, 0.8)` is half a second of a wave (shapes: "sine", "square", "saw", "triangle", "noise". The last number is how loud, 0 to 1). `the pitch of the note "C#5"` is a note's pitch ("A4" is 440). `mixed with (a, b)` plays two at once, `followed by with (a, b)` one after the other, `louder with (sound, 2)`, `faded with (sound, fade in seconds, fade out seconds)`, `echoed with (sound, delay seconds, strength)`. `save the sound with (sound, "beep.wav")` writes a .wav file (play it with the sound library), `the sound in the file "a.wav"` reads one, and `record the sound 3` records 3 seconds from the microphone (not on the web). |
| `spreadsheet` | `rows of the spreadsheet contents of file "scores.csv"` (CSV text as a list of rows, each a list of text), `the spreadsheet of rows` (back to CSV text, for `inscribe ... into file`) |
| `time` | `wait 2 seconds`, `seconds since the start`, `the current hour`, `the current minute`, `the current second`, `the day of the month`, `the current month`, `the current year`, `today` (like `2026-11-04`), `the time now` (like `14:05:09`), `the day of the week` (like `Wednesday`), `seconds since 1970`. Dates are text like `2026-11-13`, so they sort, compare and save as they are: `days between ("2026-11-13", "2026-12-25")` (42), `days until "2026-12-25"`, `date plus days (today, 30)` (and `-1` for the day before), `weekday of "2026-11-13"` (`Friday`), `date in words "2026-11-16"` (`Monday 16 November 2026`), `date plus months ("2026-01-31", 1)` (`2026-02-28`: past the end of a month is its last day). A moment is seconds since 1970: `seconds at ("2026-11-16", "14:05:00")` is that moment here, and `date at moment` and `time at moment` (`14:05:00`) show one |
| `window` | A window to etch in, for games and pictures. See below. |
| `web` | `web page "https://example.com"` (returns the page as text), `download with "https://example.com/cat.png", "cat.png"` (into a file), `send to the web page with (address, message)` (sends text, returns the answer). Any other request: `ask the web with (address, "DELETE")`, with a message and headers if it needs them, `ask the web with (address, "PUT", message, "Content-Type: application/json")` (more headers go on lines of their own). It returns the answer even when the page says no, and `the last web status` is its number (200 is fine, 404 is not found); `the last web header "Content-Type"` is one of the headers the answer came with |
| `sound` | `play the sound with "boom.wav"`, `play the sound and wait with "boom.wav"`, `play the sound again and again with "music.wav"`, `stop the sound` (stops them all). Sounds play on top of each other, so a game can have many at once. .wav or .mp3 files. |
| `computer` | `beep with 440, 0.5` (pitch, seconds), `run the command "dir"` (returns its exit number), `open "notes.txt"` (opens a file or web address), `user name`, `the output of the command "dir"` (what it printed, as text), `the words given` (a list of the words typed after the program's name: `stellanova game.stella easy 3`), `environment value of "PATH"`, `current folder`, `end the program with 0` (stops at once, giving that exit number). Programs running alongside: `set p to start the program with ("py -3 game.py", "C:\Games")` (the command and the folder it runs in. Gives a number for it), `latest output of the program p` / `latest errors of the program p` (what it printed since you last asked), `type into the program with (p, "yes")` (a line for its `ask`), `the program is running p`, `exit code of the program p`, `stop the program p` (and anything it started) |
| `email` | Sending email: `send an email with ("smtp.gmail.com:587", "me@gmail.com", app password, "friend@example.com", "Hello", "The message")`. The server is its address and port (587 switches to TLS; 465 is TLS from the start), and the user is the address it is sent from. Mail always goes over TLS, except to a server on this computer (`"localhost:2525"`, for testing). Many mail services want an app password here, not your usual one. On the web it works with node. |
| `encryption` | Keeping text secret with a password. `set secret to encrypted with ("meet at noon", password)` gives text that can be kept or sent anywhere, and `decrypted with (secret, password)` gives the message back. A wrong password, or any change to the encrypted text, is a problem (so changes are always noticed). Each time is different (a fresh random salt), but any way of running can decrypt text from any other. `a random code of 16` is 16 random bytes as hexadecimal text, for keys and names nobody can guess. (ChaCha20-Poly1305, with the key made by PBKDF2-SHA256. On the web it works with node.) |
| `folders` | `files in the folder "saves"`, `folders in the folder "saves"` (lists of names, in order), `folder "saves" exists`, `make the folder "saves/old"`, `erase the file "a.txt"`, `erase the folder "old"` (and everything in it), `move the file with "a.txt", "b.txt"` (moves or renames), `copy the file with "a.txt", "b.txt"`, `bytes in the file "a.txt"`, `the bytes of the file "cat.png"` (the file as a list of numbers from 0 to 255, for files that aren't text), `fill the file with ("out.bin", numbers)` (the other way), `last change of the file "a.txt"` (the moment it was last written, for the time library's `date at`). The parts of a path: `file name of "saves/slot 1.json"` (`slot 1.json`), `extension of` it (`json`) and `folder holding` it (`saves`) |
| `animation` | Moving things smoothly. Progress goes from 0 (the start) to 1 (the end): `progress of with (start, seconds, now)` works it out from the time. `eased with ("out", progress)` bends it: "linear", "in", "out", "in out", "back" (pulls back first), "overshoot", "bounce", "elastic". `tweened with (from, to, progress, "in out")` is the number that far along (and `tweened place` for places). `ping pong t` goes 0 to 1 and back as t grows, `wave of with (seconds, every)` swings smoothly from 0 to 1 and back every so many seconds, and `sheet frame with (frames, per second, seconds)` is which frame of a sprite sheet to show (1 to frames, looping). Draw that frame with the window's `etch the sheet frame`. |
| `markup.stella` | Reading XML and HTML, written in Stellanova itself (`use: markup.stella`). `read markup page` is the whole of it: a `markup part` with no name, holding the outermost parts. Each part has a `name`, `attributes` (a table of text), `content` (its own text, with `&amp;` and the like made plain) and `parts`. `parts named with (whole, "a")` finds every part with that name, however deep; `attribute with (link, "href")` is one attribute (`""` if it has none); `all words in p` is its text and the text of everything inside. HTML's loose ways work: `<br>` and `<img>` need no closing, a closing that doesn't fit ends the parts open inside it, and `<script>` and `<style>` are kept as they are. |
| `options.stella` | Options typed after a program's name, like `stellanova tool.stella --size=3 --loud notes.txt`, written in Stellanova itself (`use: options.stella`). `has option "loud"` says whether `--loud` was typed; `option value "size"` is what came after `--size=` (`""` if nothing, or `option value with ("size", "10")` for another fallback); `plain words` is a list of the words that aren't options. After `--` on its own, every word is a plain word. |
| `physics.stella` | Boxes that fall, slide, land and bounce, written in Stellanova itself (`use: physics.stella`. It is in Stellanova's libraries folder, so a script needs no copy). `set w to conjure a physics world` and `set the gravity of w to 1000`; `include the body with (w, a box at with (x, y, width, height))` (one that moves) or `a wall at with (...)` (one that never does); `push the body with (w, 1, across, down)` sets the first body's speed; `step the physics with (w, 1 divided by 60)` moves everything on by that many seconds, stopping bodies at what they hit (their `bounciness`, 0 to 1, says how much they bounce back). `the body numbered with (w, 1)` is a copy of a body (its `x`, `y`, `speed across`, `speed down`, `landed`...), `change the body with (w, 1, b)` puts one back, and `touching with (a, b)` says whether two overlap. |
| `big numbers` | Whole numbers of any size, kept as text: `big power with ("2", 100)` ("1267650600228229401496703205376"), `big plus`, `big minus`, `big times`, `big divided by` (rounded down) and `big remainder`, each `with ("123", "456")`, and `big compare with (a, b)` (-1, 0 or 1) |
| `network` | Talking to other programs. TCP: `connect to with ("example.com", 80)` and `accept a connection on listener` (after `set listener to listen on port 8080`) each give a connection (a number). Then `send on with (c, "hi")`, `send a line on with (c, "hi")`, `send bytes on with (c, numbers)`, `receive from c` (what has arrived, "" once it is closed), `receive a line from c`, `receive bytes from c`, `close the connection c`. UDP: `open the udp port 9000` (0 for any), `send udp with (u, "127.0.0.1", 9000, "hi")`, `receive udp from u`. WebSockets: `connect a websocket to "ws://localhost:8080/chat"`, then `send on`, `receive from` (one whole message) and `close the connection`. These also work on the web. |
| `forms` | Desktop forms: a window with buttons, fields to type in, labels, lists and tick boxes. `open a form with ("Pets", 320, 240)`, then `add a button with ("add", "Add", x, y, width, height)` (also `add a field`, `add a label`, `add a tick box`; `add a list box with (name, x, y, width, height)`). Each part has a name of your own. `wait for a click` waits until a button is clicked and gives its name (`""` once the form is closed). `the words in "name"` is what a field holds (or a list's chosen item), `set the words in with (name, words)` changes it, `put in the list with (name, item)` and `empty the list name` change a list, `is ticked "loud"` says whether a tick box is ticked, and `close the form` closes it. For tests and demos, the environment value STELLANOVA_FORM_SCRIPT can name a file of lines that act by themselves, one for each wait: `type name Rex`, `choose pets Rex`, `tick loud`, `click add` or `close`. On the web the form is a box of real buttons and fields in the page. |
| `hashing` | Fingerprints of text: `the hash of with ("sha256", "hello")` is "2cf24dba...", and changes completely if one letter does. Kinds: "sha256", "sha512", "sha1" and "md5" (old: for spotting changes, not for safety). `the hash of the bytes with ("sha256", numbers)` does bytes, and `the signature of with ("sha256", key, message)` is an HMAC: only someone with the key can make it, so it proves a message came from them. |
| `json` | Reaching into JSON text (what web services send) with a path: names with dots between, and items in brackets counted from 1. `the json at with (answer, "weather.days[2].high")` is that part: text parts come back as the text itself, anything else as JSON text (which these words read again). `the json number at` gives a number, `the json list at` a list (each item as `the json at` gives it), `the json names at` the names in a part, and `there is json at` says whether the part is there. `the json changed at with (json, "days[3]", "12")` is the JSON with that part changed or added (the new part is JSON text; `as json text "hi"` makes text into JSON text). The path `""` is the whole of it. |
| `zip` | .zip files. `pack the zip with (a list of ("saves", "notes.txt"), "backup.zip")` packs files and folders (with everything in them) into one; `the files in the zip "backup.zip"` lists what it holds (like "saves/1.txt"); `unpack the zip with ("backup.zip", "restored")` puts them all into a folder (it won't unpack a file that would land outside that folder). On the web these work with node. |
| `letters` | `the bytes of the text "hé"` (its UTF-8 bytes, numbers from 0 to 255: 104, 195, 169), `the text of the bytes b` (back again), `code of the letter "A" (65: the number behind a letter), `the letter with code 233` ("é") |
| `patterns` | Finding text by its shape (`"[0-9]+"` is one or more digits, `"."` any letter, `"(...)"` a piece to keep): `the pattern fits with ("[0-9]+", line)` (yes or no), `matches of the pattern with ("[0-9]+", line)` (every match, as a list of text), `pieces of the pattern with ("([a-z]+)=([0-9]+)", line)` (the bracketed pieces of the first match), `replace the pattern with ("[0-9]+", line, "#")` |
| `pictures` | Changing pictures, dot by dot. Each picture is a number: `a blank picture with (200, 100, "white")` or `the picture in the file "cat.png"`. `the dots across p` and `the dots down p` are its size; `the dot at with (p, x, y)` is a dot's colour ("#rrggbb", or "#rrggbbaa" when it is partly see-through) and `colour the dot with (p, x, y, "#ff8800")` changes one (dots go from 0, 0 at the top left). For changing many at once, `the dots of the picture p` is every dot's red, green, blue and how solid (0 to 255 each, row by row) and `a picture from the dots with (width, height, numbers)` makes one from such a list. `save the picture with (p, "out.png")` writes a .png, and `a copy of the picture p` is a new one to change. Colour names: black, white, red, green, blue, yellow, grey, clear. Running directly (and with node), only .png files can be read. |
| `server` | `serve the web with (8080, the command answer)` makes the program a web server for this computer: open `http://127.0.0.1:8080/hello` in a browser and `answer` (a command given text returning text) is given `"/hello"` and returns the page. It serves until the program ends, so start it with `meanwhile` to do other things too. Many people can ask at once; `answer` needs no locks. `serve the web from the folder with (8080, "site", the command answer)` also sends the files in that folder (`/` is `index.html`), and asks `answer` only about addresses that aren't files. Inside `answer`, `the web message` is what a form or `fetch` sent along (empty for a plain visit), `the web way` is how it asked (`"GET"` for a visit, `"POST"` for a form...), `the web header "Cookie"` is one of the headers it sent (`""` if not), `answer with the status 404` tells it the page isn't there (an answer that is saved text, starting with `{` or `[`, goes as data rather than a page), `answer with the file "song.mp3"` sends a file from anywhere instead of the text given back, and `web decoded "a%20b"` ("a b") and `web encoded` turn addresses into text and back. |

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
| `etch the sheet frame with ("walk.png", 3, 4, 2, 100, 50)` | One frame of a sprite sheet: a picture cut into 4 frames across and 2 down, counted from 1 (across first, then the next row). Its top left corner goes at 100, 50. The animation library's `sheet frame` says which frame to show now. |
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

**3D.** The window can show 3D too. Places go across (`horizontal`), up (`vertical`, where bigger means higher, the opposite of flat window places), and away from you (`depth`). You see everything from **the eye**:

| Words | Means |
|---|---|
| `place the eye at 0 horizontal 1.6 vertical -10 depth` | Where the picture is seen from. |
| `aim the eye with (turn, tilt)` | Which way the eye looks, in degrees: turn 0 looks along depth, 90 looks along horizontal (to the right). Tilt up is more, from -89 to 89. Walking forward at a turn is `(sine of turn) horizontal 0 vertical (cosine of turn) depth`. |
| `etch the ground with ("green", "#2a7a2a")` | A checkered floor at vertical 0 around the eye, in two colours. It is always under everything else. |
| `etch a cube with (middle, size, "red")` | A cube around a middle place. Its sides are shaded by the light. |
| `etch a block with (middle, width, height, depth, "brown")` | A box of any size. |
| `etch a ball with (middle, radius, "yellow")` | A ball. |
| `etch a triangle in space with (a, b, c, "yellow")` | A flat triangle between three places, seen from both sides. |
| `etch the model with ("ship.obj", middle, 2, 45, "")` | A 3D model from an .obj file, its middle at that place, twice its size, turned 45 degrees around the vertical. With `""` it keeps the colours of its .mtl file (others are light grey). A colour paints all of it. |
| `etch the picture in space with ("door.png", corner, across, down)` | A picture laid on the world like a texture: its top left at `corner`, its top edge along `across` and its left edge along `down` (both places, as directions and lengths). It is drawn as up to 48 by 48 cells of colour. See-through dots are left out. |
| `shine the light from 1 horizontal 2 vertical -1 depth` | Where the light comes from (the shapes facing it are brightest). |
| `set the eye view to 90` | How wide the eye sees, top to bottom, in degrees (10 to 150; it starts at 60). |
| `shade the shapes with the command tint` … `stop shading the shapes` | A shader: each 3D shape etched in between is given the colour `tint` returns. `tint` is a command given a place (the shape's middle) and text (its colour) that returns a colour. |
| `the graphics card draws` | yes or no: are the 3D shapes drawn by the graphics card? |
| `set the daylight to 0.3` | How bright the 3D world is, from 0 (dark) to 1 (full, at first). It dims every 3D shape, not the words etched on top. |
| `start keeping the shapes as "house"` … `stop keeping the shapes` | The 3D shapes etched in between aren't drawn now: they are kept under that name. `etch the kept shapes "house"` then draws them all at once, every frame, far faster than etching each one again, so worlds of many thousands of blocks stay smooth. Keeping under the same name again replaces them, and `forget the kept shapes "house"` lets them go. |
| `screen place of 3 horizontal 1 vertical 5 depth` | Where a place shows on the window, as a flat place (`not a number` when it is behind the eye). |

3D shapes get drawn right before anything flat is etched or the frame is revealed, so things like a score that you etch afterwards stay on top. The **graphics card** draws them, using OpenGL, which every Windows computer has. That means things hide behind each other properly and balls get smooth lighting. When running straight from the script you also need Pillow (`py -3 -m pip install pillow`). Without those, it draws the shapes far ones first instead, which looks a bit plainer. `the graphics card draws` tells you yes or no once a world is open, and setting the environment value `STELLANOVA_NO_GPU` to 1 turns the graphics card off. `consume the window with "#87ceeb"` gives you a sky. `examples/walk3d.stella` is a small 3D game. `examples/driftstone.stella` is a bigger one, an island of blocks you can dig, build on and craft with, and it has day and night. Left button digs, right button places, 1 to 9 or the wheel picks a block, C opens the workbench and K saves the island.

Colours can be names (`black`, `white`, `red`, `green`, `blue`, `yellow`, `orange`, `purple`, `pink`, `brown`, `grey`) or codes like `"#ff8800"`, which is red, green and blue, each from 00 to ff.

### Making a library

A library is a `.words` file, either in `libraries/` or next to your program. Each word says what it means in C++ for `build`, and in Python on an indented `runs:` line for running directly. Anything C++ or Python can do can get an English word like this, whether it's windows, sound, the internet or games. Here's a word from `libraries/time.words`:

```
to wait, given seconds (a number) = std: : this_thread: : sleep_for(std: : chrono: : duration<double>({seconds}))
  runs: time.sleep(max(0.0, {seconds}))
```

`{seconds}` is the input, and `{line}` in the C++ is the line number of whatever used the word, for error messages. A library can also have `include: <header>` for a C++ header, `link: name` for a system library, `code:` and `python:` blocks for helper code, and values like `pi = 3.14159, number, read only` with their own `runs:` line. Only use each input once in the C++ line. A word with no `runs:` line only works in built programs.

For web programs, a word also gets an indented `web:` line saying what it means in JavaScript. `{seconds}` and `{line}` work the same there. Helper code for the web goes in a `javascript:` block, which only web programs get, just like `code:`, `include:` and `link:` only go to built ones. If a library's words only make sense in a web page, start it with the line `web only`. Its words then have no ` = C++` part, and using one outside a web program tells you so.

## Programs for web pages

`stellanova web` makes a program into JavaScript, so it can be the inside of a web page or an app made with Electron. The `page` library gives it the page:

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

Programs with a window (`use: window`, 2D or 3D) or a screen (`use: screen`) work in a web page without changes. The window becomes a canvas in the page, inside the element with the id `stellanova-window` if there is one, and a screen becomes a canvas covering the whole page. Keys and the mouse work like they do on the desktop. Pictures and models load from the page's own address, so keep them next to it. Under node there's no screen, so the window is one nobody sees. Everything still gets checked, but nothing shows up.

Every element of the page is a number, and 0 means there isn't one. That way elements fit in names, lists and kinds of things. `the element "#count"` finds one by its CSS selector, and `listen for an event` hands a command each event as it happens, as a number the event words can read. Commands answering the page run one after another. `wait`, `web page` and words that wait, like `play the media`, let the page keep going in the meantime.

| Words (library `page`) | Means |
|---|---|
| `the element "sel"`, `elements matching "sel"`, `the element within with (el, "sel")`, `elements within`, `the nearest matching element with (el, "sel")`, `parent of the element`, `the element at with (x, y)` | Finding elements (`the nearest matching element` looks at the element and the ones around it, like CSS `closest`). `the whole window`, `the page`, `the page body` and `the focused element` are elements too. |
| `the element made from "<li>new</li>"`, `insert as a child with (el, parent)`, `insert as the first child`, `insert before`, `remove the element`, `empty the element` | Making elements from markup and putting them in the page. |
| `set the text with (el, "text")`, `set the markup`, `words in the element`, `safe markup of words` | What an element holds. `safe markup of` turns `<` and `&` into markup that shows them, for words a person typed. |
| `value of the element`, `set the value`, `the element is ticked`, `tick the element`, `enable the element`, `focus on the element`, `select all in the element`, `the selected words` | Fields, ticks and buttons. |
| `set the attribute with (el, "name", "value")`, `drop the attribute`, `the attribute value`, `apply the appearance with (el, "open")`, `remove the appearance`, `toggle the appearance with (el, "open", yes)`, `the element has the appearance`, `set the style with (el, "width", "20px")`, `the style value` | Attributes, looks (CSS classes) and styles. |
| `the left edge of`, `top of`, `width of`, `height of`, `width of the window`, `height of the window`, `scroll into view`, `scroll to the end`, `scrolled down in the element`, `scrolled across in the element` | Where things are, in dots from the top left of the window. |
| `listen for an event with (el, "click", the command c)`, `the pointer x coordinate of e`, `the pointer y coordinate of`, `key of the event`, `button of the event`, `wheel of the event`, `the target of`, `control held in the event`, `shift held in the event`, `alt held in the event`, `hold back the event`, `stop the event spreading`, `capture the pointer with (el, e)` | Answering the person. |
| `after with (2, the command c)`, `every with (0.5, the command c)`, `wait for the next frame` | Later, and again and again. |
| `animate with (el, "opacity", "0", "1", 0.3, "ease-out")`, `animate and wait` | Moving smoothly from one value to another (any CSS easing). |
| `start drawing on with (canvas, 1)`, `drawing width`, `drawing height`, `clear the drawing`, `begin a shape`, `shape point with (x, y)`, `fill the shape`, `fill the shape fading`, `trace the shape`, `fill a dot`, `fill a box`, `fill the drawing fading`, `fill the drawing glowing` | Drawing on a canvas element (the second input of `start drawing on` is how sharp: 1 is every dot of the screen). |
| `play the media`, `pause the media`, `the media is playing`, `media time of`, `media length of`, `set the media time`, `set the media loudness`, `local copy of address`, `loudness bands of with (el, 24)` | Sound and video elements: `local copy of` fetches a whole file into the page, and `loudness bands of` says how loud each band of pitches is (0 to 1), for a visualiser. |

The `web`, `time`, `maths`, `letters`, `patterns`, `computer` and `server` words that make sense in a page work there too. `web page` fetches, and `wait` waits without freezing the page.

## Saving and loading

`save` keeps any value in a file, and `load` puts it back, so a game can remember high scores or where the player was:

```
save high scores to file "scores.json"
...
set high scores to a table of numbers
load high scores from file "scores.json"
```

`load` needs a name that already holds the right kind of value, which here is a table of numbers. Lists, tables, places and your own kinds all work, even inside each other. If the file is missing one of a thing's parts, that part just starts empty, so adding a part to a kind later won't break your old saves. If the file holds something else entirely, you get `the file "scores.json" doesn't hold a table of numbers.` Use `try:` if you want to carry on anyway.

`scores as saved text` gives you the same JSON as text without a file, and `load scores from the text reply` reads it back in. That's how a program talks to websites and other programs that use JSON. If it doesn't fit, `load` fails with `the text doesn't hold a list of numbers.` The files are plain JSON, so other programs can read them too.

**Shared abilities.** Different kinds of things can share something they can do. `a speaker is anything that can speak.` goes on one line at the top level and makes a new kind. Any kind with its own `to speak, for a ...:` command counts as a speaker and keeps all its parts. A list of speakers can hold dogs and robots together, and `speak s` speaks the way that particular thing's kind does it:

```
a speaker is anything that can speak.

to speak, for a dog, returning text:
  return "Woof"
and the universe said i love you

to speak, for a robot, returning text:
  return "Beep"
and the universe said i love you
```

When you save a speaker, or a list of them, it writes down what kind each one is, like `{"is a": "dog", "name": "Rex"}`, so `load` gives you a dog back. Loading fails if `"is a"` is missing or names a kind that can't speak. A dog saved as a dog is written without it.

A speaker can only do what it was described with. Write `anything that can speak and sing` if you want more. `s is a dog` (or `s is not a dog`) asks what kind it really is. A puppy counts as a dog too, and nothing isn't any kind. A speaker name starts out holding nothing, and `conjure` makes a dog or a robot, never just a speaker.

**Nothing.** A name for a kind of thing can hold nothing: `set best to no enemy`. You check with `if best is nothing` or `if best is something`. If you ask for a part of nothing, like `the health of best`, it stops with `this enemy is nothing, so it has no health.` Nothing prints as `nothing` and saves as `null`. It's handy for commands that might not find anything:

```
to the weakest, given enemies (a list of enemys), returning an enemy:
  set best to no enemy
  for each e in enemies:
    if best is nothing or the health of e falls below the health of best:
      set best to e
  return best
and the universe said i love you
```

**Web services.** Most websites that hand out data, like weather, prices or maps, answer in JSON. Describe the parts you want as a kind of thing and load the answer into one:

```
a forecast has:
  city (text)
  wind speed (a number)
and the universe said i love you

genesis:
  set today's forecast to conjure a forecast
  load today's forecast from the text web page "https://example.com/forecast.json"
  scrawl the wind speed of today's forecast
and the universe said i love you
```

Parts the answer doesn't have, or has as `null`, stay empty, and parts you didn't ask for get skipped. Names match even when the answer writes them as `windSpeed`, `wind_speed` or `Wind-Speed`. To put a quotation mark in some text, use `a quotation mark` (and `new line` for a line break): `scrawl "She said " plus a quotation mark plus "hi" plus a quotation mark`.

## When something goes wrong while running

The program stops with the line and a plain reason, such as `Line 22: there is no item 9 in a list of 4 items. Items are counted from 1.`

If you'd rather keep going, put the lines that might go wrong under `try:`, and what to do instead under `if that went wrong:` right after it, at the same indent. Inside that, `the wound` is what went wrong, as text:

```
try:
  set notes to contents of file "notes.txt"
if that went wrong:
  scrawl "I couldn't read the notes: ", the wound
  set notes to ""
```

The lines under `try:` stop at the first problem, even one deep inside a command they use.

Checking the translator itself: `py -3 test_stellanova.py`.

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
