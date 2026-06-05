---
name: cliproof
description: Capture a real terminal command and its real output as a polished screenshot or animated GIF, then embed it into README.md as "proof it runs" evidence for GitHub visitors. Use when the user wants a terminal screenshot, CLI demo, README demo GIF, a styled (macOS/iOS or Windows) terminal image of a program/service/build, to "show the command output", or any visual proof that a product actually ships and works. Captures genuine output (never fabricated), redacts secrets, and inserts idempotently.
---

# Cliproof — prove your CLI actually runs

Turn a **real** command and its **real** output into a styled terminal image (or animated GIF) and embed it into `README.md`, so GitHub visitors get instant confidence the project works. The whole value is honesty: cliproof captures genuine execution, never a mock-up.

## When to use
- Capture a screenshot of a command + its output in a styled terminal (macOS/iOS traffic-light bar, Windows-style chrome, or a theme).
- Record an animated terminal demo (typing + live output) as a GIF.
- Add visual "proof it works" evidence to a `README.md`, docs page, or release notes.

## Core principles (do not violate)
1. **Never fabricate output.** Always run the real command and capture what actually happens. A faked screenshot is worse than none.
2. **Redact secrets before anything is written to disk or the README.** This is enforced by `scripts/redact.py`, not left to judgement.
3. **Guard the command before executing it.** Run it past `scripts/guard.py`; never capture a destructive or clearly unsafe command.
4. **Confirm before installing tools, before writing README.md, and before committing.**
5. **Stay local.** Cliproof never transmits captured output anywhere. It only reads/writes files in the user's repo.

