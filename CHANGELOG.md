# Changelog

All notable changes to cliproof are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- **Renamed the project `proofshot` → `cliproof`.** The previous name collided
  with an established npm package and GitHub repo (`AmElmo/proofshot`) that also
  installs to `~/.claude/skills/proofshot/`, which would clobber this skill on
  disk. `cliproof` is verified free on npm and GitHub. Install is now
  `/plugin marketplace add aks-builds/cliproof` then `/plugin install cliproof@cliproof`;
  the embed marker is `<!-- cliproof:start -->`.

### Added
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
