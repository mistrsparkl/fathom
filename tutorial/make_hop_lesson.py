"""Writes lessons/16-platformer.lesson from lessons/files/hop.stella and records.stella: the game is put together piece
by piece, in the file's own order, so every zoom names the file's real line numbers. The game uses every part of the
language the lessons before it teach."""
from pathlib import Path

HERE = Path(__file__).parent
game = (HERE / "lessons" / "files" / "hop.stella").read_text(encoding="utf-8").rstrip("\n").split("\n")
records = (HERE / "lessons" / "files" / "records.stella").read_text(encoding="utf-8").rstrip("\n").split("\n")
END = "and the universe said i love you"


def where(text, start=1, lines=None):
    """the line number of the first line (from start) holding text"""
    lines = lines or game
    for n in range(start, len(lines) + 1):
        if text in lines[n - 1]:
            return n
    raise SystemExit(f"no line with {text!r}")


def ends(start, lines=None):
    return where(END, start, lines)


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


def zoom(a, b, *spots, back=True):
    put(f"line: {b}")
    put(f"zoom: lines {a}-{b}")
    for s in spots:
        if isinstance(s, tuple):
            put(f"spot: lines {s[0]}-{s[1]}" if s[0] != s[1] else f"spot: line {s[0]}")
        else:
            put(f"say:\n  {s}")
    put("spot: off")
    if back:
        put("keys: ctrl+end")  # back to the end, where the next piece goes


def say(*lines):
    put("say:\n" + "\n".join("  " + l for l in lines))


def one(text, start=1, lines=None):
    n = where(text, start, lines)
    return (n, n)


def span(a_text, b_text, start=1, lines=None):
    a = where(a_text, start, lines)
    return (a, where(b_text, a, lines))


put("title: Making a platform game")
put("files: records.stella")
put("card: Chapter 16 | Making a game | Hop! A platform game that uses everything")
say("Now let's put it all together, and make a real game: a platform game called Hop.",
    "A little blue block runs and jumps across floating platforms, picks up every coin, dodges spikes and bees, and reaches the flag at the end.",
    "It uses every part of the language we've seen. We'll write it piece by piece, and look closely at how each piece works.")
put("uncard")

# ---- the records script
R = records
put("open: records.stella")
say("The game keeps its best time in a second script, records dot stella. It was written earlier. Let's read it first.")
rem = where("the world remembers:", 1, R)
zoom(1, ends(rem, R),
     span("use: encryption", "use: folders", 1, R), "It uses seven libraries: encryption, hashing, json, big numbers, patterns, zip, time, and folders.",
     span("best time", "level print", rem, R), "It remembers the best time, every point ever won, and a fingerprint of the level. Points ever is text, because it's a big number: it can grow without limit.", back=False)
fp = where("to fingerprint the level", 1, R)
lr = where("to load the record:", 1, R)
zoom(fp, ends(lr, R),
     one("the hash of with", fp, R), "Fingerprint the level keeps a hash of the level. If the level ever changes, so does its fingerprint, and an old record won't be used for it.",
     one("if not file", lr, R), "Load the record does nothing if there's no save file yet.",
     one("decrypted with", lr, R), "The save file is encrypted, so nobody can change their best time by editing it. Decrypted with gives back the JSON text inside.",
     one("raise a save problem", lr, R), "A record for a different level raises a save problem, a kind of problem of our own.",
     one("the pattern fits", lr, R), "The pattern checks the points are only digits, as a big number must be.",
     span("if that went wrong with a save problem", "scrawl \"Starting fresh: the record couldn't", lr, R),
     "A save problem says why the record was skipped. Any other problem, like a wrong password, is caught by the plain if that went wrong. Either way, the game starts fresh.", back=False)
sr = where("to save the record,", 1, R)
zoom(sr, ends(sr, R),
     one("holding the lock", sr, R), "Save the record will run alongside the game, with meanwhile. Holding the lock makes sure two saves never mix.",
     one("big plus", sr, R), "Big plus adds the new points to every point ever won.",
     span("the json changed at with (\"{}\"", "\"day\"", sr, R), "The json changed at builds the record, one part at a time. Today, from the time library, is the date it was set.",
     span("inscribe encrypted", "pack the zip", sr, R), "Then it's encrypted into hop dot save, and a copy is packed into a zip file, as a backup.", back=False)