## The two capture tools
cliproof uses [Charm](https://charm.sh) CLIs that run a real command in a pseudo-terminal and capture genuine ANSI output.

| Need | Tool | Output | Platforms |
|---|---|---|---|
| **Static screenshot** (default) | `freeze` | PNG / SVG / WebP | Native on Windows, macOS, Linux |
| **Animated demo** | `vhs` | GIF / MP4 / WebM / PNG frames | macOS / Linux / WSL (needs `ffmpeg` + `ttyd`; no native Windows `ttyd`) |

Default to **static** (`freeze`). Use `vhs` only when the user explicitly wants animation/a GIF.

## Workflow

### 1. Preflight — know what's possible on this machine
```bash
python skills/cliproof/scripts/preflight.py
```
It reports the OS, which tools are installed (`freeze`/`vhs`/`ffmpeg`/`ttyd`/`go`), and what capture modes are available. Use its output to decide static vs. animated and whether an install is needed. (Paths below are relative to the skill directory; when installed as a plugin, prefix with `${CLAUDE_PLUGIN_ROOT}/skills/cliproof/` if a bare path is not found.)

### 2. Choose the command to capture
Ask the user (or infer from the repo) which command best demonstrates the product working. Prefer commands that:
- finish quickly and deterministically (no hanging, no required interaction),
- produce self-evidently "working" output (success messages, results, version banners, passing tests),
- contain no secrets.

For long-running/interactive programs, suggest a short non-interactive variant, or use `vhs` with scripted `Sleep`/`Enter`.

### 3. Guard the command (security gate)
```bash
python skills/cliproof/scripts/guard.py -- "<the exact command>"
```
- Exit `0` → safe to proceed.
- Exit `2` → flagged as risky (matches a destructive/exfiltration pattern). **Stop and show the user the warning; do not run it** unless they explicitly override and you understand why it's safe.

### 4. Install the capture tool only if needed (with confirmation)
If preflight shows the tool is missing, ask the user before installing. See `references/tooling.md` for the full install matrix. Prefer a pinned version and an official source:
- `freeze`: `go install github.com/charmbracelet/freeze@v0.2.2` · `brew install charmbracelet/tap/freeze` · `scoop install freeze`
- `vhs`: `brew install vhs` (+ `ffmpeg` + `ttyd`); on Windows use WSL.

Install **locally**, never globally beyond the user's own toolchain. If install is declined, go to step 8 (fallback).

### 5. Capture to SVG via `capture.py` (don't call `freeze` directly)
Create `.github/media/` if absent. Use a descriptive kebab-case name (`cli-help`, `build-passing`).
`capture.py` wraps `freeze` and applies three fixes that otherwise break captures in agent/CI shells: it **closes stdin** (raw `freeze` *hangs* on an inherited pipe), captures to **SVG** (avoids `freeze`'s PNG rasterizer, which can *crash* on Windows, and keeps the output redactable), and forces `--language ansi`. All `freeze` style flags pass straight through.

**macOS/iOS window look (default):**
```bash
python skills/cliproof/scripts/capture.py --execute "<command>" \
  --window --theme "dracula" --background "#0d1117" \
  --padding 24 --margin 20 \
  --border.radius 8 --border.width 1 --border.color "#30363d" \
  --shadow.blur 24 --shadow.y 12 \
  --font.family "JetBrains Mono" --font.size 14 \
  -o ".github/media/<name>.svg"
```
For a **Windows-terminal look**: drop `--window`, use `--background "#0c0c0c"`, square corners (`--border.radius 0`). Full flag reference, style presets, and the per-failure-mode reliability table are in `references/tooling.md`.

On Windows, wrap shell built-ins: `--execute "powershell -NoProfile -Command \"<cmd>\""` or `--execute "cmd /c <cmd>"`. Prefer running the real project binary directly.

**Animated GIF (vhs):**
```bash
cp skills/cliproof/assets/demo.tape.template .github/media/demo.tape
# edit the Type/Enter/Sleep lines to run the real command(s)
vhs .github/media/demo.tape   # writes .github/media/demo.gif
```
The template uses `Set WindowBar Colorful` for the macOS/iOS bar.

### 6. Redact secrets (mandatory gate before embedding)
`capture.py` gave you SVG (text), so scan it directly:
```bash
python skills/cliproof/scripts/redact.py .github/media/<name>.svg --in-place
```
You can also pre-screen the raw output before capturing at all:
```bash
<command> 2>&1 | python skills/cliproof/scripts/redact.py -
```
If `redact.py` reports findings (exit `3`), the output contains likely secrets (API keys, tokens, passwords, JWTs, private IPs, home paths). **Do not embed it.** Re-run with sanitized env/args, or have the user confirm each finding is a false positive. Never commit an image you have not screened. **Always redact before rasterizing** (step 6b) — the PNG is a snapshot and cannot be re-scanned.

### 6b. Rasterize to PNG if needed, then look at it
SVG embeds fine on GitHub, so this is optional — do it when you specifically need a raster (social previews, non-GitHub renderers):
```bash
python skills/cliproof/scripts/rasterize.py .github/media/<name>.svg -o .github/media/<name>.png
```
It uses a local renderer (Chromium browser → resvg → rsvg-convert → inkscape → magick); if none exists, embed the SVG. **Then open the rendered image and look at it** — confirm the text, encoding (no `Â`/`â€"` mojibake), and alignment are right. A non-empty file is *not* proof it rendered correctly; this visual check is what catches a corrupt capture.

### 7. Embed into README.md (idempotent, with confirmation)
Use the helper so re-runs update in place instead of duplicating:
```bash
python skills/cliproof/scripts/embed.py README.md \
  --image ".github/media/<name>.png" \
  --alt "<command> running successfully" \
  --id "<name>" \
  --heading "Demo"
```
It maintains a marked block:
```html
<!-- cliproof:start id=<name> -->
![alt](.github/media/<name>.png)
<!-- cliproof:end id=<name> -->
```
Re-running with the same `--id` replaces that block; a new `--id` adds another. **Show the user the diff and get approval before writing.** Place hero shots high (right after the title/description or under a `## Demo` heading). If there is no `README.md`, offer to create one. Use repo-relative paths so images render on GitHub.

### 8. Fallback (no install possible)
- Run the command, capture raw output, pipe through `redact.py`, and embed it in a fenced code block as a labelled text stopgap (clearly: text, not an image).
- Or suggest a lighter tool the user may have (`termshot`, `carbon-now-cli`, `silicon`) or a manual OS screenshot.

## More capabilities (use when relevant)
- **Pick the command** — `python scripts/suggest.py <repo>` scans `package.json`, `Makefile`, `pyproject`, `--help`, and the README quickstart and ranks the best "proof it runs" commands. Use it when the user hasn't named a command.
- **Themes in one flag** — `capture.py --preset macos|github-dark|nord|iterm|win11` expands to a full styled look (user flags still override).
- **Verify pass/fail** — `python scripts/verify.py --command "<cmd>" --report verify.md` runs the command and judges PASS/FAIL from the exit code + error signatures across 10+ languages. Use for "prove the tests/build pass" and to attach a verdict.
- **Keep proofs fresh** — record `python scripts/check.py --update` (writes a normalised baseline next to the image) and list each proof in `.cliproof/proof.json`. `check.py` (no args) re-runs commands and fails on drift; wire the reusable action `.github/actions/cliproof-check` into CI so the README never lies. `normalize.py` neutralises volatile tokens (durations, timestamps, paths, ports) so only real drift fails.
- **Custom redaction** — drop a `.cliproof/redact.json` (`{"patterns": [...], "allow": [...]}`) to add project secret patterns and exempt false positives; `redact.py` loads it automatically.
- **Storyboard** — `python scripts/storyboard.py -o session.svg a.svg b.svg c.svg` stitches a command sequence into one image.
- **Caption** — `python scripts/annotate.py in.svg --caption "all 42 tests pass" -o out.svg` adds a labelled bar (frame only; never edits the captured text).
- **Proof to a PR** — `python scripts/pr.py --pr <n> --image-url <raw-url> --verify verify.md` posts the screenshot + verdict as a PR comment (needs `gh`).

## Guardrails recap
- Real output only · secrets redacted (enforced) · command guarded · local-only · confirm installs/writes/commits · don't pass off failing commands as "proof it works" unless the user wants an error-state shot · keep images reasonably sized.

## Reference files
- `references/tooling.md` — install matrix, full `freeze`/`vhs` flag and tape reference, macOS vs Windows style presets, cross-platform notes.
- `references/security.md` — threat model, what each script does, redaction patterns, command-guard rationale, supply-chain notes.
- `scripts/` (all pure Python stdlib, no network, auditable; run with `--help`):
  `preflight` · `guard` · `capture` · `redact` · `rasterize` · `embed` ·
  `normalize` · `check` · `suggest` · `verify` · `storyboard` · `annotate` · `pr`.
- `assets/demo.tape.template` — ready-to-edit VHS tape for an animated GIF.
- `.cliproof/proof.json` (freshness manifest) and `.cliproof/redact.json` (redaction policy) live at the repo root, not in the skill dir.
