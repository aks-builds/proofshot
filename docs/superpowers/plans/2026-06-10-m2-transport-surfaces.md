# cliproof v2 M2 — Four Transport Surfaces

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the M1 kernel through four independent transport surfaces — MCP server (agent frameworks), Python PyPI package (library consumers), Docker/OCI image (CI pipelines), and HTTP daemon (IDEs and polyglot callers) — shipping versions v0.3.0 and v0.4.0.

**Architecture:** Every surface is a thin transport wrapper. It calls the M1 scripts via subprocess with `--json`, parses the result dict, and translates to its protocol. No capture, redaction, or embedding logic lives in the surfaces — all that stays in the scripts. The `cliproof/` Python package is the dispatch layer the other surfaces import where convenient.

**Tech Stack:** Python 3.8+ stdlib only (no new deps for runtime), Node 18+ (CLI wiring), Docker (image build only — not a runtime dep)

**Pre-condition:** M1 is complete. `skills/cliproof/scripts/` contains `_kernel.py` and all 14 scripts, each with `--json` and `--timeout` flags. `pytest -q` shows 156 passing.

---

## File map

### New files
| Path | Purpose |
|------|---------|
| `cliproof/__init__.py` | Public Python API re-exports |
| `cliproof/_api.py` | Subprocess dispatch — calls scripts with `--json`, returns typed objects |
| `cliproof/_types.py` | Dataclasses (CaptureResult etc.) + exceptions |
| `cliproof/_dispatch.py` | Finds the scripts directory (dev vs installed) |
| `cliproof/py.typed` | PEP 561 marker |
| `pyproject.toml` | Python package build config |
| `skills/cliproof/scripts/mcp_server.py` | Stdio MCP server (JSON-RPC 2.0 over Content-Length framing) |
| `skills/cliproof/scripts/serve.py` | Local HTTP daemon (stdlib `http.server` + `threading`) |
| `Dockerfile` | Alpine + Python 3.12 + freeze@0.2.2 + gifsicle |
| `.github/workflows/docker.yml` | Build and push Docker image on release |
| `tests/test_pypackage.py` | Tests for `cliproof/` Python package |
| `tests/test_mcp_server.py` | Tests for `mcp_server.py` |
| `tests/test_serve.py` | Tests for `serve.py` |

### Modified files
| Path | Changes |
|------|---------|
| `bin/cli.js` | Add `mcp` and `serve` commands |
| `package.json` | Add `cliproof/` to `files` list |
| `README.md` | Add MCP, PyPI, Docker, daemon install instructions |
| `CHANGELOG.md` | v0.3.0 + v0.4.0 entries |

---

## Task 1: Python package — `cliproof/` dispatch layer

**Files:**
- Create: `cliproof/__init__.py`
- Create: `cliproof/_dispatch.py`
- Create: `cliproof/_types.py`
- Create: `cliproof/_api.py`
- Create: `cliproof/py.typed`
- Create: `pyproject.toml`
- Create: `tests/test_pypackage.py`

### 1a — Write failing tests

- [ ] **Step 1: Create `tests/test_pypackage.py`**

```python
# tests/test_pypackage.py
import sys
import os

# Make the cliproof/ package importable from the repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cliproof
from cliproof._types import (
    CaptureResult, RedactResult, EmbedResult, CheckResult,
    CliproofNotReadyError, RedactionBlockedError, CliproofError
)
from cliproof._dispatch import scripts_dir


def test_scripts_dir_points_to_real_directory():
    d = scripts_dir()
    assert os.path.isdir(d), "scripts_dir() returned non-existent path: {}".format(d)
    assert os.path.exists(os.path.join(d, "capture.py")), "capture.py missing from scripts_dir"
    assert os.path.exists(os.path.join(d, "_kernel.py")), "_kernel.py missing from scripts_dir"


def test_capture_result_is_dataclass():
    r = CaptureResult(image="out.svg", renderer="freeze", tier=1, warnings=[], scale=1, fmt="svg")
    assert r.image == "out.svg"
    assert r.renderer == "freeze"
    assert r.tier == 1


def test_redact_result_is_dataclass():
    r = RedactResult(findings=0, file="out.svg")
    assert r.findings == 0


def test_embed_result_is_dataclass():
    r = EmbedResult(readme="README.md", diff="some diff")
    assert r.readme == "README.md"


def test_check_result_is_dataclass():
    r = CheckResult(total=2, drifted=[])
    assert r.total == 2
    assert r.drifted == []


def test_cliproof_error_carries_data():
    e = CliproofError({"reason": "timeout", "step": "capture", "exit_code": 4})
    assert e.data["reason"] == "timeout"
    assert "timeout" in str(e)


def test_redaction_blocked_error():
    e = RedactionBlockedError({"reason": "secret_detected", "step": "redact"})
    assert isinstance(e, CliproofError)


def test_health_returns_dict(monkeypatch):
    """health() calls health.py --json and parses the result."""
    import subprocess as sp
    import json

    fake_result = {
        "ok": True, "renderers": ["freeze@0.2.2"], "modes": ["static"],
        "gif": False, "gif_blocked_reason": None, "gifsicle": False,
        "redaction": True, "guard": True, "python": "3.12.0", "os": "Linux"
    }

    class FakeProc:
        stdout = json.dumps(fake_result)
        stderr = ""
        returncode = 0

    monkeypatch.setattr(sp, "run", lambda *a, **kw: FakeProc())
    result = cliproof.health()
    assert result["ok"] is True
    assert "renderers" in result


def test_guard_safe_command(monkeypatch):
    """guard() returns True for safe commands."""
    import subprocess as sp, json
    fake = {"ok": True, "step": "guard", "outputs": {"safe": True},
            "warnings": [], "elapsed_s": 0.0}

    class FakeProc:
        stdout = json.dumps(fake); stderr = ""; returncode = 0

    monkeypatch.setattr(sp, "run", lambda *a, **kw: FakeProc())
    assert cliproof.guard("echo hello") is True


def test_guard_unsafe_command_raises(monkeypatch):
    """guard() raises CliproofError for unsafe commands."""
    import subprocess as sp, json
    from cliproof._types import CliproofError
    fake = {"ok": False, "step": "guard", "reason": "unsafe", "exit_code": 5, "elapsed_s": 0.0}

    class FakeProc:
        stdout = json.dumps(fake); stderr = ""; returncode = 5

    monkeypatch.setattr(sp, "run", lambda *a, **kw: FakeProc())
    try:
        cliproof.guard("rm -rf /")
        assert False, "Should have raised CliproofError"
    except CliproofError as e:
        assert e.data["reason"] == "unsafe"


def test_public_api_exports():
    """Verify the public API surface is complete."""
    for name in ["capture", "redact", "embed", "check", "health", "guard", "configure"]:
        assert hasattr(cliproof, name), "cliproof.{} missing from public API".format(name)
```

