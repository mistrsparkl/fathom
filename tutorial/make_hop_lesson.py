"""Writes lessons/12-platformer.lesson from lessons/files/hop.stella: the game is put together piece by piece, in the
file's own order, so every zoom names the file's real line numbers."""
from pathlib import Path

HERE = Path(__file__).parent
game = (HERE / "lessons" / "files" / "hop.stella").read_text(encoding="utf-8").rstrip("\n").split("\n")


def where(text, start=1):
    """the line number of the first line (from start) holding text"""
    for n in range(start, len(game) + 1):
        if text in game[n - 1]:
            return n
    raise SystemExit(f"hop.stella has no line with {text!r}")


def block(a, b):
    return "\n".join("  " + line if line else "" for line in game[a - 1: b])


out = []
put = out.append
made = 0  # how many lines of the game are in the editor so far


def paste_to(b):
    global made
    put("paste:\n" + block(made + 1, b) + ("\n  " if b < len(game) else ""))
    made = b


def type_to(b, fast=True):
    global made
    put(("type fast:" if fast else "type:") + "\n" + block(made + 1, b))
    put("keys: enter")
    made = b


def zoom(a, b, *spots):
    put(f"line: {b}")
    put(f"zoom: lines {a}-{b}")
    for s in spots:
        if isinstance(s, tuple):
            put(f"spot: lines {s[0]}-{s[1]}" if s[0] != s[1] else f"spot: line {s[0]}")
        else:
            put(f"say:\n  {s}")
    put("spot: off")
    put("keys: ctrl+end")  # back to the end, where the next piece goes


def say(*lines):
    put("say:\n" + "\n".join("  " + l for l in lines))


put("title: Making a platform game")
put("card: Chapter 12 | Making a game | Hop! A platform game, from the first line to the last")
say("Now let's put it all together, and make a real game: a platform game called Hop.",
    "A little blue block runs and jumps across floating platforms, picks up every coin, and reaches the flag at the end.",
    "We'll write it piece by piece, and look closely at how each piece works.")
put("uncard")
put("new: hop.stella")

# ---- the kinds of things
kinds_end = where("taken (yes or no)") + 1
paste_to(kinds_end)
plat = where("a platform has:")
coin = where("a coin has:")
zoom(1, kinds_end,
     (1, 2), "The top of the game says what it is, in whispers. Then use window, for the window to draw in, and use maths, for sine.",
     (plat, plat + 5), "A platform is a box: where its top left corner is, x across and y down, and how wide and high it is. Every floor, ledge and pillar in the level is one of these.",
     (coin, coin + 3), "A coin has a birth, which is where it floats, and so it has an existence too. And taken says whether the player has picked it up.")

# ---- what the world remembers
rem = where("the world remembers:")
rem_end = where("and the universe said i love you", rem)
paste_to(rem_end)
zoom(rem, rem_end,
     (rem + 1, rem + 2), "The world remembers everything about the game while it runs. Player x and player y are where the player's top left corner is.",
     (rem + 3, rem + 4), "Speed x and speed y are how far the player moves each frame: across, and down. These two are the heart of the game. We'll come back to them.",
     (rem + 5, rem + 6), "On ground says whether the player is standing on something. Facing is one for right, minus one for left, so the eyes look the right way.",
     (rem + 7, rem + 9), "The platforms, the coins, and the score.",
     (rem + 10, rem + 12), "Camera is how far the view has scrolled. Ticks counts time, for the coins' bobbing. And won says whether the game is over.")

# ---- making the level
lvl = where("to build the level:")
lvl_end = where("and the universe said i love you", lvl)
paste_to(lvl_end)
pa = where("to platform at")
zoom(pa, pa + 7,
     (pa, pa + 7), "Platform at is a small helper. It conjures a platform, sets its four parts, and returns it. Coin at does the same for a coin.")
