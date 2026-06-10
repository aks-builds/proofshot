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
