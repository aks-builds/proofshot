#!/usr/bin/env python3
"""preflight.py — report what proofshot can do on this machine.

Detects the OS and which capture tools are installed, then says which modes
(static screenshot / animated GIF) are available and what to install otherwise.

Usage:
    python preflight.py
    python preflight.py --json

Pure standard library. No network.
"""
import argparse
import json
import platform
import shutil
import sys

TOOLS = ["freeze", "vhs", "ffmpeg", "ttyd", "go", "python3"]

INSTALL_HINTS = {
    "freeze": "go install github.com/charmbracelet/freeze@v0.2.2  |  brew install charmbracelet/tap/freeze  |  scoop install freeze",
    "vhs": "brew install vhs  (needs ffmpeg + ttyd; on Windows use WSL)",
    "ffmpeg": "brew install ffmpeg  |  apt install ffmpeg  |  scoop install ffmpeg",
    "ttyd": "https://github.com/tsl0922/ttyd  (no native Windows build - use WSL)",
    "go": "https://go.dev/dl/",
}


def _png_rasterizer():
    """Name of the first local SVG->PNG renderer, or None. Reuses rasterize.py."""
    try:
        import rasterize  # sibling script
        found = rasterize.find_renderer()
        return found[0] if found else None
    except Exception:
        return None


def detect():
    system = platform.system()  # 'Windows' | 'Darwin' | 'Linux'
    found = {t: bool(shutil.which(t)) for t in TOOLS}

    static_ok = found["freeze"]
    png_rasterizer = _png_rasterizer()
    # vhs needs ffmpeg + ttyd; ttyd has no native Windows build.
    animated_ok = found["vhs"] and found["ffmpeg"] and found["ttyd"]
    animated_blocked_reason = None
    if not animated_ok:
        if system == "Windows" and not found["ttyd"]:
            animated_blocked_reason = "ttyd has no native Windows build - run vhs under WSL, or use a static screenshot."
        else:
            missing = [t for t in ("vhs", "ffmpeg", "ttyd") if not found[t]]
            animated_blocked_reason = "missing: " + ", ".join(missing)

    return {
        "os": system,
        "tools": found,
        "static_screenshot": static_ok,
        "png_rasterizer": png_rasterizer,  # SVG->PNG renderer name, or None (embed SVG)
        "animated_gif": animated_ok,
        "animated_blocked_reason": animated_blocked_reason,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Report proofshot capture capabilities.")
    p.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = p.parse_args(argv)

    info = detect()

    if args.json:
        print(json.dumps(info, indent=2))
        return 0

    print("proofshot preflight")
    print("  OS: {}".format(info["os"]))
    print("  tools:")
    for tool, present in info["tools"].items():
        mark = "ok " if present else "-- "
        print("    [{}] {}".format(mark, tool))

    print()
    print("  static screenshot (freeze): {}".format("AVAILABLE" if info["static_screenshot"] else "needs freeze"))
    if info["png_rasterizer"]:
        print("  svg -> png (rasterize.py):  AVAILABLE via {}".format(info["png_rasterizer"]))
    else:
        print("  svg -> png (rasterize.py):  none found - embed the SVG (GitHub renders it)")
    if info["animated_gif"]:
        print("  animated gif (vhs):         AVAILABLE")
    else:
        print("  animated gif (vhs):         unavailable - {}".format(info["animated_blocked_reason"]))

    missing = [t for t, ok in info["tools"].items() if not ok and t in INSTALL_HINTS]
    if missing:
        print("\n  install hints:")
        for t in missing:
            print("    {}: {}".format(t, INSTALL_HINTS[t]))

    if not info["static_screenshot"] and not info["animated_gif"]:
        print("\n  no capture tool available - install freeze (recommended) or fall back to a text snippet.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
