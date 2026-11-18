// Films lessons: opens Stellanova Studia in a hidden window, plays a lesson script in it (speaking, typing, running,
// zooming in), and writes out/parts/<lesson>.mp4 with the voice. Run from editor/studia with:
//     npx electron ../../tutorial/recorder.js <lesson files...>
// See README.md in this folder for the lesson script format.

const { app, BrowserWindow } = require("electron");
const { spawn, execFileSync } = require("child_process");
const fs = require("fs");
const net = require("net");
const http = require("http");
const path = require("path");

const here = __dirname;
const home = path.resolve(here, "..");
const studia = path.join(home, "editor", "studia");
const out = path.join(here, "out");
const workspace = path.join(out, "workspace");
const WIDTH = 1920, HEIGHT = 1080, FPS = 30;
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const py = (...words) => execFileSync("py", ["-3", ...words], { encoding: "utf8", windowsHide: true, maxBuffer: 1 << 28 });

// ---------------------------------------------------------------- reading a lesson

function readLesson(file) {
  const lines = fs.readFileSync(file, "utf8").replace(/\r/g, "").split("\n");
  const steps = [];
  let title = "", files = [];
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (!line.trim() || line.startsWith("#")) continue;
    const m = line.match(/^([a-z ]+?):\s?(.*)$/) || line.match(/^([a-z ]+)$/);
    if (!m) throw new Error(`${file} line ${i + 1}: I don't understand "${line}"`);
    const [, what, rest = ""] = m;
    if (what === "title") { title = rest; continue; }
    if (what === "files") { files = rest.split(",").map((s) => s.trim()).filter(Boolean); continue; }
    let block = null;
    if (["type", "type fast", "paste", "say", "keys"].includes(what) && rest === "") {
      block = [];
      while (i + 1 < lines.length && (lines[i + 1].startsWith("  ") || (lines[i + 1] === "" && (lines[i + 2] || "").startsWith("  ")))) {
        block.push(lines[++i].slice(2));
      }
    }
    const value = block ? (what === "say" ? block.join(" ") : block.join("\n")) : rest;
    steps.push({ what, value, line: i + 1 });
  }
  return { title, files, steps, name: path.basename(file, ".lesson"), folder: path.dirname(file) };
}

// ---------------------------------------------------------------- the studia, its system side, and a little file server

function freePort() {
  return new Promise((resolve) => {
    const s = net.createServer();
    s.listen(0, "127.0.0.1", () => {
      const p = s.address().port;
      s.close(() => resolve(p));
    });
  });
}

async function answering(port) {
  for (let k = 0; k < 100; k++) {
    try {
      await new Promise((ok, bad) => http.get({ host: "127.0.0.1", port, path: "/api/hello" }, (r) => (r.resume(), ok())).on("error", bad));
      return;
    } catch {
      await wait(150);
    }
  }
  throw new Error("the studia's system side didn't answer");
}

function serveOut(port) {  // games' films, for the page to play
  http.createServer((req, res) => {
    const file = path.join(out, decodeURIComponent(req.url.split("?")[0]));
    if (!file.startsWith(out) || !fs.existsSync(file)) return res.writeHead(404).end();
    res.writeHead(200, { "Content-Type": file.endsWith(".mp4") ? "video/mp4" : "application/octet-stream", "Access-Control-Allow-Origin": "*" });
    fs.createReadStream(file).pipe(res);
  }).listen(port, "127.0.0.1");
}

// ---------------------------------------------------------------- what is laid over the studia: the camera, captions, cursor, cards

