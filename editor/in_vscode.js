// Tries the extension in real VS Code. Use: node editor/in_vscode.js
const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawnSync } = require("child_process");

const HERE = path.resolve(__dirname, "..");

function vscodeProgram() {
  const places = process.platform === "win32"
    ? [path.join(process.env.LOCALAPPDATA || "", "Programs", "Microsoft VS Code", "Code.exe"), "C:\\Program Files\\Microsoft VS Code\\Code.exe"]
    : ["/usr/share/code/code", "/usr/bin/code", "/Applications/Visual Studio Code.app/Contents/MacOS/Electron"];
  return places.find((p) => fs.existsSync(p));
}

// Inside VS Code: the checks themselves
async function run() {
  const vscode = require("vscode");
  const folder = process.env.FATHOM_TRY_FOLDER;
  await vscode.workspace.getConfiguration("fathom").update("home", HERE, vscode.ConfigurationTarget.Global);
  const file = path.join(folder, "try.fathom");
  const doc = await vscode.workspace.openTextDocument(file);
  await vscode.window.showTextDocument(doc);
  const said = [];
  for (let k = 0; k < 60 && !vscode.languages.getDiagnostics(doc.uri).length; k++) await new Promise((r) => setTimeout(r, 500));
  const shown = vscode.languages.getDiagnostics(doc.uri);
  said.push(shown.length === 1 && shown[0].range.start.line === 2 ? "mistake ok" : "mistake WRONG: " + JSON.stringify(shown.map((d) => [d.range.start.line, d.message])));
  const offered = await vscode.commands.executeCommand("vscode.executeCompletionItemProvider", doc.uri, new vscode.Position(3, 2));
  const labels = offered.items.map((i) => (typeof i.label === "string" ? i.label : i.label.label));
  said.push(labels.includes("the time now") && labels.includes("cheer") ? "words ok" : "words WRONG: " + labels.slice(0, 10).join(", "));
  const help = await vscode.commands.executeCommand("vscode.executeHoverProvider", doc.uri, new vscode.Position(3, 4));
  const helpText = help.map((h) => h.contents.map((c) => c.value || c).join(" ")).join(" ");
  said.push(helpText.includes("cheer") ? "hover ok" : "hover WRONG: " + helpText);
  fs.writeFileSync(path.join(folder, "said.txt"), said.join("\n") + "\n", "utf8");
}

// From the command line: start VS Code to run the checks above
function main() {
  const program = vscodeProgram();
  if (!program) {
    console.log("VS Code isn't on this computer, so the extension can't be tried in it.");
    return 0;
  }
  const folder = fs.mkdtempSync(path.join(os.tmpdir(), "fathom-vscode-"));
  fs.writeFileSync(path.join(folder, "try.fathom"),
    "genesis:\n  cheer\n  scrawl 1 plus\n  cheer\nand the universe said i love you\n\n" +
    "to cheer:\n  scrawl \"hooray\"\nand the universe said i love you\n", "utf8");
  const env = { ...process.env, FATHOM_TRY_FOLDER: folder };
  delete env.ELECTRON_RUN_AS_NODE;  // (set by some editors' terminals: VS Code would start as plain Node)
  const ran = spawnSync(program, [
    `--extensionDevelopmentPath=${path.join(HERE, "editor", "vscode")}`, `--extensionTestsPath=${__filename}`,
    `--user-data-dir=${path.join(folder, "user")}`, `--extensions-dir=${path.join(folder, "extensions")}`,
    "--disable-workspace-trust", "--skip-welcome", "--skip-release-notes", "--new-window", folder,
  ], { env, timeout: 120000, encoding: "utf8" });
  const saidFile = path.join(folder, "said.txt");
  const said = fs.existsSync(saidFile) ? fs.readFileSync(saidFile, "utf8") : "VS Code didn't run the checks.\n" + (ran.stderr || "").slice(-2000);
  process.stdout.write(said);
  fs.rmSync(folder, { recursive: true, force: true, maxRetries: 5 });
  return /WRONG|didn't/.test(said) ? 1 : 0;
}

if (require.main === module) process.exitCode = main();
module.exports = { run };