zoom(lvl, lvl + 10,
     (lvl + 1, lvl + 4), "Build the level adds every platform. These four are the ground, four hundred and sixty dots down, with gaps between them to fall into. The whole level is over three thousand dots wide, much wider than the window.",
     (lvl + 5, lvl + 10), "And these are ledges floating in the air, and two pillars to jump over.")
zoom(lvl + 11, lvl_end, "And seven coins, each floating where the player will have to jump to reach it.")

# ---- moving the player
mv = where("to run and jump:")
paste_to(mv - 1)
type_to(where("and the universe said i love you", mv))
say("This is the most important part of the game. Let's go through it slowly.")
zoom(mv, mv + 13,
     (mv + 1, mv + 3), "If the left key is held, speed x goes down by point eight each frame, so the player speeds up toward the left. Not all at once, but a little more every frame. That's what makes running feel smooth.",
     (mv + 4, mv + 6), "The right key does the same toward the right.",
     (mv + 7, mv + 8), "With neither key held, speed x is multiplied by point eight every frame. So the player slows down, and glides to a stop, like friction.",
     (mv + 9, mv + 9), "Clamp keeps speed x between minus six and six, so the player can't run faster than six dots a frame.",
     (mv + 10, mv + 11), "Jumping. Key pressed is yes for only one frame per press. And only on the ground: no jumping in mid air. A jump sets speed y to minus thirteen. On a screen, up is less, so minus thirteen means thirteen dots up, every frame.",
     (mv + 12, mv + 12), "And this one line is gravity. Every frame, speed y grows by point six. So a jump starts fast upward, slows, stops at the top, and comes back down faster and faster, in a smooth curve. Smaller of keeps the fall from getting faster than fourteen.")

# ---- touching platforms
ov = where("to overlaps, given p")
paste_to(where("and the universe said i love you", ov))
zoom(ov, ov + 2,
     (ov, ov + 1), "Overlaps asks whether the player's box and a platform's box overlap. The player is thirty dots wide and forty high. Two boxes overlap when each one's left edge is left of the other's right edge, and each one's top is above the other's bottom. All four must be true.")

ac = where("to move across:")
ud_end = where("and the universe said i love you", where("to move up and down:"))
paste_to(ud_end)
ud = where("to move up and down:")
zoom(ac, ac + 8,
     (ac + 1, ac + 1), "Now the moving itself. The trick is to move across and down separately, one after the other. First across: add speed x to player x.",
     (ac + 2, ac + 6), "Then, if that put the player inside a platform, push it back out. Moving right, the player's right side goes against the platform's left edge. Moving left, its left side goes against the platform's right edge. And speed x becomes zero: we hit a wall.",
     (ac + 7, ac + 7), "And clamp keeps the player inside the level, from its left end to its right end.")
zoom(ud, ud + 10,
     (ud + 1, ud + 2), "Then up and down, the same way. On ground starts as no, and speed y moves the player.",
     (ud + 5, ud + 7), "If the player was falling into a platform, its feet are put on the platform's top, and now, on ground is yes. That's the only place on ground ever becomes yes, so jumping only works after landing.",
     (ud + 8, ud + 9), "And if it was going up, it bumped its head: it's put just under the platform.",
     (ud + 10, ud + 10), "Either way, speed y becomes zero.",
     "Why separately? If we moved both at once, and ended up inside a corner of a platform, we couldn't tell whether we hit a wall or landed on a floor. One direction at a time, the answer is always clear.")

# ---- coins and starting again
pc = where("to pick up coins:")
sa_end = where("and the universe said i love you", where("to start again:"))
paste_to(sa_end)
zoom(pc, pc + 6,
     (pc + 1, pc + 1), "Picking up coins. Middle is the middle of the player: fifteen across and twenty down from its corner.",
     (pc + 3, pc + 5), "Any coin not taken yet, within thirty dots of the middle, is taken, and the score goes up. Setting the taken of item n of coins changes the coin inside the list itself.")
sa = where("to start again:")
zoom(sa, sa + 5, (sa + 1, sa + 4), "And start again puts the player back at the beginning, standing still. It's used at the start, and after falling into a gap.")

