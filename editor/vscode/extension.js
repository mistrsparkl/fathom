// Mistakes, completion and hover help for .stella files.
const vscode = require("vscode");
const fs = require("fs");
const path = require("path");
const { execFile } = require("child_process");
const words = require("./words");

function activate(context) {
  const where = () => words.home(vscode.workspace.getConfiguration("stellanova").get("home"));
  let library = null;
  const libraryWords = () => {
    if (!library && where()) library = words.libraryWords(path.join(where(), "libraries"));
    return library || [];
  };
  const problems = vscode.languages.createDiagnosticCollection("stellanova");
  const waiting = new Map();

  // Checked as a copy next to the file, so 'use:' works.
  function check(doc) {
    if (doc.languageId !== "stellanova" || doc.uri.scheme !== "file" || !where()) return;
    const file = doc.uri.fsPath;
    const draft = path.join(path.dirname(file), "." + path.basename(file, ".stella") + ".checking.stella");
    fs.writeFileSync(draft, doc.getText(), "utf8");
    const python = process.platform === "win32" ? "py" : "python3";
    const args = [...(process.platform === "win32" ? ["-3"] : []), path.join(where(), "stellanova.py"), "check", draft];
    execFile(python, args, { cwd: path.dirname(file), timeout: 20000 }, (_, out, err) => {
      fs.rmSync(draft, { force: true });
      problems.set(doc.uri, words.mistakes(out + err).map((m) => {
        const line = Math.min(Math.max(m.line - 1, 0), doc.lineCount - 1);
        const shown = new vscode.Diagnostic(doc.lineAt(line).range, m.message, vscode.DiagnosticSeverity.Error);
        shown.source = "stellanova";
        return shown;
      }));
    });
  }
  function soon(doc) {
    clearTimeout(waiting.get(doc.uri.toString()));
    waiting.set(doc.uri.toString(), setTimeout(() => check(doc), 700));
  }

  const all = (doc) => libraryWords().concat(words.ownWords(doc.getText()));
  context.subscriptions.push(
    problems,
    vscode.workspace.onDidOpenTextDocument(check),
    vscode.workspace.onDidSaveTextDocument(check),
    vscode.workspace.onDidChangeTextDocument((e) => soon(e.document)),
    vscode.workspace.onDidCloseTextDocument((doc) => problems.delete(doc.uri)),
    vscode.languages.registerCompletionItemProvider("stellanova", {
      provideCompletionItems(doc) {
        return all(doc).map((w) => {
          const item = new vscode.CompletionItem(w.phrase, w.library ? vscode.CompletionItemKind.Function : vscode.CompletionItemKind.Method);
          item.detail = [w.given, w.gives && "returning " + w.gives].filter(Boolean).join(", ") || undefined;
          item.documentation = w.library ? `use: ${w.library}` : "this script's own command";
          return item;
        });
      },
    }),
    vscode.languages.registerHoverProvider("stellanova", {
      provideHover(doc, at) {
        const w = words.wordAt(all(doc), doc.lineAt(at.line).text, at.character);
        return w && new vscode.Hover(new vscode.MarkdownString().appendCodeblock(words.describe(w), "text"));
      },
    }),
  );
  vscode.workspace.textDocuments.forEach(check);
}

module.exports = { activate, deactivate() {} };