tr = where("to test the record:", 1, R)
zoom(tr, ends(tr, R), (tr, ends(tr, R)),
     "And a test: save a record, forget the best time, load it back, and check it's all there. Then the files are erased.", back=False)
put("zoom: out")
put("test")
put("zoom: output")
say("The test passes. Now, the game.")
put("wait")
put("zoom: out")
put("new: hop.stella")

# ---- the kinds of things
kinds_end = ends(where("a trail of anything has:"))
paste_to(kinds_end)
plat = where("a platform has:")
coin = where("a coin has:")
zoom(1, ends(coin),
     (1, 2), "The top of the game says what it is, in whispers.",
     span("use: window", "use: records.stella"), "Use window, for the window to draw in. Maths, for sine. And use records dot stella brings in the other script.",
     (plat, plat + 5), "A platform is a box: where its top left corner is, x across and y down, and how wide and high it is. Every floor, ledge and pillar in the level is one of these.",
     (coin, coin + 2), "A coin has a birth, which is where it floats, and so it has an existence too.")
sp = where("a spike has:")
zoom(sp, kinds_end,
     (sp, sp + 3), "A spike is a row of sharp points on the ground: where it starts, and how wide it is.",
     span("a bee has:", END, sp), "A bee has a birth, where its flight is centred, and a reach: how far it flies to each side.",
     span("a queen bee is a kind of bee", END, sp), "A queen bee is a kind of bee, with a crown as well.",
     one("a danger is anything"), "A danger is anything that can hurt and appear. Spikes and bees are different kinds of things, but both will be dangers.",
     span("a trail of anything has:", END, sp), "And a trail of anything keeps the last few of anything. The player will leave a trail of dust.")

# ---- what the world remembers
rem = where("the world remembers:")
rem_end = ends(rem)
paste_to(rem_end)
zoom(rem, rem_end,
     span("player x", "speed y", rem), "The world remembers everything about the game while it runs. Player x and y are where the player's top left corner is. Speed x and speed y are how far it moves each frame: across, and down. These are the heart of the game.",
     span("on ground", "facing", rem), "On ground says whether the player is standing on something. Facing is one for right, minus one for left, so the eyes look the right way.",
     one("coins taken (a number)", rem), "Coins taken is one number. Each of its bits says whether one coin has been taken.",
     span("dust (", "palette (", rem), "Dust is a trail of flat places. And the palette is a table of colours, looked up by name.",
     span("score (", "blink (", rem), "And the score, lives, the camera, the time, the points, whether the game is won, and whether the flag is blinking.")

# ---- making the level
lvl = where("to build the level:")
col_end = ends(where("to choose the colours:"))
paste_to(col_end)
pa = where("to platform at")
zoom(pa, ends(where("to spike at")),
     (pa, ends(pa)), "Platform at is a small helper. It conjures a platform, sets its four parts, and returns it. Coin at and spike at do the same.")
zoom(lvl, ends(lvl),
     span("add platform at with (0,", "(2160,", lvl), "Build the level adds every platform. These four are the ground, with gaps between them to fall into. The level is over three thousand dots wide, much wider than the window.",
     span("add coin at", "(2670, 290) to coins", lvl), "Seven coins, each where the player will have to jump to reach it.",
     span("add spike at", "(1990,", lvl), "Two rows of spikes.",
     span("conjure a bee as worker", "add worker to bees", lvl), "A bee, added to the list of bees.",
     span("set the birth of queen", "set the crown of queen", lvl), "And the queen. She's kept on her own: put into a list of bees, she'd become a plain bee, without her crown.")
ch = where("to choose the colours:")
zoom(ch, col_end, (ch + 1, col_end - 1), "Choose the colours fills the palette table. Set the entry sky of palette, to a blue.")

# ---- moving the player
mv = where("to run and jump:")
paste_to(mv - 1)
type_to(ends(mv))
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
to = where("to test overlapping:")
paste_to(ends(to))
zoom(ov, ends(to),
     (ov, ov + 1), "Overlaps asks whether the player's box and a platform's box overlap. The player is thirty dots wide and forty high. Two boxes overlap when each one's left edge is left of the other's right edge, and each one's top is above the other's bottom. All four must be true.",
     (to, ends(to)), "And a test for it: standing in the ground overlaps it, and fifty dots higher doesn't. The test button runs it.")

