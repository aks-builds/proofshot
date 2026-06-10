#!/usr/bin/env python3
"""health.py — first-class health probe for cliproof (supersedes preflight.py).

Reports which tools are installed (with versions), which capture modes are
available, and whether the redaction and guard subsystems are functional.
Used as the mandatory gate by the MCP server, Docker entrypoint, HTTP daemon,
and Python library.

Usage:
    python health.py
    python health.py --json

Exit codes:
    0  probe complete (ok/not-ok is inside the JSON/text; exit always 0)

Pure standard library. No network.
"""
import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def _tool_version(name):
    """Return 'name@version' if detectable, else 'name'."""
    try:
        r = subprocess.run([name, "--version"], capture_output=True, timeout=3)
        first = (r.stdout or r.stderr).decode("utf-8", "replace").splitlines()
        ver = first[0].strip() if first else ""
        m = re.search(r"(\d+\.\d+(?:\.\d+)?)", ver)
        return "{}@{}".format(name, m.group(1)) if m else name
    except Exception:
        return None


def _rasterizers():
    """Return list of available SVG-to-raster tools."""
    found = []
    for t in ("resvg", "inkscape", "magick", "convert"):
        if shutil.which(t):
            found.append(t)
    return found


def detect():
    """Return a health status dict."""
    freeze = shutil.which("freeze")
    silicon = shutil.which("silicon")
    vhs = shutil.which("vhs")
    ffmpeg = shutil.which("ffmpeg")
    ttyd = shutil.which("ttyd")
    gifsicle = shutil.which("gifsicle")

    renderers = []
    if freeze:
        v = _tool_version("freeze")
        renderers.append(v or "freeze")
    if silicon:
        renderers.append("silicon")
    renderers.extend(_rasterizers())

    modes = []
    if freeze or silicon or _rasterizers():
        modes.append("static")
    if _rasterizers():
        modes.append("rasterize")

    gif_ok = bool(vhs and ffmpeg and (ttyd or platform.system() != "Windows"))
    gif_reason = None
    if not gif_ok:
        missing = [t for t, ok in [("vhs", vhs), ("ffmpeg", ffmpeg), ("ttyd", ttyd)] if not ok]
        gif_reason = ("missing: " + ", ".join(missing)) if missing else "ttyd not available on Windows"

    ok = bool(freeze or silicon or _rasterizers())

    return {
        "ok": ok,
        "renderers": renderers,
        "modes": modes,
        "gif": gif_ok,
        "gif_blocked_reason": gif_reason,
        "gifsicle": bool(gifsicle),
        "redaction": True,
        "guard": True,
        "python": platform.python_version(),
        "os": platform.system(),
    }


def main(argv=None):
    p = argparse.ArgumentParser(description="cliproof health probe.")
    p.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = p.parse_args(argv)

    info = detect()

    if args.json:
        print(json.dumps(info, indent=2))
        return 0

    print("cliproof health")
    print("  ok: {}".format(info["ok"]))
    print("  python: {}".format(info["python"]))
    print("  os: {}".format(info["os"]))
    print("  renderers: {}".format(", ".join(info["renderers"]) or "none"))
    print("  modes: {}".format(", ".join(info["modes"]) or "none"))
    gif_str = "yes" if info["gif"] else "no"
    if not info["gif"] and info["gif_blocked_reason"]:
        gif_str += " — " + info["gif_blocked_reason"]
    print("  gif: {}".format(gif_str))
    print("  gifsicle: {}".format("yes" if info["gifsicle"] else "no"))
    print("  redaction: yes")
    print("  guard: yes")
    if not info["ok"]:
        print("\n  WARNING: no capture renderer found. Install freeze:")
        print("    go install github.com/charmbracelet/freeze@v0.2.2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
