#!/usr/bin/env python3
"""capture.py — run `freeze` reliably and capture a command's real output as SVG.

This is a thin, deterministic wrapper around the `freeze` binary. Call it
instead of `freeze` directly; it fixes three failure modes that otherwise bite
in non-interactive / agent shells:

  * **Hang on inherited stdin.** Run with a closed stdin (`DEVNULL`). When
    `freeze` inherits an open, non-tty stdin pipe (exactly what a CLI agent or
    CI step provides) it blocks forever probing the terminal. Closing stdin is
    the single most important fix and it is applied unconditionally.
  * **PNG rasterizer crash.** Capture to **SVG**, which is rendered natively by
    `freeze` and never invokes its bundled wasm PNG rasterizer (that component
    can segfault on some Windows machines). SVG is also text, so `redact.py`
    can scan it, and GitHub renders it directly. Convert to PNG *after*
    redaction with `rasterize.py` if a raster image is required.
  * **Garbled output.** Force `--language ansi` for `--execute` captures so the
    terminal output is lexed correctly; the SVG `freeze` writes is UTF-8.

Usage:
    python capture.py --execute "<command>" -o .github/media/<name>.svg [freeze flags...]

Any flag this wrapper does not own is forwarded verbatim to `freeze`
(`--window`, `--theme`, `--background`, `--padding`, `--font.family`, ...).
Owned flags: `-o/--output` (coerced to `.svg`) and `--freeze-bin`.

Exit codes:
    0  SVG written
    1  freeze not found, freeze failed, or no output produced

Pure standard library. No network. Invokes the local `freeze` binary only.
"""
import argparse
import os
import shutil
import subprocess
import sys

# Status/diagnostic text can contain any Unicode; never crash on a cp1252 console.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def coerce_svg_path(path: str):
    """Return (svg_path, changed). Force an .svg extension; PNG/WebP come later."""
    root, ext = os.path.splitext(path)
    if ext.lower() == ".svg":
        return path, False
    return root + ".svg", True


def partition(argv):
    """Split argv into (output, freeze_bin, passthrough).

    `output` and `--freeze-bin` are consumed here; everything else (including
    `--execute` and its value) is forwarded to `freeze` untouched.
    """
    output = None
    freeze_bin = "freeze"
    passthrough = []
    i = 0
    n = len(argv)
    while i < n:
        a = argv[i]
        if a in ("-o", "--output"):
            if i + 1 >= n:
                raise ValueError("{} requires a value".format(a))
            output = argv[i + 1]
            i += 2
            continue
        if a.startswith("--output="):
            output = a.split("=", 1)[1]
            i += 1
            continue
        if a == "--freeze-bin":
            if i + 1 >= n:
                raise ValueError("--freeze-bin requires a value")
            freeze_bin = argv[i + 1]
            i += 2
            continue
        passthrough.append(a)
        i += 1
    return output, freeze_bin, passthrough


# Named look-and-feel presets. Each is a list of (flag, value) pairs; value
# None means a boolean flag. A user-supplied flag always wins over the preset.
PRESETS = {
    "macos": [("--window", None), ("--theme", "dracula"), ("--background", "#0d1117"),
              ("--border.radius", "8"), ("--padding", "24"), ("--margin", "20"),
              ("--shadow.blur", "24"), ("--shadow.y", "12")],
    "github-dark": [("--window", None), ("--theme", "github"), ("--background", "#0d1117"),
                    ("--border.radius", "8"), ("--padding", "24"), ("--margin", "20")],
    "nord": [("--window", None), ("--theme", "nord"), ("--background", "#2e3440"),
             ("--border.radius", "8"), ("--padding", "24"), ("--margin", "20")],
    "iterm": [("--window", None), ("--theme", "catppuccin-mocha"), ("--background", "#1e1e2e"),
              ("--border.radius", "10"), ("--padding", "24"), ("--margin", "20"),
              ("--shadow.blur", "24"), ("--shadow.y", "12")],
    "win11": [("--theme", "github"), ("--background", "#0c0c0c"), ("--border.radius", "0"),
              ("--border.width", "1"), ("--border.color", "#3a3a3a"),
              ("--padding", "20"), ("--margin", "12")],
}


def _has_flag(passthrough, name):
    return any(a == name or a.startswith(name + "=") for a in passthrough)


