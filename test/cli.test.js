// Tests for the agent-agnostic npm CLI (bin/cli.js). Run: node --test test/
// Uses only Node built-ins (node:test, node:assert) — zero dependencies.
const { test } = require("node:test");
const assert = require("node:assert");
const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const CLI = path.join(__dirname, "..", "bin", "cli.js");

function run(args, env) {
  return spawnSync(process.execPath, [CLI, ...args], {
    encoding: "utf8",
    env: { ...process.env, ...(env || {}) },
  });
}

test("--version prints the package version", () => {
  const pkg = require(path.join(__dirname, "..", "package.json"));
  const r = run(["--version"]);
  assert.strictEqual(r.status, 0);
  assert.strictEqual(r.stdout.trim(), pkg.version);
});

test("--help lists pipeline commands", () => {
  const r = run(["--help"]);
  assert.strictEqual(r.status, 0);
  for (const c of ["install", "capture", "redact", "check", "verify"]) {
    assert.ok(r.stdout.includes(c), `help should mention ${c}`);
  }
});

test("unknown command exits 2", () => {
  const r = run(["definitely-not-a-command"]);
  assert.strictEqual(r.status, 2);
});

test("install copies the skill into a Claude skills dir (agent-agnostic)", () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), "cliproof-home-"));
  const r = run(["install", "--only", "claude", "--force"], {
    HOME: home,
    USERPROFILE: home, // Windows homedir source
  });
  assert.strictEqual(r.status, 0, r.stderr);
  const installed = path.join(home, ".claude", "skills", "cliproof", "SKILL.md");
  assert.ok(fs.existsSync(installed), "SKILL.md should be installed under ~/.claude/skills/cliproof");
  // bundled scripts come along too
  assert.ok(fs.existsSync(path.join(home, ".claude", "skills", "cliproof", "scripts", "redact.py")));
  fs.rmSync(home, { recursive: true, force: true });
});

test("install --dry-run writes nothing", () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), "cliproof-home-"));
  const r = run(["install", "--only", "claude", "--dry-run"], { HOME: home, USERPROFILE: home });
  assert.strictEqual(r.status, 0);
  assert.ok(!fs.existsSync(path.join(home, ".claude", "skills", "cliproof")),
    "dry-run must not create files");
  fs.rmSync(home, { recursive: true, force: true });
});
