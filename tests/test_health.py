import json
import health


def test_health_detect_returns_required_keys(monkeypatch):
    monkeypatch.setattr(health.shutil, "which", lambda t: "/usr/bin/" + t if t == "freeze" else None)
    result = health.detect()
    assert "ok" in result
    assert "renderers" in result
    assert "modes" in result
    assert "gif" in result
    assert "python" in result
    assert "redaction" in result
    assert "guard" in result
    assert "gifsicle" in result


def test_health_main_json_output(monkeypatch, capsys):
    monkeypatch.setattr(health.shutil, "which", lambda t: "/usr/bin/" + t if t == "freeze" else None)
    rc = health.main(["--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert "ok" in out
    assert "renderers" in out


def test_health_main_human_output(monkeypatch, capsys):
    monkeypatch.setattr(health.shutil, "which", lambda _: None)
    rc = health.main([])
    assert rc == 0
    captured = capsys.readouterr()
    assert "cliproof health" in captured.out


def test_health_no_renderers_ok_is_false(monkeypatch):
    monkeypatch.setattr(health.shutil, "which", lambda _: None)
    result = health.detect()
    assert result["ok"] is False
    assert result["renderers"] == []


def test_health_with_freeze_ok_is_true(monkeypatch):
    monkeypatch.setattr(health.shutil, "which", lambda t: "/usr/bin/freeze" if t == "freeze" else None)

    class FakeProc:
        returncode = 0
        stdout = b"freeze version 0.2.2\n"
        stderr = b""

    monkeypatch.setattr(health.subprocess, "run", lambda *a, **kw: FakeProc())
    result = health.detect()
    assert result["ok"] is True
    assert any("freeze" in r for r in result["renderers"])
