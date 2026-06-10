# tests/test_serve.py
import json
import threading
import time
import urllib.request
import urllib.error
import serve

_STARTED = {}


def _start_daemon(port):
    """Start the HTTP daemon on the given port in a background thread (once per port)."""
    if port in _STARTED:
        return _STARTED[port]
    t = threading.Thread(target=serve.start, args=(port,), daemon=True)
    t.start()
    for _ in range(40):
        try:
            urllib.request.urlopen("http://localhost:{}/health".format(port), timeout=1)
            _STARTED[port] = t
            return t
        except Exception:
            time.sleep(0.05)
    raise RuntimeError("Server did not start on port {}".format(port))


def test_health_endpoint_returns_json():
    _start_daemon(17171)
    resp = urllib.request.urlopen("http://localhost:17171/health", timeout=5)
    data = json.loads(resp.read())
    assert "ok" in data
    assert "renderers" in data


def test_themes_endpoint_returns_list():
    _start_daemon(17172)
    resp = urllib.request.urlopen("http://localhost:17172/themes", timeout=5)
    data = json.loads(resp.read())
    assert isinstance(data, list)
    assert len(data) >= 5
    names = [t["name"] for t in data]
    assert "macos" in names


def test_guard_post_safe_command():
    # Use a real guard call — "echo hello" has no risky patterns, guard.py exits 0.
    _start_daemon(17173)
    body = json.dumps({"command": "echo hello"}).encode()
    req = urllib.request.Request(
        "http://localhost:17173/guard",
        data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    resp = urllib.request.urlopen(req, timeout=10)
    data = json.loads(resp.read())
    assert data["ok"] is True


def test_unknown_endpoint_returns_404():
    _start_daemon(17174)
    try:
        urllib.request.urlopen("http://localhost:17174/nonexistent", timeout=5)
        assert False, "Expected 404"
    except urllib.error.HTTPError as e:
        assert e.code == 404


def test_missing_required_field_returns_400():
    _start_daemon(17175)
    body = json.dumps({}).encode()  # missing "command"
    req = urllib.request.Request(
        "http://localhost:17175/guard",
        data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        urllib.request.urlopen(req, timeout=5)
        assert False, "Expected 400"
    except urllib.error.HTTPError as e:
        assert e.code == 400
