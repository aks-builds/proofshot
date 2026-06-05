# Security Policy

proofshot runs real shell commands and writes files into a repository, so it
treats security as a first-class concern. The full threat model lives in
[`skills/proofshot/references/security.md`](./skills/proofshot/references/security.md);
this file is the reporting policy.

## Reporting a vulnerability

**Please do not open a public issue for security vulnerabilities.**

Report privately via GitHub's
[security advisory](https://github.com/aks-builds/proofshot/security/advisories/new)
("Report a vulnerability"). Include:

- a description of the issue and its impact,
- steps to reproduce (use **synthetic** data only — never real secrets),
- affected version/commit, and any suggested fix.

We aim to acknowledge reports within a few days and to address confirmed issues
promptly. Please allow reasonable time to fix before public disclosure.

## Scope — what we especially care about

- **Secret leakage** — any path where a real credential in captured output
  reaches a committed image or the README without being redacted.
- **Command execution** — any way the command-guard can be bypassed to capture
  a destructive or exfiltrating command without a human confirmation step.
- **Supply chain** — anything that would cause a bundled script to gain a
  dependency, make a network call, or execute untrusted code.

## Design guarantees

- Bundled scripts are **pure Python standard library** — no third-party
  packages, no network calls, no build/postinstall steps, no obfuscation.
- proofshot **never transmits captured output** off the machine.
- It never auto-installs global packages, auto-commits, or auto-pushes.
- Underlying tools (`freeze`/`vhs`) are **version-pinned** and installed only
  from official sources, with user confirmation.

## Out of scope

- Issues requiring an already-compromised host.
- Novel secret formats that no public redaction tool would recognise (the human
  review step is the backstop; see the security reference).
- Lack of formal trademark/legal review (not a security matter).
