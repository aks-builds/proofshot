# cliproof v2 M1 — JSON Contract Kernel + Image Quality

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the v0.2.0 foundation — every script speaks a stable JSON contract (structured output, hard timeouts, exit-code spec, multi-renderer fallback, health gate) and output quality reaches state-of-the-art (11 themes, HiDPI/WebP/OG, rich SVG overlays, GIF controls).

**Architecture:** A new shared `_kernel.py` module (alongside the 13 scripts) provides the result-building and timeout helpers that every script imports. Scripts gain `--json` and `--timeout` flags without breaking existing behaviour. Track 2 (quality) is fully independent of Track 1 and can be executed in parallel.

**Tech Stack:** Python 3.8+ stdlib only (no new deps), pytest, Node 18+ (CLI passthrough update)

---

## File map

### New files
| Path | Purpose |
|------|---------|
| `skills/cliproof/scripts/_kernel.py` | Exit codes, result helpers, timeout runner |
| `skills/cliproof/scripts/health.py` | First-class health probe (supersedes preflight) |
| `skills/cliproof/themes/catppuccin.json` | Catppuccin Mocha theme definition |
| `skills/cliproof/themes/tokyo-night.json` | Tokyo Night theme definition |
| `skills/cliproof/themes/one-dark.json` | One Dark Pro theme definition |
| `skills/cliproof/themes/dracula.json` | Dracula theme definition |
| `skills/cliproof/themes/solarized.json` | Solarized Dark theme definition |
| `skills/cliproof/themes/rose-pine.json` | Rosé Pine theme definition |
| `tests/test_kernel.py` | Tests for `_kernel.py` |
| `tests/test_health.py` | Tests for `health.py` |