def extract_preset(passthrough):
    """Pull a `--preset NAME` / `--preset=NAME` out of passthrough.

    Returns (preset_name_or_None, passthrough_without_preset). freeze doesn't
    know --preset, so it must be consumed here before the command is built.
    """
    out, preset, i, n = [], None, 0, len(passthrough)
    while i < n:
        a = passthrough[i]
        if a == "--preset":
            if i + 1 < n:
                preset = passthrough[i + 1]
                i += 2
                continue
            i += 1
            continue
        if a.startswith("--preset="):
            preset = a.split("=", 1)[1]
            i += 1
            continue
        out.append(a)
        i += 1
    return preset, out


def preset_flags(name, passthrough):
    """Flags a preset contributes, skipping any the user already set."""
    flags = []
    for flag, val in PRESETS.get(name, []):
        if not _has_flag(passthrough, flag):
            flags += [flag] if val is None else [flag, val]
    return flags


def needs_language(passthrough) -> bool:
    """`--execute` output is ANSI; inject a lexer if the caller didn't pick one."""
    return _has_flag(passthrough, "--execute") and not _has_flag(passthrough, "--language")


def strip_bom(path) -> bool:
    """Drop a leading UTF-8 BOM if the tool emitted one. Returns True if stripped.

    A BOM before `<?xml`/`<svg` can break strict SVG parsers and some renderers,
    so we guarantee the captured artifact starts at the markup. Rewrites only
    when a BOM is actually present.
    """
    with open(path, "rb") as fh:
        data = fh.read()
    if data[:3] == b"\xef\xbb\xbf":
        with open(path, "wb") as fh:
            fh.write(data[3:])
        return True
    return False


def build_command(freeze_bin, passthrough, svg_path, preset=None):
    """Assemble the final freeze argv (preset + language injected, output forced to SVG)."""
    cmd = [freeze_bin]
    if preset:
        cmd += preset_flags(preset, passthrough)
    cmd += list(passthrough)
    if needs_language(passthrough):
        cmd += ["--language", "ansi"]
    cmd += ["--output", svg_path]
    return cmd


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    # A tiny parser purely for --help; real parsing is in partition().
    if not argv or argv[0] in ("-h", "--help"):
        argparse.ArgumentParser(
            prog="capture.py",
            description="Run freeze reliably and capture command output as SVG.",
            epilog="Pass --execute and any freeze style flags; -o must be a path.",
        ).print_help()
        return 0 if argv else 1

    try:
        output, freeze_bin, passthrough = partition(argv)
    except ValueError as exc:
        print("capture: {}".format(exc), file=sys.stderr)
        return 1

    preset, passthrough = extract_preset(passthrough)
    if preset and preset not in PRESETS:
        print("capture: unknown --preset '{}'. Choose from: {}".format(
            preset, ", ".join(sorted(PRESETS))), file=sys.stderr)
        return 1

    if not output:
        print("capture: -o/--output is required (e.g. -o .github/media/help.svg)", file=sys.stderr)
        return 1
    if not _has_flag(passthrough, "--execute"):
        print("capture: warning: no --execute given; freeze will read a file, not a command.",
              file=sys.stderr)

    svg_path, changed = coerce_svg_path(output)
    if changed:
        print("capture: capturing to SVG ({}); rasterize after redaction with rasterize.py."
              .format(svg_path), file=sys.stderr)

    if shutil.which(freeze_bin) is None and not os.path.exists(freeze_bin):
        print("capture: '{}' not found. Install freeze (see references/tooling.md) "
              "or pass --freeze-bin.".format(freeze_bin), file=sys.stderr)
        return 1

    parent = os.path.dirname(os.path.abspath(svg_path))
    os.makedirs(parent, exist_ok=True)

    cmd = build_command(freeze_bin, passthrough, svg_path, preset=preset)
    try:
        # stdin=DEVNULL is the fix: never let freeze block on an inherited pipe.
        proc = subprocess.run(cmd, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as exc:
        print("capture: failed to launch freeze: {}".format(exc), file=sys.stderr)
        return 1

    if proc.returncode != 0:
        sys.stderr.buffer.write(proc.stderr or b"")
        print("\ncapture: freeze exited {}.".format(proc.returncode), file=sys.stderr)
        return 1
    if not (os.path.exists(svg_path) and os.path.getsize(svg_path) > 0):
        print("capture: freeze produced no output at {}.".format(svg_path), file=sys.stderr)
        return 1

    if strip_bom(svg_path):
        print("capture: stripped a UTF-8 BOM from the SVG.", file=sys.stderr)

    print(svg_path)
    print("capture: wrote {}. Next: redact.py {} --in-place, then (optional) rasterize.py."
          .format(svg_path, svg_path), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