- [ ] **Step 2: Run to verify failure**

```
cd C:/NashTech/cliproof && pytest tests/test_pypackage.py -v
```
Expected: `ModuleNotFoundError: No module named 'cliproof'`

### 1b — Implement

- [ ] **Step 3: Create `cliproof/_dispatch.py`**

```python
"""_dispatch.py — locate the cliproof scripts directory at runtime."""
import os
import sys


def scripts_dir():
    """Return the absolute path to the cliproof scripts directory.

    Search order:
    1. CLIPROOF_SCRIPTS_DIR environment variable (explicit override)
    2. Relative to this file: ../../skills/cliproof/scripts  (dev / editable install)
    3. Relative to this file: ../skills/cliproof/scripts  (alternative layouts)

    Raises RuntimeError if no valid directory is found.
    """
    env = os.environ.get("CLIPROOF_SCRIPTS_DIR")
    if env:
        env = os.path.abspath(env)
        if os.path.isdir(env) and os.path.exists(os.path.join(env, "capture.py")):
            return env

    this_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.normpath(os.path.join(this_dir, "..", "skills", "cliproof", "scripts")),
        os.path.normpath(os.path.join(this_dir, "scripts")),
    ]
    for candidate in candidates:
        if os.path.isdir(candidate) and os.path.exists(os.path.join(candidate, "capture.py")):
            return candidate

    raise RuntimeError(
        "Cannot locate cliproof scripts. Set the CLIPROOF_SCRIPTS_DIR environment variable "
        "to the absolute path of skills/cliproof/scripts/."
    )
```

- [ ] **Step 4: Create `cliproof/_types.py`**

```python
"""_types.py — public types, dataclasses, and exceptions for the cliproof Python API."""


class CliproofError(Exception):
    """Raised when a cliproof operation fails (non-zero exit, structured error)."""
    def __init__(self, data):
        self.data = data
        reason = data.get("reason", "error")
        step = data.get("step", "?")
        super().__init__("[{}] {}".format(step, reason))


class RedactionBlockedError(CliproofError):
    """Raised when redact() finds a SECRET-class pattern (exit code 3)."""


class CliproofNotReadyError(CliproofError):
    """Raised on import when required tools are missing (lazy_health=False)."""


class CaptureResult:
    __slots__ = ("image", "renderer", "tier", "warnings", "scale", "fmt", "elapsed_s")

    def __init__(self, image, renderer=None, tier=None, warnings=None,
                 scale=1, fmt="svg", elapsed_s=0.0):
        self.image = image
        self.renderer = renderer
        self.tier = tier
        self.warnings = warnings or []
        self.scale = scale
        self.fmt = fmt
        self.elapsed_s = elapsed_s

    def __repr__(self):
        return "CaptureResult(image={!r}, renderer={!r}, tier={})".format(
            self.image, self.renderer, self.tier)


class RedactResult:
    __slots__ = ("findings", "file")

    def __init__(self, findings, file=None):
        self.findings = findings
        self.file = file

    def __repr__(self):
        return "RedactResult(findings={}, file={!r})".format(self.findings, self.file)


class EmbedResult:
    __slots__ = ("readme", "diff")

    def __init__(self, readme, diff=""):
        self.readme = readme
        self.diff = diff


class CheckResult:
    __slots__ = ("total", "drifted")

    def __init__(self, total, drifted):
        self.total = total
        self.drifted = list(drifted)

    @property
    def fresh(self):
        return len(self.drifted) == 0
```

- [ ] **Step 5: Create `cliproof/_api.py`**

```python
"""_api.py — subprocess dispatch layer: calls scripts with --json, returns typed objects."""
import json
import os
import subprocess
import sys
import tempfile

from cliproof._dispatch import scripts_dir
from cliproof._types import (
    CaptureResult, RedactResult, EmbedResult, CheckResult,
    CliproofError, RedactionBlockedError,
)

_EXIT_SECRET = 3
_EXIT_TIMEOUT = 4
_EXIT_UNSAFE = 5
_EXIT_DRIFT = 6


def _run(script_name, args, timeout=60):
    """Run a cliproof script with --json and return the parsed result dict."""
    script = os.path.join(scripts_dir(), script_name + ".py")
    cmd = [sys.executable, script] + list(args) + ["--json"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
    stdout = proc.stdout.strip()
    if not stdout:
        raise CliproofError({
            "reason": "no_output",
            "step": script_name,
            "exit_code": proc.returncode,
            "hint": proc.stderr.strip()[:300] if proc.stderr else None,
        })
    return json.loads(stdout)


def health():
    """Return the health status dict. Does not raise — callers check result['ok']."""
    return _run("health", [])


def guard(command):
    """Check if a command is safe to capture.

    Returns True if safe.
    Raises CliproofError if unsafe (exit code 5).
    """
    data = _run("guard", [command])
    if not data["ok"]:
        raise CliproofError(data)
    return True


def capture(command, output=None, preset=None, scale=1, fmt="svg", timeout=30):
    """Capture a command's output as a styled SVG (or other format).

    Args:
        command: Shell command to execute and capture.
        output:  Output file path. Defaults to a temp file.
        preset:  Theme preset name (e.g. 'catppuccin', 'macos').
        scale:   Pixel density multiplier (1, 2, or 3).
        fmt:     Output format: 'svg' (default), 'png', 'webp', 'og'.
        timeout: Seconds before killing the renderer (default 30).

    Returns:
        CaptureResult

    Raises:
        CliproofError on failure or timeout.
    """
    if output is None:
        fd, output = tempfile.mkstemp(suffix=".svg")
        os.close(fd)

    args = ["--execute", command, "-o", output, "--timeout", str(timeout)]
    if preset:
        args += ["--preset", preset]
    if scale != 1:
        args += ["--scale", str(scale)]
    if fmt != "svg":
        args += ["--format", fmt]

    data = _run("capture", args, timeout=timeout + 5)
    if not data["ok"]:
        raise CliproofError(data)
    out = data["outputs"]
    return CaptureResult(
        image=out.get("image", output),
        renderer=data.get("renderer"),
        tier=data.get("tier"),
        warnings=data.get("warnings", []),
        scale=out.get("scale", scale),
        fmt=out.get("format", fmt),
        elapsed_s=data.get("elapsed_s", 0.0),
    )


def redact(file_path, in_place=False):
    """Redact secrets from a file.

    Returns:
        RedactResult

    Raises:
        RedactionBlockedError if SECRET-class patterns are found (exit code 3).
        CliproofError on other failures.
    """
    args = [file_path]
    if in_place:
        args.append("--in-place")

    data = _run("redact", args)
    if not data["ok"]:
        ec = data.get("exit_code", 1)
        if ec == _EXIT_SECRET:
            raise RedactionBlockedError(data)
        raise CliproofError(data)
    out = data.get("outputs", {})
    return RedactResult(
        findings=out.get("findings", 0),
        file=out.get("file", file_path),
    )


def embed(readme, image, block_id, heading="Demo", alt=None):
    """Idempotently insert or update a cliproof image block in a README.

    Returns:
        EmbedResult

    Raises:
        CliproofError on failure.
    """
    if alt is None:
        alt = os.path.basename(image)
    args = [readme, "--image", image, "--id", block_id,
            "--heading", heading, "--alt", alt]

    data = _run("embed", args)
    if not data["ok"]:
        raise CliproofError(data)
    out = data.get("outputs", {})
    return EmbedResult(
        readme=out.get("readme", readme),
        diff=out.get("diff", ""),
    )


def check(manifest=None):
    """Check that all proofs in the manifest are fresh.

    Returns:
        CheckResult

    Raises:
        CliproofError with exit_code=6 if drift is detected.
    """
    args = []
    if manifest:
        args += ["--manifest", manifest]

    data = _run("check", args)
    out = data.get("outputs", {})
    result = CheckResult(
        total=out.get("total", 0),
        drifted=out.get("drifted", []),
    )
    if not data["ok"]:
        raise CliproofError(data)
    return result
```

