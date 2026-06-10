# cliproof v2 — Open Integration Platform

**Date:** 2026-06-10
**Approach:** Protocol-first (Approach B)
**Status:** Approved — ready for implementation planning

---

## Overview

cliproof v0.1.1 ships as an npm CLI, a Claude Code plugin, and a single GitHub Action. The
core engine is 13 pure-Python stdlib scripts with zero network dependencies. This spec
defines how v2 opens that engine to the full IT community across four consumer types, four
integration surfaces, a reliability kernel, image quality upgrades, and updated positioning.

**New tagline:** *"Your README should show it works — not just say it."*

---

## Goals

1. Any CI/CD platform (GitHub Actions, GitLab CI, Jenkins, CircleCI, Bitbucket) can run
   cliproof headlessly without manual tool installation.
2. Any AI agent framework (LangChain, CrewAI, AutoGen, LlamaIndex) can call cliproof as a
   structured tool — not a subprocess.
3. Any IDE (VS Code, JetBrains) can trigger captures and surface freshness warnings inline.
4. Any Python script or test runner can import and call cliproof functions directly.
5. Every surface gets the same reliability guarantees: no hangs, structured errors, fallback
   rendering, and a health contract.
6. Output quality earns "state of the art": 11 themes, HiDPI/retina, rich overlays, optimised
   GIFs.

---

## Non-goals

- Hosted/cloud service — cliproof stays fully local; nothing is transmitted.
- Browser or UI capture — terminal output only.
- Replacing `freeze` or `vhs` — they remain the rendering back-ends.
- Windows-native `vhs` — GIF capture stays WSL-only on Windows (documented, not fixed here).

---

## Milestones

| Milestone | Tracks | Deliverables |
|-----------|--------|--------------|
| M1 | Track 1 (kernel) + Track 2 (quality) — parallel | JSON contract kernel · image quality upgrades |
| M2 | Surfaces | MCP server · PyPI package · Docker image · HTTP daemon |
| M3 | IDE integrations | VS Code extension · JetBrains plugin · daemon auto-start |

---

## Section 1 — JSON Contract Kernel (M1 Track 1)

### 1.1 Structured output flag

Every script gains a `--json` flag. With `--json`:

- **stdout** — a single JSON object (the result), machine-parseable by any consumer.
- **stderr** — human-readable progress/log lines (always separate; never pollutes stdout JSON).

Without `--json` the scripts behave exactly as today — no breaking changes.

**Success shape:**
```json
{
  "ok": true,
  "step": "capture",
  "outputs": { "image": ".github/media/help.svg" },
  "renderer": "freeze",
  "tier": 1,
  "warnings": [],
  "elapsed_s": 1.4
}
```

**Error shape:**
```json
{
  "ok": false,
  "step": "capture",
  "reason": "timeout",
  "exit_code": 4,
  "elapsed_s": 30.1,
  "hint": "use --timeout 60 or add --no-stdin"
}
```

### 1.2 Exit code contract (stable, versioned)

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Unknown command |
| 3 | Secret detected — redact blocks |
| 4 | Timeout |
| 5 | Command unsafe — guard blocks |
| 6 | Drift detected — check fails |

These codes are part of the public API from v2.0.0 onward. Semver applies.

### 1.3 Hard timeouts

Every script accepts `--timeout <seconds>`. Defaults (per step):

| Step | Default timeout |
|------|----------------|
| `capture` | 30 s |
| `redact`, `embed`, `annotate`, `storyboard` | 10 s |
| `check`, `verify`, `suggest` | 20 s |
| `guard`, `health` | 5 s |

On timeout: child process is killed via `SIGKILL`, exit code `4` returned, structured error
emitted to stdout (if `--json`) or stderr (otherwise). No hangs under any circumstance.

### 1.4 Multi-renderer fallback chain

`capture.py` walks a priority-ordered renderer list. The response always includes `renderer`
and `tier` so consumers know exactly what they received.

| Tier | Renderer | Output | Condition |
|------|----------|--------|-----------|
| 1 | `freeze` | Styled SVG | freeze on PATH and not timing out |
| 2 | `silicon` | Styled PNG | silicon on PATH |
| 3 | `resvg` / `inkscape` / `magick` | Rasterised fallback | any rasteriser found |
| 4 | Text-SVG stub | Plain monospace SVG | no renderers found |

Tier 4 always succeeds — captures never fail silently or produce an empty file.

### 1.5 Health gate

