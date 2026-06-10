#!/usr/bin/env python3
"""rasterize.py — convert a (redacted) SVG capture to PNG using a local renderer.

Run this *after* `redact.py` so the raster image reflects the redactions.

`freeze`'s own PNG output is skipped on purpose: its bundled wasm rasterizer can
crash on some Windows machines (and SVG, being text, is what `redact.py` scans).
This converts the already-screened SVG using the first renderer available on the
machine, in this order:

    1. a Chromium-family browser (Chrome / Edge / Chromium) — best fidelity,
       because it honours the base64 web font `freeze` embeds in the SVG;
    2. resvg  3. rsvg-convert  4. inkscape  5. ImageMagick (`magick`).

The browser loads the SVG file directly (via a `file://` URI), so there is no
re-encoding step that could mangle UTF-8.

Usage:
    python rasterize.py .github/media/<name>.svg               # -> <name>.png
    python rasterize.py in.svg -o out.png --scale 2
    python rasterize.py in.svg --renderer chrome

Exit codes:
    0  raster image written
    1  no renderer found, or the renderer failed

Pure standard library. No network. Invokes a local renderer binary only.
"""
import argparse
import os
import pathlib
import re
import shutil
import subprocess
import sys
import os as _os_k
import sys as _sys_k
_sys_k.path.insert(0, _os_k.path.dirname(_os_k.path.abspath(__file__)))
from _kernel import EXIT_SUCCESS, EXIT_ERROR, success, error, emit, default_timeout, setup_streams

setup_streams()

_SVG_TAG = re.compile(r"<svg\b[^>]*>", re.IGNORECASE)
_DIM = lambda attr: re.compile(attr + r'\s*=\s*"([0-9]*\.?[0-9]+)', re.IGNORECASE)

# Chromium-family browsers: PATH names first, then well-known install locations
# (Chrome/Edge are usually NOT on PATH on Windows/macOS).
_BROWSER_NAMES = [
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
    "chrome", "msedge", "microsoft-edge", "microsoft-edge-stable",
]
_BROWSER_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
]
# Dedicated SVG rasterizers, in preference order.
_TOOL_NAMES = ["resvg", "rsvg-convert", "inkscape", "magick"]


def svg_pixel_size(svg_text: str, default=(1000, 600)):
    """Parse the root <svg> width/height (px). Fall back to viewBox, then default."""
    m = _SVG_TAG.search(svg_text)
    tag = m.group(0) if m else svg_text
    w = _DIM("width").search(tag)
    h = _DIM("height").search(tag)
    if w and h:
        return _ceil(float(w.group(1))), _ceil(float(h.group(1)))
    # viewBox = "minX minY width height" — take the 3rd and 4th numbers.
    vb = re.search(r'viewBox\s*=\s*"\s*[-0-9.]+\s+[-0-9.]+\s+([0-9.]+)\s+([0-9.]+)', tag)
    if vb:
        return _ceil(float(vb.group(1))), _ceil(float(vb.group(2)))
    return default


def _ceil(x: float) -> int:
    return int(x) + (1 if x > int(x) else 0)


def find_renderer(preferred=None):
    """Return (kind, path). kind is 'browser' or the tool name. None if nothing found."""
    if preferred:
        if preferred in ("chrome", "edge", "chromium", "browser"):
            path = _which_browser()
            return ("browser", path) if path else None
        path = shutil.which(preferred)
        return (preferred, path) if path else None

    path = _which_browser()
    if path:
        return ("browser", path)
    for tool in _TOOL_NAMES:
        path = shutil.which(tool)
        if path:
            return (tool, path)
    return None


def _which_browser():
    for name in _BROWSER_NAMES:
        path = shutil.which(name)
        if path:
            return path
    for path in _BROWSER_PATHS:
        if os.path.exists(path):
            return path
    return None