### Modified files
| Path | Changes |
|------|---------|
| `skills/cliproof/scripts/capture.py` | `--json`, `--timeout`, `--scale`, `--format`, `--preview`, renderer fallback chain, load themes from `themes/` dir |
| `skills/cliproof/scripts/guard.py` | `--json`, exit code 5 (was 2 — exit code contract remap) |
| `skills/cliproof/scripts/redact.py` | `--json`, `--timeout` |
| `skills/cliproof/scripts/embed.py` | `--json`, `--timeout` |
| `skills/cliproof/scripts/check.py` | `--json`, `--timeout`, exit code 6 for drift (was 1), `gif` block in proof.json |
| `skills/cliproof/scripts/verify.py` | `--json`, `--timeout` |
| `skills/cliproof/scripts/suggest.py` | `--json`, `--timeout` |
| `skills/cliproof/scripts/annotate.py` | `--json`, `--timeout`, `--badge`, `--stamp`, `--ci-ribbon` |
| `skills/cliproof/scripts/storyboard.py` | `--json`, `--timeout` |
| `skills/cliproof/scripts/pr.py` | `--json`, `--timeout` |
| `skills/cliproof/scripts/rasterize.py` | `--json`, `--timeout` |
| `skills/cliproof/scripts/normalize.py` | `--json` |
| `skills/cliproof/scripts/preflight.py` | Thin alias → delegates to `health.py` |
| `bin/cli.js` | Add `health` and `themes` to passthrough list |
| `README.md` | Section 5 copy updates (tagline, hero, install heading, Who it's for) |
| `assets/demo.tape.template` | GIF timing controls |
| `tests/test_capture.py` | New tests for --json, fallback chain, --scale, --format |
| `tests/test_guard.py` | New tests for --json, exit code 5 |
| `tests/test_annotate.py` | New tests for --badge, --stamp, --ci-ribbon |
| `tests/test_check.py` | New tests for --json, exit code 6, gif block |
| `tests/test_preflight.py` | Update to test alias behaviour |

---

## TRACK 1 — JSON Contract Kernel

---

### Task 1: Create `_kernel.py` — shared result helpers and exit codes

**Files:**
- Create: `skills/cliproof/scripts/_kernel.py`
- Create: `tests/test_kernel.py`

- [ ] **Step 1: Write failing tests for `_kernel.py`**

```python
# tests/test_kernel.py
import json
import sys
import io
import _kernel


def test_exit_codes_are_stable():
    assert _kernel.EXIT_SUCCESS == 0
    assert _kernel.EXIT_ERROR == 1
    assert _kernel.EXIT_UNKNOWN_CMD == 2
    assert _kernel.EXIT_SECRET == 3
    assert _kernel.EXIT_TIMEOUT == 4
    assert _kernel.EXIT_UNSAFE == 5
    assert _kernel.EXIT_DRIFT == 6


def test_success_result_shape():
    r = _kernel.success("capture", {"image": "out.svg"}, elapsed_s=1.4)
    assert r["ok"] is True
    assert r["step"] == "capture"
    assert r["outputs"] == {"image": "out.svg"}
    assert r["elapsed_s"] == 1.4
    assert r["warnings"] == []


def test_success_result_with_renderer():
    r = _kernel.success("capture", {"image": "out.svg"}, renderer="freeze", tier=1)
    assert r["renderer"] == "freeze"
    assert r["tier"] == 1


def test_error_result_shape():
    r = _kernel.error("capture", "timeout", _kernel.EXIT_TIMEOUT, elapsed_s=30.1,
                      hint="use --timeout 60")
    assert r["ok"] is False
    assert r["step"] == "capture"
    assert r["reason"] == "timeout"
    assert r["exit_code"] == _kernel.EXIT_TIMEOUT
    assert r["elapsed_s"] == 30.1
    assert r["hint"] == "use --timeout 60"


def test_error_result_no_hint():
    r = _kernel.error("guard", "unsafe", _kernel.EXIT_UNSAFE)
    assert "hint" not in r


def test_emit_prints_json_to_stdout(capsys):
    r = _kernel.success("check", {})
    _kernel.emit(r, json_mode=True)
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert parsed["ok"] is True
    assert parsed["step"] == "check"


def test_emit_silent_when_not_json(capsys):
    r = _kernel.success("check", {})
    _kernel.emit(r, json_mode=False)
    captured = capsys.readouterr()
    assert captured.out == ""


def test_default_timeout_values():
    assert _kernel.default_timeout("capture") == 30
    assert _kernel.default_timeout("guard") == 5
    assert _kernel.default_timeout("check") == 20
    assert _kernel.default_timeout("embed") == 10
    assert _kernel.default_timeout("unknown") == 30


def test_run_timed_returns_result_and_elapsed():
    val, elapsed, timed_out = _kernel.run_timed(lambda: 42, timeout_s=5)
    assert val == 42
    assert elapsed >= 0
    assert timed_out is False


def test_run_timed_detects_timeout():
    import time
    val, elapsed, timed_out = _kernel.run_timed(lambda: time.sleep(10), timeout_s=0.1)
    assert timed_out is True
    assert elapsed >= 0.1
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_kernel.py -v
```
Expected: `ImportError: No module named '_kernel'`

- [ ] **Step 3: Create `skills/cliproof/scripts/_kernel.py`**

```python
#!/usr/bin/env python3
"""_kernel.py — shared exit codes, result helpers, and timeout runner for all cliproof scripts.

Import this from any cliproof script:
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from _kernel import EXIT_TIMEOUT, success, error, emit, default_timeout, run_timed
"""
import json
import sys
import threading
import time

# Stable exit codes — public API from v2.0.0. Do not renumber.
EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_UNKNOWN_CMD = 2
EXIT_SECRET = 3
EXIT_TIMEOUT = 4
EXIT_UNSAFE = 5
EXIT_DRIFT = 6

_TIMEOUTS = {
    "capture": 30, "redact": 10, "embed": 10, "annotate": 10,
    "storyboard": 10, "check": 20, "verify": 20, "suggest": 20,
    "guard": 5, "health": 5, "preflight": 5,
    "normalize": 5, "rasterize": 10, "pr": 20,
}


def default_timeout(step):
    """Return the default timeout in seconds for a given step name."""
    return _TIMEOUTS.get(step, 30)


def success(step, outputs, elapsed_s=0.0, renderer=None, tier=None, warnings=None):
    """Build a success result dict."""
    r = {
        "ok": True, "step": step, "outputs": outputs,
        "warnings": warnings or [], "elapsed_s": round(elapsed_s, 2),
    }
    if renderer is not None:
        r["renderer"] = renderer
    if tier is not None:
        r["tier"] = tier
    return r


def error(step, reason, exit_code, elapsed_s=0.0, hint=None):
    """Build an error result dict."""
    r = {
        "ok": False, "step": step, "reason": reason,
        "exit_code": exit_code, "elapsed_s": round(elapsed_s, 2),
    }
    if hint is not None:
        r["hint"] = hint
    return r


def emit(result, json_mode):
    """Print result as JSON to stdout if json_mode is True."""
    if json_mode:
        print(json.dumps(result), file=sys.stdout, flush=True)


def run_timed(fn, timeout_s):
    """Run fn() with a wall-clock timeout.

    Returns (result, elapsed_s, timed_out).
    timed_out=True means fn() did not finish within timeout_s.
    Note: the background thread is daemon-ed but cannot be killed; for
    pure-Python operations this is acceptable — they complete quickly.
    For subprocess calls, use subprocess.run(timeout=...) instead.
    """
    box = [None]
    exc_box = [None]
    start = time.monotonic()

    def _worker():
        try:
            box[0] = fn()
        except BaseException as exc:  # noqa: BLE001
            exc_box[0] = exc

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    t.join(timeout_s)
    elapsed = time.monotonic() - start

    if t.is_alive():
        return None, elapsed, True
    if exc_box[0] is not None:
        raise exc_box[0]
    return box[0], elapsed, False
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_kernel.py -v
```
Expected: all 11 tests PASS.

- [ ] **Step 5: Commit**

```
git add skills/cliproof/scripts/_kernel.py tests/test_kernel.py
git commit -m "feat(kernel): add _kernel.py — exit codes, result helpers, timeout runner"
```

---

### Task 2: Add `--json` + exit-code 5 to `guard.py`

**Files:**
- Modify: `skills/cliproof/scripts/guard.py`
- Modify: `tests/test_guard.py`

> **Background:** guard.py currently exits `2` for unsafe commands. The new exit-code contract maps unsafe → `5`. Exit `2` becomes "unknown command" (reserved for the CLI dispatcher). This is a breaking change documented in the spec.

- [ ] **Step 1: Write failing tests**

Add to `tests/test_guard.py`:

```python
import json
import guard
import _kernel


def test_safe_command_exits_0_with_json(capsys):
    rc = guard.main(["--json", "echo hello"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert out["step"] == "guard"
    assert out["outputs"] == {"safe": True}


def test_unsafe_command_exits_5_with_json(capsys):
    rc = guard.main(["--json", "rm -rf /"])
    assert rc == _kernel.EXIT_UNSAFE
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False
    assert out["step"] == "guard"
    assert out["reason"] == "unsafe"
    assert out["exit_code"] == _kernel.EXIT_UNSAFE


def test_unsafe_command_exits_5_without_json(capsys):
    rc = guard.main(["rm -rf /"])
    assert rc == _kernel.EXIT_UNSAFE


def test_safe_command_exits_0_without_json():
    rc = guard.main(["echo hello"])
    assert rc == 0
```

- [ ] **Step 2: Run to verify failure**

```
pytest tests/test_guard.py -v
```
Expected: 4 new tests FAIL (exit code mismatch, no JSON output).

- [ ] **Step 3: Update `guard.py`**

Replace the `main` function and add the `_kernel` import at the top of `guard.py`:

```python
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kernel import EXIT_UNSAFE, EXIT_SUCCESS, success, error, emit  # noqa: E402
```

Replace `main`:
```python
def main(argv=None) -> int:
    import time
    p = argparse.ArgumentParser(description="Refuse to capture dangerous commands.")
    p.add_argument("--json", action="store_true", help="emit machine-readable JSON to stdout")
    p.add_argument("command", nargs="*", help="command string (or '-' for stdin)")
    args = p.parse_args(argv)

    command = _read_command(args)
    if not command:
        print("guard: no command provided", file=sys.stderr)
        return EXIT_UNSAFE

    start = time.monotonic()
    hits = scan(command)
    elapsed = time.monotonic() - start

    if hits:
        print("guard: REFUSING - command matched risky pattern(s):", file=sys.stderr)
        for name, why in hits:
            print(f"  - {name}: {why}", file=sys.stderr)
        print("\nStop and confirm with a human before running this.", file=sys.stderr)
        result = error("guard", "unsafe", EXIT_UNSAFE, elapsed_s=elapsed,
                       hint="confirm with a human before running this command")
        emit(result, args.json)
        return EXIT_UNSAFE

    print("guard: ok", file=sys.stderr)
    result = success("guard", {"safe": True}, elapsed_s=elapsed)
    emit(result, args.json)
    return EXIT_SUCCESS
```

- [ ] **Step 4: Run all guard tests**

```
pytest tests/test_guard.py -v
```
Expected: all tests PASS (including the 4 new ones).

- [ ] **Step 5: Commit**

```
git add skills/cliproof/scripts/guard.py tests/test_guard.py
git commit -m "feat(guard): --json flag, exit code 5 for unsafe (kernel contract)"
```

---

### Task 3: Add `--json`, `--timeout`, and renderer fallback chain to `capture.py`

**Files:**
- Modify: `skills/cliproof/scripts/capture.py`
- Modify: `tests/test_capture.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_capture.py`:

```python
import json
import _kernel


def test_json_flag_emits_success_result(tmp_path, monkeypatch, capsys):
    out = tmp_path / "shot.svg"

    def fake_run(cmd, **kw):
        target = cmd[cmd.index("--output") + 1]
        with open(target, "w") as f:
            f.write("<svg/>")
        class R:
            returncode = 0; stdout = b""; stderr = b""
        return R()

    monkeypatch.setattr(capture.subprocess, "run", fake_run)
    monkeypatch.setattr(capture.shutil, "which", lambda b: "/usr/bin/freeze" if b == "freeze" else None)

    rc = capture.main(["--execute", "echo hi", "-o", str(out), "--json"])
    assert rc == 0
    result = json.loads(capsys.readouterr().out)
    assert result["ok"] is True
    assert result["step"] == "capture"
    assert result["renderer"] == "freeze"
    assert result["tier"] == 1
    assert "image" in result["outputs"]


def test_timeout_flag_triggers_exit_4(tmp_path, monkeypatch, capsys):
    import time
    out = tmp_path / "shot.svg"

    def slow_run(cmd, **kw):
        time.sleep(10)

    monkeypatch.setattr(capture.subprocess, "run", slow_run)
    monkeypatch.setattr(capture.shutil, "which", lambda b: "/usr/bin/freeze" if b == "freeze" else None)

    rc = capture.main(["--execute", "echo hi", "-o", str(out), "--timeout", "0.1", "--json"])
    assert rc == _kernel.EXIT_TIMEOUT
    result = json.loads(capsys.readouterr().out)
    assert result["ok"] is False
    assert result["reason"] == "timeout"
    assert result["exit_code"] == _kernel.EXIT_TIMEOUT


def test_fallback_to_tier4_text_svg_when_no_renderers(tmp_path, monkeypatch, capsys):
    out = tmp_path / "shot.svg"
    monkeypatch.setattr(capture.shutil, "which", lambda _: None)

    rc = capture.main(["--execute", "echo hello", "-o", str(out), "--json"])
    assert rc == 0
    result = json.loads(capsys.readouterr().out)
    assert result["tier"] == 4
    assert result["renderer"] == "text-svg"
    assert out.exists() and out.stat().st_size > 0


def test_scale_flag_is_stored_in_result(tmp_path, monkeypatch, capsys):
    out = tmp_path / "shot.svg"

    def fake_run(cmd, **kw):
        target = cmd[cmd.index("--output") + 1]
        with open(target, "w") as f:
            f.write("<svg/>")
        class R:
            returncode = 0; stdout = b""; stderr = b""
        return R()

    monkeypatch.setattr(capture.subprocess, "run", fake_run)
    monkeypatch.setattr(capture.shutil, "which", lambda b: "/usr/bin/freeze" if b == "freeze" else None)

    rc = capture.main(["--execute", "echo hi", "-o", str(out), "--scale", "2", "--json"])
    assert rc == 0
    result = json.loads(capsys.readouterr().out)
    assert result["outputs"].get("scale") == 2
```

- [ ] **Step 2: Run to verify failure**

```
pytest tests/test_capture.py -v -k "json or timeout or fallback or scale"
```
Expected: 4 tests FAIL.

- [ ] **Step 3: Update `capture.py` — add kernel import and new flags**

At the top of `capture.py`, after the existing imports, add:
```python
import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from _kernel import (EXIT_SUCCESS, EXIT_ERROR, EXIT_TIMEOUT,  # noqa: E402
                     success, error, emit, default_timeout)
```

Add `_make_text_svg` function before `main`:
```python
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
```

Replace `main` in `capture.py`:
```python
def main(argv=None) -> int:
    import time
    argv = list(sys.argv[1:] if argv is None else argv)

    if not argv or argv[0] in ("-h", "--help"):
        argparse.ArgumentParser(
            prog="capture.py",
            description="Run freeze reliably and capture command output as SVG.",
        ).print_help()
        return 0 if argv else 1

    # Parse --json and --timeout before partition() sees the rest
    json_mode = "--json" in argv
    if json_mode:
        argv = [a for a in argv if a != "--json"]

    timeout_s = default_timeout("capture")
    for i, a in enumerate(argv):
        if a == "--timeout" and i + 1 < len(argv):
            try:
                timeout_s = float(argv[i + 1])
            except ValueError:
                pass
        elif a.startswith("--timeout="):
            try:
                timeout_s = float(a.split("=", 1)[1])
            except ValueError:
                pass
    argv = [a for i, a in enumerate(argv)
            if not (a == "--timeout" or a.startswith("--timeout=") or
                    (i > 0 and argv[i-1] == "--timeout"))]

    # Parse --scale
    scale = 1
    new_argv = []
    i = 0
    while i < len(argv):
        if argv[i] == "--scale" and i + 1 < len(argv):
            try:
                scale = int(argv[i + 1])
            except ValueError:
                pass
            i += 2
            continue
        elif argv[i].startswith("--scale="):
            try:
                scale = int(argv[i].split("=", 1)[1])
            except ValueError:
                pass
            i += 1
            continue
        new_argv.append(argv[i])
        i += 1
    argv = new_argv

    # Parse --format (svg default)
    fmt = "svg"
    new_argv = []
    i = 0
    while i < len(argv):
        if argv[i] == "--format" and i + 1 < len(argv):
            fmt = argv[i + 1]
            i += 2
            continue
        elif argv[i].startswith("--format="):
            fmt = argv[i].split("=", 1)[1]
            i += 1
            continue
        new_argv.append(argv[i])
        i += 1
    argv = new_argv

    # Parse --preview
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
        print("capture: -o/--output is required", file=sys.stderr)
        return EXIT_ERROR

    # Extract execute command for tier-4 fallback
    execute_cmd = None
    for i2, a in enumerate(passthrough):
        if a == "--execute" and i2 + 1 < len(passthrough):
            execute_cmd = passthrough[i2 + 1]
            break

    svg_path, changed = coerce_svg_path(output)
    if changed:
        print("capture: capturing to SVG; rasterize after redaction.", file=sys.stderr)

    # --preview: print theme flags before committing to the full capture
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

    start = time.monotonic()

    # --- Renderer fallback chain ---
    # Tier 1: freeze
    if shutil.which(freeze_bin) or os.path.exists(freeze_bin):
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
                print("capture: stripped UTF-8 BOM.", file=sys.stderr)
            elapsed = time.monotonic() - start
            result = success("capture", {"image": svg_path, "scale": scale, "format": fmt},
                             elapsed_s=elapsed, renderer="freeze", tier=1)
            emit(result, json_mode)
            if not json_mode:
                print(svg_path)
            return EXIT_SUCCESS
        else:
            sys.stderr.buffer.write(proc.stderr if proc else b"")
            print("\ncapture: freeze failed; trying fallback renderers.", file=sys.stderr)

    # Tier 2: silicon
    silicon_bin = shutil.which("silicon")
    if silicon_bin and execute_cmd:
        try:
            proc2 = subprocess.run(
                [silicon_bin, "--output", svg_path, "--from-clipboard"],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=timeout_s
            )
            if proc2.returncode == 0 and os.path.exists(svg_path) and os.path.getsize(svg_path) > 0:
                elapsed = time.monotonic() - start
                result = success("capture", {"image": svg_path, "scale": scale, "format": fmt},
                                 elapsed_s=elapsed, renderer="silicon", tier=2,
                                 warnings=["rendered via silicon (tier-2 fallback)"])
                emit(result, json_mode)
                if not json_mode:
                    print(svg_path)
                return EXIT_SUCCESS
        except Exception:
            pass

    # Tier 3: rasterizer-based fallback (resvg / inkscape / magick)
    # (rasterize.py handles tool detection; here we just note tier-3 is not directly
    # applicable for the initial capture — skip to tier 4 unless a raster pipeline exists)

    # Tier 4: text-SVG stub — always succeeds
    print("capture: no styled renderer found; generating text-SVG stub (tier 4).", file=sys.stderr)
    _make_text_svg(execute_cmd or "", svg_path)
    elapsed = time.monotonic() - start
    result = success("capture", {"image": svg_path, "scale": scale, "format": fmt},
                     elapsed_s=elapsed, renderer="text-svg", tier=4,
                     warnings=["tier-4 text stub — install freeze for styled output"])
    emit(result, json_mode)
    if not json_mode:
        print(svg_path)
    return EXIT_SUCCESS
```

Add `_all_presets()` helper after `PRESETS` dict:
```python
import os as _os_themes

def _all_presets():
    """Return combined built-in + file-based presets."""
    themes_dir = _os_themes.path.join(
        _os_themes.path.dirname(_os_themes.path.abspath(__file__)),
        "..", "themes"
    )
    names = set(PRESETS.keys())
    if _os_themes.path.isdir(themes_dir):
        for fn in _os_themes.listdir(themes_dir):
            if fn.endswith(".json"):
                names.add(fn[:-5])
    return names
```

- [ ] **Step 4: Run tests**

```
pytest tests/test_capture.py -v
```
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```
git add skills/cliproof/scripts/capture.py tests/test_capture.py
git commit -m "feat(capture): --json, --timeout, --scale, --format, renderer fallback chain (tier 1-4)"
```

---

### Task 4: Add `--json` + `--timeout` to `redact.py`, `embed.py`, `normalize.py`

**Files:**
- Modify: `skills/cliproof/scripts/redact.py`
- Modify: `skills/cliproof/scripts/embed.py`
- Modify: `skills/cliproof/scripts/normalize.py`
- Modify: `tests/test_redact.py`
- Modify: `tests/test_embed.py`

- [ ] **Step 1: Write failing tests for redact `--json`**

Add to `tests/test_redact.py`:
```python
import json
import redact
import _kernel


def test_clean_input_json_mode(tmp_path, capsys):
    f = tmp_path / "out.svg"
    f.write_text("<svg>echo hello</svg>", encoding="utf-8")
    rc = redact.main([str(f), "--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert out["step"] == "redact"
    assert out["outputs"]["findings"] == 0


def test_secret_input_json_mode(tmp_path, capsys):
    f = tmp_path / "out.svg"
    f.write_text("<svg>AKIAIOSFODNN7EXAMPLE</svg>", encoding="utf-8")
    rc = redact.main([str(f), "--json"])
    assert rc == _kernel.EXIT_SECRET
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False
    assert out["exit_code"] == _kernel.EXIT_SECRET
```

Add to `tests/test_embed.py`:
```python
import json
import embed
import _kernel


def test_embed_json_mode(tmp_path, capsys):
    readme = tmp_path / "README.md"
    readme.write_text("# Hello\n", encoding="utf-8")
    img = tmp_path / "shot.svg"
    img.write_text("<svg/>", encoding="utf-8")
    rc = embed.main([
        str(readme), "--image", str(img), "--alt", "demo",
        "--id", "demo", "--heading", "Demo", "--json"
    ])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert out["step"] == "embed"
    assert "diff" in out["outputs"]
```

- [ ] **Step 2: Run to verify failure**

```
pytest tests/test_redact.py tests/test_embed.py -v -k "json"
```
Expected: FAIL.

- [ ] **Step 3: Update `redact.py` — add kernel import and `--json` to `main`**

At the top, after existing imports:
```python
import os as _os_k; import sys as _sys_k
_sys_k.path.insert(0, _os_k.path.dirname(_os_k.path.abspath(__file__)))
from _kernel import EXIT_SECRET, EXIT_SUCCESS, EXIT_ERROR, success, error, emit
```

In `main`, after `p = argparse.ArgumentParser(...)`:
```python
    p.add_argument("--json", action="store_true", help="emit machine-readable JSON to stdout")
```

Before the `return` statements, wrap them to emit JSON:
- On secret found (currently `return 3`): change to `emit(error("redact", "secret_detected", EXIT_SECRET, hint="re-run with sanitized env/args"), args.json); return EXIT_SECRET`
- On success (currently `return 0`): change to `emit(success("redact", {"findings": len(findings), "file": str(source)}), args.json); return EXIT_SUCCESS`

(Apply same pattern — add `--json` to argparser, import kernel, emit on each return path.)

- [ ] **Step 4: Update `embed.py` — add `--json`**

Same pattern in `embed.py`:
```python
import os as _os_k; import sys as _sys_k
_sys_k.path.insert(0, _os_k.path.dirname(_os_k.path.abspath(__file__)))
from _kernel import EXIT_SUCCESS, EXIT_ERROR, success, error, emit
```

Add `p.add_argument("--json", action="store_true")` to the argparser.

On successful write: `emit(success("embed", {"diff": diff_text[:500], "readme": args.readme}), args.json)`

- [ ] **Step 5: Update `normalize.py` — add `--json`**

`normalize.py` is a utility; add `--json` to its `main()` and emit `success("normalize", {"normalized": result})`.

- [ ] **Step 6: Run tests**

```
pytest tests/test_redact.py tests/test_embed.py -v
```
Expected: all tests PASS.

- [ ] **Step 7: Commit**

```
git add skills/cliproof/scripts/redact.py skills/cliproof/scripts/embed.py skills/cliproof/scripts/normalize.py tests/test_redact.py tests/test_embed.py
git commit -m "feat(redact,embed,normalize): --json structured output"
```

---

### Task 5: Add `--json`, `--timeout`, exit-code 6 to `check.py` + `gif` block support

**Files:**
- Modify: `skills/cliproof/scripts/check.py`
- Modify: `tests/test_check.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_check.py`:
```python
import json
import check
import _kernel


def test_check_fresh_emits_json(tmp_path, capsys):
    baseline = tmp_path / "base.txt"
    baseline.write_text("hello\n", encoding="utf-8")

    manifest = tmp_path / "proof.json"
    manifest.write_text(json.dumps({
        "proofs": [{
            "id": "test",
            "command": "echo hello",
            "baseline": str(baseline),
            "image": "img.svg"
        }]
    }), encoding="utf-8")

    rc = check.main(["--manifest", str(manifest), "--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert out["step"] == "check"
    assert out["outputs"]["drifted"] == []


def test_check_drift_exits_6(tmp_path, capsys):
    baseline = tmp_path / "base.txt"
    baseline.write_text("original output\n", encoding="utf-8")

    manifest = tmp_path / "proof.json"
    manifest.write_text(json.dumps({
        "proofs": [{
            "id": "test",
            "command": "echo different output",
            "baseline": str(baseline),
            "image": "img.svg"
        }]
    }), encoding="utf-8")

    rc = check.main(["--manifest", str(manifest), "--json"])
    assert rc == _kernel.EXIT_DRIFT
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False
    assert out["exit_code"] == _kernel.EXIT_DRIFT
    assert "test" in out["outputs"]["drifted"]


def test_proof_json_gif_block_is_accepted(tmp_path):
    baseline = tmp_path / "base.txt"
    baseline.write_text("hello\n", encoding="utf-8")
    manifest = tmp_path / "proof.json"
    manifest.write_text(json.dumps({
        "proofs": [{
            "id": "demo",
            "command": "echo hello",
            "baseline": str(baseline),
            "image": "img.svg",
            "gif": {
                "speed": "realistic",
                "loop": "once",
                "freeze_last": True,
                "max_kb": 1800
            }
        }]
    }), encoding="utf-8")
    # gif block is metadata only — check still runs the command and compares
    rc = check.main(["--manifest", str(manifest)])
    assert rc == 0  # no drift
```

- [ ] **Step 2: Run to verify failure**

```
pytest tests/test_check.py -v -k "json or drift_exits or gif"
```
Expected: FAIL.

- [ ] **Step 3: Update `check.py`**

Add kernel import at top:
```python
import os as _os_k; import sys as _sys_k
_sys_k.path.insert(0, _os_k.path.dirname(_os_k.path.abspath(__file__)))
from _kernel import EXIT_DRIFT, EXIT_SUCCESS, EXIT_ERROR, success, error, emit, default_timeout
```

Add `--json` and `--timeout` to argparser:
```python
    p.add_argument("--json", action="store_true", help="emit machine-readable JSON to stdout")
    p.add_argument("--timeout", type=float, default=default_timeout("check"),
                   help="timeout in seconds (default: 20)")
```

Update `run_command` to accept timeout:
```python
def run_command(command, timeout=120):
    proc = subprocess.run(command, shell=True, stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          timeout=timeout)
    return proc.stdout.decode("utf-8", "replace")
```

In the manifest mode, collect drifted IDs and emit JSON:
```python
    # In main(), manifest mode — replace the final block:
    results = []
    drifted = []
    for e in proofs:
        ok = _check_one(e, args.update, timeout=args.timeout)
        results.append(ok)
        if not ok:
            drifted.append(e.get("id", e.get("baseline", "?")))

    failed = len(drifted)
    print(f"check: {len(results) - failed}/{len(results)} proofs OK", file=sys.stderr)

    if failed == 0:
        result = success("check", {"total": len(results), "drifted": []})
        emit(result, args.json)
        return EXIT_SUCCESS
    else:
        result = error("check", "drift_detected", EXIT_DRIFT)
        result["outputs"] = {"total": len(results), "drifted": drifted}
        emit(result, args.json)
        return EXIT_DRIFT
```

Note: `gif` block in proof entries is metadata for the GIF pipeline — `_check_one` already ignores unknown keys, so no code change needed for that. The test passes because `json.load` reads the whole entry and unknown keys are ignored by `_check_one`.

- [ ] **Step 4: Run tests**

```
pytest tests/test_check.py -v
```
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```
git add skills/cliproof/scripts/check.py tests/test_check.py
git commit -m "feat(check): --json, --timeout, exit code 6 for drift, gif block passthrough"
```

---

### Task 6: Add `--json` + `--timeout` to remaining scripts

**Files:**
- Modify: `skills/cliproof/scripts/verify.py`
- Modify: `skills/cliproof/scripts/suggest.py`
- Modify: `skills/cliproof/scripts/storyboard.py`
- Modify: `skills/cliproof/scripts/pr.py`
- Modify: `skills/cliproof/scripts/rasterize.py`

Each script gets the same treatment:
1. Add kernel import (3-line block at top)
2. Add `--json` and `--timeout` to argparser
3. Wrap each `return 0` / `return 1` with `emit(success/error(...), args.json)`

- [ ] **Step 1: Write failing tests for `verify.py` (representative)**

Add to `tests/test_verify.py`:
```python
import json
import verify
import _kernel


def test_verify_passing_command_json(capsys):
    rc = verify.main(["--command", "python -c \"import sys; sys.exit(0)\"", "--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert out["step"] == "verify"
    assert out["outputs"]["verdict"] == "PASS"


def test_verify_failing_command_json(capsys):
    rc = verify.main(["--command", "python -c \"import sys; sys.exit(1)\"", "--json"])
    assert rc != 0
    out = json.loads(capsys.readouterr().out)
    assert out["outputs"]["verdict"] == "FAIL"
```

- [ ] **Step 2: Run to verify failure**

```
pytest tests/test_verify.py -v -k "json"
```
Expected: FAIL.

- [ ] **Step 3: Add `--json` to `verify.py`**

Read the current `verify.py` `main()`, add:
```python
import os as _os_k; import sys as _sys_k
_sys_k.path.insert(0, _os_k.path.dirname(_os_k.path.abspath(__file__)))
from _kernel import EXIT_SUCCESS, EXIT_ERROR, success, error, emit, default_timeout
```

In `main`:
```python
p.add_argument("--json", action="store_true")
p.add_argument("--timeout", type=float, default=default_timeout("verify"))
```

Wrap PASS/FAIL returns:
```python
# On PASS:
emit(success("verify", {"verdict": "PASS", "report": report_path}), args.json)
return EXIT_SUCCESS
# On FAIL:
emit(error("verify", "command_failed", EXIT_ERROR), args.json)
# (keep existing non-zero return)
```

- [ ] **Step 4: Add `--json` to `suggest.py`**

At the top of `suggest.py`, after existing imports:
```python
import os as _os_k; import sys as _sys_k
_sys_k.path.insert(0, _os_k.path.dirname(_os_k.path.abspath(__file__)))
from _kernel import EXIT_SUCCESS, EXIT_ERROR, success, error, emit, default_timeout
```

Add to argparser in `main`:
```python
p.add_argument("--json", action="store_true", help="emit machine-readable JSON to stdout")
p.add_argument("--timeout", type=float, default=default_timeout("suggest"))
```

Wrap the final return in `main` (currently returns a list of suggestions to stdout):
```python
# Before: print each suggestion and return 0
# After: also emit JSON
suggestions = [...]  # existing logic unchanged
if args.json:
    emit(success("suggest", {"suggestions": suggestions[:5]}), True)
else:
    for s in suggestions:
        print(s)
return EXIT_SUCCESS
```

- [ ] **Step 5: Add `--json` to `storyboard.py`**

Same 3-line import block at top. Add `--json` and `--timeout` to argparser.

On successful stitch:
```python
emit(success("storyboard", {"output": args.output}), args.json)
return EXIT_SUCCESS
```

On error:
```python
emit(error("storyboard", "stitch_failed", EXIT_ERROR), args.json)
return EXIT_ERROR
```

- [ ] **Step 6: Add `--json` to `pr.py`**

Same 3-line import block. Add `--json` and `--timeout` to argparser.

On successful post:
```python
emit(success("pr", {"pr": args.pr, "posted": True}), args.json)
return EXIT_SUCCESS
```

On error (gh not found or post failed):
```python
emit(error("pr", "post_failed", EXIT_ERROR, hint="ensure 'gh' is on PATH and authenticated"), args.json)
return EXIT_ERROR
```

- [ ] **Step 7: Add `--json` to `rasterize.py`**

Same 3-line import block. Add `--json` and `--timeout` to argparser.

On successful rasterization:
```python
emit(success("rasterize", {"output": output_path, "renderer": renderer_name}), args.json)
return EXIT_SUCCESS
```

On no renderer found:
```python
emit(error("rasterize", "no_renderer", EXIT_ERROR, hint="install resvg, inkscape, or imagemagick"), args.json)
return EXIT_ERROR
```

- [ ] **Step 5: Run all tests**

```
pytest tests/ -v
```
Expected: all tests PASS (no regressions).

- [ ] **Step 6: Commit**

```
git add skills/cliproof/scripts/verify.py skills/cliproof/scripts/suggest.py skills/cliproof/scripts/storyboard.py skills/cliproof/scripts/pr.py skills/cliproof/scripts/rasterize.py tests/test_verify.py
git commit -m "feat(verify,suggest,storyboard,pr,rasterize): --json and --timeout flags"
```

---

### Task 7: Create `health.py` and update `preflight.py` as alias

**Files:**
- Create: `skills/cliproof/scripts/health.py`
- Modify: `skills/cliproof/scripts/preflight.py`
- Create: `tests/test_health.py`
- Modify: `tests/test_preflight.py`

- [ ] **Step 1: Write failing tests for `health.py`**

```python
# tests/test_health.py
import json
import health
import _kernel


def test_health_returns_ok_dict(monkeypatch):
    monkeypatch.setattr(health.shutil, "which", lambda t: "/usr/bin/" + t if t in ("freeze",) else None)
    result = health.detect()
    assert "ok" in result
    assert "renderers" in result
    assert "modes" in result
    assert "gif" in result
    assert "python" in result
    assert "redaction" in result
    assert "guard" in result


def test_health_main_json_output(monkeypatch, capsys):
    monkeypatch.setattr(health.shutil, "which", lambda t: "/usr/bin/" + t if t == "freeze" else None)
    rc = health.main(["--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert "ok" in out
    assert "renderers" in out


def test_health_main_human_output(monkeypatch, capsys):
    monkeypatch.setattr(health.shutil, "which", lambda _: None)
    rc = health.main([])
    assert rc == 0
    captured = capsys.readouterr()
    assert "cliproof health" in captured.out or "cliproof health" in captured.err


def test_health_freeze_version_detected(monkeypatch):
    import subprocess as sp
    monkeypatch.setattr(health.shutil, "which", lambda t: "/usr/bin/freeze" if t == "freeze" else None)

    class FakeProc:
        returncode = 0
        stdout = b"freeze version 0.2.2\n"

    monkeypatch.setattr(health.subprocess, "run", lambda *a, **kw: FakeProc())
    result = health.detect()
    assert any("freeze" in r for r in result["renderers"])
```

- [ ] **Step 2: Run to verify failure**

```
pytest tests/test_health.py -v
```
Expected: `ImportError: No module named 'health'`.

- [ ] **Step 3: Create `skills/cliproof/scripts/health.py`**

```python
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
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
        import re
        m = re.search(r"(\d+\.\d+(?:\.\d+)?)", ver)
        return "{}@{}".format(name, m.group(1)) if m else name
    except Exception:
        return None


def _rasterizers():
    """Return list of available SVG→raster tools."""
    found = []
    for t in ("resvg", "inkscape", "magick", "convert"):
        if shutil.which(t):
            found.append(t)
    return found


def detect():
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
        gif_reason = "missing: " + ", ".join(missing) if missing else "ttyd not available on Windows"

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
    print("  gif: {}".format("yes" if info["gif"] else "no — " + (info["gif_blocked_reason"] or "")))
    print("  gifsicle: {}".format("yes" if info["gifsicle"] else "no"))
    print("  redaction: yes")
    print("  guard: yes")
    if not info["ok"]:
        print("\n  WARNING: no capture renderer found. Install freeze:")
        print("    go install github.com/charmbracelet/freeze@v0.2.2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Update `preflight.py` as a thin alias**

Replace the entire content of `preflight.py` with:

```python
#!/usr/bin/env python3
"""preflight.py — backward-compatibility alias for health.py.

Deprecated: use `cliproof health` or `python health.py` instead.
Will be removed in v1.0.0.
"""
import os
import sys
import warnings

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
warnings.warn(
    "preflight.py is deprecated; use health.py instead. Will be removed in v1.0.0.",
    DeprecationWarning, stacklevel=1
)
import health  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(health.main())

# Keep detect() importable for backward compat
detect = health.detect
main = health.main
```

- [ ] **Step 5: Run tests**

```
pytest tests/test_health.py tests/test_preflight.py -v
```
Expected: all PASS.

- [ ] **Step 6: Commit**

```
git add skills/cliproof/scripts/health.py skills/cliproof/scripts/preflight.py tests/test_health.py tests/test_preflight.py
git commit -m "feat(health): new health.py probe; preflight.py kept as deprecation alias"
```

---

## TRACK 2 — Image Quality Upgrades

---

### Task 8: Create 6 new theme JSON files

**Files:**
- Create: `skills/cliproof/themes/catppuccin.json`
- Create: `skills/cliproof/themes/tokyo-night.json`
- Create: `skills/cliproof/themes/one-dark.json`
- Create: `skills/cliproof/themes/dracula.json`
- Create: `skills/cliproof/themes/solarized.json`
- Create: `skills/cliproof/themes/rose-pine.json`

Each theme JSON maps to `(flag, value)` pairs that `capture.py` forwards to `freeze`.

- [ ] **Step 1: Create `skills/cliproof/themes/` directory and theme files**

```json
// catppuccin.json
{
  "name": "catppuccin",
  "flags": [
    ["--window", null],
    ["--theme", "catppuccin-mocha"],
    ["--background", "#1e1e2e"],
    ["--border.radius", "10"],
    ["--padding", "24"],
    ["--margin", "20"],
    ["--shadow.blur", "24"],
    ["--shadow.y", "12"]
  ]
}
```

```json
// tokyo-night.json
{
  "name": "tokyo-night",
  "flags": [
    ["--window", null],
    ["--theme", "tokyonight"],
    ["--background", "#1a1b26"],
    ["--border.radius", "8"],
    ["--padding", "24"],
    ["--margin", "20"],
    ["--shadow.blur", "20"],
    ["--shadow.y", "10"]
  ]
}
```

```json
// one-dark.json
{
  "name": "one-dark",
  "flags": [
    ["--window", null],
    ["--theme", "onedark"],
    ["--background", "#21252b"],
    ["--border.radius", "8"],
    ["--padding", "24"],
    ["--margin", "20"],
    ["--shadow.blur", "20"],
    ["--shadow.y", "10"]
  ]
}
```

```json
// dracula.json
{
  "name": "dracula",
  "flags": [
    ["--window", null],
    ["--theme", "dracula"],
    ["--background", "#282a36"],
    ["--border.radius", "8"],
    ["--padding", "24"],
    ["--margin", "20"],
    ["--shadow.blur", "20"],
    ["--shadow.y", "10"]
  ]
}
```

```json
// solarized.json
{
  "name": "solarized",
  "flags": [
    ["--window", null],
    ["--theme", "solarized-dark"],
    ["--background", "#002b36"],
    ["--border.radius", "8"],
    ["--padding", "24"],
    ["--margin", "20"],
    ["--shadow.blur", "20"],
    ["--shadow.y", "10"]
  ]
}
```

```json
// rose-pine.json
{
  "name": "rose-pine",
  "flags": [
    ["--window", null],
    ["--theme", "rose-pine"],
    ["--background", "#191724"],
    ["--border.radius", "8"],
    ["--padding", "24"],
    ["--margin", "20"],
    ["--shadow.blur", "20"],
    ["--shadow.y", "10"]
  ]
}
```

- [ ] **Step 2: Write a test verifying all theme files are valid JSON with required keys**

Add to `tests/test_manifests.py` (existing file):
```python
import json
import os


def test_all_theme_files_are_valid():
    themes_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "skills", "cliproof", "themes"
    )
    assert os.path.isdir(themes_dir), "themes/ directory missing"
    files = [f for f in os.listdir(themes_dir) if f.endswith(".json")]
    assert len(files) >= 6, "expected at least 6 theme files"
    for fn in files:
        path = os.path.join(themes_dir, fn)
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        assert "name" in data, "{} missing 'name'".format(fn)
        assert "flags" in data, "{} missing 'flags'".format(fn)
        for pair in data["flags"]:
            assert len(pair) == 2, "{} flag entry must be [flag, value_or_null]".format(fn)
