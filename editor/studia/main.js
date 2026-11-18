// Studia's shell: rebuilds the screens and system side if changed, then opens the window.

const { app, BrowserWindow } = require("electron");
const { spawn, execFileSync } = require("child_process");
const fs = require("fs");
const net = require("net");
const http = require("http");
const path = require("path");

const here = __dirname;
const home = path.resolve(here, "..", "..");
const compiler = path.join(home, "stellanova.py");
const screens = path.join(here, "ui");
const systemExe = path.join(here, "system.exe");
let system = null;

function older(made, from) {
  return !fs.existsSync(made) || fs.statSync(made).mtimeMs < fs.statSync(from).mtimeMs;
}

function remake() {
  const run = (...words) => execFileSync("py", ["-3", compiler, ...words], { cwd: here, windowsHide: true });
  if (older(path.join(screens, "screens.js"), path.join(here, "screens.stella"))) run("web", "screens.stella", "ui");
  if (older(systemExe, path.join(here, "system.stella"))) run("build", "system.stella");
}

function freePort() {
  return new Promise((resolve, reject) => {
    const s = net.createServer();
    s.on("error", reject);
    s.listen(0, "127.0.0.1", () => {
      const p = s.address().port;
      s.close(() => resolve(p));
    });
  });
}

function answering(port, until = Date.now() + 15000) {
  return new Promise((resolve, reject) => {
    const once = () => {
      const req = http.get({ host: "127.0.0.1", port, path: "/api/hello", timeout: 1000 }, (res) => (res.resume(), resolve()));
      req.on("error", () => (Date.now() > until ? reject(new Error("the system side didn't answer")) : setTimeout(once, 150)));
      req.on("timeout", () => req.destroy());
    };
    once();
  });
}

async function start() {
  remake();
  const port = await freePort();
  system = spawn(systemExe, [String(port), screens, home], { windowsHide: true, stdio: "ignore" });
  await answering(port);
  const win = new BrowserWindow({
    width: 1400, height: 900, backgroundColor: "#1e1e1e", autoHideMenuBar: true, title: "Stellanova Studia",
    webPreferences: { contextIsolation: true, sandbox: true, spellcheck: false },
  });
  win.loadURL(`http://127.0.0.1:${port}/`);
  // For tests: STUDIA_PLAY runs a script, STUDIA_SHOT saves a picture and closes.
  win.webContents.once("did-finish-load", () => {
    if (process.env.STUDIA_PLAY) win.webContents.on("console-message", (e) => console.log(e.message));
    if (process.env.STUDIA_PLAY) setTimeout(() => require(process.env.STUDIA_PLAY)(win), 1500);
    if (process.env.STUDIA_SHOT)
      setTimeout(async () => {
        try {
          fs.writeFileSync(process.env.STUDIA_SHOT, (await win.webContents.capturePage()).toPNG());
        } finally {
          app.quit();
        }
      }, Number(process.env.STUDIA_SHOT_WAIT || 4000));
  });
}

app.whenReady().then(start).catch((e) => {
  console.error(e.message);
  app.quit();
});
app.on("window-all-closed", () => app.quit());
app.on("quit", () => system && system.kill());