- [ ] **Step 6: Create `cliproof/__init__.py`**

```python
"""cliproof — Python library for capturing, redacting, and embedding terminal proofs.

Usage:
    from cliproof import capture, redact, embed, check, health, guard

    result = capture("pytest -q", preset="catppuccin")
    redact(result.image, in_place=True)
    embed("README.md", image=result.image, block_id="tests")
"""
from cliproof._api import capture, redact, embed, check, health, guard
from cliproof._types import (
    CaptureResult, RedactResult, EmbedResult, CheckResult,
    CliproofError, RedactionBlockedError, CliproofNotReadyError,
)

_lazy_health = False


def configure(lazy_health=False):
    """Configure cliproof behaviour.

    Args:
        lazy_health: If True, skip the health check on import (default False).
                     Useful in CI where tools are known to be present.
    """
    global _lazy_health
    _lazy_health = lazy_health


__all__ = [
    "capture", "redact", "embed", "check", "health", "guard", "configure",
    "CaptureResult", "RedactResult", "EmbedResult", "CheckResult",
    "CliproofError", "RedactionBlockedError", "CliproofNotReadyError",
]
```

- [ ] **Step 7: Create `cliproof/py.typed`** (empty file, PEP 561 marker)

```
(empty file)
```

- [ ] **Step 8: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "cliproof"
version = "0.2.0"
description = "Your README should show it works — not just say it."
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.8"
keywords = ["terminal", "screenshot", "cli", "readme", "documentation", "developer-tools"]
authors = [{name = "aks-builds"}]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.8",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]

[tool.setuptools.packages.find]
include = ["cliproof*"]

[tool.setuptools.package-data]
cliproof = ["py.typed"]
```

- [ ] **Step 9: Run tests**

```
pytest tests/test_pypackage.py -v
```
Expected: all 11 tests PASS.

- [ ] **Step 10: Verify full suite still green**

```
pytest -q
```
Expected: 167 passed (156 + 11 new).

- [ ] **Step 11: Commit**

```
git add cliproof/ pyproject.toml tests/test_pypackage.py
git commit -m "feat(pypackage): cliproof Python library — dispatch layer, typed API, pyproject.toml"
```

---

## Task 2: MCP server

**Files:**
- Create: `skills/cliproof/scripts/mcp_server.py`
- Modify: `bin/cli.js`
- Create: `tests/test_mcp_server.py`

The MCP protocol uses JSON-RPC 2.0 over stdio with `Content-Length` headers.
Wire format:
```
Content-Length: 123\r\n
\r\n
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{...}}
```

### 2a — Tests

- [ ] **Step 1: Create `tests/test_mcp_server.py`**

```python
# tests/test_mcp_server.py
import json
import mcp_server


def _msg(obj):
    """Encode a JSON-RPC message as Content-Length framed bytes."""
    body = json.dumps(obj).encode("utf-8")
    return b"Content-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body


def _parse(data):
    """Parse Content-Length framed response bytes into a dict."""
    header, _, body = data.partition(b"\r\n\r\n")
    return json.loads(body)


def test_read_message_parses_content_length_frame(monkeypatch):
    msg = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
    import io
    monkeypatch.setattr(mcp_server.sys, "stdin",
                        io.TextIOWrapper(io.BytesIO(_msg(msg)), encoding="utf-8"))
    monkeypatch.setattr(mcp_server.sys.stdin, "buffer",
                        io.BytesIO(_msg(msg)))
    result = mcp_server._read_message()
    assert result["method"] == "initialize"
    assert result["id"] == 1


def test_tools_list_returns_all_tools():
    tools = mcp_server.TOOLS
    names = {t["name"] for t in tools}
    for expected in ["capture", "redact", "embed", "check", "guard",
                     "verify", "suggest", "annotate", "health"]:
        assert expected in names, "tool '{}' missing from TOOLS".format(expected)


def test_tool_has_required_fields():
    for tool in mcp_server.TOOLS:
        assert "name" in tool
        assert "description" in tool
        assert "inputSchema" in tool
        assert tool["inputSchema"]["type"] == "object"


def test_handle_initialize_returns_capabilities():
    req = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
           "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                      "clientInfo": {"name": "test", "version": "1.0"}}}
    resp = mcp_server._handle_request(req)
    assert resp["id"] == 1
    assert "result" in resp
    assert "capabilities" in resp["result"]
    assert "tools" in resp["result"]["capabilities"]
    assert "serverInfo" in resp["result"]


