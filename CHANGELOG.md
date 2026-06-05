# Changelog

All notable changes to proofshot are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-06-05

Initial public release.

### Added
- **Agent Skill** (`skills/proofshot/SKILL.md` + `references/`) that captures a
  real CLI command and its real output as a styled screenshot (Charm `freeze`)
  or animated GIF (`vhs`) and embeds it into `README.md` as proof-it-runs
  evidence. macOS/iOS and Windows-terminal style presets.
- **Plugin packaging** — `.claude-plugin/plugin.json` and a self-hosted
  `.claude-plugin/marketplace.json`, installable via
  `/plugin marketplace add aks-builds/proofshot` then
  `/plugin install proofshot@proofshot`.
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
