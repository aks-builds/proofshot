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
Pure standard library. No network.
"""
import argparse
import json
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _kernel import setup_streams  # noqa: E402 — same directory
setup_streams()

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))

_ALLOWED_SCRIPTS = frozenset([
    "capture", "redact", "embed", "check", "guard", "verify",
    "suggest", "annotate", "storyboard", "pr", "health",
])


def _run_script(name, args, timeout=120):
    """Call a cliproof script with --json and return parsed result dict."""
    if name not in _ALLOWED_SCRIPTS:
        return {"ok": False, "error": "unknown operation", "step": name}
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


class _BadRequest(Exception):
    pass


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
            # Security gate: validate command is safe before running it
            guard_check = _run_script("guard", [body["command"]])
            if not guard_check.get("ok"):
                raise _BadRequest("command rejected by safety guard: {}".format(
                    guard_check.get("reason", "unsafe")))
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
            guard_check = _run_script("guard", [body["command"]])
            if not guard_check.get("ok"):
                raise _BadRequest("command rejected by safety guard")
            args = ["--command", body["command"]]
            if body.get("timeout"):
                args += ["--timeout", str(body["timeout"])]
            return _run_script("verify", args)

        if path == "/suggest":
            return _run_script("suggest", [body.get("repo", ".")])

        return None

    def log_message(self, fmt, *args):
        pass  # suppress request logs


def start(port=7070):
    """Start the HTTP server. Blocks until interrupted."""
    server = HTTPServer(("127.0.0.1", port), _Handler)
    print("cliproof serve: listening on http://localhost:{}".format(port), file=sys.stderr)
    server.serve_forever()


def main(argv=None):
    p = argparse.ArgumentParser(description="cliproof HTTP daemon.")
    p.add_argument("--port", type=int, default=7070, help="port to listen on (default 7070)")
    args = p.parse_args(argv)

    import health as _health
    info = _health.detect()
    if not info["ok"]:
        print("cliproof serve: WARNING — no capture renderer found (will use tier-4 fallback).",
              file=sys.stderr)

    start(args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
