#!/usr/bin/env python3
"""suggest.py — propose the best command to capture as "proof it runs".

Scans a repo for commands that demonstrate the project working — test/build
scripts, declared entry points, Makefile targets, README quickstart lines — and
ranks them. Deterministic, self-evidently-working commands (`--help`,
`--version`, `test`) score highest; long-running/interactive ones score low.

Usage:
    python suggest.py [repo_dir] [--json] [--top N]

Pure standard library. No network.
"""
import argparse
import json
import os
import re
import sys

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# Higher score = better proof candidate.
_GOOD = ("--help", "--version", "version", "test", "build", "lint", "check", "doctor")
_RISKY = ("dev", "start", "serve", "watch", "deploy", "publish", "release")


def _score(command: str) -> int:
    c = command.lower()
    score = 5
    if any(g in c for g in ("--help", "--version", " version")):
        score += 6           # deterministic, finishes instantly, self-evident
    if any(g in c for g in ("test", "build", "lint", "check", "doctor")):
        score += 4           # proof it actually works
    if any(r in c for r in _RISKY):
        score -= 5           # long-running / needs a port / interactive
    return score


def _read(path):
    try:
        with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def scan(root: str):
    """Return a list of {command, source, reason, score} sorted best-first."""
    out = []

    def add(command, source, reason):
        out.append({"command": command, "source": source, "reason": reason,
                    "score": _score(command)})

    pkg = os.path.join(root, "package.json")
    if os.path.exists(pkg):
        try:
            data = json.loads(_read(pkg) or "{}")
        except json.JSONDecodeError:
            data = {}
        for name in data.get("scripts", {}):
            add(f"npm run {name}" if name != "test" else "npm test",
                "package.json", f"npm script '{name}'")
        bins = data.get("bin")
        if isinstance(bins, dict):
            for b in bins:
                add(f"{b} --help", "package.json", f"declared bin '{b}'")
        elif isinstance(bins, str) and data.get("name"):
            add(f"{data['name']} --help", "package.json", "declared bin")

    mk = os.path.join(root, "Makefile")
    if os.path.exists(mk):
        for m in re.finditer(r"(?m)^([a-zA-Z][\w-]*):", _read(mk)):
            target = m.group(1)
            if target.lower() in ("test", "build", "run", "demo", "check", "lint"):
                add(f"make {target}", "Makefile", f"make target '{target}'")

    if os.path.exists(os.path.join(root, "pyproject.toml")):
        txt = _read(os.path.join(root, "pyproject.toml"))
        for m in re.finditer(r"(?m)^\s*([A-Za-z0-9_-]+)\s*=\s*\"[^\"]+:[^\"]+\"", txt):
            add(f"{m.group(1)} --help", "pyproject.toml", f"console script '{m.group(1)}'")
        add("pytest -q", "pyproject.toml", "Python project") if "pytest" in txt else None

    if os.path.exists(os.path.join(root, "Cargo.toml")):
        add("cargo test", "Cargo.toml", "Rust project")
        add("cargo run -- --help", "Cargo.toml", "Rust binary")
    if os.path.exists(os.path.join(root, "go.mod")):
        add("go test ./...", "go.mod", "Go module")

    readme = os.path.join(root, "README.md")
    if os.path.exists(readme):
        for line in _read(readme).splitlines():
            m = re.match(r"^\s*\$\s+(\S.*)$", line)
            if m and len(m.group(1)) < 80:
                add(m.group(1).strip(), "README.md", "README quickstart line")

    # de-dupe by command, keep best reason/score
    seen = {}
    for item in out:
        key = item["command"]
        if key not in seen or item["score"] > seen[key]["score"]:
            seen[key] = item
    return sorted(seen.values(), key=lambda d: d["score"], reverse=True)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Suggest the best 'proof it runs' command for a repo.")
    p.add_argument("root", nargs="?", default=".", help="repo directory (default: cwd)")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--top", type=int, default=8, help="max suggestions")
    args = p.parse_args(argv)

    results = scan(args.root)[: args.top]
    if args.json:
        print(json.dumps(results, indent=2))
        return 0
    if not results:
        print("suggest: no obvious proof command found. Try '<your-tool> --help'.")
        return 0
    print("Suggested commands to capture (best first):")
    for r in results:
        print(f"  [{r['score']:>2}] {r['command']}   ({r['reason']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
