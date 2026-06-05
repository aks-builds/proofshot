#!/usr/bin/env python3
"""storyboard.py — stitch several SVG captures into one vertical "session" image.

Tells a story across multiple commands (init -> run -> result) as a single image
you can drop in a README. Inputs are SVGs from capture.py; output is one SVG.

Usage:
    python storyboard.py -o .github/media/session.svg step1.svg step2.svg step3.svg [--gap 16]

Pure standard library (xml via regex on freeze's well-formed SVG). No network.
"""
import argparse
import re
import sys

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def _fmt(n):
    """Render a number without a trailing '.0' for whole values."""
    return str(int(n)) if float(n).is_integer() else str(n)


def dims(svg_text):
    """Return (width, height) of an SVG from width/height attrs or viewBox."""
    m = re.search(r"<svg\b[^>]*>", svg_text)
    if not m:
        raise ValueError("no <svg> root found")
    tag = m.group(0)
    w = re.search(r'\bwidth="([\d.]+)', tag)
    h = re.search(r'\bheight="([\d.]+)', tag)
    if w and h:
        return float(w.group(1)), float(h.group(1))
    vb = re.search(r'viewBox="[\d.]+ [\d.]+ ([\d.]+) ([\d.]+)"', tag)
    if vb:
        return float(vb.group(1)), float(vb.group(2))
    raise ValueError("SVG has neither width/height nor viewBox")


def stitch(svg_texts, gap=16):
    """Vertically stack child SVGs into one outer SVG (nested <svg> with y offset)."""
    if not svg_texts:
        raise ValueError("nothing to stitch")
    sizes = [dims(t) for t in svg_texts]
    width = max(w for w, _ in sizes)
    height = sum(h for _, h in sizes) + gap * (len(svg_texts) - 1)
    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<svg xmlns="http://www.w3.org/2000/svg" '
             'width="{w}" height="{h}" viewBox="0 0 {w} {h}">'.format(w=_fmt(width), h=_fmt(height))]
    y = 0.0
    for text, (_, h) in zip(svg_texts, sizes):
        body = text[text.index("<svg"):]                 # drop xml decl / doctype
        body = re.sub(r"<svg\b", '<svg x="0" y="{}"'.format(_fmt(y)), body, count=1)
        parts.append(body)
        y += h + gap
    parts.append("</svg>")
    return "\n".join(parts)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Stitch SVG captures into one vertical session image.")
    p.add_argument("inputs", nargs="+", help="input SVG files, top to bottom")
    p.add_argument("-o", "--output", required=True, help="output SVG path")
    p.add_argument("--gap", type=int, default=16, help="vertical gap between frames (px)")
    args = p.parse_args(argv)

    texts = []
    for path in args.inputs:
        with open(path, "r", encoding="utf-8-sig") as fh:
            texts.append(fh.read())
    out = stitch(texts, gap=args.gap)
    with open(args.output, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(out)
    print("storyboard: wrote {} ({} frames)".format(args.output, len(texts)), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