ac = where("to move across:")
ud = where("to move up and down:")
paste_to(ends(ud))
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

# ---- coins, in bits
it = where("to is taken,")
pc = where("to pick up coins:")
paste_to(ends(pc))
zoom(it, ends(pc),
     one("shifted right by", it), "Is taken looks at one bit of coins taken. Shifted right moves bit n to the end, and bitwise and one keeps only that bit.",
     one("set middle to", pc), "Picking up coins. Middle is the middle of the player: fifteen across and twenty down from its corner.",
     span("if not is taken with n", "set score to score plus 1", pc), "Any coin not taken yet, within thirty dots of the middle, is taken: bitwise or sets its bit, and the score goes up.")

# ---- dangers
hs = where("to hurt, for a spike")
dt = where("to the danger touching")
paste_to(ends(dt))
zoom(hs, ends(where("to appear, for a spike")),
     (hs, ends(hs)), "Hurt, for a spike: is the player's box touching it? A spike's own commands use its parts by their names: x and width.",
     span("to appear, for a spike", END, hs), "Appear draws it: one grey point every twelve dots.")
hb = where("to hurt, for a bee")
zoom(hb, ends(where("to appear, for a bee")),
     (hb, ends(hb)), "A bee hurts when its existence is within twenty six dots of the player's middle.",
     span("to appear, for a bee", END, hb), "And appears as a yellow circle with stripes, and a wing that flaps with sine.")
q = where("to appear, for a queen bee")
fl = where("to fly, for a bee")
zoom(q, ends(fl),
     (q, ends(q)), "A queen bee is a kind of bee, so she hurts the way bees do. But she has her own appear: bigger, and with her crown.",
     (fl, ends(fl)), "Fly moves a bee: existence is its birth, plus sine of the time across, times its reach, and a little up and down.")
td = where("to the dangers,")
zoom(td, ends(dt),
     (td, ends(td)), "The dangers puts every spike, every bee, and the queen into one list of dangers. It can hold them all, because each can hurt and appear.",
     (dt, ends(dt)), "The danger touching gives back the first danger that hurts. Hurt d does it the way that kind of thing does. And if none do, it gives back no danger: nothing.")

# ---- starting again
sa = where("to start again:")
ll = where("to lose a life:")
lv = where("to leave, for a trail")
paste_to(ends(lv))
zoom(sa, ends(lv),
     (sa, ends(sa)), "Start again puts the player back at the beginning, standing still.",
     span("set lives to lives minus 1", "set seconds to 0", ll), "Losing a life takes one away. At none, the game starts over: three lives, and no coins. Coins taken back to zero clears every bit at once.",
     (lv, ends(lv)), "And leave, for a trail of anything, adds a place to the trail, and lets go of the oldest after ten.")

# ---- drawing
sky = where("to etch the sky:")
paste_to(ends(sky))
zoom(sky, sky + 10,
     (sky + 1, sky + 1), "Now the drawing. Every frame, the whole picture is drawn again from the back to the front. First, the sky, in the palette's sky colour.",
     (sky + 2, sky + 4), "Then hills. Here's the camera's first trick. The hills move at only point three of the camera's speed, so they seem far away. Remainder of wraps them around, so they never run out.",
     (sky + 5, sky + 9), "Clouds move even slower, so they seem further still. Things further away moving slower is called parallax, and it makes a flat game look deep.")
el = where("to etch the level:")
paste_to(ends(where("to etch the dangers:")))
zoom(el, ends(el),
     span("set left to the x of p minus camera", "the entry \"grass\"", el), "Here's the camera's main trick. Every platform is drawn at its x minus camera. As the player runs right, the camera grows, and everything slides left. The level never moves: only the view of it does.",
     span("if not is taken with n:", "\"#fff3c4\"", el), "Coins not yet taken are gold circles with a shine, bobbing gently with sine.",
     span("if score is the size of coins:", "if blink:", el), "And once every coin is taken, the flag turns green, and blinks.")