`preflight.py` is superseded by `health.py` — a first-class health probe promoted to a
mandatory gate across every surface. `preflight.py` is kept as a thin alias that calls
`health.py` for backward compatibility; it will be removed in v1.0.0.

- **MCP server** — runs health check on startup; refuses connections if required tools absent.
- **Docker image** — `HEALTHCHECK` and `ENTRYPOINT` probe; container exits non-zero if broken.
- **HTTP daemon** — exposes `GET /health` (see Section 3.4).
- **Python library** — raises `CliproofNotReadyError` on `import cliproof` when required tools
  are missing (can be suppressed with `cliproof.configure(lazy_health=True)`).

**Health response shape:**
```json
{
  "ok": true,
  "renderers": ["freeze@0.2.2", "resvg"],
  "modes": ["static", "rasterize"],
  "gif": false,
  "redaction": true,
  "guard": true,
  "python": "3.12.3"
}
```

---

## Section 2 — Image Quality Upgrades (M1 Track 2)

Runs in parallel with Track 1. No dependencies on the kernel work.

### 2.1 Theme library

Theme definitions live in `skills/cliproof/themes/<name>.json` — pure data, no Python changes
needed to add themes.

**Shipping in v2:**

| Theme | Status |
|-------|--------|
| `macos`, `github-dark`, `nord`, `iterm`, `win11` | Existing |
| `catppuccin`, `tokyo-night`, `one-dark`, `dracula`, `solarized`, `rose-pine` | New |

**New CLI flags:**
```bash
cliproof themes list                        # lists all presets with a one-line colour swatch
cliproof capture --preset catppuccin \
  --preview -- "cmd"                        # renders a 3-line sample, prompts confirm
```

### 2.2 HiDPI / multi-format output

`capture.py` gains two new flags:

```bash
--scale 1|2|3          # pixel density multiplier (raster outputs only; default 1)
--format svg|png|webp|og
```

| Format | Description |
|--------|-------------|
| `svg` | Default — scalable, redactable, GitHub-native |
| `png` | Rasterised; respects `--scale` |
| `webp` | ~40% smaller than PNG at same quality |
| `og` | 1200 × 630 crop — GitHub/Twitter social preview |

### 2.3 Rich overlays

`annotate.py` gains composable overlay primitives, all implemented as SVG `<g>` layers
appended to the base SVG after redaction. The captured text is never mutated.

```bash
cliproof annotate in.svg \
  --badge pass|fail \                   # corner badge: ✓ PASS (green) / ✗ FAIL (red)
  --stamp "v1.2.0 · 2026-06-10" \       # bottom-right version watermark
  --ci-ribbon "CI passing" \            # top ribbon bar
  -o out.svg
```

`verify.py` can pipe directly: `cliproof verify --command "pytest -q" | cliproof annotate -`

### 2.4 GIF quality controls

`proof.json` gains an optional `gif` block per proof entry:

```jsonc
{
  "id": "demo",
  "command": "...",
  "gif": {
    "speed": "realistic",    // "realistic" | "fast" | number (chars/s)
    "loop": "once",          // "once" | "infinite" | N (integer)
    "freeze_last": true,     // hold final frame instead of blank loop
    "max_kb": 1800           // auto-compress with gifsicle to stay under limit
  }
}
```

`demo.tape.template` is updated to reflect the new timing controls.
`gifsicle` added to the Docker image; `preflight`/`health` reports its presence.

---

## Section 3 — Four Transport Surfaces (M2)

All four surfaces are transport wrappers over the M1 kernel. No capture, redaction, or
embedding logic lives in the surfaces themselves.

### 3.1 MCP Server

**Activation:**
```bash
cliproof mcp              # stdio MCP server (default)
cliproof mcp --http       # HTTP+SSE MCP for non-stdio agents
```

**Wire-up (Claude Code):**
```json
{ "mcpServers": { "cliproof": { "command": "cliproof", "args": ["mcp"] } } }
```

**Tools exposed** (one per kernel operation):
`capture`, `redact`, `embed`, `check`, `guard`, `verify`, `suggest`,
`storyboard`, `annotate`, `pr`, `health`

Each tool definition is generated from the JSON schema: input schema → MCP `inputSchema`,
output schema → MCP response type. No hand-written tool definitions.

Health check runs on MCP server startup. If required tools are absent the server starts but
marks affected tools as unavailable in their descriptions.

### 3.2 Python Package on PyPI

**Install:**
```bash
pip install cliproof
```

