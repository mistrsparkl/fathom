// Runs PROGRAM.wasm with Node's WASI: node PROGRAM.mjs [words...]  (any WASI runner works too: wasmtime --dir . PROGRAM.wasm)
// Made by 'stellanova wasm' from runtime/wasi.mjs.
import { readFile } from "node:fs/promises";
import { readdirSync, lstatSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const warn = process.emitWarning;  // (Node calls WASI experimental: say nothing about that)
process.emitWarning = (w, ...more) => (String(w).includes("WASI") ? undefined : warn.call(process, w, ...more));
const { WASI } = await import("node:wasi");

const wasi = new WASI({ version: "preview1", args: ["PROGRAM", ...process.argv.slice(2)], env: process.env, preopens: { ".": "." }, returnOnExit: true });
const imports = wasi.getImportObject();
const calls = imports.wasi_snapshot_preview1;
let memory;

// Node's WASI can't list a folder on Windows (fd_readdir: "not implemented"), so it is done here: path_open says which
// folder each number is, and fd_readdir lists it, the way WASI lays a folder's entries out.
const ENOSYS = 52, EBADF = 8;
const folders = new Map([[3, "."]]);  // 3: the first (and only) preopened folder
const open = calls.path_open, close = calls.fd_close, readdir = calls.fd_readdir;
calls.path_open = (fd, dirflags, path, length, ...rest) => {
  const answer = open(fd, dirflags, path, length, ...rest);
  if (answer === 0 && folders.has(fd)) {
    const name = new TextDecoder().decode(new Uint8Array(memory.buffer, path, length));
    const opened = new DataView(memory.buffer).getUint32(rest[rest.length - 1], true);
    folders.set(opened, join(folders.get(fd), name));
  }
  return answer;
};
calls.fd_close = (fd) => {
  if (fd !== 3) folders.delete(fd);
  return close(fd);
};
calls.fd_readdir = (fd, buffer, size, cookie, used) => {
  const answer = readdir(fd, buffer, size, cookie, used);
  if (answer !== ENOSYS) return answer;
  if (!folders.has(fd)) return EBADF;
  const folder = folders.get(fd);
  const names = [".", "..", ...readdirSync(folder)];
  const bytes = new Uint8Array(memory.buffer), view = new DataView(memory.buffer);
  let at = 0;
  for (let k = Number(cookie); k < names.length && at < size; k++) {
    const name = new TextEncoder().encode(names[k]);
    let type = 0;  // unknown
    try {
      const s = lstatSync(join(folder, names[k]));
      type = s.isDirectory() ? 3 : s.isSymbolicLink() ? 7 : s.isFile() ? 4 : 0;
    } catch {}
    const entry = new Uint8Array(24 + name.length);  // next cookie (u64), inode (u64), name length (u32), type (u8), then the name
    const e = new DataView(entry.buffer);
    e.setBigUint64(0, BigInt(k + 1), true);
    e.setUint32(16, name.length, true);
    e.setUint8(20, type);
    entry.set(name, 24);
    const fits = Math.min(entry.length, size - at);  // the last one may be cut short: the caller asks again from it
    bytes.set(entry.subarray(0, fits), buffer + at);
    at += fits;
  }
  view.setUint32(used, at, true);
  return 0;
};

const code = await WebAssembly.compile(await readFile(fileURLToPath(new URL("PROGRAM.wasm", import.meta.url))));
const instance = await WebAssembly.instantiate(code, imports);
memory = instance.exports.memory;
process.exitCode = wasi.start(instance);