def test_handle_tools_list():
    req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
    resp = mcp_server._handle_request(req)
    assert resp["id"] == 2
    assert "result" in resp
    assert "tools" in resp["result"]
    assert len(resp["result"]["tools"]) > 0


def test_handle_unknown_method_returns_error():
    req = {"jsonrpc": "2.0", "id": 3, "method": "unknown/method", "params": {}}
    resp = mcp_server._handle_request(req)
    assert "error" in resp
    assert resp["error"]["code"] == -32601  # Method not found


def test_notification_returns_none():
    # Notifications have no "id" — server should not respond
    notif = {"jsonrpc": "2.0", "method": "initialized", "params": {}}
    resp = mcp_server._handle_request(notif)
    assert resp is None


def test_tools_call_guard_dispatches(monkeypatch):
    import subprocess as sp, json as _json

    fake_result = {"ok": True, "step": "guard", "outputs": {"safe": True},
                   "warnings": [], "elapsed_s": 0.0}

    class FakeProc:
        stdout = _json.dumps(fake_result)
        stderr = ""
        returncode = 0

    monkeypatch.setattr(sp, "run", lambda *a, **kw: FakeProc())

    req = {
        "jsonrpc": "2.0", "id": 4, "method": "tools/call",
        "params": {"name": "guard", "arguments": {"command": "echo hello"}}
    }
    resp = mcp_server._handle_request(req)
    assert resp["id"] == 4
    assert "result" in resp
    content = resp["result"]["content"]
    assert len(content) > 0
    parsed = _json.loads(content[0]["text"])
    assert parsed["ok"] is True
