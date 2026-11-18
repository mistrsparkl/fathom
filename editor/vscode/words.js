// What the editor knows without VS Code: where Stellanova is, its library words, and its mistakes.
const fs = require("fs");
const path = require("path");

// The folder holding stellanova.py: the setting, a folder on PATH that has it, or where the extension was made.
function home(setting) {
  const made = path.join(__dirname, "home.txt");
  const places = [setting, ...(process.env.PATH || "").split(path.delimiter),
                  fs.existsSync(made) ? fs.readFileSync(made, "utf8").trim() : path.join(__dirname, "..", "..")].filter(Boolean);
  return places.find((p) => fs.existsSync(path.join(p, "stellanova.py"))) || null;
}

// Every library word, read from libraries/*.words the way the studia reads them.
function libraryWords(folder) {
  const found = [];
  for (const name of fs.readdirSync(folder).filter((n) => n.endsWith(".words")).sort()) {
    const library = name.slice(0, -6);
    let inside = false, note = "";
    for (const line of fs.readFileSync(path.join(folder, name), "utf8").split(/\r?\n/)) {
      if (["code:", "python:", "javascript:"].includes(line)) inside = true;
      else if (!line.startsWith(" ") && line !== "") inside = false;
      if (inside || line.startsWith(" ")) continue;
      if (line.startsWith("note:")) { note = line.slice(5).trim(); continue; }
      if (!line.includes(" = ") || line.startsWith("include:") || line.startsWith("link:")) { note = ""; continue; }
      const head = line.split(" = ")[0];
      if (line.startsWith("to ")) {
        const parts = head.slice(3).split(", ");
        found.push({ phrase: parts[0], library, given: parts.find((p) => p.startsWith("given ")) || "",
                     gives: (parts.find((p) => p.startsWith("returning ")) || "").slice(10), note });
      } else if (line.includes(", ")) {
        found.push({ phrase: head.trim(), library, given: "", gives: "", note });
      }
      note = "";
    }
  }
  return found;
}

// The script's own commands: 'to greet, given name (text):'
function ownWords(text) {
  const found = [];
  for (const m of text.matchAll(/^to ([a-z ]+?)(?:, for an? [a-z ]+?)?(?:, (given .+?))?(?:, returning (.+))?:\s*$/gm))
    found.push({ phrase: m[1], library: "", given: m[2] || "", gives: m[3] || "", note: "" });
  return found;
}

// 'x.stella line 12: I don't know 'nope'.' -> [{line: 12, message}] (line counted from 1)
function mistakes(said) {
  const found = [];
  for (const m of said.matchAll(/line (\d+): (.+)/g))
    if (!m[2].includes("A program needs a 'genesis:' command"))  // a part of a program has no genesis
      found.push({ line: Number(m[1]), message: m[2].trim() });
  return found;
}

// The word that covers this spot of a line, longest phrase first.
function wordAt(words, line, column) {
  const lower = line.toLowerCase();
  let best = null;
  for (const w of words) {
    for (let at = lower.indexOf(w.phrase); at >= 0; at = lower.indexOf(w.phrase, at + 1)) {
      const edges = !/[a-z]/.test(lower[at - 1] || "") && !/[a-z]/.test(lower[at + w.phrase.length] || "");
      if (edges && at <= column && column <= at + w.phrase.length && (!best || w.phrase.length > best.phrase.length)) best = w;
    }
  }
  return best;
}

function describe(w) {
  const shown = [w.phrase, w.given, w.gives && "returning " + w.gives].filter(Boolean).join(", ");
  return [shown, w.note, w.library && `use: ${w.library}`].filter(Boolean).join("\n\n");
}

module.exports = { home, libraryWords, ownWords, mistakes, wordAt, describe };
