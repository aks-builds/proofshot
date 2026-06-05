# Security model

cliproof runs real shell commands and writes images into a repo, so it treats
security as a first-class concern — not advice the model "should" follow, but
gates enforced by small, auditable scripts.

## Trust boundaries
- cliproof **never makes network calls.** Every bundled script is pure Python
  standard library — no third-party packages, no `pip install`, no telemetry.
- cliproof only **reads and writes files inside the user's repo** (the captured
  image and `README.md`) and runs the command the user chose to demonstrate.
- The only external programs it invokes are the user's own toolchain
  (`freeze`/`vhs`, and — for `rasterize.py` — a locally installed SVG renderer
  such as a Chromium browser, `resvg`, `rsvg-convert`, `inkscape`, or `magick`,
  always run headless against a local file) and the command being captured.
  `capture.py` additionally runs `freeze` with stdin closed so it can't block on,
  or read from, an inherited pipe.

## The three enforced gates

### 1. Command guard — `scripts/guard.py`
Before any command is executed for capture, it is matched against a denylist of
destructive and exfiltration patterns (recursive deletes, disk wipes, fork
bombs, piping a remote download straight into a shell, credential file reads,
overwriting devices, etc.). A match exits non-zero and the workflow stops and
asks the user. This prevents "capture this command" from becoming an arbitrary
code-execution foot-gun.

The guard is a safety net, **not** a sandbox. It cannot catch every dangerous
command. The real protections are: (a) the user chooses the command, (b) it's
meant to be a short demo command, and (c) the human confirms before it runs.

### 2. Secret redaction — `scripts/redact.py`
Captured terminal output frequently contains secrets the author never meant to
publish. `redact.py` scans text (use SVG capture, or pipe the command's stdout)
for high-signal patterns and masks them:

- Cloud / provider keys: AWS access keys (`AKIA…`), Google API keys, Slack
  tokens (`xox[baprs]-…`), GitHub tokens (`ghp_`/`gho_`/`ghu_`/`ghs_`/`ghr_`),
  Stripe (`sk_live_`), OpenAI/Anthropic-style `sk-…`.
- Generic bearer tokens, `Authorization:` headers, JWTs (`eyJ…`).
- `key=`, `token=`, `secret=`, `password=`, `passwd=`, `api_key=` assignments.
- Private RSA/EC/OPENSSH key blocks.
- Email addresses, private IPv4 ranges, and absolute home paths
  (`/home/<user>`, `/Users/<user>`, `C:\Users\<user>`) → normalised.

Findings cause a non-zero exit so the workflow halts before embedding. Masking
preserves enough shape to stay legible (`AKIA****…****`) without leaking value.

Redaction is **best-effort, not a guarantee.** Novel secret formats can slip
through, so the human still reviews the captured output before it is committed.

### 3. Idempotent README writes — `scripts/embed.py`
Edits are confined to a marked block:
```
<!-- cliproof:start id=<id> -->
…image markdown…
<!-- cliproof:end id=<id> -->
```
Re-running with the same `id` replaces that block instead of appending a
duplicate. The rest of the README is never touched. The script makes a `.bak`
on first write and prints a unified diff so the change is reviewable.

## Supply-chain notes
- cliproof does not bundle or download `freeze`/`vhs`. It points the user to
  official sources and **pins versions** (`references/tooling.md`) so output is
  reproducible and an unexpected upstream change can't silently alter results.
- Installs are always surfaced to the user for confirmation; nothing is fetched
  or executed silently.
- The bundled scripts have **zero dependencies** — audit them in full in
  `scripts/`. There is no build step, no postinstall hook, no obfuscation.

## What cliproof deliberately does NOT do
- Send captured output anywhere off the machine.
- Auto-commit or auto-push.
- Install global packages without consent.
- Capture or embed output it has not screened for secrets.

Report a vulnerability privately via the repo's Security Advisories (see the
repository `SECURITY.md`), not a public issue.
