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


def add_badge(svg_text, verdict):
    """Add a pass/fail corner badge (top-right) as an SVG <g> layer."""
    w, h = _dims(svg_text)
    color = "#238636" if verdict.lower() == "pass" else "#da3633"
    label = "✓ PASS" if verdict.lower() == "pass" else "✗ FAIL"
    badge_w, badge_h = 72, 24
    x = w - badge_w - 8
    y = 8
    overlay = (
        '<g id="cliproof-badge">'
        '<rect x="{x}" y="{y}" width="{bw}" height="{bh}" rx="4" fill="{c}"/>'
        '<text x="{tx}" y="{ty}" fill="#ffffff" font-family="JetBrains Mono, monospace" '
        'font-size="12" font-weight="bold">{lbl}</text>'
        '</g>'
    ).format(x=_fmt(x), y=_fmt(y), bw=badge_w, bh=badge_h, c=color,
             tx=_fmt(x + 8), ty=_fmt(y + 16), lbl=_escape(label))
    return svg_text.replace("</svg>", overlay + "\n</svg>")


def add_stamp(svg_text, stamp_text):
    """Add a version/date watermark to the bottom-right corner."""
    w, h = _dims(svg_text)
    overlay = (
        '<g id="cliproof-stamp">'
        '<text x="{x}" y="{y}" fill="#484f58" font-family="JetBrains Mono, monospace" '
        'font-size="11" text-anchor="end">{txt}</text>'
        '</g>'
    ).format(x=_fmt(w - 8), y=_fmt(h - 8), txt=_escape(stamp_text))
    return svg_text.replace("</svg>", overlay + "\n</svg>")


def add_ci_ribbon(svg_text, ribbon_text):
    """Add a ribbon bar across the top of the SVG."""
    w, _ = _dims(svg_text)
    ribbon_h = 22
    overlay = (
        '<g id="cliproof-ribbon">'
        '<rect x="0" y="0" width="{w}" height="{rh}" fill="#1f6feb"/>'
        '<text x="10" y="{ty}" fill="#ffffff" font-family="JetBrains Mono, monospace" '
        'font-size="12">{txt}</text>'
        '</g>'
    ).format(w=_fmt(w), rh=ribbon_h, ty=ribbon_h - 6, txt=_escape(ribbon_text))
    return svg_text.replace("</svg>", overlay + "\n</svg>")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Add overlays to an SVG capture.")
    p.add_argument("input", help="input SVG (or '-' for stdin)")
    p.add_argument("--caption", default=None, help="caption bar text")
    p.add_argument("--badge", choices=["pass", "fail"], default=None,
                   help="corner badge: pass (green) or fail (red)")
    p.add_argument("--stamp", default=None, help="bottom-right version watermark text")
    p.add_argument("--ci-ribbon", dest="ci_ribbon", default=None, help="top ribbon bar text")
    p.add_argument("-o", "--output", required=True, help="output SVG")
    p.add_argument("--accent", default="#3fb950", help="caption accent color (hex)")
    args = p.parse_args(argv)

    if args.input == "-":
        svg = sys.stdin.read()
    else:
        with open(args.input, "r", encoding="utf-8-sig") as fh:
            svg = fh.read()

    if not any([args.caption, args.badge, args.stamp, args.ci_ribbon]):
        print("annotate: no overlay flags given. Use --caption, --badge, --stamp, or --ci-ribbon.",
              file=sys.stderr)
        return 1

    out = svg
    if args.caption:
        out = add_caption(out, args.caption, accent=args.accent)
    if args.badge:
        out = add_badge(out, args.badge)
    if args.stamp:
        out = add_stamp(out, args.stamp)
    if args.ci_ribbon:
        out = add_ci_ribbon(out, args.ci_ribbon)

    with open(args.output, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(out)
    print("annotate: wrote {}".format(args.output), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