const OVERLAY = String.raw`
(() => {
  const css = document.createElement("style");
  css.textContent = ${"`"}
    #camera { position: fixed; inset: 0; display: flex; flex-direction: column; transform-origin: 0 0;
              transition: transform 0.9s cubic-bezier(0.65, 0, 0.35, 1); will-change: transform; }
    #film-caption { position: fixed; left: 50%; bottom: 46px; transform: translateX(-50%); max-width: 78%; z-index: 160;
              padding: 10px 22px; border-radius: 10px; background: rgba(12, 14, 20, 0.82); color: #f3f3f3;
              font: 500 25px/1.35 "Segoe UI", sans-serif; text-align: center; opacity: 0; transition: opacity 0.25s;
              box-shadow: 0 6px 30px rgba(0,0,0,0.35); pointer-events: none; }
    #film-caption.on { opacity: 1; }
    #film-cursor { position: fixed; left: 0; top: 0; width: 26px; height: 26px; z-index: 101; pointer-events: none;
              transition: transform 0.7s cubic-bezier(0.65, 0, 0.35, 1), opacity 0.3s; opacity: 0; }
    #film-cursor.on { opacity: 1; }
    #film-cursor .ring { position: absolute; left: -14px; top: -14px; width: 28px; height: 28px; border-radius: 50%;
              border: 3px solid #4fc3f7; opacity: 0; transform: scale(0.4); }
    #film-cursor.click .ring { animation: ring 0.5s ease-out; }
    @keyframes ring { 0% { opacity: 1; transform: scale(0.4); } 100% { opacity: 0; transform: scale(1.6); } }
    #film-card { position: fixed; inset: 0; z-index: 200; display: flex; flex-direction: column; align-items: center;
              justify-content: center; opacity: 0; transition: opacity 0.8s; pointer-events: none; color: #fff;
              background: radial-gradient(ellipse at 30% 20%, #2b3a67 0%, #141a2e 45%, #0b0e17 100%); }
    #film-card.on { opacity: 1; }
    #film-card .kicker { font: 600 22px "Segoe UI", sans-serif; letter-spacing: 6px; text-transform: uppercase; color: #8fb3ff; }
    #film-card h1 { font: 300 84px "Segoe UI Light", "Segoe UI", sans-serif; margin: 18px 0 14px; letter-spacing: 1px; }
    #film-card p { font: 400 28px "Segoe UI", sans-serif; color: #b9c3dc; margin: 0; max-width: 1100px; text-align: center; }
    #film-card .line { width: 120px; height: 3px; background: linear-gradient(90deg, #4fc3f7, #b388ff); margin-top: 26px; border-radius: 2px; }
    #film-spot { position: fixed; z-index: 99; border-radius: 8px; pointer-events: none; opacity: 0; transition: opacity 0.4s;
              box-shadow: 0 0 0 3px rgba(79, 195, 247, 0.9), 0 0 0 9999px rgba(0, 0, 0, 0.0); }
    #film-spot.on { opacity: 1; }
    #film-game { position: fixed; z-index: 150; left: 50%; top: 47%; transform: translate(-50%, -50%) scale(0.96); opacity: 0;
              transition: opacity 0.5s, transform 0.5s; border-radius: 10px; overflow: hidden; background: #000;
              box-shadow: 0 30px 80px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.08); }
    #film-game.on { opacity: 1; transform: translate(-50%, -50%) scale(1); }
    #film-game .bar { height: 34px; background: #2b2b2b; color: #ddd; font: 14px "Segoe UI", sans-serif; display: flex;
              align-items: center; padding: 0 14px; gap: 8px; }
    #film-game .bar i { width: 12px; height: 12px; border-radius: 50%; background: #555; display: inline-block; }
    #film-game video { display: block; }
    #film-shade { position: fixed; inset: 0; z-index: 140; background: rgba(5, 8, 15, 0.55); opacity: 0; transition: opacity 0.5s; pointer-events: none; }
    #film-shade.on { opacity: 1; }
  ${"`"};
  document.head.append(css);
  const camera = document.createElement("div");
  camera.id = "camera";
  while (document.body.firstChild) camera.append(document.body.firstChild);
  document.body.append(camera);
  document.body.insertAdjacentHTML("beforeend",
    '<div id="film-spot"></div><div id="film-shade"></div><div id="film-game"></div><div id="film-caption"></div>' +
    '<div id="film-cursor"><svg width="26" height="26" viewBox="0 0 26 26"><path d="M3 2 L3 21 L8.5 16 L12 24 L15.5 22.5 L12 15 L19 15 Z" fill="#fff" stroke="#111" stroke-width="1.5" stroke-linejoin="round"/></svg><div class="ring"></div></div>' +
    '<div id="film-card"></div>');
  const film = window.film = { s: 1, x: 0, y: 0, timers: [] };
  const W = innerWidth, H = innerHeight;
  // where something is with the camera back at the start (a box in page dots)
  film.flat = (r) => ({ left: (r.left - film.x) / film.s, top: (r.top - film.y) / film.s, width: r.width / film.s, height: r.height / film.s });
  film.look = (box, most = 2.3) => {
    if (!box) { film.s = 1; film.x = 0; film.y = 0; }
    else {
      const s = Math.max(1, Math.min(most, (W * 0.86) / box.width, (H * 0.66) / box.height));
      film.s = s;
      film.x = Math.min(0, Math.max(W - W * s, W / 2 - (box.left + box.width / 2) * s));
      film.y = Math.min(0, Math.max(H - H * s, H * 0.45 - (box.top + box.height / 2) * s));
    }
    camera.style.transform = "translate(" + film.x + "px, " + film.y + "px) scale(" + film.s + ")";
  };
  film.box = (selector) => { const e = document.querySelector(selector); return e && film.flat(e.getBoundingClientRect()); };
  // what a program printed: just its text, so a few short lines fill the screen
  film.output = () => {
    const o = document.getElementById("output");
    const shown = o.getBoundingClientRect();
    const range = document.createRange();
    range.selectNodeContents(o);
    const text = range.getBoundingClientRect();
    const top = Math.max(shown.top, text.top), bottom = Math.min(shown.bottom, text.bottom);
    if (!text.width || bottom <= top) return film.flat(shown);
    const width = Math.max(text.right - shown.left, 560 * film.s);
    return film.flat({ left: shown.left, top: top - 8 * film.s, width: width + 24 * film.s, height: bottom - top + 16 * film.s });
  };
  film.lines = (a, b) => {
    const rows = [...document.querySelectorAll(".shown .row")].filter((r) => { const n = +r.querySelector(".num").textContent; return n >= a && n <= b; });
    if (!rows.length) return null;
    const boxes = rows.map((r) => r.getBoundingClientRect());
    const texts = rows.map((r) => r.querySelector(".txt").getBoundingClientRect());
    const code = document.getElementById("code").getBoundingClientRect();
    const left = boxes[0].left, top = boxes[0].top, bottom = boxes[boxes.length - 1].bottom;
    const right = Math.min(code.right, Math.max(left + 420 * film.s, ...texts.map((t) => t.left + Math.min(t.width, 1200 * film.s))));
    return film.flat({ left, top: top - 6 * film.s, width: right - left + 20 * film.s, height: bottom - top + 12 * film.s });
  };
  film.say = (chunks) => {
    film.timers.forEach(clearTimeout);
    film.timers = [];
    const cap = document.getElementById("film-caption");
    for (const c of chunks) {
      film.timers.push(setTimeout(() => { cap.textContent = c.text; cap.classList.add("on"); }, c.at * 1000));
    }
    const last = chunks[chunks.length - 1];
    if (last) film.timers.push(setTimeout(() => cap.classList.remove("on"), (last.end + 0.25) * 1000));
  };
  film.cursorTo = (x, y) => {
    const c = document.getElementById("film-cursor");
    c.classList.add("on");
    c.style.transform = "translate(" + x + "px, " + y + "px)";
  };
  film.pointAt = (selector) => {
    const e = document.querySelector(selector);
    const r = e.getBoundingClientRect();
    film.cursorTo(r.left + Math.min(r.width / 2, 40), r.top + r.height / 2);
  };
  film.press = (selector) => {
    const c = document.getElementById("film-cursor");
    c.classList.remove("click"); void c.offsetWidth; c.classList.add("click");
    const e = document.querySelector(selector);
    e.click();
    if (e.matches("input, textarea")) e.focus();
  };
  film.hideCursor = () => document.getElementById("film-cursor").classList.remove("on");
  film.card = (kicker, title, words) => {
    const card = document.getElementById("film-card");
    if (!title) { card.classList.remove("on"); return; }
    card.innerHTML = (kicker ? '<div class="kicker"></div>' : "") + "<h1></h1>" + (words ? "<p></p>" : "") + '<div class="line"></div>';
    if (kicker) card.querySelector(".kicker").textContent = kicker;
    card.querySelector("h1").textContent = title;
    if (words) card.querySelector("p").textContent = words;
    card.classList.add("on");
  };
  film.spot = (box) => {
    const spot = document.getElementById("film-spot");
    if (!box) { spot.classList.remove("on"); return; }
    const pad = 6;
    Object.assign(spot.style, { left: box.left * film.s + film.x - pad + "px", top: box.top * film.s + film.y - pad + "px",
      width: box.width * film.s + pad * 2 + "px", height: box.height * film.s + pad * 2 + "px" });
    spot.classList.add("on");
  };
  // the spot keeps measuring what it frames, so it stays put while the editor finishes scrolling
  film.spotOn = null;
  film.spotAt = (what) => { film.spotOn = what; film.spotPaint(); };
  film.spotPaint = () => {
    const w = film.spotOn;
    if (!w) { film.spot(); return; }
    const box = w.lines ? film.lines(w.lines[0], w.lines[1]) : film.box(w.sel);
    if (box) film.spot(box);
  };
  setInterval(film.spotPaint, 100);
  film.game = (src, title, w, h) => new Promise((done) => {
    const g = document.getElementById("film-game");
    const shade = document.getElementById("film-shade");
    const most = Math.min(1, (H * 0.78) / h, (W * 0.8) / w);
    g.innerHTML = '<div class="bar"><i></i><i></i><i></i><span></span></div><video muted playsinline></video>';
    g.querySelector("span").textContent = title;
    const v = g.querySelector("video");
    v.width = Math.round(w * most); v.height = Math.round(h * most);
    v.src = src;
    v.oncanplay = () => { v.oncanplay = null; shade.classList.add("on"); g.classList.add("on"); setTimeout(() => v.play(), 600); };
    v.onended = () => { setTimeout(() => { g.classList.remove("on"); shade.classList.remove("on"); setTimeout(done, 600); }, 700); };
  });
  film.state = () => ({
    where: document.getElementById("where").textContent,
    line: (document.querySelector(".row.here .txt") || {}).textContent || "",
    suggesting: !document.getElementById("suggest").hidden,
    status: document.getElementById("status").textContent,
    running: !document.getElementById("stop").disabled,
  });
})();
`;

// ---------------------------------------------------------------- filming

class Film {
  constructor(file) {
    this.started = Date.now();
    this.written = 0;
    this.frame = null;
    this.encoder = spawn("ffmpeg", ["-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", `${WIDTH}x${HEIGHT}`, "-r", String(FPS), "-i", "-",
      "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-tune", "stillimage", file], { stdio: ["pipe", "inherit", "inherit"] });
    this.clock = setInterval(() => this.keepUp(), 1000 / FPS / 2);
  }
  now() { return (Date.now() - this.started) / 1000; }
  paint(image) {
    const size = image.getSize();
    if (size.width === WIDTH && size.height === HEIGHT) this.frame = image.getBitmap();
  }
  keepUp() {
    if (!this.frame) { this.started = Date.now(); return; }
    const due = Math.floor(this.now() * FPS);
    while (this.written < due) {
      this.encoder.stdin.write(this.frame);
      this.written++;
    }
  }
  async end() {
    clearInterval(this.clock);
    this.keepUp();
    await new Promise((done) => { this.encoder.on("close", done); this.encoder.stdin.end(); });
  }
}

// caption pieces: a few words at a time, at the times the voice says them
function captionChunks(text, words) {
  if (!words.length) return [{ text, at: 0, end: 3 }];
  const chunks = [];
  let piece = [];
  const flush = () => {
    if (!piece.length) return;
    chunks.push({ text: piece.map((w) => w.word).join(" "), at: piece[0].at, end: piece[piece.length - 1].at + piece[piece.length - 1].for });
    piece = [];
  };
  // put the punctuation back: the voice's words come without it, so take each word from the text as written
  const written = text.split(/\s+/).filter(Boolean);
  let k = 0;
  for (const w of words) {
    let shown = w.word;
    for (let look = k; look < Math.min(written.length, k + 4); look++) {
      if (written[look].replace(/[^A-Za-z0-9']/g, "").toLowerCase().startsWith(w.word.replace(/[^A-Za-z0-9']/g, "").toLowerCase().slice(0, 3))) {
        shown = written[look]; k = look + 1; break;
      }
    }
    piece.push({ ...w, word: shown });
    const long = piece.map((p) => p.word).join(" ").length;
    if ((/[.!?:]$/.test(shown) && long > 20) || (/[,;]$/.test(shown) && long > 45) || long > 70) flush();
  }
  flush();
  for (let i = 0; i + 1 < chunks.length; i++) chunks[i].end = chunks[i + 1].at;
  return chunks;
}

// ---------------------------------------------------------------- one lesson

async function film(lesson, filePort) {
  fs.rmSync(workspace, { recursive: true, force: true });
  fs.mkdirSync(workspace, { recursive: true });
  for (const f of lesson.files) fs.copyFileSync(path.join(lesson.folder, "files", f), path.join(workspace, path.basename(f)));
  const appdata = path.join(out, "appdata");
  fs.mkdirSync(path.join(appdata, "Stellanova Studia"), { recursive: true });
  fs.writeFileSync(path.join(appdata, "Stellanova Studia", "settings.json"), JSON.stringify({ folder: workspace, files: [] }));

  // the voice first: every line spoken ahead, so the film knows how long each takes
  const said = lesson.steps.filter((s) => s.what === "say").map((s) => s.value);
  const linesFile = path.join(out, "lines.json");
  fs.writeFileSync(linesFile, JSON.stringify(said));
  const voices = JSON.parse(py(path.join(here, "voice.py"), linesFile));
  let spoken = 0;

  // games are filmed ahead too, by the game itself (see STELLANOVA_DEMO_FRAMES in the window library)
  for (const s of lesson.steps.filter((s) => s.what === "game")) {
    const [file, keys, title] = s.value.split("|").map((x) => x.trim());
    s.game = await filmGame(lesson, file, keys);
    s.game.title = title || file;
  }

  const port = await freePort();
  const system = spawn(path.join(studia, "system.exe"), [String(port), path.join(studia, "ui"), home], {
    windowsHide: true, stdio: "ignore", env: { ...process.env, APPDATA: appdata } });
  await answering(port);
  const win = new BrowserWindow({ width: WIDTH, height: HEIGHT, show: false, useContentSize: true,
    webPreferences: { offscreen: true, zoomFactor: 1.25, backgroundThrottling: false } });
  win.webContents.setFrameRate(FPS);
  await win.loadURL(`http://127.0.0.1:${port}/`);
  await wait(1200);
  const wc = win.webContents;
  wc.setZoomFactor(1.25);
  const js = (code) => wc.executeJavaScript(code);
  await js(OVERLAY);
  await wait(300);
  wc.focus();

  const partFile = path.join(out, "parts", `${lesson.name}.video.mp4`);
  fs.mkdirSync(path.dirname(partFile), { recursive: true });
  const filmed = new Film(partFile);
  wc.on("paint", (_e, _dirty, image) => filmed.paint(image));
  wc.invalidate();
  await wait(400);
  const placed = [];  // [seconds, mp3] for the sound track
  let talkingUntil = 0;
  let gameDone = Promise.resolve();

  const state = () => js("film.state()");
  const key = async (keyCode, modifiers = [], gap = 45) => {
    wc.sendInputEvent({ type: "keyDown", keyCode, modifiers });
    wc.sendInputEvent({ type: "keyUp", keyCode, modifiers });
    await wait(gap);
  };
  const char = async (c, gap) => {
    wc.sendInputEvent({ type: "char", keyCode: c });
    await wait(gap + Math.random() * gap * 0.6);
  };
  const typeLines = async (text, gap) => {
    const lines = text.split("\n");
    for (let i = 0; i < lines.length; i++) {
      const want = lines[i].match(/^ */)[0].length;
      if (i > 0) {
        if ((await state()).suggesting) await key("Escape");
        await key("Return", [], gap * 2);
        let have = (await state()).line.match(/^ */)[0].length;
        while (have > want) { await key("Backspace", [], 25); have = (await state()).line.match(/^ */)[0].length; }
        for (; have < want; have++) await char(" ", gap / 2);
      } else {
        for (let k = 0; k < want; k++) await char(" ", gap / 2);
      }
      for (const c of lines[i].slice(want)) await char(c, gap);
    }
    if ((await state()).suggesting) await key("Escape");
  };
  const goLine = async (n) => {
    await key("Home", ["control"], 20);
    for (let k = 1; k < n; k++) await key("Down", [], 6);
    await key("End", [], 20);
  };
  const untilQuiet = async () => {
    const left = talkingUntil - filmed.now();
    if (left > 0) await wait(left * 1000);
  };
  const press = async (selector) => {
    await js(`film.pointAt(${JSON.stringify(selector)})`);
    await wait(800);
    await js(`film.press(${JSON.stringify(selector)})`);
    await wait(350);
  };

  for (const step of lesson.steps) {
    const v = step.value;
    try {
      // everything else waits for the voice, so what's shown matches what's said
      if (!["say", "pause", "until finished", "until game ends"].includes(step.what)) await untilQuiet();
      switch (step.what) {
        case "say": {
          await untilQuiet();
          const voice = voices[spoken++];
          const at = filmed.now();
          placed.push([at, voice.file]);
          talkingUntil = at + voice.seconds + 0.35;
          await js(`film.say(${JSON.stringify(captionChunks(v, voice.words))})`);
          break;
        }
        case "wait": await untilQuiet(); break;
        case "pause": await wait(parseFloat(v) * 1000); break;
        case "card": {
          const [kicker, title, words] = v.split("|").map((x) => x.trim());
          await js(`film.card(${JSON.stringify(kicker)}, ${JSON.stringify(title)}, ${JSON.stringify(words || "")})`);
          await wait(900);
          break;
        }
        case "uncard": await untilQuiet(); await js("film.card()"); await wait(900); break;
        case "new": {
          await press("#new-file");
          await wait(300);
          for (const c of v) await char(c, 70);
          await key("Return");
          await wait(900);
          await key("a", ["control"]);
          await key("Delete");
          break;
        }
        case "open": {
          await press(`.file[data-path$=${JSON.stringify("\\" + v)}]`);
          await wait(700);
          break;
        }
        case "open library": {
          // a library's own file, opened like any other (it isn't changed)
          await js(`document.dispatchEvent(new Event("film-open")); 0`);
          await js(`(async () => { const f = document.createElement("div"); f.className = "file"; f.dataset.path = ${JSON.stringify(path.join(home, "libraries", v + ".words"))}; document.getElementById("files").append(f); f.click(); f.remove(); })()`);
          await wait(900);
          break;
        }
        case "clear": await key("a", ["control"]); await key("Delete"); break;
        case "type": await typeLines(v, 55); break;
        case "type fast": await typeLines(v, 18); break;
        case "paste": {
          await js(`navigator.clipboard ? 0 : 0`);
          const { clipboard } = require("electron");
          clipboard.writeText(v);
          await key("v", ["control"]);
          await wait(300);
          break;
        }
        case "keys": {  // key presses: "down", "end", "shift+home", "ctrl+z" ...
          for (const k of v.split(/[\s,]+/).filter(Boolean)) {
            const parts = k.split("+");
            const name = parts.pop();
            const mods = parts.map((m) => (m === "ctrl" ? "control" : m));
            const code = { down: "Down", up: "Up", left: "Left", right: "Right", end: "End", home: "Home", enter: "Return", tab: "Tab",
              backspace: "Backspace", delete: "Delete", escape: "Escape", space: "Space", pageup: "PageUp", pagedown: "PageDown" }[name.toLowerCase()] || name;
            await key(code, mods, 120);
          }
          break;
        }
        case "line": await goLine(parseInt(v, 10)); break;
        case "select": {
          const [a, b] = v.split("-").map((x) => parseInt(x, 10));
          await key("Home", ["control"], 20);
          for (let k = 1; k < a; k++) await key("Down", [], 6);
          await key("Home", [], 20);
          if ((await state()).where.endsWith("Column 1") === false) await key("Home", [], 20);
          for (let k = a; k <= (b || a); k++) await key("Down", ["shift"], 60);
          break;
        }
        case "zoom": {
          let box;
          const lines = v.match(/^lines? (\d+)(?:\s*-\s*(\d+))?$/);
          if (v === "out") box = null;
          else if (lines) box = await js(`film.lines(${lines[1]}, ${lines[2] || lines[1]})`);
          else if (v === "output") box = await js("film.output()");
          else box = await js(`film.box(${JSON.stringify(v)})`);
          await js(`film.look(${JSON.stringify(box)})`);
          await wait(1000);
          break;
        }
        case "spot": {
          if (v === "off") { await js("film.spotAt(null)"); break; }
          const lines = v.match(/^lines? (\d+)(?:\s*-\s*(\d+))?$/);
          const what = lines ? { lines: [+lines[1], +(lines[2] || lines[1])] } : { sel: v };
          await js(`film.spotAt(${JSON.stringify(what)})`);
          await wait(400);
          break;
        }
        case "point": await js(`film.pointAt(${JSON.stringify(v)})`); await wait(800); break;
        case "click": await press(v); break;
        case "hide cursor": await js("film.hideCursor()"); break;
        case "run": case "watch": case "test": case "build": case "web": case "wasm": case "profile": case "debug": {
          await press(`#${step.what}`);
          if (v !== "and keep going") {
            for (let k = 0; k < 1200; k++) {
              await wait(250);
              const now = await state();
              if (!now.running || now.status.startsWith("Paused")) break;
            }
            await wait(500);
          }
          break;
        }
        case "stop at": {  // a click beside a line's number: the program will stop there when debugged
          const spot = JSON.parse(await js(`(() => { const n = [...document.querySelectorAll(".row .num")].find((e) => e.textContent === ${JSON.stringify(v)}); const r = n.getBoundingClientRect(); return JSON.stringify({ x: r.left + r.width - 22, y: r.top + r.height / 2 }); })()`));
          await js(`film.cursorTo(${spot.x}, ${spot.y})`);
          await wait(600);
          // the click, sent inside the page onto whatever is at that point (the studia reads mousedown on the code)
          await js(`(() => { const c = document.getElementById("film-cursor"); c.classList.remove("click"); void c.offsetWidth; c.classList.add("click");
            const at = document.elementFromPoint(${spot.x}, ${spot.y});
            for (const type of ["mousedown", "mouseup"]) at.dispatchEvent(new MouseEvent(type, { clientX: ${spot.x}, clientY: ${spot.y}, button: 0, bubbles: true })); })()`);
          await wait(500);
          break;
        }
        case "until paused": {
          for (let k = 0; k < 1200; k++) {
            await wait(250);
            const now = await state();
            if (!now.running || now.status.startsWith("Paused")) break;
          }
          await wait(400);
          break;
        }
        case "until finished": {
          for (let k = 0; k < 1200; k++) { await wait(250); if (!(await state()).running) break; }
          await wait(400);
          break;
        }
        case "answer": {
          await js(`film.pointAt("#answer")`);
          await wait(500);
          await js(`document.getElementById("answer").focus()`);
          for (const c of v) await char(c, 90);
          await wait(250);
          await js(`document.getElementById("answer").dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }))`);
          await wait(800);
          await js(`document.getElementById("catcher").focus()`);
          break;
        }
        case "focus": await js(`document.getElementById("catcher").focus()`); break;
        case "save": await key("s", ["control"]); await wait(400); break;
        case "game": {
          const g = step.game;
          // plays on while the lesson carries on (to talk over it); "until game ends" waits for it
          gameDone = js(`film.game("http://127.0.0.1:${filePort}/${g.film}", ${JSON.stringify(g.title)}, ${g.width}, ${g.height})`);
          await wait(1500);
          break;
        }
        case "until game ends": await gameDone; break;
        default:
          throw new Error(`I don't know '${step.what}'`);
      }
    } catch (problem) {
      throw new Error(`${lesson.name}.lesson line ${step.line}: ${problem.message}`);
    }
  }
  await untilQuiet();
  await gameDone;
  await wait(800);
  await filmed.end();
  win.destroy();
  system.kill();

  // the sound track: each spoken line where it started, then put together with the picture
  const track = path.join(out, "parts", `${lesson.name}.placed.json`);
  fs.writeFileSync(track, JSON.stringify({ seconds: filmed.written / FPS, placed }));
  py(path.join(here, "sound.py"), track, path.join(out, "parts", `${lesson.name}.wav`));
  execFileSync("ffmpeg", ["-v", "error", "-y", "-i", partFile, "-i", path.join(out, "parts", `${lesson.name}.wav`),
    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", path.join(out, "parts", `${lesson.name}.mp4`)]);
  console.log(`filmed ${lesson.name}: ${(filmed.written / FPS / 60).toFixed(1)} minutes`);
}

// a game played by a list of key presses, filmed frame by frame by the game itself
async function filmGame(lesson, file, keysFile) {
  const games = path.join(out, "games");
  fs.mkdirSync(games, { recursive: true });
  const name = path.basename(file, ".stella");
  const source = path.join(lesson.folder, "files", file);
  const folder = path.join(games, name);
  fs.mkdirSync(folder, { recursive: true });
  // the game and the scripts it uses; and no saves from an earlier filming, so it plays as a first game
  for (const f of fs.readdirSync(path.dirname(source)).filter((f) => f.endsWith(".stella"))) fs.copyFileSync(path.join(path.dirname(source), f), path.join(folder, f));
  for (const f of fs.readdirSync(folder).filter((f) => f.endsWith(".save") || f.endsWith(".zip"))) fs.rmSync(path.join(folder, f));
  const exe = path.join(folder, name + ".exe");
  py(path.join(home, "stellanova.py"), "build", path.join(folder, path.basename(file)));
  const raw = path.join(folder, "frames.raw");
  execFileSync(exe, [], { cwd: folder, windowsHide: true, timeout: 600000,
    env: { ...process.env, STELLANOVA_DEMO_FRAMES: raw, STELLANOVA_DEMO_KEYS: path.join(lesson.folder, "files", keysFile) } });
  const size = fs.readFileSync(source, "utf8").match(/open a world with "[^"]*", (\d+), (\d+)/);
  const [width, height] = [parseInt(size[1], 10), parseInt(size[2], 10)];
  const film = `games/${name}.mp4`;
  execFileSync("ffmpeg", ["-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr0", "-s", `${width}x${height}`, "-r", "60", "-i", raw,
    "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p", path.join(out, film)]);
  fs.rmSync(raw);
  return { film, width, height };
}

// ---------------------------------------------------------------- start

app.disableHardwareAcceleration();
app.on("window-all-closed", () => {});  // each lesson closes its window; keep going to the next
app.whenReady().then(async () => {
  try {
    execFileSync("py", ["-3", path.join(home, "stellanova.py"), "web", "screens.stella", "ui"], { cwd: studia, windowsHide: true });
    if (!fs.existsSync(path.join(studia, "system.exe")))
      execFileSync("py", ["-3", path.join(home, "stellanova.py"), "build", "system.stella"], { cwd: studia, windowsHide: true });
    const filePort = await freePort();
    serveOut(filePort);
    const files = process.argv.slice(2).filter((a) => a.endsWith(".lesson"));
    for (const f of files) await film(readLesson(path.resolve(f)), filePort);
  } catch (problem) {
    console.error(problem.stack || problem.message);
    process.exitCode = 1;
  }
  app.quit();
});
