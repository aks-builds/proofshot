#!/usr/bin/env node
"use strict";
/*
 * cliproof — agent-agnostic CLI.
 *
 * Two jobs:
 *   1. `cliproof install`  — copy the skill into the skills dir of every AI
 *      coding agent on this machine (Claude Code, Cursor, Codex, OpenCode,
 *      Gemini CLI, Windsurf). User-level, works across all projects.
 *   2. passthrough        — `cliproof <preflight|guard|capture|redact|embed|
 *      check|suggest|verify|storyboard|annotate|pr> ...` runs the bundled
 *      Python script. The capture pipeline is pure Python (stdlib).
 *
 * Zero npm dependencies. Requires Python 3.8+ on PATH for the pipeline
 * commands (not for `install`).
 */
const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawnSync } = require("child_process");

const ROOT = path.resolve(__dirname, "..");
const SKILL_DIR = path.join(ROOT, "skills", "cliproof");
const SCRIPTS = path.join(SKILL_DIR, "scripts");
const VERSION = require(path.join(ROOT, "package.json")).version;

const PASSTHROUGH = ["preflight", "guard", "capture", "redact", "embed",
  "check", "suggest", "verify", "storyboard", "annotate", "pr", "health"];

const HOME = os.homedir();
// name -> how to install. kind 'dir' copies the skill folder; 'file' writes
// SKILL.md to a path; 'append' appends a pointer line to an existing rules file.
const AGENTS = {
  claude:   { base: path.join(HOME, ".claude"),  kind: "dir",  dest: path.join(HOME, ".claude", "skills", "cliproof") },
  codex:    { base: path.join(HOME, ".codex"),   kind: "dir",  dest: path.join(HOME, ".codex", "skills", "cliproof") },
  opencode: { base: path.join(HOME, ".config", "opencode"), kind: "dir", dest: path.join(HOME, ".config", "opencode", "skills", "cliproof") },
  cursor:   { base: path.join(HOME, ".cursor"),  kind: "file", dest: path.join(HOME, ".cursor", "rules", "cliproof.mdc") },
  gemini:   { base: path.join(HOME, ".gemini"),  kind: "append", dest: path.join(HOME, ".gemini", "GEMINI.md") },
  windsurf: { base: path.join(HOME, ".codeium", "windsurf"), kind: "append", dest: path.join(HOME, ".codeium", "windsurf", "memories", "global_rules.md") },
};

function findPython() {
  for (const cmd of ["python3", "python"]) {
    const r = spawnSync(cmd, ["--version"], { encoding: "utf8" });
    if (r.status === 0) return cmd;
  }
  return null;
}

function ensureDir(p) { fs.mkdirSync(p, { recursive: true }); }

function installAgent(name, opts) {
  const a = AGENTS[name];
  const detected = fs.existsSync(a.base);
  if (!opts.force && !detected && !opts.only) return { name, status: "skipped (not detected)" };
  if (opts.dryRun) return { name, status: `would install -> ${a.dest}` };

  if (a.kind === "dir") {
    if (fs.existsSync(a.dest) && !opts.force) return { name, status: "exists (use --force)" };
    ensureDir(path.dirname(a.dest));
    fs.cpSync(SKILL_DIR, a.dest, { recursive: true });
    return { name, status: `installed -> ${a.dest}` };
  }
  if (a.kind === "file") {
    ensureDir(path.dirname(a.dest));
    fs.copyFileSync(path.join(SKILL_DIR, "SKILL.md"), a.dest);
    return { name, status: `installed -> ${a.dest}` };
  }
  // append a pointer (idempotent)
  ensureDir(path.dirname(a.dest));
  const marker = "<!-- cliproof -->";
  const pointer = `\n${marker}\nWhen asked to capture a terminal screenshot / README "proof it runs" image, follow the cliproof skill at ${SKILL_DIR}/SKILL.md.\n`;
  const cur = fs.existsSync(a.dest) ? fs.readFileSync(a.dest, "utf8") : "";
  if (cur.includes(marker)) return { name, status: "already referenced" };
  fs.writeFileSync(a.dest, cur + pointer);
  return { name, status: `pointer added -> ${a.dest}` };
}

