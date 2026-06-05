import pr


def test_build_comment_has_marker_image_and_caption():
    body = pr.build_comment("https://x/y.svg", caption="mytool --help")
    assert body.startswith(pr.MARKER)
    assert "![mytool --help](https://x/y.svg)" in body
    assert "`mytool --help`" in body
    assert "cliproof" in body


def test_build_comment_includes_verify_report():
    body = pr.build_comment("https://x/y.svg", caption="t", verify_md="### verify — ✅ PASS")
    assert "✅ PASS" in body


def test_build_comment_without_image():
    body = pr.build_comment("", caption="")
    assert pr.MARKER in body
    assert "![" not in body