# ---- drawing
sky = where("to etch the sky:")
paste_to(where("and the universe said i love you", sky))
zoom(sky, sky + 10,
     (sky + 1, sky + 1), "Now the drawing. Every frame, the whole picture is drawn again from the back to the front. First, consume the window fills it with sky blue.",
     (sky + 2, sky + 4), "Then hills. Here's the camera's first trick. The hills move at only point three of the camera's speed, so they seem far away. Remainder of wraps them around, so they never run out.",
     (sky + 5, sky + 9), "Clouds move even slower, at point one five, so they seem further still. Each cloud is three white circles. Things further away moving slower is called parallax, and it makes a flat game look deep.")
lv = where("to etch the level:")
paste_to(where("and the universe said i love you", lv))
zoom(lv, lv + 14,
     (lv + 1, lv + 4), "The level. Here's the camera's main trick. Every platform is drawn at its x minus camera. As the player runs right, the camera grows, and everything slides left. The level never moves: only the view of it does. Each platform is brown earth with a strip of green grass on top.",
     (lv + 5, lv + 9), "Coins not yet taken are drawn as gold circles with a shine. Bob is sine of time, times four, so each coin floats gently up and down. Adding the coin's own x makes each one bob a little out of step with the others.",
     (lv + 10, lv + 13), "And the flag at the end turns from red to green once every coin is taken.")
pl = where("to etch the player:")
paste_to(where("and the universe said i love you", pl))
zoom(pl, pl + 10,
     (pl + 2, pl + 4), "The player is a blue box. In the air, squash makes it four dots shorter, which makes jumps feel lively.",
     (pl + 5, pl + 9), "And two eyes, moved six dots toward the way it's facing, with the pupils one more. Small things like this give a block a personality.")
sc = where("to etch the score:")
paste_to(where("and the universe said i love you", sc))
zoom(sc, sc + 6, (sc + 1, sc + 5), "And the score at the top. Once the game is won, it says so, in big letters.")

# ---- the game loop
gen = where("genesis:")
paste_to(len(game))
zoom(gen, gen + 20,
     (gen + 1, gen + 3), "Last, genesis. It opens a window nine hundred and sixty by five hundred and forty, builds the level, and puts the player at the start.",
     (gen + 5, gen + 5), "As long as the world lives repeats once a frame, sixty times a second, until the window is closed. Everything inside it is one frame of the game.",
     (gen + 6, gen + 10), "While the game isn't won: read the keys, move across, move up and down, and pick up coins. In that order, every frame.",
     (gen + 11, gen + 11), "Fall below the screen, and you start again.",
     (gen + 12, gen + 12), "Every coin, and past the flag: you've won.",
     (gen + 13, gen + 13), "The camera follows the player, keeping it three hundred and sixty dots from the left of the window. Clamp stops it at the level's two ends, so we never see past them.",
     (gen + 15, gen + 19), "Then draw it all, back to front: sky, level, player, score. And reveal the frame shows the finished picture, and waits, so there are sixty frames a second.")
put("zoom: out")
say("That's the whole game, two hundred lines. Let's play it.")
put("game: hop.stella | hop.keys | Hop!")
say("Running right, faster each frame. Jumping: up fast, slowing, and falling, as gravity adds point six every frame.")
say("Coins, ledges, pillars, and the flag turns green. We win!")
put("until game ends")
say("And that's how a platform game works: speed changes the place, gravity changes the speed, one direction at a time, and a camera that the whole world is drawn around.")
put("card: Thank you | That's Stellanova | Every word is in the list on the left of the studio, and in LANGUAGE.md. Now go and make something of your own.")
say("That's every part of Stellanova. Every word is listed in the studio, and in the language guide. Now it's your turn: go and make something of your own.")
put("pause: 2")

(HERE / "lessons" / "12-platformer.lesson").write_text("\n".join(out) + "\n", encoding="utf-8")
print("made 12-platformer.lesson")
