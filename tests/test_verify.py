import sys

import verify


def test_detect_errors_python_traceback():
    text = "Traceback (most recent call last):\n  File x\nValueError: boom"
    tags = verify.detect_errors(text)
    assert "python" in tags


def test_detect_errors_clean():
    assert verify.detect_errors("All 42 tests passed in 1.2s") == []


def test_verify_pass():
    r = verify.verify(f'{sys.executable} -c "print(\'all good\')"')
    assert r["ok"] is True and r["exit_code"] == 0


def test_verify_fail_on_exit_code():
    r = verify.verify(f'{sys.executable} -c "import sys; sys.exit(1)"')
    assert r["ok"] is False and r["exit_code"] == 1


def test_verify_fail_on_error_signature_despite_zero_exit():
    # exits 0 but prints a traceback signature -> still FAIL
    code = "print('Traceback (most recent call last):')"
    r = verify.verify(f'{sys.executable} -c "{code}"')
    assert r["exit_code"] == 0
    assert r["ok"] is False
    assert "python" in r["errors"]


def test_report_markdown_shapes():
    ok = verify.report_markdown("x", {"ok": True, "exit_code": 0, "errors": [], "output": "hi"})
    bad = verify.report_markdown("y", {"ok": False, "exit_code": 1, "errors": ["python"], "output": "boom"})
    assert "PASS" in ok and "FAIL" in bad and "python" in bad
