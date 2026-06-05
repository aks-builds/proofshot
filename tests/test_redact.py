import redact


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


def test_exit_codes(tmp_path, capsys):
    secret = tmp_path / "s.txt"
    secret.write_text("AKIAIOSFODNN7EXAMPLE", encoding="utf-8")
    assert redact.main([str(secret), "--in-place"]) == 3

    clean = tmp_path / "c.txt"
    clean.write_text("hello world", encoding="utf-8")
    assert redact.main([str(clean), "--in-place"]) == 0
