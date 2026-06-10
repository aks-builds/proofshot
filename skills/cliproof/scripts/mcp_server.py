#!/usr/bin/env python3
"""mcp_server.py — stdio MCP server for cliproof.

Exposes every cliproof kernel operation as an MCP tool using JSON-RPC 2.0
over Content-Length-framed stdio. Wire up in Claude Code:

    // .mcp.json
    { "mcpServers": { "cliproof": { "command": "cliproof", "args": ["mcp"] } } }

Or directly:
    python mcp_server.py

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
def _read_version():
    try:
        _pkg = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "package.json"))
        with open(_pkg, encoding="utf-8") as _f:
            return json.load(_f).get("version", "0.3.0")
    except Exception:
        return "0.3.0"

_VERSION = _read_version()
_PROTOCOL = "2024-11-05"

TOOLS = [
    {
        "name": "capture",
        "description": "Capture a real command's output as a styled SVG screenshot. Returns the image path and renderer tier.",
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
        "description": "Scan a captured SVG for secrets and redact them. Exits with error if SECRET-class patterns are found.",
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
        "description": "Add overlays to an SVG capture: caption bar, pass/fail badge, version stamp, CI ribbon.",
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
        return list(a.get("inputs", [])) + ["-o", a["output"]]

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
    req_id = req.get("id")

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

    return {
        "jsonrpc": "2.0", "id": req_id,
        "error": {"code": -32601, "message": "Method not found: {}".format(method)},
    }


def main(argv=None):
    print("cliproof MCP server v{} starting (stdio)".format(_VERSION), file=sys.stderr)
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
