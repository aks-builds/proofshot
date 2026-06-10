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
