import json
import redact
import _kernel


def _names(findings):
    return {f[0] for f in findings}


def test_github_token_is_secret_and_masked():
    text = "export TOKEN=ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    out, findings = redact.redact(text)
    assert "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789" not in out
    assert any(sev == redact.SECRET for _, sev, _ in findings)


def test_aws_key_masked():
    out, findings = redact.redact("key AKIAIOSFODNN7EXAMPLE here")
    assert "AKIAIOSFODNN7EXAMPLE" not in out
    assert "aws-access-key" in _names(findings)


def test_private_key_block_redacted():
    text = "-----BEGIN RSA PRIVATE KEY-----\nMIIEabc\n-----END RSA PRIVATE KEY-----"
    out, findings = redact.redact(text)
    assert "[redacted-private-key]" in out
    assert "private-key-block" in _names(findings)


def test_kv_secret_masked():
    out, _ = redact.redact("password: hunter2supersecret")
    assert "hunter2supersecret" not in out


def test_privacy_items_normalised_not_blocking():
    text = "ping from 192.168.1.50 by me@example.com in /home/aditya/app"
    out, findings = redact.redact(text)
    assert "me@example.com" not in out
    assert "192.168.1.50" not in out
    assert "/home/aditya" not in out
    assert all(sev == redact.PRIVACY for _, sev, _ in findings)


def test_windows_home_path_normalised():
    out, _ = redact.redact(r"at C:\Users\AdityaKumarSingh\proj")
    assert "AdityaKumarSingh" not in out
    assert "<user>" in out


def test_clean_text_unchanged():
    text = "All 42 tests passed in 1.3s"
    out, findings = redact.redact(text)
    assert out == text
    assert findings == []


def test_bom_input_is_stripped_not_preserved(tmp_path):
    f = tmp_path / "bom.svg"
    # UTF-8 BOM + clean content
    f.write_bytes(b"\xef\xbb\xbf<svg>All 42 tests passed</svg>")
    assert redact.main([str(f), "--in-place"]) == 0
    data = f.read_bytes()
    assert data[:3] != b"\xef\xbb\xbf"          # BOM removed on rewrite
    assert data.startswith(b"<svg>")            # starts at markup
    assert "﻿" not in f.read_text(encoding="utf-8")


def test_inplace_writes_lf_not_crlf(tmp_path):
    f = tmp_path / "multi.txt"
    f.write_bytes(b"line one\nline two\nall clean\n")
    assert redact.main([str(f), "--in-place"]) == 0
    assert b"\r\n" not in f.read_bytes()


def test_exit_codes(tmp_path, capsys):
    secret = tmp_path / "s.txt"
    secret.write_text("AKIAIOSFODNN7EXAMPLE", encoding="utf-8")
    assert redact.main([str(secret), "--in-place"]) == 3

    clean = tmp_path / "c.txt"
    clean.write_text("hello world", encoding="utf-8")
    assert redact.main([str(clean), "--in-place"]) == 0


def test_clean_input_json_mode(tmp_path, capsys):
    f = tmp_path / "out.svg"
    f.write_text("<svg>echo hello</svg>", encoding="utf-8")
    rc = redact.main([str(f), "--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert out["step"] == "redact"
    assert out["outputs"]["findings"] == 0


def test_secret_input_json_mode(tmp_path, capsys):
    f = tmp_path / "out.svg"
    f.write_text("<svg>AKIAIOSFODNN7EXAMPLE</svg>", encoding="utf-8")
    rc = redact.main([str(f), "--json"])
    assert rc == _kernel.EXIT_SECRET
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False
    assert out["exit_code"] == _kernel.EXIT_SECRET
