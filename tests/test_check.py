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


import json
import _kernel


def test_check_fresh_emits_json(tmp_path, capsys):
    import json as _json
    baseline = tmp_path / "base.txt"
    baseline.write_text("hello\n", encoding="utf-8")

    manifest = tmp_path / "proof.json"
    manifest.write_text(_json.dumps({
        "proofs": [{
            "id": "test",
            "command": "echo hello",
            "baseline": str(baseline),
            "image": "img.svg"
        }]
    }), encoding="utf-8")

    rc = check.main(["--manifest", str(manifest), "--json"])
    assert rc == 0
    out = _json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert out["step"] == "check"
    assert out["outputs"]["drifted"] == []


def test_check_drift_exits_6(tmp_path, capsys):
    import json as _json
    baseline = tmp_path / "base.txt"
    baseline.write_text("original output\n", encoding="utf-8")

    manifest = tmp_path / "proof.json"
    manifest.write_text(_json.dumps({
        "proofs": [{
            "id": "test",
            "command": "echo different output",
            "baseline": str(baseline),
            "image": "img.svg"
        }]
    }), encoding="utf-8")

    rc = check.main(["--manifest", str(manifest), "--json"])
    assert rc == _kernel.EXIT_DRIFT
    out = _json.loads(capsys.readouterr().out)
    assert out["ok"] is False
    assert out["exit_code"] == _kernel.EXIT_DRIFT
    assert "test" in out["outputs"]["drifted"]


def test_proof_json_gif_block_is_accepted(tmp_path):
    import json as _json
    baseline = tmp_path / "base.txt"
    baseline.write_text("hello\n", encoding="utf-8")
    manifest = tmp_path / "proof.json"
    manifest.write_text(_json.dumps({
        "proofs": [{
            "id": "demo",
            "command": "echo hello",
            "baseline": str(baseline),
            "image": "img.svg",
            "gif": {
                "speed": "realistic",
                "loop": "once",
                "freeze_last": True,
                "max_kb": 1800
            }
        }]
    }), encoding="utf-8")
    rc = check.main(["--manifest", str(manifest)])
    assert rc == 0
