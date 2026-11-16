// Runs the VS Code extension with a stand-in for VS Code: opens a script, prints the mistakes it shows and a hover.
// node check_extension.js script.stella
const Module = require("module");
const fs = require("fs");
const file = require("path").resolve(process.argv[2]);
const text = fs.readFileSync(file, "utf8");
const lines = text.split(/\r?\n/);
const doc = {
  languageId: "stellanova", uri: { scheme: "file", fsPath: file, toString: () => file }, lineCount: lines.length,
  getText: () => text, lineAt: (n) => ({ text: lines[n], range: { line: n } }),
};
const shown = [], providers = {};
const vscode = {
  workspace: { getConfiguration: () => ({ get: () => "" }), textDocuments: [doc],
               onDidOpenTextDocument() {}, onDidSaveTextDocument() {}, onDidChangeTextDocument() {}, onDidCloseTextDocument() {} },
  languages: {
    createDiagnosticCollection: () => ({ set: (_, d) => { shown.push(...d); done(); }, delete() {} }),
    registerCompletionItemProvider: (_, p) => { providers.complete = p; },
    registerHoverProvider: (_, p) => { providers.hover = p; },
  },
  Diagnostic: function (range, message) { this.range = range; this.message = message; },
  DiagnosticSeverity: { Error: 0 }, CompletionItemKind: { Function: 1, Method: 2 },
  CompletionItem: function (label, kind) { this.label = label; this.kind = kind; },
  Hover: function (md) { this.md = md; }, MarkdownString: function () { this.value = ""; this.appendCodeblock = (s) => { this.value += s; return this; }; },
};
const load = Module._load;
Module._load = (name, ...rest) => (name === "vscode" ? vscode : load(name, ...rest));
require("./vscode/extension.js").activate({ subscriptions: [] });

function done() {
  for (const d of shown) console.log(`line ${d.range.line + 1}: ${d.message}`);
  const words = providers.complete.provideCompletionItems(doc);
  console.log(`${words.length} words to complete, own: ${words.filter((w) => w.kind === 2).map((w) => w.label).join(", ")}`);
  const at = lines.findIndex((l) => l.includes("days between"));
  if (at >= 0) console.log(providers.hover.provideHover(doc, { line: at, character: lines[at].indexOf("days between") + 2 }).md.value.split("\n")[0]);
}
