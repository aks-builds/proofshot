#!/usr/bin/env python3
"""normalize.py — neutralise volatile tokens so a capture is reproducible.

"Deterministic mode." Terminal output is full of values that change every run
(durations, timestamps, temp paths, PIDs, ports, hashes). Normalising them lets
`check.py` tell a *real* drift ("3 tests now fail") from cosmetic noise ("ran in
0.21s vs 0.19s"). Used by the freshness check and available standalone.

Usage:
    python normalize.py output.txt              # normalised text to stdout
    some-command 2>&1 | python normalize.py -   # filter a pipe
    python normalize.py output.txt --in-place

Pure standard library. No network.
"""
import argparse
import re
import sys
import os as _os_k
import sys as _sys_k
_sys_k.path.insert(0, _os_k.path.dirname(_os_k.path.abspath(__file__)))
from _kernel import EXIT_SUCCESS, EXIT_ERROR, success, error, emit

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# Order matters: timestamps before bare times/dates; specific before general.
_RULES = [
    # ISO-8601 timestamp (date + time, optional fraction/zone)
    (re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?"), "<timestamp>"),
    (re.compile(r"\b\d{4}-\d{2}-\d{2}\b"), "<date>"),
    (re.compile(r"\b\d{2}:\d{2}:\d{2}(?:\.\d+)?\b"), "<time>"),
    # UUID
    (re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"), "<uuid>"),
    # git-ish / long hex hash
    (re.compile(r"\b[0-9a-f]{12,40}\b"), "<hash>"),
    # temp paths
    (re.compile(r"(?i)(?:/tmp/|/var/folders/|[A-Z]:\\Users\\[^\\]+\\AppData\\Local\\Temp\\)\S+"), "<tmp>"),
    # durations: 0.21s, 1.3 s, 250ms, 2m, 1h  -> Ns / Nms ...
    (re.compile(r"\b\d+(?:\.\d+)?(\s?)(ns|µs|us|ms|s|m|h)\b"), r"N\1\2"),
    # pids
    (re.compile(r"(?i)\b(pid)[\s:=]+\d+"), r"\1 N"),
    # ports on local hosts
    (re.compile(r"\b(localhost|127\.0\.0\.1|0\.0\.0\.0):\d{2,5}\b"), r"\1:PORT"),
]


def normalize(text: str) -> str:
    # Normalise line endings first: a baseline captured on Windows (CRLF) must
    # match the same command re-run in CI on Linux (LF). This is part of making
    # a capture reproducible, not cosmetic.
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    for rx, repl in _RULES:
        text = rx.sub(repl, text)
    return text


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Neutralise volatile tokens for reproducible captures.")
    p.add_argument("path", help="file to normalise, or '-' for stdin")
    p.add_argument("--in-place", action="store_true", help="rewrite the file")
    p.add_argument("--json", action="store_true", help="emit machine-readable JSON to stdout")
    args = p.parse_args(argv)

    if args.path == "-":
        text = sys.stdin.read()
    else:
        with open(args.path, "r", encoding="utf-8-sig", errors="replace") as fh:
            text = fh.read()

    out = normalize(text)
    if args.in_place and args.path != "-":
        with open(args.path, "w", encoding="utf-8") as fh:
            fh.write(out)
    else:
        if not args.json:
            sys.stdout.write(out)
    emit(success("normalize", {"normalized": True}), args.json)
    return EXIT_SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())
