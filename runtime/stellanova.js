// What every Stellanova program made for the web uses: the same words as stellanova.h, in JavaScript.
// stellanova.py writes programs that call these ('stellanova web game.stella'); they run in a web page
// (load this file first) or with node. Messages and the way values are shown match the other two ways exactly.
"use strict";
(function () {
  const inNode = typeof process !== "undefined" && !!(process.versions && process.versions.node) && typeof require === "function";
  const fs = inNode ? require("fs") : null;

  // ---- what went wrong, and on which line
  class Problem extends Error {
    constructor(line, message, kind = "") {
      super(message);
      this.line = line;
      this.kind = kind;  // a kind of problem of the program's own ('raise a fuel problem with'), or ""
    }
  }
  const fail = (line, message, kind = "") => { throw new Problem(line, message, kind); };
  const problem_kind = (e) => (e instanceof Problem ? e.kind : "");

  // ---- places, with the same names Unreal uses
  class Place3 {
    constructor(x, y, z) { this.X = x; this.Y = y; this.Z = z; }
    Size() { return Math.sqrt(this.X * this.X + this.Y * this.Y + this.Z * this.Z); }
  }
  class Place2 {
    constructor(x, y) { this.X = x; this.Y = y; }
    Size() { return Math.sqrt(this.X * this.X + this.Y * this.Y); }
  }
  const FVector = (x, y, z) => new Place3(x, y, z);
  const FVector2D = (x, y) => (x instanceof Place3 ? new Place2(x.X, x.Y) : new Place2(x, y));
  const isPlace = (v) => v instanceof Place3 || v instanceof Place2;
  const each = (a, b, f) => (a instanceof Place3 ? new Place3(f(a.X, b.X), f(a.Y, b.Y), f(a.Z, b.Z)) : new Place2(f(a.X, b.X), f(a.Y, b.Y)));

  const FMath = {
    Clamp: (x, lo, hi) => Math.min(Math.max(x, lo), hi),
    Min: (a, b) => Math.min(a, b),
    Max: (a, b) => Math.max(a, b),
    Sqrt: (x) => Math.sqrt(x),
    Abs: (x) => Math.abs(x),
    Atan2: (y, x) => Math.atan2(y, x),
    RadiansToDegrees: (r) => (r * 180.0) / 3.14159265358979323846,
    UnwindDegrees: (a) => {
      a = a % 360.0;
      if (a > 180.0) a -= 360.0;
      if (a < -180.0) a += 360.0;
      return a;
    },
  };

  // ---- kinds of things: each is a class, told its parts by kind()
  const kinds = {};

  // ---- showing values as text
  function stripZeros(digits) {
    return digits.includes(".") ? digits.replace(/0+$/, "").replace(/\.$/, "") : digits;
  }
  function numberText(d) {
    if (Number.isNaN(d)) return "not a number";
    if (!Number.isFinite(d)) return d > 0 ? "infinity" : "-infinity";
    if (Math.floor(d) === d && Math.abs(d) < 1e21) return d === 0 ? "0" : d.toFixed(0);
    // 15 significant digits, as C's %.15g writes them
    const [mantissa, power] = d.toExponential(14).split("e");
    const exp = Number(power);
    if (exp < -4 || exp >= 15) return stripZeros(mantissa) + "e" + (exp < 0 ? "-" : "+") + String(Math.abs(exp)).padStart(2, "0");
    return stripZeros(d.toFixed(14 - exp));
  }
  const isGroup = (v) => Array.isArray(v) || v instanceof Map;
  const partText = (v) => (isGroup(v) && count(v) ? "(" + text(v) + ")" : text(v));
  function text(v) {
    if (typeof v === "string") return v;
    if (v === undefined) return "nothing";  // a thing that isn't there ('no enemy')
    if (typeof v === "number") return numberText(v);
    if (typeof v === "boolean") return v ? "yes" : "no";
    if (Array.isArray(v)) return v.length ? v.map(partText).join(", ") : "(nothing)";
    if (v instanceof Map) return v.size ? [...v.keys()].sort(order).map((k) => k + ": " + partText(v.get(k))).join(", ") : "(nothing)";
    if (v instanceof Place3) return `${numberText(v.X)} horizontal ${numberText(v.Y)} vertical ${numberText(v.Z)} depth`;
    if (v instanceof Place2) return `${numberText(v.X)} horizontal ${numberText(v.Y)} vertical`;
    if (v === null || typeof v === "function") return "a command";
    const kind = v.constructor;
    return `a ${kind.title} (` + kind.spec.map(([words, member]) => `${words}: ${text(v[member])}`).join(", ") + ")";
  }
  const order = (a, b) => (a < b ? -1 : a > b ? 1 : 0);

  // ---- copying and comparing: lists, tables, places and things are values, copied when they are stored
  function dup(v) {
    if (v === null || typeof v !== "object") return v;
    if (Array.isArray(v)) return v.map(dup);
    if (v instanceof Map) return new Map([...v].map(([k, x]) => [k, dup(x)]));
    if (v instanceof Place3) return new Place3(v.X, v.Y, v.Z);
    if (v instanceof Place2) return new Place2(v.X, v.Y);
    const made = Object.create(Object.getPrototypeOf(v));
    for (const k of Object.keys(v)) made[k] = dup(v[k]);
    return made;
  }
  function same(a, b) {
    if (a === b) return typeof a !== "number" || !Number.isNaN(a);
    if (a === null || b === null || typeof a !== "object" || typeof b !== "object") return false;
    if (Array.isArray(a)) return Array.isArray(b) && a.length === b.length && a.every((x, k) => same(x, b[k]));
    if (a instanceof Map) return b instanceof Map && a.size === b.size && [...a].every(([k, x]) => b.has(k) && same(x, b.get(k)));
    if (Object.getPrototypeOf(a) !== Object.getPrototypeOf(b)) return false;
    return Object.keys(a).every((k) => same(a[k], b[k]));
  }

  // ---- lists and tables
  function index_of(items, number, line) {
    if (Math.floor(number) !== number || number < 1 || number > items.length)
      fail(line, `there is no item ${numberText(number)} in a list of ${items.length} item${items.length === 1 ? "" : "s"}. Items are counted from 1.`);
    return number - 1;
  }
  const count = (v) => (v instanceof Map ? v.size : v.length);

  // ---- the program as a whole
  let files = [];
  const others = [];
  function where(line) {
    return line < 100000 || Math.floor(line / 100000) >= files.length ? `Line ${line}` : `${files[Math.floor(line / 100000)]} line ${line % 100000}`;
  }
  function problem_text(e) {
    if (e instanceof Problem) return e.message;
    if (e instanceof RangeError && /call stack/i.test(e.message)) return "commands called each other too many times in a row (they may never stop).";
    return "something went wrong inside Stellanova: " + (e && e.message ? e.message : String(e));
  }
  function report(e) {
    const shown = `${where(e instanceof Problem ? e.line : 0)}: ${problem_text(e)}`;
    if (stellanova.on_problem) stellanova.on_problem(shown);
    if (inNode) fs.writeSync(2, shown + "\n");
    else console.error(shown);
  }
  function out(s) {
    if (stellanova.on_say) stellanova.on_say(s);
    else if (inNode) fs.writeSync(1, s + "\n");
    else console.log(s);
  }
  function leave(code) {
    if (inNode) process.exit(code);
    throw new Problem(0, "the program ended.");
  }

  // ---- typing answers (node reads them from its input; a page asks with a small box)
  function readLine() {
    if (!inNode) {
      const answer = typeof prompt === "function" ? prompt("") : null;
      return answer === null ? null : answer;
    }
    const one = Buffer.alloc(1), bytes = [];
    for (;;) {
      let n;
      try {
        n = fs.readSync(0, one, 0, 1, null);
      } catch (e) {
        if (e.code === "EAGAIN") continue;
        if (e.code === "EOF") n = 0;
        else throw e;
      }
      if (n === 0) return bytes.length ? Buffer.from(bytes).toString("utf8") : null;
      if (one[0] === 10) break;
      bytes.push(one[0]);
    }
    return Buffer.from(bytes).toString("utf8");
  }
  const NUMBER_TEXT = /^\s*[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?\s*$/;
  function ask_text(question) {
    if (inNode) fs.writeSync(1, question);
    const line = readLine();
    if (line === null) leave(0); // nobody is left to answer (input closed)
    return line.replace(/\r$/, "");
  }

  // ---- saving and loading, as JSON, exactly as the other two ways write it
  function saved_number(x, line) {
    if (!Number.isFinite(x)) fail(line, "I can't save infinity or not a number.");
    if (x === Math.floor(x) && Math.abs(x) < 1e16) return (x === 0 ? 0 : x).toFixed(0);
    const [mantissa, power] = x.toExponential().split("e"); // the shortest digits that read back the same
    const exp = Number(power), sign = mantissa[0] === "-" ? "-" : "", digits = mantissa.replace(/[-.]/g, "");
    if (exp >= -4 && exp < 16) {
      if (exp < 0) return sign + "0." + "0".repeat(-exp - 1) + digits;
      return sign + digits.slice(0, exp + 1).padEnd(exp + 1, "0") + "." + (digits.slice(exp + 1) || "0");
    }
    return sign + digits[0] + (digits.length > 1 ? "." + digits.slice(1) : "") + "e" + (exp < 0 ? "-" : "+") + String(Math.abs(exp)).padStart(2, "0");
  }
  function saved_string(s) {
    let o = '"';
    for (const c of s) {
      const code = c.codePointAt(0);
      if (c === '"') o += '\\"';
      else if (c === "\\") o += "\\\\";
      else if (c === "\n") o += "\\n";
      else if (c === "\r") o += "\\r";
      else if (c === "\t") o += "\\t";
      else if (c === "\b") o += "\\b";
      else if (c === "\f") o += "\\f";
      else if (code < 0x20) o += "\\u" + code.toString(16).padStart(4, "0");
      else o += c;
    }
    return o + '"';
  }
  function saved(v, line, kind = "") {  // kind: what it is saved as (a speaker also says which kind of thing it is)
    if (typeof v === "number") return saved_number(v, line);
    if (v === undefined) return "null";
    if (kind.startsWith("list of ") && Array.isArray(v)) return "[" + v.map((x) => saved(x, line, kind.slice(8))).join(", ") + "]";
    if (kind.startsWith("table of ") && v instanceof Map)
      return "{" + [...v.keys()].sort(order).map((k) => saved_string(k) + ": " + saved(v.get(k), line, kind.slice(9))).join(", ") + "}";
    if (kind.startsWith("thing ") && v !== null && typeof v === "object" && v.constructor.spec) {
      const parts = v.constructor.spec.map(([words, member, part]) => `${saved_string(words)}: ${saved(v[member], line, part)}`);
      if (kinds[kind.slice(6)] && kinds[kind.slice(6)].able) parts.unshift(`"is a": ${saved_string(v.constructor.title)}`);
      return "{" + parts.join(", ") + "}";
    }
    if (typeof v === "boolean") return v ? "true" : "false";
    if (typeof v === "string") return saved_string(v);
    if (v === null || typeof v === "function") fail(line, "I can't save a command in a file.");
    if (Array.isArray(v)) return "[" + v.map((x) => saved(x, line)).join(", ") + "]";
    if (v instanceof Map) return "{" + [...v.keys()].sort(order).map((k) => saved_string(k) + ": " + saved(v.get(k), line)).join(", ") + "}";
    if (v instanceof Place3) return `[${saved_number(v.X, line)}, ${saved_number(v.Y, line)}, ${saved_number(v.Z, line)}]`;
    if (v instanceof Place2) return `[${saved_number(v.X, line)}, ${saved_number(v.Y, line)}]`;
    return "{" + v.constructor.spec.map(([words, member]) => `${saved_string(words)}: ${saved(v[member], line)}`).join(", ") + "}";
  }
  class NotSaved extends Error {}
  function from_saved(d, kind) {
    const isList = Array.isArray(d), isTable = d !== null && typeof d === "object" && !isList;
    if (kind === "number" && typeof d === "number") return d;
    if (kind === "yes or no" && typeof d === "boolean") return d;
    if (kind === "text" && typeof d === "string") return d;
    if ((kind === "place" || kind === "flat") && isList && d.length === (kind === "place" ? 3 : 2) && d.every((x) => typeof x === "number"))
      return kind === "place" ? new Place3(d[0], d[1], d[2]) : new Place2(d[0], d[1]);
    if (kind.startsWith("list of ") && isList) return d.map((x) => from_saved(x, kind.slice(8)));
    if (kind.startsWith("table of ") && isTable) return new Map(Object.keys(d).map((k) => [k, from_saved(d[k], kind.slice(9))]));
    if (kind.startsWith("thing ") && d === null) return undefined;
    if (kind.startsWith("thing ") && kinds[kind.slice(6)].able) {  // a speaker: made as the kind it says it is
      if (!isTable || !kinds[kind.slice(6)].able.includes(d["is a"])) throw new NotSaved();
      return from_saved(d, "thing " + d["is a"]);
    }
    if (kind.startsWith("thing ") && isTable) {
      const Kind = kinds[kind.slice(6)], made = new Kind();
      const loose = (key) => key.replace(/[ _-]/g, "").replace(/[A-Z]/g, (c) => c.toLowerCase());
      const near = new Map(Object.keys(d).map((key) => [loose(key), key]));  // a web service's "windSpeed" or "wind_speed" is 'wind speed'
      for (const [words, member, part] of Kind.spec) {
        const key = Object.prototype.hasOwnProperty.call(d, words) ? words : near.get(loose(words));
        if (key !== undefined && d[key] !== null) made[member] = from_saved(d[key], part);  // missing, or null: the part stays empty
      }
      return made;
    }
    throw new NotSaved();
  }
  function reading(data, kind) {
    try {
      return from_saved(JSON.parse(data), kind);
    } catch (e) {
      if (e instanceof NotSaved || e instanceof SyntaxError || e instanceof RangeError) return NotSaved;
      throw e;
    }
  }

  // ---- files: only where there are files (node, or the Tidal shell's own words)
  function need_files(line) {
    if (!fs) fail(line, "a web page can't open files on the computer.");
  }
  function read_file(path, line) {
    need_files(line);
    try {
      return fs.readFileSync(path, "utf8");
    } catch {
      fail(line, `there is no file called "${path}" (or it can't be opened).`);
    }
  }
  function lines_of(s) {
    if (!s) return [];
    const parts = s.split("\n");
    if (s.endsWith("\n")) parts.pop();
    return parts.map((p) => (p.endsWith("\r") ? p.slice(0, -1) : p));
  }
  const letters_in = (s) => Array.from(s);
  const ascii = (s, from, to) => s.replace(from, (c) => String.fromCharCode(c.charCodeAt(0) + to));

  const stellanova = {
    Problem, fail, text, dup, same, count, kinds, problem_text, problem_kind, report,
    on_say: null, on_problem: null,
    table: () => new Map(),
    kind(Kind, title, spec) {
      Kind.title = title;
      Kind.spec = spec;
      kinds[title] = Kind;
    },
    as_kind(v, Kind) {
      if (v === undefined) return undefined;
      const made = new Kind();
      for (const [, member] of Kind.spec) made[member] = dup(v[member]);
      return made;
    },
    replace_thing(own, v) {
      const fresh = dup(v);
      for (const k of Object.keys(own)) own[k] = fresh[k];
    },
    born(owner, where) {
      owner.birth = dup(where);
      owner.existence = dup(where);
    },
    plus: (a, b) => each(a, b, (x, y) => x + y),
    minus: (a, b) => each(a, b, (x, y) => x - y),
    times: (a, k) => each(a, a, (x) => x * k),
    repeats: (n) => (Number.isFinite(n) ? Math.trunc(n) : 0),
    over: (a, k) => each(a, a, (x) => x / k),
    negative: (a) => each(a, a, (x) => -x),
    within: (a, b, reach) => (isPlace(a) ? each(a, b, (x, y) => x - y).Size() <= reach : Math.abs(a - b) <= reach),

    async main(scripts, start) {
      files = scripts;
      try {
        await start();
        await stellanova.wait_for_others();
      } catch (e) {
        report(e);
        if (inNode) process.exitCode = 1;
      }
    },
    meanwhile(f) {
      others.push(Promise.resolve().then(f).catch((e) => { report(e); leave(1); }));
    },
    async wait_for_others() {
      while (others.length) await others.shift();
    },
    async invoke(f, line, ...args) {
      if (!f) fail(line, "there is no command in it yet: set it to one first, like 'set f to the command double'.");
      try {
        return await f(...args);
      } catch (e) {
        if (e instanceof Problem && !e.line) e.line = line;
        throw e;
      }
    },
    async changed_by(items, f, line) {
      const made = [];
      for (const x of items) made.push(dup(await stellanova.invoke(f, line, x)));
      return made;
    },
    async kept_by(items, f, line) {
      const made = [];
      for (const x of items) if (await stellanova.invoke(f, line, x)) made.push(dup(x));
      return made;
    },

    at: (items, number, line) => items[index_of(items, number, line)],
    put_at(items, number, line, v) { items[index_of(items, number, line)] = v; },
    remove_item(items, number, line) { items.splice(index_of(items, number, line), 1); },
    power(a, b, line) {
      const out = Math.pow(a, b);
      if (!Number.isFinite(out)) fail(line, `${text(a)} to the power ${text(b)} can't be worked out (it is too big, or not a real number).`);
      return out;
    },
    bits(op, a, b, line) {
      const limit = 9007199254740992;
      for (const x of [a, b]) if (x !== Math.floor(x) || Math.abs(x) >= limit) fail(line, `bits need whole numbers smaller than 9007199254740992, not ${text(x)}.`);
      const x = BigInt(a), y = BigInt(b);
      if ((op === 3 || op === 4) && (b < 0 || b > 63)) fail(line, `I can shift by 0 to 63 places, not ${b}.`);
      const out = [x & y, x | y, x ^ y, x << y, x >> y][op];
      if (out >= BigInt(limit) || out <= -BigInt(limit)) fail(line, `that makes a number too big for bits (${out}).`);
      return Number(out);
    },
    insert_item(items, number, x, line) { if (number === items.length + 1) items.push(x); else items.splice(index_of(items, number, line), 0, x); },
    remove_value(items, v) {
      const k = items.findIndex((x) => same(x, v));
      if (k >= 0) items.splice(k, 1);
    },
    contains: (a, b) => (typeof a === "string" ? a.includes(b) : a instanceof Map ? a.has(b) : a.some((x) => same(x, b))),
    entry(table, key, line) {
      if (!table.has(key)) fail(line, `there is no entry "${key}" in the table.`);
      return table.get(key);
    },
    put_entry(table, key, v) { table.set(key, v); },
    remove_entry(table, key, line) {
      if (!table.delete(key)) fail(line, `there is no entry "${key}" in the table to remove.`);
    },
    keys: (table) => [...table.keys()].sort(order),
    last(items, line) {
      if (!items.length) fail(line, "the list is empty, so it has no last item.");
      return items[items.length - 1];
    },
    sorted: (items) => [...items].sort(order),
    sorted_by(items, part, line) {
      if (items.includes(undefined)) fail(line, "a list sorted by a part can't hold nothing.");
      return dup(items).sort((a, b) => order(part(a), part(b)));
    },
    able(table, able, what, line, thing, ...rest) {  // 'speak s': the version for whatever kind of thing s is
      if (thing === undefined) fail(line, `this ${able} is nothing, so it can't ${what}.`);
      return table[thing.constructor.title](thing, ...rest);
    },
    something(thing, kind, part, line) {
      if (thing === undefined) fail(line, `this ${kind} is nothing, so it has no ${part}.`);
      return thing;
    },
    reversed: (items) => dup(items).reverse(),
    items_from(items, first, last, line) {
      if (Math.floor(first) !== first || Math.floor(last) !== last || first < 1 || last > items.length || first > last + 1)
        fail(line, `there are no items ${numberText(first)} to ${numberText(last)} in a list of ${items.length} items.`);
      return dup(items.slice(first - 1, last));
    },
    first_of(items, count, line, end = false) {
      if (Math.floor(count) !== count || count < 0)
        fail(line, `I can't take ${numberText(count)} of something: it must be a whole number, 0 or more.`);
      const all = typeof items === "string" ? letters_in(items) : items;
      const part = end ? all.slice(Math.max(0, all.length - count)) : all.slice(0, count);
      return typeof items === "string" ? part.join("") : dup(part);
    },
    last_of(items, count, line) {
      return stellanova.first_of(items, count, line, true);
    },
    unique(items) {
      const out = [];
      for (const x of items) if (!out.some((y) => same(x, y))) out.push(dup(x));
      return out;
    },
    shuffled(items) {
      const out = dup(items);
      for (let k = out.length - 1; k > 0; k--) {
        const j = Math.floor(Math.random() * (k + 1));
        [out[k], out[j]] = [out[j], out[k]];
      }
      return out;
    },
    with_commas(n) {
      let s = numberText(n), sign = "";
      if (s.startsWith("-")) [sign, s] = ["-", s.slice(1)];
      const [whole, ...rest] = s.split(".");
      if (!/^\d+$/.test(whole)) return sign + s;
      return sign + whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",") + (rest.length ? "." + rest.join(".") : "");
    },
    padded(n, digits, line) {
      if (Math.floor(digits) !== digits || digits < 0)
        fail(line, `I can't pad to ${numberText(digits)} digits: it must be a whole number, 0 or more.`);
      let s = numberText(n), sign = "";
      if (s.startsWith("-")) [sign, s] = ["-", s.slice(1)];
      const [whole, ...rest] = s.split(".");
      return sign + whole.padStart(digits, "0") + (rest.length ? "." + rest.join(".") : "");
    },
    sum_of(items) {
      let total = 0;
      for (const x of items) total += x;
      return total;
    },
    average_of(items, line) {
      if (!items.length) fail(line, "the list is empty, so it has no average.");
      return stellanova.sum_of(items) / items.length;
    },
    biggest_of(items, line) {
      if (!items.length) fail(line, "the list is empty, so it has no biggest.");
      return items.reduce((a, b) => (b > a ? b : a));
    },
    smallest_of(items, line) {
      if (!items.length) fail(line, "the list is empty, so it has no smallest.");
      return items.reduce((a, b) => (b < a ? b : a));
    },
    random_fraction: () => Math.random(),
    random(lo, hi, line) {
      const a = Math.ceil(Math.min(lo, hi)), b = Math.floor(Math.max(lo, hi));
      if (a > b) fail(line, `there is no whole number from ${numberText(lo)} to ${numberText(hi)}.`);
      return a + Math.floor(Math.random() * (b - a + 1));
    },
    random_item(items, line) {
      if (!items.length) fail(line, "the list is empty, so I can't pick a random item.");
      return items[Math.floor(Math.random() * items.length)];
    },

    rounded(x, places, line) {
      if (Math.floor(places) !== places || places < 0 || places > 15) fail(line, `I can round to 0 to 15 places, not ${numberText(places)}.`);
      if (!Number.isFinite(x)) return x;
      const scale = 10 ** places; // halves go away from zero, as taught at school
      const r = Math.floor(Math.abs(x) * scale + 0.5) / scale;
      return x < 0 || Object.is(x, -0) ? -r : r;
    },
    to_number(s, line) {
      if (NUMBER_TEXT.test(s)) return Number(s.trim());
      fail(line, `"${s}" is not a number.`);
    },
    lines_of,
    words_of: (s) => s.split(/\s+/).filter(Boolean),
    letters: (s) => letters_in(s).length,
    letter(s, number, line) {
      const all = letters_in(s);
      if (Math.floor(number) !== number || number < 1 || number > all.length)
        fail(line, `there is no letter ${numberText(number)} in text of ${all.length} letters.`);
      return all[number - 1];
    },
    letters_from(s, first, last, line) {
      const all = letters_in(s);
      if (Math.floor(first) !== first || Math.floor(last) !== last || first < 1 || last > all.length || first > last + 1)
        fail(line, `there are no letters ${numberText(first)} to ${numberText(last)} in text of ${all.length} letters.`);
      return all.slice(first - 1, last).join("");
    },
    position(s, part) {
      if (Array.isArray(s)) return s.findIndex((x) => same(x, part)) + 1;
      const at = s.indexOf(part);
      return at < 0 ? 0 : letters_in(s.slice(0, at)).length + 1;
    },
    replace_all(s, from, to, line) {
      if (!from) fail(line, "I can't replace empty text.");
      return s.split(from).join(to);
    },
    split(s, by, line) {
      if (!by) fail(line, "I can't split text by empty text.");
      return s.split(by);
    },
    join: (items, between) => items.map(text).join(between),
    trimmed: (s) => s.replace(/^[ \t\r\n]+|[ \t\r\n]+$/g, ""),
    begins_with: (s, part) => s.startsWith(part),
    ends_with: (s, part) => s.endsWith(part),
    upper: (s) => ascii(s, /[a-z]/g, -32),
    lower: (s) => ascii(s, /[A-Z]/g, 32),

    say(parts) { out(parts.join("")); },
    ask_text,
    ask_yes_no(question) {
      for (;;) {
        const answer = stellanova.lower(ask_text(question).trim());
        if (answer === "yes" || answer === "y") return true;
        if (answer === "no" || answer === "n") return false;
        out("Please type yes or no.");
      }
    },
    ask_number(question) {
      for (;;) {
        const answer = ask_text(question);
        if (NUMBER_TEXT.test(answer)) return Number(answer.trim());
        out("Please type a number.");
      }
    },

    saved_text: (v, line, kind) => saved(v, line, kind),
    able_kinds(able, names) { kinds[able].able = names; },
    load_text(data, kind, kindName, line) {
      const v = reading(data, kind);
      if (v === NotSaved) fail(line, `the text doesn't hold ${kindName}.`);
      return v;
    },
    load_file(path, kind, kindName, line) {
      const v = reading(read_file(path, line), kind);
      if (v === NotSaved) fail(line, `the file "${path}" doesn't hold ${kindName}.`);
      return v;
    },
    save_file(v, path, line, kind) { stellanova.write_file(path, saved(v, line, kind) + "\n", line); },
    file_exists(path) {
      try {
        return !!fs && fs.statSync(path).isFile();
      } catch {
        return false;
      }
    },
    read_file,
    read_lines: (path, line) => lines_of(read_file(path, line)),
    write_file(path, s, line) {
      need_files(line);
      try {
        fs.writeFileSync(path, s);
      } catch {
        fail(line, `I couldn't write the file "${path}".`);
      }
    },
    add_line(path, s, line) {
      need_files(line);
      try {
        fs.appendFileSync(path, s + "\n");
      } catch {
        fail(line, `I couldn't add to the file "${path}".`);
      }
    },
    leave,
  };

  const runtime = { stellanova, FMath, FVector, FVector2D };
  globalThis.stellanova = runtime;
  if (typeof module !== "undefined") module.exports = runtime;
})();