```

- [ ] **Step 2: Run to verify failure**

```
pytest tests/test_mcp_server.py -v
```
Expected: `ImportError: No module named 'mcp_server'`

### 2b — Implement

- [ ] **Step 3: Create `skills/cliproof/scripts/mcp_server.py`**

```python
#!/usr/bin/env python3
"""mcp_server.py — stdio MCP server for cliproof.

Exposes every cliproof kernel operation as an MCP tool using JSON-RPC 2.0
over Content-Length-framed stdio. Wire up in Claude Code:

    // .mcp.json
    { "mcpServers": { "cliproof": { "command": "cliproof", "args": ["mcp"] } } }

Or directly:
    python mcp_server.py

Exit codes: 0 clean shutdown, 1 fatal error.
Pure standard library. No network (beyond dispatching to scripts).
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_VERSION = "0.2.0"
_PROTOCOL = "2024-11-05"

# Tool definitions — each maps directly to a kernel script.
TOOLS = [
    {
        "name": "capture",
        "description": "Capture a real command's output as a styled SVG screenshot. "
                       "Returns the image path and renderer tier.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute and capture"},
                "output": {"type": "string", "description": "Output SVG path (required)"},
                "preset": {"type": "string", "description": "Theme preset (e.g. catppuccin, macos, tokyo-night)"},
                "scale": {"type": "integer", "description": "Pixel density 1/2/3 (default 1)"},
                "format": {"type": "string", "enum": ["svg", "png", "webp", "og"], "description": "Output format"},
                "timeout": {"type": "number", "description": "Renderer timeout in seconds (default 30)"},
            },
            "required": ["command", "output"],
        },
    },
    {
        "name": "redact",
        "description": "Scan a captured SVG for secrets and redact them. "
                       "Exits with error if SECRET-class patterns are found.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": "Path to SVG file to scan"},
                "in_place": {"type": "boolean", "description": "Rewrite the file (default false)"},
            },
            "required": ["file"],
        },
    },
    {
        "name": "embed",
        "description": "Idempotently insert or update a cliproof image block in README.md.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "readme": {"type": "string", "description": "Path to README.md"},
                "image": {"type": "string", "description": "Path to image file"},
                "id": {"type": "string", "description": "Unique block ID for idempotent updates"},
                "heading": {"type": "string", "description": "Heading under which to insert (default Demo)"},
                "alt": {"type": "string", "description": "Alt text for the image"},
            },
            "required": ["readme", "image", "id"],
        },
    },
    {
        "name": "check",
        "description": "Verify all proof baselines are still fresh. Fails if any proof has drifted.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "manifest": {"type": "string", "description": "Path to proof.json (default .cliproof/proof.json)"},
            },
        },
    },
    {
        "name": "guard",
        "description": "Check if a command is safe to capture. Returns ok=true if safe.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Command string to safety-check"},
            },
            "required": ["command"],
        },
    },
    {
        "name": "verify",
        "description": "Run a command and judge PASS/FAIL from exit code and error signatures.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Command to run and judge"},
                "timeout": {"type": "number", "description": "Timeout in seconds (default 20)"},
            },
            "required": ["command"],
        },
    },
    {
        "name": "suggest",
        "description": "Scan the repo and suggest the best command to capture as proof.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "Path to the repository (default .)"},
            },
        },
    },
    {
        "name": "annotate",
        "description": "Add overlays to an SVG capture: caption bar, pass/fail badge, "
                       "version stamp, CI ribbon.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "input": {"type": "string", "description": "Input SVG path"},
                "output": {"type": "string", "description": "Output SVG path"},
                "caption": {"type": "string", "description": "Caption bar text"},
                "badge": {"type": "string", "enum": ["pass", "fail"], "description": "Corner badge"},
                "stamp": {"type": "string", "description": "Version watermark text"},
                "ci_ribbon": {"type": "string", "description": "Top ribbon bar text"},
            },
            "required": ["input", "output"],
        },
    },
    {
        "name": "health",
        "description": "Report which capture tools are installed and what modes are available.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "storyboard",
        "description": "Stitch multiple SVG captures into a single storyboard image.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "inputs": {"type": "array", "items": {"type": "string"}, "description": "SVG file paths"},
                "output": {"type": "string", "description": "Output SVG path"},
            },
            "required": ["inputs", "output"],
        },
    },
    {
        "name": "pr",
        "description": "Post the screenshot and verify report as a pull-request comment.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pr": {"type": "integer", "description": "PR number"},
                "image_url": {"type": "string", "description": "Raw URL of the image"},
                "verify": {"type": "string", "description": "Path to verify report markdown"},
            },
            "required": ["pr"],
        },
    },
]

# Map tool name → (script_name, arg_builder)
def _build_args(name, arguments):
    """Translate MCP tool arguments to script CLI args."""
    a = arguments or {}
    if name == "capture":
        args = ["--execute", a["command"], "-o", a["output"]]
        if a.get("preset"):
            args += ["--preset", a["preset"]]
        if a.get("scale") and a["scale"] != 1:
            args += ["--scale", str(a["scale"])]
        if a.get("format") and a["format"] != "svg":
            args += ["--format", a["format"]]
        if a.get("timeout"):
            args += ["--timeout", str(a["timeout"])]
        return args

    if name == "redact":
        args = [a["file"]]
        if a.get("in_place"):
            args.append("--in-place")
        return args

    if name == "embed":
        args = [a["readme"], "--image", a["image"], "--id", a["id"]]
        if a.get("heading"):
            args += ["--heading", a["heading"]]
        if a.get("alt"):
            args += ["--alt", a["alt"]]
        return args

    if name == "check":
        return (["--manifest", a["manifest"]] if a.get("manifest") else [])

    if name == "guard":
        return [a["command"]]

    if name == "verify":
        args = ["--command", a["command"]]
        if a.get("timeout"):
            args += ["--timeout", str(a["timeout"])]
        return args

    if name == "suggest":
        return [a.get("repo", ".")]

    if name == "annotate":
        args = [a["input"], "-o", a["output"]]
        if a.get("caption"):
            args += ["--caption", a["caption"]]
        if a.get("badge"):
            args += ["--badge", a["badge"]]
        if a.get("stamp"):
            args += ["--stamp", a["stamp"]]
        if a.get("ci_ribbon"):
            args += ["--ci-ribbon", a["ci_ribbon"]]
        return args

    if name == "health":
        return []

    if name == "storyboard":
        args = list(a.get("inputs", [])) + ["-o", a["output"]]
        return args

    if name == "pr":
        args = ["--pr", str(a["pr"])]
        if a.get("image_url"):
            args += ["--image-url", a["image_url"]]
        if a.get("verify"):
            args += ["--verify", a["verify"]]
        return args

    return []


def _run_script(name, args):
    """Call a script with --json and return the parsed result dict."""
    script = os.path.join(_SCRIPTS_DIR, name + ".py")
    cmd = [sys.executable, script] + args + ["--json"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    stdout = proc.stdout.strip()
    if not stdout:
        return {"ok": False, "step": name, "reason": "no_output",
                "exit_code": proc.returncode,
                "stderr": proc.stderr.strip()[:300]}
    return json.loads(stdout)


def _read_message():
    """Read one Content-Length-framed JSON-RPC message from stdin."""
    headers = {}
    while True:
        raw = sys.stdin.buffer.readline()
        if raw in (b"\r\n", b"\n", b""):
            break
        line = raw.decode("utf-8", "replace").rstrip()
        if ":" in line:
            k, _, v = line.partition(":")
            headers[k.strip()] = v.strip()

    length = int(headers.get("Content-Length", 0))
    if length == 0:
        return None
    content = sys.stdin.buffer.read(length)
    return json.loads(content.decode("utf-8"))


def _write_message(obj):
    """Write one Content-Length-framed JSON-RPC message to stdout."""
    body = json.dumps(obj).encode("utf-8")
    sys.stdout.buffer.write(
        b"Content-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body
    )
    sys.stdout.buffer.flush()


def _handle_request(req):
    """Process one JSON-RPC request and return the response (or None for notifications)."""
    method = req.get("method", "")
    req_id = req.get("id")  # None for notifications

    # Notifications: no response
    if req_id is None:
        return None

    if method == "initialize":
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "protocolVersion": _PROTOCOL,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "cliproof", "version": _VERSION},
            },
        }

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}

    if method == "tools/call":
        params = req.get("params", {})
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        tool_names = {t["name"] for t in TOOLS}
        if tool_name not in tool_names:
            return {
                "jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32602, "message": "Unknown tool: {}".format(tool_name)},
            }

        try:
            args = _build_args(tool_name, arguments)
            result = _run_script(tool_name, args)
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(result, indent=2)}],
                    "isError": not result.get("ok", False),
                },
            }
        except Exception as exc:
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {
                    "content": [{"type": "text",
                                 "text": json.dumps({"ok": False, "error": str(exc)})}],
                    "isError": True,
                },
            }

    # Method not found
    return {
        "jsonrpc": "2.0", "id": req_id,
        "error": {"code": -32601, "message": "Method not found: {}".format(method)},
    }


def main(argv=None):
    print("cliproof MCP server v{} starting (stdio)".format(_VERSION), file=sys.stderr)
    # Startup health check — warn but do not refuse to start
    try:
        import health as _h
        info = _h.detect()
        if not info.get("ok"):
            print("mcp_server: WARNING — no capture renderer found; capture tool will use tier-4 stub.",
                  file=sys.stderr)
        else:
            print("mcp_server: renderers: {}".format(", ".join(info.get("renderers", []))),
                  file=sys.stderr)
    except Exception:
        pass
    while True:
        try:
            msg = _read_message()
        except EOFError:
            break
        except Exception as exc:
            print("mcp_server: read error: {}".format(exc), file=sys.stderr)
            break

        if msg is None:
            break

        resp = _handle_request(msg)
        if resp is not None:
            _write_message(resp)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests**

```
pytest tests/test_mcp_server.py -v
```
Expected: all 9 tests PASS.

- [ ] **Step 5: Add `mcp` command to `bin/cli.js`**

Read `bin/cli.js`. Do NOT add `mcp_server` to PASSTHROUGH (the command name `mcp` differs from
the script name `mcp_server`). Add an explicit handler in `main()` before the passthrough check:

```js
if (cmd === "mcp") {
  const py = findPython();
  if (!py) { console.error("cliproof: Python 3.8+ not found on PATH."); return 1; }
  return runPython(py, "mcp_server", argv.slice(1));
}
```

`serve` CAN go in PASSTHROUGH (command name matches script name), OR use an explicit handler.
Use an explicit handler for clarity alongside `mcp`:
```js
if (cmd === "serve") {
  const py = findPython();
  if (!py) { console.error("cliproof: Python 3.8+ not found on PATH."); return 1; }
  return runPython(py, "serve", argv.slice(1));
}
```

Do NOT add `mcp_server` or `serve` to the PASSTHROUGH array.

- [ ] **Step 6: Run full suite**

```
pytest -q && npm test
```
Expected: pytest 176+ passing, npm 5 passing.

- [ ] **Step 7: Commit**

```
git add skills/cliproof/scripts/mcp_server.py tests/test_mcp_server.py bin/cli.js
git commit -m "feat(mcp): stdio MCP server exposing 11 cliproof tools (JSON-RPC 2.0)"
```

---

## Task 3: HTTP daemon

**Files:**
- Create: `skills/cliproof/scripts/serve.py`
- Create: `tests/test_serve.py`
- Modify: `bin/cli.js` (add `serve`)

### 3a — Tests

- [ ] **Step 1: Create `tests/test_serve.py`**

```python
# tests/test_serve.py
import json
import threading
import time
import urllib.request
import urllib.error
import serve


def _start_daemon(port):
    """Start the HTTP daemon on the given port in a background thread. Returns the thread."""
    t = threading.Thread(target=serve.start, args=(port,), daemon=True)
    t.start()
    # Give server time to bind
    for _ in range(20):
        try:
            urllib.request.urlopen("http://localhost:{}/health".format(port), timeout=1)
            return t
        except Exception:
            time.sleep(0.05)
    raise RuntimeError("Server did not start on port {}".format(port))


def test_health_endpoint_returns_json():
    port = 17171
    _start_daemon(port)
    resp = urllib.request.urlopen("http://localhost:{}/health".format(port), timeout=5)
    data = json.loads(resp.read())
    assert "ok" in data
    assert "renderers" in data


def test_themes_endpoint_returns_list():
    port = 17172
    _start_daemon(port)
    resp = urllib.request.urlopen("http://localhost:{}/themes".format(port), timeout=5)
    data = json.loads(resp.read())
    assert isinstance(data, list)
    assert len(data) >= 5
    names = [t["name"] for t in data]
    assert "macos" in names


def test_guard_post_safe_command():
    # Use a real guard call — "echo hello" has no risky patterns, so guard.py exits 0.
    # No monkeypatching: the server runs in a background thread and subprocess.run
    # inside it would not be reliably intercepted by monkeypatch.
    port = 17173
    _start_daemon(port)
    body = json.dumps({"command": "echo hello"}).encode()
    req = urllib.request.Request(
        "http://localhost:{}/guard".format(port),
        data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    resp = urllib.request.urlopen(req, timeout=5)
    data = json.loads(resp.read())
    assert data["ok"] is True


def test_unknown_endpoint_returns_404():
    port = 17174
    _start_daemon(port)
    try:
        urllib.request.urlopen("http://localhost:{}/nonexistent".format(port), timeout=5)
        assert False, "Expected 404"
    except urllib.error.HTTPError as e:
        assert e.code == 404


def test_missing_required_field_returns_400():
    port = 17175
    _start_daemon(port)
    body = json.dumps({}).encode()  # missing "command"
    req = urllib.request.Request(
        "http://localhost:{}/guard".format(port),
        data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        urllib.request.urlopen(req, timeout=5)
        assert False, "Expected 400"
    except urllib.error.HTTPError as e:
        assert e.code == 400
```

- [ ] **Step 2: Run to verify failure**

```
pytest tests/test_serve.py -v
```
Expected: `ImportError: No module named 'serve'`

### 3b — Implement

- [ ] **Step 3: Create `skills/cliproof/scripts/serve.py`**

```python
#!/usr/bin/env python3
"""serve.py — local HTTP daemon for cliproof.

