# tests/test_pypackage.py
import sys
import os
import json

# Make the cliproof/ package importable from the repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cliproof
from cliproof._types import (
    CaptureResult, RedactResult, EmbedResult, CheckResult,
    RedactionBlockedError, CliproofError
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
    import subprocess as sp

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
    import subprocess as sp
    fake = {"ok": True, "step": "guard", "outputs": {"safe": True},
            "warnings": [], "elapsed_s": 0.0}

    class FakeProc:
        stdout = json.dumps(fake); stderr = ""; returncode = 0

    monkeypatch.setattr(sp, "run", lambda *a, **kw: FakeProc())
    assert cliproof.guard("echo hello") is True


def test_guard_unsafe_command_raises(monkeypatch):
    import subprocess as sp
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
    for name in ["capture", "redact", "embed", "check", "health", "guard", "configure"]:
        assert hasattr(cliproof, name), "cliproof.{} missing from public API".format(name)