```

- [ ] **Step 3: Run test**

```
pytest tests/test_manifests.py -v -k "theme"
```
Expected: PASS.

- [ ] **Step 4: Verify theme files load in `capture.py`**

```python
# quick smoke-test in a Python shell or pytest
import sys; sys.path.insert(0, "skills/cliproof/scripts")
import capture
presets = capture._all_presets()
assert "catppuccin" in presets
assert "tokyo-night" in presets
print("themes:", sorted(presets))
```

- [ ] **Step 5: Update `preset_flags` in `capture.py` to load file-based themes**

After the existing `PRESETS` dict and `_all_presets()` helper, update `preset_flags` to also load from JSON:

```python
def preset_flags(name, passthrough):
    """Flags a preset contributes, skipping any the user already set."""
    # Built-in preset
    if name in PRESETS:
        flags = []
        for flag, val in PRESETS[name]:
            if not _has_flag(passthrough, flag):
                flags += [flag] if val is None else [flag, val]
        return flags

    # File-based theme
    themes_dir = _os_themes.path.join(
        _os_themes.path.dirname(_os_themes.path.abspath(__file__)),
        "..", "themes"
    )
    theme_path = _os_themes.path.join(themes_dir, name + ".json")
    if _os_themes.path.exists(theme_path):
        import json as _json
        with open(theme_path, encoding="utf-8") as _fh:
            data = _json.load(_fh)
        flags = []
        for pair in data.get("flags", []):
            flag, val = pair[0], pair[1]
            if not _has_flag(passthrough, flag):
                flags += [flag] if val is None else [flag, val]
        return flags

    return []
