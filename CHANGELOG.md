# Changelog

All notable changes to cliproof are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-06-10

### Added
- MCP server (`cliproof mcp`): stdio JSON-RPC 2.0 server exposing 11 cliproof tools — any MCP-compatible agent (Claude Code, Cursor, Windsurf, LangChain, CrewAI, AutoGen) can call cliproof natively
- Python library (`pip install cliproof`): `capture()`, `redact()`, `embed()`, `check()`, `health()`, `guard()` with typed return objects and exceptions
- Docker image (`ghcr.io/aks-builds/cliproof`): Alpine + Python 3.12 + freeze@0.2.2 + gifsicle, health gate at container start, multi-arch amd64/arm64
- HTTP daemon (`cliproof serve`): stdlib REST API on localhost:7070 for IDE extensions and polyglot callers
- `.mcp.json` example for one-line Claude Code / Cursor wiring

## [0.2.0] - 2026-06-10

### Added
- JSON contract kernel: `--json` flag on all 13 scripts emits structured `{ ok, step, outputs, ... }` to stdout
- `--timeout` flag on all scripts; hard timeouts with exit code 4 — no hangs ever
- Stable exit code contract: 0 success, 3 secret, 4 timeout, 5 unsafe, 6 drift
- Multi-renderer fallback chain in `capture.py`: freeze (tier 1) → silicon (tier 2) → text-SVG stub (tier 4)
- `health.py` — first-class health probe; `preflight.py` kept as deprecation alias
- 6 new themes: catppuccin, tokyo-night, one-dark, dracula, solarized, rose-pine
- `annotate.py`: `--badge pass/fail`, `--stamp`, `--ci-ribbon` SVG overlay layers
- `check.py`: `gif` block support in proof.json (speed, loop, freeze_last, max_kb)
- `bin/cli.js`: `themes list` subcommand, `health` passthrough

### Changed
- README tagline: "Your README should show it works — not just say it."
- README: broader hero copy, "Who it's for" section, updated install heading
- `guard.py` exit code for unsafe: 5 (was 2; 2 is now reserved for unknown command)
- `check.py` exit code for drift: 6 (was 1)

### Changed
- **Renamed the project `proofshot` → `cliproof`.** The previous name collided
  with an established npm package and GitHub repo (`AmElmo/proofshot`) that also
  installs to `~/.claude/skills/proofshot/`, which would clobber this skill on
  disk. `cliproof` is verified free on npm and GitHub. Install is now
  `/plugin marketplace add aks-builds/cliproof` then `/plugin install cliproof@cliproof`;
  the embed marker is `<!-- cliproof:start -->`.

### Added
- **Agent-agnostic npm CLI** (`npm i -g cliproof`) — `bin/cli.js` (zero deps):
  `cliproof install` copies the skill into Claude Code, Cursor, Codex, OpenCode,
  Gemini CLI, and Windsurf; `cliproof <cmd>` passes through to the Python
  pipeline; `cliproof doctor` reports capabilities.
- **Determinism + freshness check** — `scripts/normalize.py` neutralises volatile
  tokens (durations, timestamps, UUIDs, hashes, temp paths, ports) and
  `scripts/check.py` re-runs proof commands listed in `.cliproof/proof.json`,
  failing on real drift. Reusable composite action `.github/actions/cliproof-check`
  and a `freshness.yml` workflow keep README proofs honest in CI.
- **`scripts/verify.py`** — runs a command and judges PASS/FAIL from the exit code
  plus error signatures across 10+ languages; emits a PR-ready Markdown report.
- **`scripts/suggest.py`** — scans a repo (package.json/Makefile/pyproject/--help/
  README quickstart) and ranks the best "proof it runs" commands.
- **`scripts/storyboard.py`** — stitches multiple SVG captures into one vertical
  session image; **`scripts/annotate.py`** adds a caption bar (frame only).
- **`scripts/pr.py`** — posts the screenshot + verify verdict as a GitHub PR comment.
- **Theme presets** — `capture.py --preset macos|github-dark|nord|iterm|win11`.
- **Custom redaction policy** — `redact.py` loads `.cliproof/redact.json`
  (`patterns` + `allow`) to add project secret patterns and exempt false positives.
