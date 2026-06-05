#!/usr/bin/env python3
"""check.py — fail when a README proof has gone stale (the moat feature).

A screenshot proves the software worked *once*. check.py keeps that promise
honest: it re-runs the proof command, normalises volatile tokens (see
normalize.py), and compares against the baseline recorded when the shot was
made. If the output drifted ("3 tests now fail", "command not found"), it exits
non-zero so CI fails and the README never lies.

Baselines live next to the image as `<name>.cliproof.txt`. A manifest at
`.cliproof/proof.json` lists every proof:

    { "proofs": [
        { "id": "cli-help",
          "command": "mytool --help",
          "baseline": ".github/media/cli-help.cliproof.txt",
          "image": ".github/media/cli-help.svg" } ] }

Usage:
    python check.py                       # check every proof in the manifest
    python check.py --update              # refresh baselines (after an intended change)
    python check.py --command "mytool --help" --baseline path.txt [--update]
    python check.py --expected a.txt --actual b.txt   # direct compare

Exit codes:
    0  all proofs match their baseline (or --update succeeded)
    1  drift detected, or a proof command failed
    2  usage / manifest error

Pure standard library. No network.
"""
import argparse
import difflib
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import normalize  # noqa: E402

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

DEFAULT_MANIFEST = os.path.join(".cliproof", "proof.json")


def compare(expected: str, actual: str):
    """Return (ok, unified_diff_text) comparing normalised expected vs actual."""
    e = normalize.normalize(expected)
    a = normalize.normalize(actual)
    if e == a:
        return True, ""
    diff = "".join(difflib.unified_diff(
        e.splitlines(keepends=True), a.splitlines(keepends=True),
        fromfile="baseline (normalised)", tofile="current (normalised)",
    ))
    return False, diff


def run_command(command: str, timeout: int = 120) -> str:
    """Run a shell command, return combined stdout+stderr (trusted/committed cmd)."""
    proc = subprocess.run(command, shell=True, stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          timeout=timeout)
    return proc.stdout.decode("utf-8", "replace")


def _check_one(entry, update):
    cmd = entry["command"]
    baseline = entry["baseline"]
    name = entry.get("id", baseline)
    try:
        current = run_command(cmd)
    except Exception as exc:  # noqa: BLE001
        print(f"check: {name}: command FAILED to run: {exc}", file=sys.stderr)
        return False

    if update:
        os.makedirs(os.path.dirname(os.path.abspath(baseline)), exist_ok=True)
        with open(baseline, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(normalize.normalize(current))
        print(f"check: {name}: baseline updated", file=sys.stderr)
        return True

    if not os.path.exists(baseline):
        print(f"check: {name}: no baseline at {baseline} (run --update once)", file=sys.stderr)
        return False
    with open(baseline, "r", encoding="utf-8-sig") as fh:
        expected = fh.read()
    ok, diff = compare(expected, current)
    if ok:
        print(f"check: {name}: OK", file=sys.stderr)
    else:
        print(f"check: {name}: DRIFT", file=sys.stderr)
        sys.stderr.write(diff)
    return ok


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Fail when a README proof has gone stale.")
    p.add_argument("--manifest", default=DEFAULT_MANIFEST, help="path to proof.json")
    p.add_argument("--command", help="single proof command (skips manifest)")
    p.add_argument("--baseline", help="baseline file for --command")
    p.add_argument("--expected", help="direct compare: expected file")
    p.add_argument("--actual", help="direct compare: actual file")
    p.add_argument("--update", action="store_true", help="(re)write baselines instead of comparing")
    args = p.parse_args(argv)

    # Direct compare mode
    if args.expected and args.actual:
        with open(args.expected, "r", encoding="utf-8-sig") as fh:
            e = fh.read()
        with open(args.actual, "r", encoding="utf-8-sig") as fh:
            a = fh.read()
        ok, diff = compare(e, a)
        if not ok:
            sys.stderr.write(diff)
        return 0 if ok else 1

    # Single-command mode
    if args.command:
        if not args.baseline:
            print("check: --command requires --baseline", file=sys.stderr)
            return 2
        ok = _check_one({"id": "cli", "command": args.command, "baseline": args.baseline}, args.update)
        return 0 if ok else 1

    # Manifest mode
    if not os.path.exists(args.manifest):
        print(f"check: no manifest at {args.manifest}", file=sys.stderr)
        return 2
    with open(args.manifest, "r", encoding="utf-8-sig") as fh:
        manifest = json.load(fh)
    proofs = manifest.get("proofs", [])
    if not proofs:
        print("check: manifest has no proofs", file=sys.stderr)
        return 2
    results = [_check_one(e, args.update) for e in proofs]
    failed = results.count(False)
    print(f"check: {results.count(True)}/{len(results)} proofs OK", file=sys.stderr)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
