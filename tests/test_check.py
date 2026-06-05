import sys

import check


def test_compare_equal():
    ok, diff = check.compare("hello\nworld\n", "hello\nworld\n")
    assert ok and diff == ""


def test_compare_ignores_volatile_noise():
    # only the duration changed — normalised, so NOT drift
    ok, _ = check.compare("42 passed in 0.21s\n", "42 passed in 0.19s\n")
    assert ok


def test_compare_detects_real_drift():
    ok, diff = check.compare("42 passed\n", "3 failed, 39 passed\n")
    assert not ok and "passed" in diff


def test_run_command_captures_output():
    out = check.run_command(f'{sys.executable} -c "print(123)"')
    assert "123" in out


def test_check_one_update_then_match(tmp_path):
    baseline = tmp_path / "b.txt"
    cmd = f'{sys.executable} -c "print(\'ok in 0.1s\')"'
    entry = {"id": "t", "command": cmd, "baseline": str(baseline)}
    assert check._check_one(entry, update=True) is True   # writes baseline
    assert baseline.exists()
    assert check._check_one(entry, update=False) is True   # matches (duration normalised)


def test_check_one_detects_drift(tmp_path):
    baseline = tmp_path / "b.txt"
    baseline.write_text("EXPECTED OUTPUT\n", encoding="utf-8")
    entry = {"id": "t", "command": f'{sys.executable} -c "print(\'DIFFERENT\')"',
             "baseline": str(baseline)}
    assert check._check_one(entry, update=False) is False