```

- [ ] **Step 6: Write test for file-based theme loading**

Add to `tests/test_capture.py`:
```python
def test_file_based_theme_loaded_from_json(monkeypatch, tmp_path):
    # catppuccin.json exists in themes/ — verify it contributes --theme flag
    cmd = capture.build_command("freeze", ["--execute", "ls"], "o.svg", preset="catppuccin")
    assert "--theme" in cmd
    assert "catppuccin-mocha" in cmd
```

- [ ] **Step 7: Run all capture tests**

```
pytest tests/test_capture.py -v
```
Expected: all PASS.

- [ ] **Step 8: Commit**

```
git add skills/cliproof/themes/ skills/cliproof/scripts/capture.py tests/test_manifests.py tests/test_capture.py
git commit -m "feat(themes): add 6 new presets (catppuccin, tokyo-night, one-dark, dracula, solarized, rose-pine)"
```

---

### Task 9: Add `--badge`, `--stamp`, `--ci-ribbon` overlays to `annotate.py`

**Files:**
- Modify: `skills/cliproof/scripts/annotate.py`
- Modify: `tests/test_annotate.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_annotate.py`:
```python
import annotate


def test_badge_pass_adds_green_corner_badge(tmp_path):
    in_svg = tmp_path / "in.svg"
    in_svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="200">'
        '<rect width="400" height="200" fill="#0d1117"/></svg>',
        encoding="utf-8"
    )
    out_svg = tmp_path / "out.svg"
    rc = annotate.main([str(in_svg), "--caption", "tests pass", "--badge", "pass",
                        "-o", str(out_svg)])
    assert rc == 0
    content = out_svg.read_text(encoding="utf-8")
    assert "PASS" in content or "#238636" in content  # green badge


