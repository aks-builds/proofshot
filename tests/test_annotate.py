import annotate

SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="40"><rect/></svg>'


def test_caption_grows_height_and_embeds_text():
    out = annotate.add_caption(SVG, "all 42 tests pass", bar=44)
    assert 'height="84"' in out          # 40 + 44 bar
    assert "all 42 tests pass" in out
    assert "<rect/>" in out              # original content preserved


def test_caption_escapes_markup():
    out = annotate.add_caption(SVG, "a < b & c > d")
    assert "&lt;" in out and "&amp;" in out and "&gt;" in out


def test_accent_color_applied():
    out = annotate.add_caption(SVG, "ok", accent="#ff0000")
    assert "#ff0000" in out