function cmdInstall(argv) {
  const opts = { force: false, dryRun: false, only: null, skip: [] };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--force") opts.force = true;
    else if (argv[i] === "--dry-run") opts.dryRun = true;
    else if (argv[i] === "--only") opts.only = (argv[++i] || "").split(",").filter(Boolean);
    else if (argv[i] === "--skip") opts.skip = (argv[++i] || "").split(",").filter(Boolean);
  }
  let names = Object.keys(AGENTS);
  if (opts.only) names = names.filter((n) => opts.only.includes(n));
  names = names.filter((n) => !opts.skip.includes(n));

  console.log(`cliproof v${VERSION} — installing skill (user level)\n`);
  let any = false;
  for (const n of names) {
    const r = installAgent(n, { ...opts, only: opts.only && opts.only.includes(n) });
    if (!r.status.startsWith("skipped")) any = true;
    console.log(`  ${n.padEnd(9)} ${r.status}`);
  }
  if (!any && !opts.only) {
    console.log("\n  No agents detected. Re-run with --only claude (or another agent) to force.");
  }
  console.log("\nDone. In your agent, ask: \"screenshot <command> for the README\".");
  return 0;
}

function cmdDoctor() {
  const py = findPython();
  console.log(`cliproof v${VERSION}`);
  console.log(`  node:   ${process.version}`);
  console.log(`  python: ${py || "NOT FOUND (needed for capture commands)"}`);
  console.log(`  skill:  ${SKILL_DIR}`);
  if (py) {
    console.log("");
    return runPython(py, "preflight", []);
  }
  return 0;
}

function runPython(py, script, args) {
  const r = spawnSync(py, [path.join(SCRIPTS, `${script}.py`), ...args], { stdio: "inherit" });
  return r.status === null ? 1 : r.status;
}

function usage() {
  console.log(`cliproof v${VERSION} — prove your CLI actually works.

Usage:
  cliproof install [--only a,b] [--skip x] [--force] [--dry-run]
  cliproof doctor
  cliproof <command> [args...]      run a pipeline step

Pipeline commands (require Python 3.8+):
  ${PASSTHROUGH.join(", ")}

Examples:
  cliproof install
  cliproof suggest .
  cliproof guard -- "mytool --help"
  cliproof check
`);
}

function cmdThemes(argv) {
  const sub = argv[0];
  if (!sub || sub === "list") {
    const builtin = ["macos", "github-dark", "nord", "iterm", "win11"];
    const themesDir = path.join(ROOT, "skills", "cliproof", "themes");
    let fileBased = [];
    try {
      fileBased = fs.readdirSync(themesDir)
        .filter(f => f.endsWith(".json"))
        .map(f => f.replace(".json", ""));
    } catch (_) {}
    const all = [...new Set([...builtin, ...fileBased])].sort();
    console.log("Available themes (" + all.length + "):");
    all.forEach(t => console.log("  " + t));
    return 0;
  }
  console.error("cliproof themes: unknown subcommand '" + sub + "'. Try: list");
  return 2;
}

function main() {
  const argv = process.argv.slice(2);
  const cmd = argv[0];
  if (!cmd || cmd === "-h" || cmd === "--help") { usage(); return 0; }
  if (cmd === "-v" || cmd === "--version") { console.log(VERSION); return 0; }
  if (cmd === "install") return cmdInstall(argv.slice(1));
  if (cmd === "doctor") return cmdDoctor();
  if (cmd === "themes") return cmdThemes(argv.slice(1));
  if (cmd === "mcp") {
    const py = findPython();
    if (!py) { console.error("cliproof: Python 3.8+ not found on PATH."); return 1; }
    return runPython(py, "mcp_server", argv.slice(1));
  }
  if (cmd === "serve") {
    const py = findPython();
    if (!py) { console.error("cliproof: Python 3.8+ not found on PATH."); return 1; }
    return runPython(py, "serve", argv.slice(1));
  }
  if (PASSTHROUGH.includes(cmd)) {
    const py = findPython();
    if (!py) { console.error("cliproof: Python 3.8+ not found on PATH (needed for this command)."); return 1; }
    return runPython(py, cmd, argv.slice(1));
  }
  console.error(`cliproof: unknown command '${cmd}'. Run 'cliproof --help'.`);
  return 2;
}

process.exit(main());