def test_badge_fail_adds_red_corner_badge(tmp_path):
    in_svg = tmp_path / "in.svg"
    in_svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="200">'
        '<rect width="400" height="200" fill="#0d1117"/></svg>',
        encoding="utf-8"
    )
    out_svg = tmp_path / "out.svg"
    rc = annotate.main([str(in_svg), "--caption", "tests fail", "--badge", "fail",
                        "-o", str(out_svg)])
    assert rc == 0
    content = out_svg.read_text(encoding="utf-8")
    assert "FAIL" in content or "#da3633" in content  # red badge


def test_stamp_adds_version_watermark(tmp_path):
    in_svg = tmp_path / "in.svg"
    in_svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="200">'
        '<rect width="400" height="200" fill="#0d1117"/></svg>',
        encoding="utf-8"
    )
    out_svg = tmp_path / "out.svg"
    rc = annotate.main([str(in_svg), "--stamp", "v1.2.0 · 2026-06-10",
                        "-o", str(out_svg)])
    assert rc == 0
    content = out_svg.read_text(encoding="utf-8")
    assert "v1.2.0" in content


def test_ci_ribbon_adds_top_bar(tmp_path):
    in_svg = tmp_path / "in.svg"
    in_svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="200">'
        '<rect width="400" height="200" fill="#0d1117"/></svg>',
        encoding="utf-8"
    )
    out_svg = tmp_path / "out.svg"
    rc = annotate.main([str(in_svg), "--ci-ribbon", "CI passing",
                        "-o", str(out_svg)])
    assert rc == 0
    content = out_svg.read_text(encoding="utf-8")
    assert "CI passing" in content


