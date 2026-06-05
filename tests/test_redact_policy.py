import json

import redact


def test_allowlist_exempts_false_positive():
    # the canonical AWS example key would normally be masked; allowlist keeps it
    text = "key AKIAIOSFODNN7EXAMPLE here"
    out, findings = redact.redact(text, allow=[r"AKIAIOSFODNN7EXAMPLE"])
    assert "AKIAIOSFODNN7EXAMPLE" in out
    assert findings == []


def test_extra_pattern_masks_custom_secret():
    rules = [("custom-0", redact.SECRET, redact.re.compile(r"CUSTOMSECRET\d+"), redact._mask_match)]
    out, findings = redact.redact("token CUSTOMSECRET12345 end", extra_rules=rules)
    assert "CUSTOMSECRET12345" not in out
    assert any(name == "custom-0" for name, _, _ in findings)


def test_load_policy_roundtrip(tmp_path):
    policy = tmp_path / "redact.json"
    policy.write_text(json.dumps({"patterns": [r"ACME-\d+"], "allow": [r"ACME-0+"]}), encoding="utf-8")
    extra, allow = redact.load_policy(str(policy))
    assert len(extra) == 1 and allow == [r"ACME-0+"]
    # custom pattern masks, but the allowlisted variant survives
    out, _ = redact.redact("ACME-12345 and ACME-0000", extra_rules=extra, allow=allow)
    assert "ACME-12345" not in out
    assert "ACME-0000" in out


def test_load_policy_missing_file_is_empty():
    assert redact.load_policy("/nonexistent/redact.json") == ([], [])