- **Test coverage for every advertised capability** — Node tests for the
  agent-agnostic `install`/CLI (`test/cli.test.js`, run in CI), a guard test
  asserting the scripts import only stdlib and no network modules
  (`test_no_dependencies.py`), multi-language `verify` signature tests, and an
  `integration.yml` workflow that installs real `freeze` and runs
  capture → redact → embed → check end-to-end on Linux (plus a best-effort real
  `vhs` GIF). 114 pytest + 5 Node tests.
- **Release automation** — `release.yml` (dispatch → bump → sync npm + Claude
  marketplace manifests → release PR → auto-merge) and `publish.yml`
  (npm publish with provenance + tag + GitHub release). Requires `NPM_TOKEN` and
  `RELEASE_PR_PAT` secrets.
- **`scripts/capture.py`** — reliable wrapper around `freeze`: launches it with
  stdin closed, forces `--language ansi` for `--execute`, and captures to SVG.
  All `freeze` style flags pass through. This is now the recommended way to
  capture (use it instead of calling `freeze` directly).
- **`scripts/rasterize.py`** — converts a (redacted) SVG to PNG using the first
  available local renderer (Chromium browser → `resvg` → `rsvg-convert` →
  `inkscape` → `magick`), loading the SVG file directly. Retina (`--scale 2`)
  by default; `--renderer` to force one.
- `preflight.py` now reports SVG→PNG rasterize availability.
- Tests for `capture.py` and `rasterize.py`.

### Fixed
- **`freeze` hangs** when launched with an inherited non-tty stdin (every
  agent/CI shell). `capture.py` closes stdin (`subprocess.DEVNULL`); docs show
  the manual `< /dev/null` / `cmd /c "… < NUL"` equivalents.
- **`freeze` PNG/WebP rasterizer can crash** on some Windows machines (Go
  `0xc0000005`). The pipeline now captures SVG and rasterizes separately via
  `rasterize.py`, so PNG no longer depends on `freeze`'s wasm rasterizer.
- **`--execute` "Language Unknown"** error — `capture.py` injects `--language ansi`.
- **UTF-8 mojibake** (`Â`, `â€"`) from re-encoding the SVG — renderers now read
  the `.svg` file directly; docs warn about cp1252 defaults (PowerShell).
- **UTF-8 BOM handling** — all scripts that read text now use `utf-8-sig` (strips
  a leading BOM) and write plain `utf-8` (never adds one), so a BOM'd input
  (Notepad/VS Code) can't break SVG parsing or README frontmatter. `capture.py`
  also strips a BOM from `freeze`'s output defensively.
- **Line endings** — `redact.py`/`embed.py` write `newline="\n"`, so editing a
  file on Windows no longer silently rewrites it with CRLF.

### Changed
- Docs (`SKILL.md`, `references/tooling.md`, `README.md`) route captures through
  `capture.py`/`rasterize.py`, drop the "PNG works natively everywhere" claim,
  and add a per-failure-mode reliability table plus a "view the rendered image"
  verification step.

## [0.1.0] - 2026-06-05

Initial public release.

### Added
- **Agent Skill** (`skills/cliproof/SKILL.md` + `references/`) that captures a
  real CLI command and its real output as a styled screenshot (Charm `freeze`)
  or animated GIF (`vhs`) and embeds it into `README.md` as proof-it-runs
  evidence. macOS/iOS and Windows-terminal style presets.
- **Plugin packaging** — `.claude-plugin/plugin.json` and a self-hosted
  `.claude-plugin/marketplace.json`, installable via
  `/plugin marketplace add aks-builds/cliproof` then
  `/plugin install cliproof@cliproof`.
- **Enforced security gates** (pure stdlib, no network):
  - `scripts/guard.py` — refuses to capture destructive/exfiltration commands.
  - `scripts/redact.py` — masks secrets (keys, tokens, JWTs, private keys) and
    normalises personal data (emails, private IPs, home paths) before embedding.
  - `scripts/embed.py` — idempotent, marker-based README inserts with diff + backup.
  - `scripts/preflight.py` — reports OS + available capture modes and install hints.
- **Tooling reference** with version-pinned `freeze`/`vhs`, full flag/tape
  reference, and cross-platform (Windows/macOS/Linux/WSL) notes.
- **Quality + governance** — pytest suite (manifest validation + script tests),
  CI on Python 3.10–3.12, CodeQL security analysis, Dependabot, issue/PR
  templates, and full governance docs.
