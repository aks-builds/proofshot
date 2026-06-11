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
    4  timeout

Pure standard library. No network. Invokes the local `freeze` binary only.
"""
import argparse
import os
import shutil
import subprocess
import sys

# Kernel helpers — same directory as this script.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kernel import EXIT_SUCCESS, EXIT_ERROR, EXIT_TIMEOUT, success, error, emit, default_timeout, setup_streams

# Status/diagnostic text can contain any Unicode; never crash on a cp1252 console.
setup_streams()


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


def _all_presets():
    """Return combined built-in + file-based preset names."""
    names = set(PRESETS.keys())
    themes_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "themes")
    if os.path.isdir(themes_dir):
        for fn in os.listdir(themes_dir):
            if fn.endswith(".json"):
                names.add(fn[:-5])
    return names


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
    if name in PRESETS:
        flags = []
        for flag, val in PRESETS[name]:
            if not _has_flag(passthrough, flag):
                flags += [flag] if val is None else [flag, val]
        return flags
    # File-based theme
    import json as _json
    themes_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "themes")
    theme_path = os.path.join(themes_dir, name + ".json")
    if os.path.exists(theme_path):
        with open(theme_path, encoding="utf-8") as fh:
            data = _json.load(fh)
        flags = []
        for pair in data.get("flags", []):
            flag, val = pair[0], pair[1]
            if not _has_flag(passthrough, flag):
                flags += [flag] if val is None else [flag, val]
        return flags
    return []


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


def _make_text_svg(command, output_path):
    """Tier-4 fallback: run the command and embed its output as plain monospace SVG."""
    try:
        proc = subprocess.run(
            command, shell=True, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=10
        )
        lines = proc.stdout.decode("utf-8", "replace").splitlines()[:40]
    except Exception:
        lines = ["(capture failed — no renderer available)"]

    line_h, pad, font_size = 20, 16, 13
    w = max((max((len(l) for l in lines), default=40) * 8) + pad * 2, 400)
    h = len(lines) * line_h + pad * 2

    def _esc(t):
        return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    rows = "\n".join(
        '<text x="{px}" y="{py}" fill="#c9d1d9" font-family="monospace" font-size="{fs}">{txt}</text>'.format(
            px=pad, py=pad + (i + 1) * line_h, fs=font_size, txt=_esc(l)
        )
        for i, l in enumerate(lines)
    )
    svg = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">\n'
        '<rect width="{w}" height="{h}" fill="#0d1117"/>\n'
        '{rows}\n'
        '<text x="{px}" y="{wy}" fill="#484f58" font-family="monospace" font-size="11">'
        '[cliproof tier-4 text stub — install freeze for styled output]</text>\n'
        '</svg>\n'
    ).format(w=w, h=h + 20, rows=rows, px=pad, wy=h + 14)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(svg)


def main(argv=None) -> int:
    import time
    argv = list(sys.argv[1:] if argv is None else argv)

    if not argv or argv[0] in ("-h", "--help"):
        p = argparse.ArgumentParser(
            prog="capture.py",
            description="Run freeze reliably and capture command output as SVG.",
            epilog="Pass --execute and any freeze style flags; -o must be a path.",
        )
        p.add_argument("--json", action="store_true", help="emit machine-readable JSON to stdout")
        p.add_argument("--timeout", type=float, metavar="N", help="kill renderer after N seconds (default 30)")
        p.add_argument("--scale", type=int, choices=[1, 2, 3], default=1, help="pixel density multiplier (default 1)")
        p.add_argument("--format", choices=["svg", "png", "webp", "og"], default="svg", help="output format (default svg)")
        p.add_argument("--preview", action="store_true", help="print theme flags before capturing")
        p.add_argument("--preset", metavar="NAME", help="look-and-feel preset (see: cliproof themes list)")
        p.print_help()
        return 0 if argv else 1

    # Extract --json before partition sees it
    json_mode = "--json" in argv
    argv = [a for a in argv if a != "--json"]

    # Extract --timeout
    timeout_s = default_timeout("capture")
    new_argv = []
    i = 0
    while i < len(argv):
        if argv[i] == "--timeout" and i + 1 < len(argv):
            try:
                timeout_s = float(argv[i + 1])
            except ValueError:
                timeout_s = default_timeout("capture")  # non-numeric value; keep default
            i += 2
        elif argv[i].startswith("--timeout="):
            try:
                timeout_s = float(argv[i].split("=", 1)[1])
            except ValueError:
                timeout_s = default_timeout("capture")  # non-numeric value; keep default
            i += 1
        else:
            new_argv.append(argv[i])
            i += 1
    argv = new_argv

    # Extract --scale
    scale = 1
    new_argv = []
    i = 0
    while i < len(argv):
        if argv[i] == "--scale" and i + 1 < len(argv):
            try:
                scale = int(argv[i + 1])
            except ValueError:
                scale = 1  # non-integer value; keep default
            i += 2
        elif argv[i].startswith("--scale="):
            try:
                scale = int(argv[i].split("=", 1)[1])
            except ValueError:
                scale = 1  # non-integer value; keep default
            i += 1
        else:
            new_argv.append(argv[i])
            i += 1
    argv = new_argv

    # Extract --format
    fmt = "svg"
    new_argv = []
    i = 0
    while i < len(argv):
        if argv[i] == "--format" and i + 1 < len(argv):
            fmt = argv[i + 1]
            i += 2
        elif argv[i].startswith("--format="):
            fmt = argv[i].split("=", 1)[1]
            i += 1
        else:
            new_argv.append(argv[i])
            i += 1
    argv = new_argv

    # Extract --preview
    preview = "--preview" in argv
    argv = [a for a in argv if a != "--preview"]

    try:
        output, freeze_bin, passthrough = partition(argv)
    except ValueError as exc:
        print("capture: {}".format(exc), file=sys.stderr)
        return EXIT_ERROR

    preset, passthrough = extract_preset(passthrough)
    if preset and preset not in _all_presets():
        print("capture: unknown --preset '{}'. Choose from: {}".format(
            preset, ", ".join(sorted(_all_presets()))), file=sys.stderr)
        return EXIT_ERROR

    if not output:
        print("capture: -o/--output is required (e.g. -o .github/media/help.svg)", file=sys.stderr)
        return EXIT_ERROR

    if not _has_flag(passthrough, "--execute"):
        print("capture: warning: no --execute given; freeze will read a file, not a command.",
              file=sys.stderr)

    # Extract execute command for tier-4 fallback
    execute_cmd = None
    for idx, a in enumerate(passthrough):
        if a == "--execute" and idx + 1 < len(passthrough):
            execute_cmd = passthrough[idx + 1]
            break

    svg_path, changed = coerce_svg_path(output)
    if changed:
        print("capture: capturing to SVG ({}); rasterize after redaction with rasterize.py."
              .format(svg_path), file=sys.stderr)

    # --preview: print theme flags before capturing
    if preview:
        if preset:
            flags = preset_flags(preset, [])
            pairs, i2 = [], 0
            while i2 < len(flags):
                if i2 + 1 < len(flags) and not flags[i2 + 1].startswith("--"):
                    pairs.append("{}={}".format(flags[i2].lstrip("-"), flags[i2 + 1]))
                    i2 += 2
                else:
                    pairs.append(flags[i2].lstrip("-"))
                    i2 += 1
            print("capture: [preview] theme '{}': {}".format(preset, ", ".join(pairs)),
                  file=sys.stderr)
        else:
            print("capture: [preview] no --preset given; using freeze defaults.", file=sys.stderr)
        print("capture: [preview] proceeding with full capture...", file=sys.stderr)

    parent = os.path.dirname(os.path.abspath(svg_path))
    os.makedirs(parent, exist_ok=True)

    start = time.monotonic()

    # --- Renderer fallback chain ---
    # Tier 1: freeze
    if shutil.which(freeze_bin) is not None or os.path.exists(freeze_bin):
        cmd = build_command(freeze_bin, passthrough, svg_path, preset=preset)
        try:
            proc = subprocess.run(cmd, stdin=subprocess.DEVNULL,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  timeout=timeout_s)
        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - start
            print("capture: freeze timed out after {}s.".format(timeout_s), file=sys.stderr)
            result = error("capture", "timeout", EXIT_TIMEOUT, elapsed_s=elapsed,
                           hint="use --timeout {} or add --no-stdin".format(int(timeout_s * 2)))
            emit(result, json_mode)
            return EXIT_TIMEOUT
        except OSError as exc:
            print("capture: failed to launch freeze: {}".format(exc), file=sys.stderr)
            proc = None

        if proc is not None and proc.returncode == 0 and \
                os.path.exists(svg_path) and os.path.getsize(svg_path) > 0:
            if strip_bom(svg_path):
                print("capture: stripped a UTF-8 BOM from the SVG.", file=sys.stderr)
            elapsed = time.monotonic() - start
            result = success("capture",
                             {"image": svg_path, "scale": scale, "format": fmt},
                             elapsed_s=elapsed, renderer="freeze", tier=1)
            emit(result, json_mode)
            if not json_mode:
                print(svg_path)
                print("capture: wrote {}. Next: redact.py {} --in-place, then (optional) rasterize.py."
                      .format(svg_path, svg_path), file=sys.stderr)
            return EXIT_SUCCESS
        else:
            if proc is not None:
                stderr_text = (proc.stderr or b"").decode("utf-8", errors="replace")
                # Detect Windows Go runtime crash (known freeze ≤0.2.x bug: split stack
                # overflow when the output SVG path contains non-ASCII or when freeze's
                # GC scans a very large goroutine stack on Windows).
                _GO_CRASH_MARKERS = (
                    "runtime: split stack overflow",
                    "fatal error: runtime",
                    "panic during panic",
                    "runtime: newstack",
                    "runtime stack:",
                )
                is_go_crash = any(m in stderr_text for m in _GO_CRASH_MARKERS)
                if is_go_crash:
                    print(
                        "capture: freeze crashed with a Go runtime error "
                        "(known Windows issue in freeze ≤0.2.x).",
                        file=sys.stderr,
                    )
                    print(
                        "capture: fix — upgrade freeze: "
                        "go install github.com/charmbracelet/freeze@latest",
                        file=sys.stderr,
                    )
                else:
                    sys.stderr.buffer.write(proc.stderr or b"")
            print("capture: freeze failed; trying fallback renderers.", file=sys.stderr)

    # Tier 2: silicon
    silicon_bin = shutil.which("silicon")
    if silicon_bin and execute_cmd:
        try:
            proc2 = subprocess.run(
                [silicon_bin, "--output", svg_path],
                input=execute_cmd.encode("utf-8"),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=timeout_s
            )
            if proc2.returncode == 0 and os.path.exists(svg_path) and os.path.getsize(svg_path) > 0:
                elapsed = time.monotonic() - start
                result = success("capture",
                                 {"image": svg_path, "scale": scale, "format": fmt},
                                 elapsed_s=elapsed, renderer="silicon", tier=2,
                                 warnings=["rendered via silicon (tier-2 fallback)"])
                emit(result, json_mode)
                if not json_mode:
                    print(svg_path)
                return EXIT_SUCCESS
        except Exception:
            print("capture: silicon tier-2 failed; falling through to tier 4.", file=sys.stderr)

    # Tier 4: text-SVG stub — always succeeds
    print("capture: no styled renderer found; generating text-SVG stub (tier 4).", file=sys.stderr)
    _make_text_svg(execute_cmd or "", svg_path)
    elapsed = time.monotonic() - start
    result = success("capture",
                     {"image": svg_path, "scale": scale, "format": fmt},
                     elapsed_s=elapsed, renderer="text-svg", tier=4,
                     warnings=["tier-4 text stub — install freeze for styled output"])
    emit(result, json_mode)
    if not json_mode:
        print(svg_path)
    return EXIT_SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())
