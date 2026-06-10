import json
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