def build_render_command(kind, path, svg_path, out_path, size, scale):
    """Build the renderer argv. `size` is the SVG's (w, h) in px (browser only)."""
    svg_uri = pathlib.Path(svg_path).resolve().as_uri()
    dpi = str(int(round(96 * scale)))
    if kind == "browser":
        w, h = size
        return [
            path, "--headless=new", "--disable-gpu", "--hide-scrollbars",
            # We render a local, self-generated SVG; --no-sandbox lets headless
            # Chrome run in restricted CI/container environments.
            "--no-sandbox",
            "--force-device-scale-factor={}".format(scale),
            "--window-size={},{}".format(w, h),
            "--default-background-color=00000000",
            "--screenshot={}".format(out_path), svg_uri,
        ]
    if kind == "resvg":
        return [path, "--zoom", str(scale), svg_path, out_path]
    if kind == "rsvg-convert":
        return [path, "--zoom", str(scale), "--output", out_path, svg_path]
    if kind == "inkscape":
        return [path, svg_path, "--export-type=png",
                "--export-filename={}".format(out_path), "--export-dpi={}".format(dpi)]
    if kind == "magick":
        return [path, "-density", dpi, "-background", "none", svg_path, out_path]
    raise ValueError("unknown renderer kind: {}".format(kind))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Convert a redacted SVG capture to PNG.")
    p.add_argument("svg", help="path to the (already redacted) .svg")
    p.add_argument("-o", "--output", help="output image path (default: <svg>.png)")
    p.add_argument("--scale", type=float, default=2.0, help="device scale factor (default 2 = crisp/retina)")
    p.add_argument("--renderer", default="auto",
                   help="auto | chrome | edge | chromium | resvg | rsvg-convert | inkscape | magick")
    p.add_argument("--json", action="store_true", help="emit machine-readable JSON to stdout")
    p.add_argument("--timeout", type=float, default=default_timeout("rasterize"),
                   help="timeout in seconds")
    args = p.parse_args(argv)

    if not os.path.exists(args.svg):
        print("rasterize: input not found: {}".format(args.svg), file=sys.stderr)
        emit(error("rasterize", "no_renderer", EXIT_ERROR,
                   hint="install resvg, inkscape, or imagemagick"), args.json)
        return EXIT_ERROR
    # Absolute path: headless browsers resolve --screenshot against their own cwd.
    out_path = os.path.abspath(args.output or (os.path.splitext(args.svg)[0] + ".png"))

    # utf-8-sig so a BOM'd SVG doesn't confuse the dimension parse.
    with open(args.svg, "r", encoding="utf-8-sig", errors="replace") as fh:
        svg_text = fh.read()
    size = svg_pixel_size(svg_text)

    preferred = None if args.renderer == "auto" else args.renderer
    found = find_renderer(preferred)
    if not found:
        hint = ("install one of: a Chromium browser, resvg, rsvg-convert, inkscape, or "
                "ImageMagick — or embed the .svg directly (GitHub renders it).")
        if preferred:
            print("rasterize: renderer '{}' not found. {}".format(preferred, hint), file=sys.stderr)
        else:
            print("rasterize: no SVG renderer found. {}".format(hint), file=sys.stderr)
        emit(error("rasterize", "no_renderer", EXIT_ERROR,
                   hint="install resvg, inkscape, or imagemagick"), args.json)
        return EXIT_ERROR

    kind, path = found
    parent = os.path.dirname(os.path.abspath(out_path))
    os.makedirs(parent, exist_ok=True)

    cmd = build_render_command(kind, path, args.svg, out_path, size, args.scale)
    try:
        proc = subprocess.run(cmd, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as exc:
        print("rasterize: failed to launch {}: {}".format(kind, exc), file=sys.stderr)
        emit(error("rasterize", "no_renderer", EXIT_ERROR,
                   hint="install resvg, inkscape, or imagemagick"), args.json)
        return EXIT_ERROR

    # Browsers (and some tools) chatter on stderr and still succeed; trust the file.
    if not (os.path.exists(out_path) and os.path.getsize(out_path) > 0):
        sys.stderr.buffer.write(proc.stderr or b"")
        print("\nrasterize: {} produced no output (exit {}).".format(kind, proc.returncode),
              file=sys.stderr)
        emit(error("rasterize", "no_renderer", EXIT_ERROR,
                   hint="install resvg, inkscape, or imagemagick"), args.json)
        return EXIT_ERROR

    print(out_path)
    print("rasterize: wrote {} via {} (scale {}).".format(out_path, kind, args.scale),
          file=sys.stderr)
    emit(success("rasterize", {"output": out_path}), args.json)
    return EXIT_SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())
