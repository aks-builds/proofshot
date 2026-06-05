#!/usr/bin/env python3
"""annotate.py — add a caption bar to an SVG capture (purely cosmetic).

Adds a labelled bar under a capture (e.g. "✓ all 42 tests pass"). It only adds
a frame around the image — it never alters the captured terminal text, so the
proof stays honest.

Usage:
    python annotate.py in.svg --caption "All 42 tests pass" -o out.svg [--accent "#3fb950"]

Pure standard library. No network.
"""
import argparse
import re
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0] if "/" in __file__ else ".")

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def _dims(svg_text):
    m = re.search(r"<svg\b[^>]*>", svg_text)
    tag = m.group(0)
    w = re.search(r'\bwidth="([\d.]+)', tag)
    h = re.search(r'\bheight="([\d.]+)', tag)
    if w and h:
        return float(w.group(1)), float(h.group(1))
    vb = re.search(r'viewBox="[\d.]+ [\d.]+ ([\d.]+) ([\d.]+)"', tag)
    if vb:
        return float(vb.group(1)), float(vb.group(2))
    raise ValueError("SVG has no width/height or viewBox")


def _fmt(n):
    return str(int(n)) if float(n).is_integer() else str(n)


def _escape(text):
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def add_caption(svg_text, caption, accent="#3fb950", bar=44):
    """Return a new SVG with a caption bar appended below the original."""
    w, h = _dims(svg_text)
    body = svg_text[svg_text.index("<svg"):]
    body = re.sub(r"<svg\b", '<svg x="0" y="0"', body, count=1)
    total_h = h + bar
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{th}" '
        'viewBox="0 0 {w} {th}">\n'
        '{body}\n'
        '<rect x="0" y="{by}" width="{w}" height="{bar}" fill="#161b22"/>\n'
        '<rect x="0" y="{by}" width="6" height="{bar}" fill="{accent}"/>\n'
        '<text x="20" y="{ty}" fill="#e6edf3" font-family="JetBrains Mono, monospace" '
        'font-size="15">{cap}</text>\n'
        '</svg>\n'
    ).format(w=_fmt(w), th=_fmt(total_h), body=body, by=_fmt(h), bar=_fmt(bar), accent=accent,
             ty=_fmt(h + bar / 2 + 5), cap=_escape(caption))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Add a caption bar to an SVG capture.")
    p.add_argument("input", help="input SVG")
    p.add_argument("--caption", required=True, help="caption text")
    p.add_argument("-o", "--output", required=True, help="output SVG")
    p.add_argument("--accent", default="#3fb950", help="accent color (hex)")
    args = p.parse_args(argv)

    with open(args.input, "r", encoding="utf-8-sig") as fh:
        svg = fh.read()
    out = add_caption(svg, args.caption, accent=args.accent)
    with open(args.output, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(out)
    print("annotate: wrote {}".format(args.output), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
