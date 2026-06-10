#!/usr/bin/env python3
"""verify.py — run a command and decide if it actually succeeded.

Closes the loop for terminal proof: runs the command, then judges pass/fail from
the exit code *and* error signatures across 10+ languages/toolchains (so a tool
that prints a stack trace but exits 0 is still flagged). Emits a short verdict
and an optional Markdown report you can attach to a PR alongside the screenshot.

Usage:
    python verify.py --command "npm test"
    python verify.py --command "pytest -q" --report .github/media/verify.md

Exit codes:
    0  PASS (clean exit, no error signatures)
    1  FAIL (non-zero exit or error signatures found)
    2  usage error

Pure standard library. No network.
"""
import argparse
import re
import subprocess
import sys
import os as _os_k
import sys as _sys_k
_sys_k.path.insert(0, _os_k.path.dirname(_os_k.path.abspath(__file__)))
from _kernel import EXIT_SUCCESS, EXIT_ERROR, success, error, emit, default_timeout, setup_streams

setup_streams()

# (language/tool, regex). Case-insensitive unless the pattern needs case.
_ERROR_SIGNS = [
    ("python", re.compile(r"Traceback \(most recent call last\):")),
    ("python", re.compile(r"^\w*(Error|Exception):", re.M)),
    ("node/npm", re.compile(r"npm ERR!")),
    ("node", re.compile(r"UnhandledPromiseRejection|ReferenceError|TypeError:")),
    ("go", re.compile(r"^panic:|^--- FAIL", re.M)),
    ("rust", re.compile(r"error\[E\d+\]|thread '.*' panicked")),
    ("java", re.compile(r"Exception in thread|BUILD FAILURE")),
    ("ruby", re.compile(r"\(.*Error\)\s*$|\.rb:\d+:in ", re.M)),
    ("dotnet", re.compile(r"Unhandled exception")),
    ("php", re.compile(r"PHP (Fatal|Parse) error")),
    ("elixir", re.compile(r"\*\* \(\w+Error\)")),
    ("compiler", re.compile(r"(?im)^\s*error:")),
    ("test", re.compile(r"\bFAILED\b|\b\d+ failed\b|\bSegmentation fault\b")),
    ("shell", re.compile(r"command not found|No such file or directory")),
]


def detect_errors(text: str):
    """Return a sorted list of language/tool tags whose error signature matched."""
    hits = set()
    for tag, rx in _ERROR_SIGNS:
        if rx.search(text):
            hits.add(tag)
    return sorted(hits)


def verify(command: str, timeout: int = 300):
    """Run command; return dict(ok, exit_code, errors, output)."""
    proc = subprocess.run(command, shell=True, stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          timeout=timeout)
    output = proc.stdout.decode("utf-8", "replace")
    errors = detect_errors(output)
    ok = proc.returncode == 0 and not errors
    return {"ok": ok, "exit_code": proc.returncode, "errors": errors, "output": output}


def report_markdown(command: str, result: dict) -> str:
    badge = "✅ PASS" if result["ok"] else "❌ FAIL"
    lines = [
        f"### cliproof verify — {badge}",
        "",
        f"- **Command:** `{command}`",
        f"- **Exit code:** `{result['exit_code']}`",
    ]
    if result["errors"]:
        lines.append(f"- **Error signatures:** {', '.join(result['errors'])}")
    lines += ["", "<details><summary>Output</summary>", "", "```", result["output"].rstrip(), "```", "", "</details>"]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Run a command and decide pass/fail.")
    p.add_argument("--command", required=True, help="command to run and judge")
    p.add_argument("--report", help="write a Markdown report to this path")
    p.add_argument("--quiet", action="store_true", help="suppress the command output echo")
    p.add_argument("--json", action="store_true", help="emit machine-readable JSON to stdout")
    p.add_argument("--timeout", type=float, default=default_timeout("verify"),
                   help="timeout in seconds")
    args = p.parse_args(argv)

    try:
        result = verify(args.command)
    except Exception as exc:  # noqa: BLE001
        print(f"verify: command failed to run: {exc}", file=sys.stderr)
        _r = error("verify", "command_failed", EXIT_ERROR)
        _r["outputs"] = {"verdict": "FAIL", "command": args.command}
        emit(_r, args.json)
        return EXIT_ERROR

    verdict = "PASS" if result["ok"] else "FAIL"

    if not args.quiet:
        sys.stdout.write(result["output"])
    print(f"verify: {verdict} (exit {result['exit_code']}"
          + (f", errors: {', '.join(result['errors'])}" if result["errors"] else "") + ")",
          file=sys.stderr)

    if args.report:
        with open(args.report, "w", encoding="utf-8") as fh:
            fh.write(report_markdown(args.command, result))
        print(f"verify: wrote {args.report}", file=sys.stderr)

    if result["ok"]:
        emit(success("verify", {"verdict": "PASS", "command": args.command}), args.json)
        return EXIT_SUCCESS
    else:
        _r = error("verify", "command_failed", EXIT_ERROR)
        _r["outputs"] = {"verdict": "FAIL", "command": args.command}
        emit(_r, args.json)
        return EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
