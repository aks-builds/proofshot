#!/usr/bin/env python3
"""guard.py — refuse to capture obviously dangerous commands.

A safety net, NOT a sandbox. It matches a command string against a denylist of
destructive / exfiltration patterns. A match exits non-zero so the cliproof
workflow stops and asks the human before running anything.

Usage:
    python guard.py -- "<command string>"
    python guard.py "<command string>"
    echo "<command>" | python guard.py -

Exit codes:
    0  no risky pattern matched
    2  at least one risky pattern matched (STOP — confirm with a human)

Pure standard library. No network. No side effects.
"""
import argparse
import re
import sys

# (name, compiled regex, human explanation). Patterns are intentionally broad;
# false positives are acceptable for a "demo command" use case.
_RULES = [
    ("recursive-force-delete",
     r"\brm\s+(-[a-z]*\s+)*-[a-z]*r[a-z]*f|\brm\s+(-[a-z]*\s+)*-[a-z]*f[a-z]*r",
     "recursive force delete (rm -rf)"),
    ("delete-root-or-home",
     r"\brm\b[^\n]*\s(/|~|\$HOME|\*)(\s|$)",
     "delete targeting /, ~, $HOME, or *"),
    ("windows-recursive-delete",
     r"(?i)\bremove-item\b[^\n]*-recurse[^\n]*-force|\bdel\b[^\n]*/s[^\n]*/q|\brd\b[^\n]*/s",
     "Windows recursive force delete"),
    ("disk-write",
     r"(?i)\b(mkfs|fdisk|format-volume|format\s+[a-z]:)\b|\bdd\b[^\n]*\bof=/dev/",
     "writing to a raw disk/partition"),
    ("redirect-to-device",
     r">\s*/dev/(sd|nvme|hd|mmcblk|disk)",
     "redirecting output onto a block device"),
    ("fork-bomb",
     r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:",
     "fork bomb"),
    ("pipe-remote-to-shell",
     r"(?i)\b(curl|wget|iwr|invoke-webrequest|invoke-restmethod)\b[^\n|]*\|\s*(sudo\s+)?(sh|bash|zsh|pwsh|powershell|python\d?|iex|invoke-expression)\b",
     "piping a remote download straight into a shell (curl|sh)"),
    ("powershell-iex-download",
     r"(?i)\b(iex|invoke-expression)\b[^\n]*(downloadstring|invoke-webrequest|iwr|new-object\s+net\.webclient)",
     "PowerShell download-and-execute"),
    ("read-private-key",
     r"(?i)(cat|type|more|less|gc|get-content|copy|scp)\b[^\n]*(id_rsa|id_ed25519|\.ssh[\\/]|\.aws[\\/]credentials|\.npmrc|\.netrc|secrets?\.|\.pem\b|\.env\b)",
     "reading a private key / credential / .env file"),
    ("dump-env",
     r"(?i)\b(printenv|env|set|get-childitem\s+env:|gci\s+env:|export\s*-p)\b",
     "dumping the full environment (may contain secrets)"),
    ("chmod-world-root",
     r"(?i)\bchmod\b[^\n]*\b777\b[^\n]*\s(/|~)(\s|$)",
     "chmod 777 on / or ~"),
    ("power-control",
     r"(?i)\b(shutdown|reboot|halt|poweroff|stop-computer|restart-computer)\b",
     "power/reboot control"),
    ("truncate-file",
     r"(^|\s):\s*>\s*\S|>\s*/etc/",
     "truncating a file or writing under /etc"),
]

_COMPILED = [(name, re.compile(rx), why) for name, rx, why in _RULES]


def scan(command: str):
    """Return a list of (name, explanation) for every rule the command trips."""
    hits = []
    for name, rx, why in _COMPILED:
        if rx.search(command):
            hits.append((name, why))
    return hits


def _read_command(args) -> str:
    if args.command == ["-"] or (not args.command and not sys.stdin.isatty()):
        return sys.stdin.read().strip()
    return " ".join(args.command).strip()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Refuse to capture dangerous commands.")
    p.add_argument("command", nargs="*", help="command string (or '-' for stdin)")
    args = p.parse_args(argv)

    command = _read_command(args)
    if not command:
        print("guard: no command provided", file=sys.stderr)
        return 2

    hits = scan(command)
    if hits:
        print("guard: REFUSING - command matched risky pattern(s):", file=sys.stderr)
        for name, why in hits:
            print(f"  - {name}: {why}", file=sys.stderr)
        print("\nStop and confirm with a human before running this.", file=sys.stderr)
        return 2

    print("guard: ok", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
