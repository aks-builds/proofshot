# Contributing to proofshot

Thanks for your interest! proofshot helps developers prove their CLI actually
works by capturing **real** command output as polished screenshots and GIFs and
embedding them into a README. Contributions of all kinds are welcome — code,
docs, new style presets, redaction patterns, and tests.

## Ground rules

- Be respectful (see [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md)).
- **Never commit real secrets or personal data.** Use obviously fake fixtures
  (e.g. `AKIAIOSFODNN7EXAMPLE`).
- Keep the project's posture intact: **real output only, secrets redacted,
  local-only, confirm before installs/writes.** Changes that fabricate output,
  weaken redaction, add network calls, or auto-install/commit will not be merged.
- Bundled skill scripts must stay **pure Python standard library** — zero
  third-party runtime dependencies, no network access.

## Dev setup

```bash
git clone https://github.com/aks-builds/proofshot.git
cd proofshot
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
pytest -q
```

## Making a change

1. **Fork** and create a branch: `git checkout -b feat/short-description`.
2. Make your change. Keep functions small; stdlib-first; match existing style.
3. **Add or update tests** in `tests/` and make sure `pytest -q` passes.
4. Update docs (`README.md` / `SKILL.md` / `references/`) if behavior changes.
5. Use [Conventional Commits](https://www.conventionalcommits.org)
   (`feat:`, `fix:`, `docs:`, `test:`, `chore:`).
6. Open a PR against `main`. CI must be green; a CODEOWNER review is required
   (see [.github/CODEOWNERS](./.github/CODEOWNERS)).

## Good contributions

- **Redaction patterns** — new secret formats for `scripts/redact.py` (add a
  test with a fake example).
- **Guard rules** — additional destructive/exfiltration patterns for
  `scripts/guard.py`.
- **Style presets** — new `freeze`/`vhs` looks in `references/tooling.md`.
- **Cross-platform fixes** — Windows/macOS/Linux/WSL capture edge cases.

## Reporting bugs / ideas

Use the issue templates. For anything security-sensitive, follow
[SECURITY.md](./SECURITY.md) instead of opening a public issue.

By contributing, you agree your contributions are licensed under the
[MIT License](./LICENSE.md).