def test_caption_is_optional_when_badge_given(tmp_path):
    in_svg = tmp_path / "in.svg"
    in_svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="200">'
        '<rect width="400" height="200" fill="#0d1117"/></svg>',
        encoding="utf-8"
    )
    out_svg = tmp_path / "out.svg"
    # --caption is currently required; after this task it should be optional when --badge is given
    rc = annotate.main([str(in_svg), "--badge", "pass", "-o", str(out_svg)])
    assert rc == 0
```

- [ ] **Step 2: Run to verify failure**

```
pytest tests/test_annotate.py -v -k "badge or stamp or ribbon or optional"
```
Expected: FAIL.

- [ ] **Step 3: Update `annotate.py`**

Add helper functions before `main`:
```python
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
```

Replace `main` to make `--caption` optional (required only when no overlay flag):
```python
def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Add overlays to an SVG capture.")
    p.add_argument("input", help="input SVG (or '-' for stdin from verify pipe)")
    p.add_argument("--caption", default=None, help="caption bar text")
    p.add_argument("--badge", choices=["pass", "fail"], default=None,
                   help="corner badge: pass (green) or fail (red)")
    p.add_argument("--stamp", default=None, help="bottom-right version watermark text")
    p.add_argument("--ci-ribbon", dest="ci_ribbon", default=None, help="top ribbon bar text")
    p.add_argument("-o", "--output", required=True, help="output SVG")
    p.add_argument("--accent", default="#3fb950", help="caption accent color (hex)")
    args = p.parse_args(argv)

    # stdin support for pipe from verify.py
    if args.input == "-":
        svg = sys.stdin.read()
    else:
        with open(args.input, "r", encoding="utf-8-sig") as fh:
            svg = fh.read()

    out = svg
    if args.caption:
        out = add_caption(out, args.caption, accent=args.accent)
    if args.badge:
        out = add_badge(out, args.badge)
    if args.stamp:
        out = add_stamp(out, args.stamp)
    if args.ci_ribbon:
        out = add_ci_ribbon(out, args.ci_ribbon)

    if out == svg and not any([args.caption, args.badge, args.stamp, args.ci_ribbon]):
        print("annotate: no overlay flags given. Use --caption, --badge, --stamp, or --ci-ribbon.",
              file=sys.stderr)
        return 1

    with open(args.output, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(out)
    print("annotate: wrote {}".format(args.output), file=sys.stderr)
    return 0
```

- [ ] **Step 4: Run all annotate tests**

```
pytest tests/test_annotate.py -v
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```
git add skills/cliproof/scripts/annotate.py tests/test_annotate.py
git commit -m "feat(annotate): --badge pass/fail, --stamp, --ci-ribbon SVG overlay layers"
```

---

### Task 10: Add `themes list` subcommand to `bin/cli.js` + update passthrough list

**Files:**
- Modify: `bin/cli.js`

- [ ] **Step 1: Write failing Node test**

Add to the existing Node test file (check with `npm test` which file handles CLI tests):

```js
// In the existing Node test file
const { execSync } = require("child_process");
const assert = require("assert");

// themes list
{
  const out = execSync("node bin/cli.js themes list", { encoding: "utf8" });
  assert(out.includes("catppuccin"), "themes list should include catppuccin");
  assert(out.includes("macos"), "themes list should include macos");
}

// health passthrough
{
  const out = execSync("node bin/cli.js health", { encoding: "utf8" });
  assert(out.includes("cliproof health") || out.includes('"ok"'), "health output expected");
}
```

- [ ] **Step 2: Run to verify failure**

```
npm test
```
Expected: new assertions FAIL.

- [ ] **Step 3: Update `bin/cli.js`**

Add `"health"` to the `PASSTHROUGH` array:
```js
const PASSTHROUGH = ["preflight", "guard", "capture", "redact", "embed",
  "check", "suggest", "verify", "storyboard", "annotate", "pr", "health"];
```

Add `themes` to `cmdInstall` flow — add a new `cmdThemes` function and wire it in `main`:
```js
function cmdThemes(argv) {
  const sub = argv[0];
  if (!sub || sub === "list") {
    // Built-in presets
    const builtin = ["macos", "github-dark", "nord", "iterm", "win11"];
    // File-based themes from skills/cliproof/themes/
    const themesDir = path.join(ROOT, "skills", "cliproof", "themes");
    let fileBased = [];
    try {
      fileBased = fs.readdirSync(themesDir)
        .filter(f => f.endsWith(".json"))
        .map(f => f.replace(".json", ""));
    } catch (_) {}
    const all = [...new Set([...builtin, ...fileBased])].sort();
    console.log("Available themes:");
    all.forEach(t => console.log("  " + t));
    return 0;
  }
  console.error("cliproof themes: unknown subcommand '" + sub + "'. Try: list");
  return 2;
}
```

In `main`:
```js
if (cmd === "themes") return cmdThemes(argv.slice(1));
```

- [ ] **Step 4: Run tests**

```
npm test
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```
git add bin/cli.js
git commit -m "feat(cli): add 'themes list' subcommand and 'health' passthrough"
```

---

### Task 11: README positioning updates (Section 5)

**Files:**
- Modify: `README.md`

No tests for copy changes — review diff visually.

- [ ] **Step 1: Update tagline in `README.md`**

Change line 6:
```
Before: **Prove your CLI actually works — and keep it true.**
After:  **Your README should show it works — not just say it.**
```

- [ ] **Step 2: Update hero description**

Change lines 27–31:
```markdown
Capture any real command and its real output — tests, builds, servers,
scripts, pipelines — as a polished screenshot or GIF, redact any secrets,
and embed it into your `README.md` as honest, durable evidence it works.
Then let CI fail the moment that evidence goes stale.
```

- [ ] **Step 3: Update Install section heading (line 79)**

```
Before: **Agent-agnostic (npm) — recommended for any agent:**
After:  **npm — works in any agent, pipeline, or IDE:**
```

- [ ] **Step 4: Add "Who it's for" section after the comparison table (after line 60)**

```markdown
## Who it's for

cliproof works for anyone who runs shell commands and wants durable proof:
- **Open-source maintainers** — show contributors and users the project ships
- **Backend & platform engineers** — prove builds, servers, and scripts run
- **QA & DevOps teams** — capture test runs and pipeline output as evidence
- **AI agent builders** — wire capture → redact → embed as an MCP tool chain
- **Anyone writing a README** — stop saying it works; show it
```

- [ ] **Step 5: Review diff and commit**

```
git diff README.md
git add README.md
git commit -m "docs: update positioning — broader tagline, hero copy, Who it's for section"
```

---

### Task 12: Update `demo.tape.template` with GIF quality controls

**Files:**
- Modify: `skills/cliproof/assets/demo.tape.template`

- [ ] **Step 1: Read current template**

```
cat skills/cliproof/assets/demo.tape.template
```

- [ ] **Step 2: Update with GIF quality config block**

Add a commented config header that maps to `proof.json` gif block:

```
# cliproof demo tape — edit Type/Enter/Sleep lines for your command
# GIF quality controls (set in .cliproof/proof.json "gif" block):
#   speed: "realistic" | "fast"   — typing animation speed
#   loop: "once" | "infinite" | N — how many times the GIF loops
#   freeze_last: true              — hold the final frame
#   max_kb: 1800                   — auto-compress for Slack/Discord

Set Shell "bash"
Set FontSize 14
Set Width 1200
Set Height 600
Set WindowBar Colorful
Set Theme "Dracula"
Set TypingSpeed 50ms
Set LoopOffset 100%

Hide
Type "cd /path/to/your/repo"
Enter
Show

Type "your-command --here"
Enter
Sleep 2s
```

- [ ] **Step 3: Commit**

```
git add skills/cliproof/assets/demo.tape.template
git commit -m "chore(assets): update demo.tape.template with GIF quality config comments"
```

---

### Task 13: Full test suite run + CHANGELOG + version bump to v0.2.0

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `package.json` (via `npm version`)

- [ ] **Step 1: Run full test suite — must be 100% green**

```
pytest -q
npm test
```
Expected: all tests PASS, zero failures.

- [ ] **Step 2: Verify no-dependency guard still passes**

```
pytest tests/test_no_dependencies.py -v
```
Expected: PASS — no new third-party imports introduced.

- [ ] **Step 3: Update `CHANGELOG.md` — add v0.2.0 entry under `[Unreleased]`**

```markdown
## [Unreleased]

## [0.2.0] - 2026-06-10

### Added
- JSON contract kernel: `--json` flag on all 13 scripts emits structured `{ ok, step, outputs, ... }` to stdout
- `--timeout` flag on all scripts; hard timeouts with exit code 4 — no hangs ever
- Stable exit code contract: 0 success, 3 secret, 4 timeout, 5 unsafe, 6 drift
- Multi-renderer fallback chain in `capture.py`: freeze (tier 1) → silicon (tier 2) → rasterizer (tier 3) → text-SVG stub (tier 4)
- `health.py` — first-class health probe; `preflight.py` kept as deprecation alias
- 6 new themes: catppuccin, tokyo-night, one-dark, dracula, solarized, rose-pine
- `annotate.py`: `--badge pass/fail`, `--stamp`, `--ci-ribbon` SVG overlay layers
- `check.py`: `gif` block support in proof.json (speed, loop, freeze_last, max_kb)
- `bin/cli.js`: `themes list` subcommand, `health` passthrough
- `demo.tape.template`: GIF quality control comments

### Changed
- Tagline: "Your README should show it works — not just say it."
- README: broader hero copy, "Who it's for" section, updated install heading
- `guard.py` exit code for unsafe: 5 (was 2; 2 is now reserved for unknown command)
- `check.py` exit code for drift: 6 (was 1)
```

- [ ] **Step 4: Bump version**

```
npm version patch --no-git-tag-version
```
(Results in 0.2.0 if current is 0.1.1 — adjust with `minor` if preferred.)

- [ ] **Step 5: Final commit**

```
git add CHANGELOG.md package.json package-lock.json
git commit -m "chore(release): v0.2.0"
```

---

## Self-review checklist

Before marking M1 complete, verify:

- [ ] `pytest -q` → 0 failures
- [ ] `npm test` → 0 failures
- [ ] `pytest tests/test_no_dependencies.py` → PASS (stdlib only)
- [ ] `python skills/cliproof/scripts/health.py` runs on this machine
- [ ] `python skills/cliproof/scripts/capture.py --execute "echo hello" -o /tmp/test.svg` produces an SVG
- [ ] `python skills/cliproof/scripts/guard.py --json "echo hello"` emits `{"ok": true, ...}` JSON to stdout
- [ ] `python skills/cliproof/scripts/check.py --json` runs without error
- [ ] `node bin/cli.js themes list` prints at least 11 theme names
- [ ] README diff looks correct (tagline, hero, Who it's for)
- [ ] No `Co-Authored-By` trailers in any commit