ed = where("to etch the dangers:")
zoom(ed, ends(ed), (ed + 1, ed + 1), "Etch the dangers asks each one to appear, in its own way.")
pl = where("to etch the player:")
paste_to(ends(pl))
zoom(pl, ends(pl),
     span("for each spot in the items of dust", "etch a circle with spot", pl), "The dust trail first, behind the player.",
     span("depending on lives:", "anything else:", pl), "Depending on lives chooses its colour: blue with three, purple with two, red with one.",
     span("set eye x", "plus facing, player y plus 14, 2, \"black\"", pl), "And two eyes, moved toward the way it's facing. Small things like this give a block a personality.")
hh = where("to etch a heart,")
sc = where("to etch the score:")
paste_to(ends(sc))
zoom(hh, ends(sc),
     (hh, hh), "Etch a heart draws a heart from circles and a box. Its size is usually nine, so it can be left out.",
     one("Coins: [score]", sc), "The score and the time, rounded to one decimal place, filled in from the square brackets.",
     span("repeat lives times:", "set heart x to heart x minus 30", sc), "Repeat lives times draws a heart for each life.",
     span("if best time exceeds 0:", "Points ever:", sc), "The best time and points ever come from the records script.",
     span("if won:", "points\", 400, 240", sc), "And once it's won, it says so, in big letters, with the points.")

# ---- the game loop
gen = where("genesis:")
paste_to(len(game))
zoom(gen, where("set layers to", gen),
     span("open a world", "build the level", gen), "Last, genesis. It opens a window nine hundred and sixty by five hundred and forty, and builds the level.",
     span("fingerprint the level", "load the record", gen), "As saved text writes the platforms as JSON, and their fingerprint picks out this level's record. Then load the record.",
     one("set flying to the command fly", gen), "Flying keeps the command fly, for a bee.",
     one("set layers to", gen), "And layers is a list of commands: the drawing, from the back to the front.")
ef = where("every frame:", gen)
zoom(ef, len(game) - 1,
     (ef, ef), "Every frame repeats once a frame, sixty times a second, until the window is closed.",
     span("if not won:", "pick up coins", ef), "While the game isn't won: read the keys, move across, move up and down, and pick up coins. In that order, every frame.",
     one("the danger touching is something", ef), "Fall below the screen, or touch a danger, and a life is lost.",
     one("player x exceeds 3030", ef), "Every coin, and past the flag: you've won.",
     span("leave with (dust", "remove item 1", ef), "Running fast on the ground leaves dust. Otherwise the trail fades, one dot each frame.",
     span("for each n from 1 to the size of bees:", "fly with (queen", ef), "Invoke flying moves each bee in the list, and gives back the moved bee. The queen flies too.",
     one("set camera to", ef), "The camera follows the player, three hundred and sixty dots from the left of the window, and stops at the level's two ends.",
     one("for each layer in layers", ef), "And each layer is invoked, back to front.",
     span("whenever won:", "meanwhile save the record", ef), "Whenever won becomes yes: the points. Point nine seven to the power of the seconds shrinks the bonus the longer you take. Then meanwhile saves the record alongside, so the game doesn't stop to wait.",
     span("every 0.5 seconds:", "set blink to not blink", ef), "And every half a second, the flag's blink turns on or off.")
put("zoom: out")
put("test")
put("zoom: output")
say("Both scripts' tests pass.")
put("wait")
put("zoom: out")
say("That's the whole game. It's built into a program of its own, so it runs fast. Let's play it.")
put("game: hop.stella | hop.keys | Hop!")
say("Running right, faster each frame. Jumping: up fast, slowing, and falling, as gravity adds point six every frame.")
say("Over the spikes, under the bees, and every coin. The flag turns green, and blinks. We win, and the record is saved.")
put("until game ends")
say("And that's how a platform game works: speed changes the place, gravity changes the speed, one direction at a time, and a camera that the whole world is drawn around.")
put("card: Thank you | That's Stellanova | Every word is in the list on the left of the studio, and in LANGUAGE.md. Now go and make something of your own.")
say("That's every part of Stellanova. Every word is listed in the studio, and in the language guide. Now it's your turn: go and make something of your own.")
put("pause: 2")

(HERE / "lessons" / "16-platformer.lesson").write_text("\n".join(out) + "\n", encoding="utf-8")
print("made 16-platformer.lesson")
