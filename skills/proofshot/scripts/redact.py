#!/usr/bin/env python3
"""redact.py — mask secrets and personal data in captured terminal output.

Reads text from a file or stdin, masks anything that looks like a secret or
personal identifier, and writes the redacted text back out. Designed to run on
SVG captures (text) or on a command's piped stdout BEFORE an image is made.

Usage:
    python redact.py output.svg --in-place
    python redact.py output.svg            # redacted text to stdout
    some-command 2>&1 | python redact.py - # filter a pipe

Exit codes:
    0  clean, or only privacy normalisations applied (safe to use the output)
    3  SECRET-class match found (STOP — re-run with sanitized env/args)

Severity:
    secret  -> keys, tokens, passwords, private keys  (exit 3, blocks)
    privacy -> emails, private IPs, home paths         (exit 0, auto-normalised)

Pure standard library. No network. No side effects beyond the optional rewrite.
"""
import argparse
import re
import sys

# Captured output can contain any Unicode; never crash on a cp1252 console.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

SECRET = "secret"
PRIVACY = "privacy"


def _mask(value: str, keep: int = 4) -> str:
    """Preserve shape: keep a short prefix, replace the rest with '*'."""
    value = value.strip()
    if len(value) <= keep:
        return "*" * len(value)
    stars = min(len(value) - keep, 12)
    return value[:keep] + "*" * stars


def _mask_match(m: "re.Match") -> str:
    return _mask(m.group(0))


def _mask_kv(m: "re.Match") -> str:
    # group(1)=key, group(2)=separator-ish, group('val')=value
    return m.group(0)[: m.start("val") - m.start(0)] + _mask(m.group("val"))


# (name, severity, compiled-regex, replacement) where replacement is a str or callable.
_RULES = [
    ("private-key-block", SECRET,
     re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z0-9 ]*PRIVATE KEY-----"),
     "[redacted-private-key]"),
    ("aws-access-key", SECRET, re.compile(r"\bAKIA[0-9A-Z]{16}\b"), _mask_match),
    ("github-token", SECRET, re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,255}\b"), _mask_match),
    ("slack-token", SECRET, re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"), _mask_match),
    ("stripe-key", SECRET, re.compile(r"\bsk_(live|test)_[A-Za-z0-9]{16,}\b"), _mask_match),
    ("google-api-key", SECRET, re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"), _mask_match),
    ("openai-anthropic-key", SECRET, re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}\b"), _mask_match),
    ("jwt", SECRET, re.compile(r"\beyJ[A-Za-z0-9_\-]{6,}\.[A-Za-z0-9_\-]{6,}\.[A-Za-z0-9_\-]{6,}\b"), _mask_match),
    ("bearer", SECRET, re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{8,}"), lambda m: "Bearer " + _mask(m.group(0).split(None, 1)[1])),
    ("authorization-header", SECRET, re.compile(r"(?i)\bauthorization:\s*\S+"), "Authorization: [redacted]"),
    ("kv-secret", SECRET,
     re.compile(r"(?i)\b(api[_-]?key|secret|token|password|passwd|pwd|access[_-]?key|client[_-]?secret)\b\s*[:=]\s*[\"']?(?P<val>[^\s\"']{4,})"),
     _mask_kv),
    # privacy-class (auto-normalised, non-blocking)
    ("email", PRIVACY, re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"), "[redacted-email]"),
    ("private-ipv4", PRIVACY,
     re.compile(r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b"),
     "[private-ip]"),
    ("home-path-unix", PRIVACY, re.compile(r"/(?:home|Users)/[^/\s\"']+"), lambda m: m.group(0).rsplit("/", 1)[0] + "/<user>"),
    ("home-path-windows", PRIVACY, re.compile(r"(?i)([A-Z]:\\Users\\)[^\\\s\"']+"), lambda m: m.group(1) + "<user>"),
]


def redact(text: str):
    """Return (redacted_text, findings) where findings is a list of (name, severity, count)."""
    findings = []
    for name, severity, rx, repl in _RULES:
        count = len(rx.findall(text))
        if count:
            text = rx.sub(repl, text)
            findings.append((name, severity, count))
    return text, findings


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Mask secrets/PII in captured output.")
    p.add_argument("path", help="file to scan, or '-' for stdin")
    p.add_argument("--in-place", action="store_true", help="rewrite the file with redacted text")
    args = p.parse_args(argv)

    if args.path == "-":
        text = sys.stdin.read()
    else:
        with open(args.path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()

    redacted, findings = redact(text)

    if args.in_place and args.path != "-":
        with open(args.path, "w", encoding="utf-8") as fh:
            fh.write(redacted)
    else:
        sys.stdout.write(redacted)

    secrets = [f for f in findings if f[1] == SECRET]
    privacy = [f for f in findings if f[1] == PRIVACY]
    for name, severity, count in findings:
        print(f"redact: {severity}: {name} x{count}", file=sys.stderr)

    if secrets:
        print("redact: SECRET-class data found - do NOT embed; re-run with sanitized input.", file=sys.stderr)
        return 3
    if privacy:
        print("redact: privacy items normalised; redacted output is safe to use.", file=sys.stderr)
    else:
        print("redact: clean.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