Exposes every cliproof kernel operation as a REST endpoint.
Any language (Node, Go, Rust) can call it without needing Python on the caller side.
IDE extensions call it to trigger captures and check freshness.

Usage:
    python serve.py                 # default port 7070
    python serve.py --port 8080     # custom port
    cliproof serve                  # via the npm CLI

Endpoints:
    GET  /health
    GET  /themes
    POST /capture   { command, output, preset?, scale?, format?, timeout? }
    POST /redact    { file, in_place? }
    POST /embed     { readme, image, id, heading?, alt? }
    POST /check     { manifest? }
    POST /guard     { command }
    POST /annotate  { input, output, caption?, badge?, stamp?, ci_ribbon? }
    POST /verify    { command, timeout? }
    POST /suggest   { repo? }

All responses are JSON. Errors use { "ok": false, "error": "...", "hint"?: "..." }.
Exit codes: 0 clean, 1 startup failure.
Pure standard library. No network.
"""
import argparse
import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))


def _run_script(name, args, timeout=120):
    """Call a cliproof script with --json and return parsed result dict."""
    script = os.path.join(_SCRIPTS_DIR, name + ".py")
    cmd = [sys.executable, script] + list(args) + ["--json"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    stdout = proc.stdout.strip()
    if not stdout:
        return {"ok": False, "error": "no output from {}".format(name),
                "stderr": proc.stderr.strip()[:300]}
    return json.loads(stdout)


def _list_themes():
    """Return list of { name, preview_line } dicts from built-in + file-based themes."""
    builtin = ["macos", "github-dark", "nord", "iterm", "win11"]
    themes_dir = os.path.normpath(os.path.join(_SCRIPTS_DIR, "..", "themes"))
    file_based = []
    if os.path.isdir(themes_dir):
        file_based = [f[:-5] for f in os.listdir(themes_dir) if f.endswith(".json")]
    all_names = sorted(set(builtin + file_based))
    return [{"name": n, "preview_line": "theme: {}".format(n)} for n in all_names]


class _Handler(BaseHTTPRequestHandler):
    def _json_response(self, status, data):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length))

    def do_GET(self):
        if self.path == "/health":
            self._json_response(200, _run_script("health", []))
        elif self.path == "/themes":
            self._json_response(200, _list_themes())
        else:
            self._json_response(404, {"ok": False, "error": "not found: {}".format(self.path)})

    def do_POST(self):
        try:
            body = self._read_body()
        except Exception as exc:
            self._json_response(400, {"ok": False, "error": "invalid JSON body: {}".format(exc)})
            return

        path = self.path.rstrip("/")

        try:
            result = self._dispatch(path, body)
        except _BadRequest as e:
            self._json_response(400, {"ok": False, "error": str(e)})
            return
        except Exception as exc:
            self._json_response(500, {"ok": False, "error": str(exc)})
            return

        if result is None:
            self._json_response(404, {"ok": False, "error": "not found: {}".format(path)})
        else:
            status = 200 if result.get("ok") else 422
            self._json_response(status, result)

    def _dispatch(self, path, body):
        if path == "/capture":
            if "command" not in body or "output" not in body:
                raise _BadRequest("capture requires 'command' and 'output'")
            args = ["--execute", body["command"], "-o", body["output"]]
            if body.get("preset"):
                args += ["--preset", body["preset"]]
            if body.get("scale") and body["scale"] != 1:
                args += ["--scale", str(body["scale"])]
            if body.get("format") and body["format"] != "svg":
                args += ["--format", body["format"]]
            timeout = body.get("timeout", 30)
            if body.get("timeout"):
                args += ["--timeout", str(timeout)]
            return _run_script("capture", args, timeout=timeout + 10)

        if path == "/redact":
            if "file" not in body:
                raise _BadRequest("redact requires 'file'")
            args = [body["file"]]
            if body.get("in_place"):
                args.append("--in-place")
            return _run_script("redact", args)

        if path == "/embed":
            if not all(k in body for k in ("readme", "image", "id")):
                raise _BadRequest("embed requires 'readme', 'image', 'id'")
            args = [body["readme"], "--image", body["image"], "--id", body["id"]]
            if body.get("heading"):
                args += ["--heading", body["heading"]]
            if body.get("alt"):
                args += ["--alt", body["alt"]]
            return _run_script("embed", args)

        if path == "/check":
            args = []
            if body.get("manifest"):
                args += ["--manifest", body["manifest"]]
            return _run_script("check", args)

        if path == "/guard":
            if "command" not in body:
                raise _BadRequest("guard requires 'command'")
            return _run_script("guard", [body["command"]])

        if path == "/annotate":
            if not all(k in body for k in ("input", "output")):
                raise _BadRequest("annotate requires 'input' and 'output'")
            args = [body["input"], "-o", body["output"]]
            for flag, key in [("--caption", "caption"), ("--badge", "badge"),
                               ("--stamp", "stamp"), ("--ci-ribbon", "ci_ribbon")]:
                if body.get(key):
                    args += [flag, body[key]]
            return _run_script("annotate", args)

        if path == "/verify":
            if "command" not in body:
                raise _BadRequest("verify requires 'command'")
            args = ["--command", body["command"]]
            if body.get("timeout"):
                args += ["--timeout", str(body["timeout"])]
            return _run_script("verify", args)

        if path == "/suggest":
            return _run_script("suggest", [body.get("repo", ".")])

        return None

    def log_message(self, fmt, *args):
        pass  # suppress request logs (daemon runs silently)


class _BadRequest(Exception):
    pass


def start(port=7070):
    """Start the HTTP server. Blocks until interrupted."""
    server = HTTPServer(("127.0.0.1", port), _Handler)
    print("cliproof serve: listening on http://localhost:{}".format(port), file=sys.stderr)
    server.serve_forever()


def main(argv=None):
    p = argparse.ArgumentParser(description="cliproof HTTP daemon.")
    p.add_argument("--port", type=int, default=7070, help="port to listen on (default 7070)")
    args = p.parse_args(argv)

    # Run health check before starting
    import health as _health
    info = _health.detect()
    if not info["ok"]:
        print("cliproof serve: WARNING — no capture renderer found (will use tier-4 fallback).",
              file=sys.stderr)

    start(args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests**

```
pytest tests/test_serve.py -v
```
Expected: all 5 tests PASS. (Each test uses a unique port to avoid collisions.)

- [ ] **Step 5: Verify `serve` command works in `bin/cli.js`**

The `serve` explicit handler was added in Task 2 Step 5. Verify it's present:
```
node bin/cli.js serve --help
```
Expected: prints serve.py help output.

- [ ] **Step 6: Run full suite**

```
pytest -q && npm test
```

- [ ] **Step 7: Commit**

```
git add skills/cliproof/scripts/serve.py tests/test_serve.py bin/cli.js
git commit -m "feat(daemon): HTTP daemon on port 7070 with REST API for all cliproof operations"
```

---

## Task 4: Dockerfile + docker.yml

**Files:**
- Create: `Dockerfile`
- Create: `docker-entrypoint.sh`
- Create: `.github/workflows/docker.yml`

No unit tests for the Dockerfile (build happens in CI). A smoke test using `--dry-run` validates structure.

- [ ] **Step 1: Create `docker-entrypoint.sh`**

```bash
#!/bin/sh
# docker-entrypoint.sh — run health check then dispatch to the requested script.
set -e

# Health gate: verify tools are present before running any command
python /app/skills/cliproof/scripts/health.py --json > /tmp/health.json 2>&1
if ! python -c "import sys,json; d=json.load(open('/tmp/health.json')); sys.exit(0 if d.get('ok') else 1)" 2>/dev/null; then
    echo "cliproof: health check failed at container start" >&2
    cat /tmp/health.json >&2
    exit 1
fi

# Dispatch: first arg is the script name, rest are args
SCRIPT="$1"
shift
exec python "/app/skills/cliproof/scripts/${SCRIPT}.py" "$@"
```

- [ ] **Step 2: Create `Dockerfile`**

```dockerfile
# cliproof — Alpine + Python 3.12 + freeze@0.2.2 + gifsicle
# Usage: docker run --rm -v $PWD:/repo ghcr.io/aks-builds/cliproof:latest \
#            capture --execute "mytool --help" -o /repo/.github/media/help.svg --json

FROM python:3.12-alpine

# Install build tools, Go (for freeze), and runtime tools
RUN apk add --no-cache \
    go \
    gcc \
    musl-dev \
    git \
    gifsicle \
    && go install github.com/charmbracelet/freeze@v0.2.2 \
    && apk del go gcc musl-dev git

# Go binaries are at /root/go/bin
ENV PATH="/root/go/bin:${PATH}"

WORKDIR /app
COPY . .

RUN chmod +x /app/docker-entrypoint.sh

# Verify the image works at build time
RUN python skills/cliproof/scripts/health.py

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=2 \
    CMD python /app/skills/cliproof/scripts/health.py --json | \
        python -c "import sys,json; sys.exit(0 if json.load(sys.stdin).get('ok') else 1)"

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["health"]
```

- [ ] **Step 3: Create `.github/workflows/docker.yml`**

```yaml
name: docker

# Build and push the Docker image when a GitHub release is published.
# Image pushed to ghcr.io/aks-builds/cliproof and aks-builds/cliproof (Docker Hub).
#
# Required secrets:
#   DOCKERHUB_USERNAME   Docker Hub username
#   DOCKERHUB_TOKEN      Docker Hub access token

on:
  release:
    types: [published]
  workflow_dispatch:
    inputs:
      tag:
        description: "Image tag override (default: from package.json)"
        required: false

permissions:
  contents: read
  packages: write    # push to ghcr.io

jobs:
  build-push:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6

      - name: Resolve version tag
        id: ver
        run: |
          VERSION=$(node -p "require('./package.json').version")
          echo "version=$VERSION" >> "$GITHUB_OUTPUT"
          echo "tag=${INPUT_TAG:-v$VERSION}" >> "$GITHUB_OUTPUT"
        env:
          INPUT_TAG: ${{ inputs.tag }}

      - name: Set up QEMU (multi-arch)
        uses: docker/setup-qemu-action@v3

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Login to ghcr.io
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Login to Docker Hub
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKERHUB_USERNAME }}
          password: ${{ secrets.DOCKERHUB_TOKEN }}

      - name: Build and push
        uses: docker/build-push-action@v6
        with:
          context: .
          platforms: linux/amd64,linux/arm64
          push: true
          tags: |
            ghcr.io/aks-builds/cliproof:latest
            ghcr.io/aks-builds/cliproof:${{ steps.ver.outputs.tag }}
            aks-builds/cliproof:latest
            aks-builds/cliproof:${{ steps.ver.outputs.tag }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

- [ ] **Step 4: Validate Dockerfile syntax (no build needed)**

```bash
# Verify Dockerfile exists and is readable
python -c "
with open('Dockerfile') as f:
    content = f.read()
assert 'FROM python:3.12-alpine' in content
assert 'freeze@v0.2.2' in content
assert 'HEALTHCHECK' in content
assert 'ENTRYPOINT' in content
print('Dockerfile structure OK')
"
```

- [ ] **Step 5: Commit**

```
git add Dockerfile docker-entrypoint.sh .github/workflows/docker.yml
git commit -m "feat(docker): Alpine image with freeze pre-installed, health gate at start"
```

---

## Task 5: Wire up MCP config, update README, add `.mcp.json` example

**Files:**
- Create: `.mcp.json`
- Modify: `README.md`
- Modify: `package.json` (add `cliproof/` to `files`)

- [ ] **Step 1: Create `.mcp.json` at repo root**

```json
{
  "mcpServers": {
    "cliproof": {
      "command": "cliproof",
      "args": ["mcp"]
    }
  }
}
```

- [ ] **Step 2: Add `cliproof/` to `package.json` files list**

In `package.json`, update the `files` array:
```json
"files": [
  "bin/",
  "cliproof/",
  "skills/",
  "README.md",
  "LICENSE.md"
]
```

- [ ] **Step 3: Update README.md Install section**

Add after the existing npm install block (under the `## Install` heading), new installation entries:

```markdown
**MCP server (any MCP-compatible agent — Claude Code, Cursor, Windsurf, LangChain):**
```json
// .mcp.json
{ "mcpServers": { "cliproof": { "command": "cliproof", "args": ["mcp"] } } }
```

**Python library:**
```bash
pip install cliproof
```
```python
from cliproof import capture, redact, embed
result = capture("pytest -q", preset="catppuccin")
redact(result.image, in_place=True)
embed("README.md", image=result.image, block_id="tests")
```

**Docker (CI — GitHub Actions, GitLab CI, Jenkins, any runner):**
```yaml
- docker run --rm -v $PWD:/repo \
    ghcr.io/aks-builds/cliproof:latest \
    capture --execute "pytest -q" -o /repo/.github/media/tests.svg --json
```

**Local HTTP daemon (IDE extensions, polyglot callers):**
```bash
cliproof serve            # starts on localhost:7070
curl localhost:7070/health
```
```

- [ ] **Step 4: Run full suite**

```
pytest -q && npm test
```
Expected: all tests pass.

- [ ] **Step 5: Commit**

```
git add .mcp.json package.json README.md
git commit -m "feat(integration): .mcp.json example, PyPI + Docker + daemon install docs"
```

---

## Task 6: CHANGELOG + version bumps (v0.3.0)

- [ ] **Step 1: Run the final checklist**

```bash
pytest -q                                    # all green
npm test                                     # all green
pytest tests/test_no_dependencies.py -v      # stdlib only
python skills/cliproof/scripts/mcp_server.py --help 2>&1 || true
python skills/cliproof/scripts/serve.py --help
node bin/cli.js mcp --help 2>&1 | head -3
node bin/cli.js serve --help 2>&1 | head -3
python -c "import cliproof; print(cliproof.health())"
```

- [ ] **Step 2: Update `CHANGELOG.md`**

Add after the `## [0.2.0]` entry:

```markdown
## [0.3.0] - 2026-06-10

### Added
- MCP server (`cliproof mcp`): stdio JSON-RPC 2.0 server exposing 11 tools — any MCP-compatible agent can call cliproof natively
- Python library (`pip install cliproof`): `capture()`, `redact()`, `embed()`, `check()`, `health()`, `guard()` with typed return objects and exceptions
- Docker image (`ghcr.io/aks-builds/cliproof`): Alpine + Python 3.12 + freeze@0.2.2 + gifsicle, health gate at container start, multi-arch amd64/arm64
- HTTP daemon (`cliproof serve`): stdlib REST API on localhost:7070 for IDE extensions and polyglot callers
- `.mcp.json` example for one-line Claude Code / Cursor wiring
```

- [ ] **Step 3: Bump version**

```bash
npm version minor --no-git-tag-version
# Results in 0.3.0
```

Update `pyproject.toml` version to match:
Change `version = "0.2.0"` → `version = "0.3.0"`

- [ ] **Step 4: Commit**

```
git add CHANGELOG.md package.json package-lock.json pyproject.toml
git commit -m "chore(release): v0.3.0"
```

---

## M2 self-review checklist

Before marking M2 complete, verify:

- [ ] `pytest -q` → 0 failures
- [ ] `npm test` → 0 failures
- [ ] `pytest tests/test_no_dependencies.py` → PASS (stdlib only — pypackage dispatch uses subprocess, not imports)
- [ ] `python skills/cliproof/scripts/mcp_server.py` starts without crash (Ctrl-C to stop)
- [ ] `python -c "import cliproof; r = cliproof.health(); print(r['ok'])"` → True
- [ ] `node bin/cli.js themes list` still works (11 themes)
- [ ] Dockerfile exists, contains `FROM python:3.12-alpine` and `HEALTHCHECK`
- [ ] `.mcp.json` present at repo root
- [ ] `cliproof/` added to `package.json` files list
- [ ] No `Co-Authored-By` trailers in any commit
