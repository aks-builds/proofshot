# Tooling reference: `freeze` and `vhs`

Both are [Charm](https://charm.sh) CLIs that run a real command in a pseudo-terminal and capture genuine ANSI output. proofshot pins to known-good versions for deterministic results.

Pinned versions (bump deliberately, test, then update here):
- `freeze` — `v0.2.2`
- `vhs` — `v0.10.0`

---

## `freeze` — static terminal screenshots (default)

Single self-contained Go binary that runs on Windows, macOS, and Linux. It emits **SVG** natively and can *also* rasterize to PNG/WebP — but its PNG/WebP path uses a bundled wasm rasterizer that **can crash on some Windows machines**, and `freeze` **hangs** when launched with an inherited (non-tty) stdin, which is exactly what an agent/CI shell provides. proofshot therefore drives `freeze` through `scripts/capture.py`, which closes stdin and captures to SVG; PNG is produced afterwards by `scripts/rasterize.py`. See **Reliability** below.

### Install
| Method | Command |
|---|---|
| Go | `go install github.com/charmbracelet/freeze@v0.2.2` |
| Homebrew | `brew install charmbracelet/tap/freeze` |
| Scoop (Windows) | `scoop bucket add charm https://github.com/charmbracelet/scoop-bucket` then `scoop install freeze` |
| Arch | `pacman -S freeze` |
| Release binary | https://github.com/charmbracelet/freeze/releases |

### Two modes
- **Capture a command's output** (what proofshot uses): `freeze --execute "ls -la" -o out.svg`
- **Capture a file** (syntax-highlighted code): `freeze main.go -o code.svg`

> Run captures through `capture.py` rather than calling `freeze` directly — it
> applies the stdin/SVG/encoding fixes for you (see **Reliability**).

### Key flags
| Flag | Purpose |
|---|---|
| `--execute "<cmd>"` | Run the command in a pty and capture its real output |
| `--execute.timeout 10s` | Kill the command after a timeout (keep captures deterministic) |
| `-o, --output <file>` | Output path; format inferred from extension (`.png`, `.svg`, `.webp`) |
| `--window` | macOS/iOS-style title bar with red/yellow/green traffic lights |
| `--theme <name>` | Color theme (`dracula`, `github`, `nord`, `catppuccin-mocha`, …) |
| `--background <hex>` | Terminal background, e.g. `#0d1117` |
| `--padding T,R,B,L` / `--margin T,R,B,L` | Inner padding / outer margin (shadow falls in the margin) |
| `--border.radius <n>` | Rounded corners (0 = square, Windows-terminal look) |
| `--border.width <n>` / `--border.color <hex>` | Border |
| `--shadow.blur <n>` / `--shadow.x <n>` / `--shadow.y <n>` | Drop shadow |
| `--font.family "<name>"` / `--font.size <n>` / `--line-height <n>` | Typography |
| `--width <n>` / `--height <n>` | Force dimensions (tame wide/tall output) |
| `--config full` | Print a full config to save and reuse via `--config <file.json>` |

### Style presets

These flags pass straight through `capture.py` (which writes `.svg`); the same
flags also work on raw `freeze` if you add the stdin redirect from **Reliability**.

**macOS / iOS look** (rounded, traffic lights, soft shadow):
```bash
python scripts/capture.py --execute "<cmd>" --window --theme dracula \
  --background "#0d1117" --padding 24 --margin 20 \
  --border.radius 8 --shadow.blur 24 --shadow.y 12 \
  --font.family "JetBrains Mono" --font.size 14 \
  -o .github/media/<name>.svg
```

**Windows-terminal look** (square, flat, no traffic lights):
```bash
python scripts/capture.py --execute "<cmd>" --theme github \
  --background "#0c0c0c" --padding 20 --margin 12 \
  --border.radius 0 --border.width 1 --border.color "#3a3a3a" \
  --font.family "Cascadia Code" --font.size 14 \
  -o .github/media/<name>.svg
```

### SVG-first capture (the proofshot pipeline)
SVG is text, so it can be scanned by `redact.py`, it renders on GitHub as-is, and
it sidesteps the PNG rasterizer entirely. Capture → redact → (optionally) rasterize:
```bash
# 1. capture: wraps freeze with stdin closed + --language ansi; always writes SVG.
#    All freeze style flags pass straight through.
python scripts/capture.py --execute "<cmd>" --window --theme dracula \
  --background "#0d1117" --padding 24 --margin 20 --border.radius 8 \
  --font.family "JetBrains Mono" --font.size 14 \
  -o .github/media/<name>.svg

# 2. redact BEFORE rasterizing, so the PNG reflects the redactions.
python scripts/redact.py .github/media/<name>.svg --in-place

# 3. optional: rasterize the redacted SVG to PNG (retina by default).
python scripts/rasterize.py .github/media/<name>.svg -o .github/media/<name>.png
```
Embed the `.svg` directly (GitHub renders it) or the `.png` from step 3.

### Reliability (non-interactive shells, Windows)
These are real failure modes of `freeze` v0.2.2 that `capture.py`/`rasterize.py`
handle. If you must call `freeze` by hand, apply them yourself:

| Symptom | Cause | Fix |
|---|---|---|
| `freeze` **hangs forever**, no output | It blocks probing an inherited non-tty stdin (agent/CI shells) | Close stdin: `freeze … < /dev/null` (POSIX) or `cmd /c "freeze … < NUL"` (Windows). `capture.py` does this via `subprocess.DEVNULL`. |
| PNG/WebP output **crashes** (Go `0xc0000005` / panic) | Bundled wasm rasterizer faults on some Windows setups | Output `.svg`, then `rasterize.py` (browser/resvg/rsvg/inkscape/magick). |
| `--execute` errors **"Language Unknown"** | No lexer chosen for the captured output | Add `--language ansi`. `capture.py` injects it for `--execute`. |
| Text shows `Â`/`â€"` mojibake | SVG re-read with the wrong encoding (e.g. PowerShell `Get-Content` defaults to cp1252) | Read/write UTF-8 explicitly, or let the renderer load the `.svg` file directly (what `rasterize.py` does). |
| Stray glyph / broken parse from a **UTF-8 BOM** at the start of a file | A BOM'd input (Notepad/VS Code) is read as a literal `﻿` and re-emitted | Read with `utf-8-sig` (strips a BOM), write plain `utf-8` (never adds one). `capture.py`/`redact.py`/`embed.py`/`rasterize.py` all do this; `capture.py` also strips a BOM from freeze's output defensively. |

### `rasterize.py` — SVG → PNG renderers
Tries, in order: a Chromium-family browser (Chrome/Edge/Chromium — best fidelity
for `freeze`'s embedded web font), then `resvg`, `rsvg-convert`, `inkscape`,
`magick`. Force one with `--renderer chrome|resvg|…`; set density with `--scale`
(default `2` = retina). If none is installed, just embed the SVG.

### Windows command-wrapping
- Plain executables work directly: `--execute "myapp --help"`.
- PowerShell pipelines/built-ins: `--execute "powershell -NoProfile -Command \"Get-ChildItem | Select-Object -First 5\""`.
- cmd built-ins: `--execute "cmd /c dir"`.
- Prefer the actual project binary so the screenshot reflects the real product.

---

## `vhs` — animated GIF demos

Scripts a terminal session from a `.tape` file (typing, output, pauses) and renders GIF/MP4/WebM or PNG frames.

### Dependencies (important)
`vhs` needs **`ffmpeg`** and **`ttyd`**. `ttyd` is Linux/macOS only — there is **no native Windows build**. On Windows, run `vhs` inside **WSL**, or skip GIFs and use `freeze`.

### Install
| Platform | Command |
|---|---|
| macOS | `brew install vhs` (pulls ffmpeg/ttyd) |
| Linux/WSL | `sudo apt install ffmpeg`, install `ttyd` (https://github.com/tsl0922/ttyd), then `go install github.com/charmbracelet/vhs@v0.10.0` |
| Release | https://github.com/charmbracelet/vhs/releases |

### Run
```bash
vhs demo.tape          # renders the Output target(s) declared in the tape
vhs new demo.tape      # scaffold a fresh tape
```

### Tape command reference
**Settings** (before any typing):
| Command | Effect |
|---|---|
| `Output demo.gif` | Render target (`.gif`/`.mp4`/`.webm`, or `frame.png`) |
| `Set Shell "bash"` | Shell (`bash`, `zsh`, `pwsh`, `fish`) |
| `Set FontSize 22` / `Set FontFamily "JetBrains Mono"` | Typography |
| `Set Width 1200` / `Set Height 600` | Canvas size (px) |
| `Set Theme "Dracula"` | Color theme |
| `Set Padding 20` / `Set Margin 20` / `Set MarginFill "#0d1117"` | Spacing + fill |
| `Set WindowBar Colorful` | macOS/iOS title bar with traffic lights |
| `Set BorderRadius 10` | Rounded corners |
| `Set TypingSpeed 50ms` | Per-keystroke speed |

**Actions:**
| Command | Effect |
|---|---|
| `Type "echo hello"` | Type text (animated) |
| `Enter` | Press Enter |
| `Sleep 2s` / `Sleep 500ms` | Pause (let output render) |
| `Ctrl+C`, `Tab`, `Backspace`, `Up`, `Down` | Key presses |
| `Hide` … `Show` | Run setup commands without recording them |
| `Screenshot frame.png` | Capture a single still PNG at this point |

---

## Lightweight fallbacks (if neither installs)
- `termshot` — wraps a command and screenshots its output in a window frame.
- `carbon-now-cli` — beautiful images, designed for code (not live output).
- `silicon` — fast code-to-image (Rust).
- Manual OS screenshot of a real terminal window.
- Last resort: paste real (redacted) output into a fenced code block, labelled as text.