**Public API:**
```python
from cliproof import capture, redact, embed, check, health, CaptureResult

status = health()                    # raises CliproofNotReadyError if tools missing
result: CaptureResult = capture(
    command="pytest -q",
    preset="catppuccin",
    scale=2,
    timeout=30
)
redact(result.image, in_place=True)  # raises RedactionBlockedError on secrets (exit 3)
embed("README.md", image=result.image, id="tests", heading="Tests")
```

**Return types** are dataclasses mirroring the JSON schema — `CaptureResult`, `RedactResult`,
`EmbedResult`, `CheckResult`. All raise typed exceptions on failure rather than returning
`ok: false`.

**Package layout:**
```
cliproof/          ← new Python package (importable)
  __init__.py      ← public API re-exports
  _kernel.py       ← subprocess dispatch + JSON parsing
  _types.py        ← dataclasses / exceptions
  py.typed         ← PEP 561 marker
skills/cliproof/   ← existing skill (unchanged)
pyproject.toml     ← new; version kept in sync with package.json by release workflow
```

Both `npm publish` (existing) and `pip publish` run from the same release PR. Version is
single-sourced in `package.json`; `pyproject.toml` reads it via a build hook.

### 3.3 Docker / OCI Image

**Registry:** `ghcr.io/aks-builds/cliproof` (primary) + `aks-builds/cliproof` (Docker Hub mirror)

**Tags:** `latest`, `v<semver>`, `v<major>`, `v<major>.<minor>`

**Base:** `python:3.12-alpine` — `freeze@0.2.2` + `gifsicle` pre-installed.
Multi-arch: `linux/amd64` + `linux/arm64`.

**Usage (any CI):**
```yaml
- docker run --rm -v $PWD:/repo \
    ghcr.io/aks-builds/cliproof:latest \
    capture --execute "pytest -q" --preset catppuccin \
    --json -o /repo/.github/media/tests.svg
```

**Health gate at container start:**
`ENTRYPOINT` runs `health.py` before any command. If tools are broken the container exits `1`
with a structured error — never silently produces corrupt output.

**`HEALTHCHECK` instruction** for orchestrators (Kubernetes, Docker Compose):
```dockerfile
HEALTHCHECK --interval=30s CMD cliproof health --json | python -c \
  "import sys,json; d=json.load(sys.stdin); sys.exit(0 if d['ok'] else 1)"
```

### 3.4 Local HTTP Daemon

**Start:**
```bash
cliproof serve                  # default port 7070
cliproof serve --port 8080      # custom port
```

Implementation: Python `http.server` + `threading` — zero new dependencies.

**REST endpoints:**

| Method | Path | Body / Params | Response |
|--------|------|---------------|----------|
| `GET` | `/health` | — | Health JSON (§1.5) |
| `GET` | `/themes` | — | `[{ name, preview_line }]` |
| `POST` | `/capture` | `{ command, preset?, scale?, format?, timeout? }` | Kernel JSON result |
| `POST` | `/redact` | `{ image, in_place? }` | `{ ok, findings }` |
| `POST` | `/embed` | `{ readme, image, id, heading? }` | `{ ok, diff }` |
| `POST` | `/check` | `{ manifest? }` | `{ ok, fresh, drifted: [] }` |
| `POST` | `/annotate` | `{ image, badge?, stamp?, ci_ribbon? }` | `{ ok, output }` |
| `POST` | `/verify` | `{ command, timeout? }` | `{ ok, verdict, report }` |

All endpoints return JSON. Error responses use the unified error shape from §1.1.

**Auto-start registration** (added to `cliproof install`):
```bash
cliproof install --with-daemon       # registers daemon as user-level background service
```
- macOS: `launchd` plist in `~/Library/LaunchAgents/`
- Linux: `systemd --user` unit
- Windows: Task Scheduler entry

---

## Section 4 — IDE Extensions (M3)

Both extensions are HTTP clients over the daemon (§3.4). No Python on the extension host,
no bundling of scripts, no platform packaging of the capture pipeline.

### 4.1 VS Code Extension

**Marketplace ID:** `aks-builds.cliproof`
**Activation:** workspace contains `README.md` or `.cliproof/proof.json`

**Command palette entries:**
| Command | Action |
|---------|--------|
| `cliproof: Capture screenshot` | Input box for command → `POST /capture` → inserts into open editor |
| `cliproof: Check proofs are fresh` | `POST /check` → results in Problems panel |
| `cliproof: Suggest best proof command` | `POST /suggest` → Quick Pick list |

