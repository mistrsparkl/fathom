# Anything

Anything is a programming language written in plain English words. Scripts end in `.any`. `anything.py` turns each one into Unreal C++ (`<name>.any.cpp`, which you never edit):

```
py -3 anything.py <scripts folder> <output folder>
```

It A mistake stops the build with a plain message, such as:

```
follow.any line 31: I don't know 'walk sped'. Did you mean 'walk speed'?
```

`examples/follow.any` is a working example: it is how a deer follows the player.

## A script, top to bottom

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

1. **`this is part of:`** names the thing the script belongs to. Its words (what it already knows, like `fallen` or `walk speed`) are listed in `<name>.words` next to the script, e.g. `examples/creature body.words`.
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

Mixing kinds is an error: `set turn rate to fallen` says "'turn rate' holds a number, not yes or no."

## Lines inside a command

| Line | Means |
|---|---|
| `set gap to goal minus centre of mass` | Remember a value under a name. A new name is made the first time it is set. |
| `move turn rate toward 20 by at most 5` | Change a number toward a goal, but by no more than the step. |
| `if fallen: stop` | Do the part after the colon only when it is yes. |
| `if ...:` / `otherwise if ...:` / `otherwise:` | With indented lines below, for longer choices. |
| `stop` | Leave the command now. |
| `note: ...` | A note for people. |

## Working things out

| Write | Gives |
|---|---|
| `a plus b`, `a minus b`, `a times b`, `a divided by b` (or `+ - * /`) | arithmetic |
| `-look limit` | the negative |
| `smaller of a and b`, `larger of a and b` | the smaller or larger number |
| `clamp x between low and high` | x, kept inside the range |
| `square root of x` | the square root |
| `size of x` | a number without its sign, or the length of a (flat) place |
| `flat (place)` | the place without its height |
| `direction of flat place` | its compass angle in degrees |
| `angle from a to b` | the turn from angle a to angle b, -180 to 180 degrees |
| `a is more than b`, `is less than`, `is at least`, `is at most`, `is`, `is not` | yes or no |
| `x and y`, `x or y`, `not x` | combining yes or no |

`of` takes everything after it until a word like `is`, `and`, `between` or `by`. Use brackets to say exactly what belongs together: `(size of gap) minus stop distance`.

## Names

Names can be several words (`turn needed`, `braking speed`). They can't use the language's own words: set, to, if, otherwise, stop, note, and, or, not, is, more, less, than, at, least, most, plus, minus, times, divided, by, clamp, between, smaller, larger, of, square, root, size, flat, direction, angle, from, yes, no, move, toward.

## Adding words

A script can only use words its thing knows. New words (another part of the deer's state, a new ability) are added to the `.words` file; a new physical ability (jumping, a gallop) needs C++ underneath first, then it gets a word.

Checking the translator itself: `py -3 test_anything.py`.