**Context menu:** right-click `README.md` in Explorer → "Embed cliproof proof here"
(opens command input, captures, shows diff preview before writing).

**Status bar item** (when `proof.json` present):
- `✓ Proofs fresh` — click to re-run check
- `⚠ 1 proof drifted` — click to open Problems panel

**Diagnostics:** when a proof has drifted, a yellow diagnostic squiggle appears on the image
reference line in `README.md` — inline, without running a command.

**Daemon handling:** on first use, `GET /health` is called. If the daemon is not running, a
notification offers "Start cliproof daemon" (runs `cliproof serve` in a background terminal).

### 4.2 JetBrains Plugin

**Marketplace:** JetBrains Marketplace, targets IntelliJ IDEA, PyCharm, WebStorm, GoLand, Rider.

Same three entry points as VS Code, implemented as JetBrains Platform SDK actions.

Freshness check integrates with the **Inspections** system:
`CliproofFreshnessInspection` fires on `README.md` files when `proof.json` is present and
a baseline has drifted — same inline signal, different platform SDK.

---

## Section 5 — Positioning & README Updates

### 5.1 Tagline

```
Before: "Prove your CLI actually works — and keep it true."
After:  "Your README should show it works — not just say it."
```

### 5.2 Hero description

```
Before:
  Capture a real terminal command and its real output as a polished screenshot
  (or GIF), redact any secrets, and embed it into your README.md as
  proof-it-runs evidence — then let CI fail if that proof ever goes stale.

After:
  Capture any real command and its real output — tests, builds, servers,
  scripts, pipelines — as a polished screenshot or GIF, redact any secrets,
  and embed it into your README.md as honest, durable evidence it works.
  Then let CI fail the moment that evidence goes stale.
```

### 5.3 Install section heading

```
Before: "Agent-agnostic (npm) — recommended for any agent"
After:  "npm — works in any agent, pipeline, or IDE"
```

### 5.4 New "Who it's for" section

Added after the comparison table:

```markdown
## Who it's for
cliproof works for anyone who runs shell commands and wants durable proof:
- **Open-source maintainers** — show contributors and users the project ships
- **Backend & platform engineers** — prove builds, servers, and scripts run
- **QA & DevOps teams** — capture test runs and pipeline output as evidence
- **AI agent builders** — wire capture → redact → embed as an MCP tool chain
- **Anyone writing a README** — stop saying it works; show it
```

---

## Architecture summary

```
Consumers
─────────────────────────────────────────────────────────────
CI / GitHub Actions  │  Agent frameworks  │  IDE extensions  │  Python scripts
        │                    │                    │                  │
        ▼                    ▼                    ▼                  ▼
  Docker image          MCP server          HTTP daemon        PyPI package
  (§3.3)                (§3.1)              (§3.4)             (§3.2)
        │                    │                    │                  │
        └────────────────────┴────────────────────┴──────────────────┘
                                      │
                         JSON contract kernel (§1)
                  structured output · timeouts · fallback chain · health
                                      │
                    ┌─────────────────┼─────────────────┐
                capture           redact              embed
                guard             verify              check
                suggest           storyboard          annotate
                pr                normalize           rasterize
```

---

## Release plan

| Milestone | npm/PyPI | Docker | Surfaces |
|-----------|----------|--------|----------|
| v0.2.0 | npm (kernel + quality) | — | — |
| v0.3.0 | npm + PyPI alpha | ghcr.io image | MCP server |
| v0.4.0 | npm + PyPI stable | updated | HTTP daemon |
| v0.5.0 | npm + PyPI | updated | VS Code extension beta |
| v1.0.0 | npm + PyPI | stable | All surfaces GA · JetBrains plugin |

---

## Open questions (resolved during implementation planning)

1. JSON schema format — JSON Schema draft-07 vs a custom TypedDict approach for the Python
   library. Recommendation: TypedDict + dataclasses in Python; JSON Schema for MCP tool
   definitions (generated from TypedDicts via `dataclasses-jsonschema`).
2. PyPI package name — `cliproof` matches npm. Verify it is unclaimed before publishing.
3. Daemon port conflict handling — if `7070` is in use, auto-increment or require explicit
   `--port`. Recommendation: auto-increment with a warning.
4. Extension distribution — VS Code extension requires a publisher account. JetBrains requires
   a vendor account. Both can be `aks-builds`; set up before M3 starts.
