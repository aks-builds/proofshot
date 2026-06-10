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


def test_badge_pass_adds_green_corner_badge(tmp_path):
    in_svg = tmp_path / "in.svg"
    in_svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="200">'
        '<rect width="400" height="200" fill="#0d1117"/></svg>',
        encoding="utf-8"
    )
    out_svg = tmp_path / "out.svg"
    rc = annotate.main([str(in_svg), "--caption", "tests pass", "--badge", "pass",
                        "-o", str(out_svg)])
    assert rc == 0
    content = out_svg.read_text(encoding="utf-8")
    assert "PASS" in content
    assert "#238636" in content


def test_badge_fail_adds_red_corner_badge(tmp_path):
    in_svg = tmp_path / "in.svg"
    in_svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="200">'
        '<rect width="400" height="200" fill="#0d1117"/></svg>',
        encoding="utf-8"
    )
    out_svg = tmp_path / "out.svg"
    rc = annotate.main([str(in_svg), "--caption", "tests fail", "--badge", "fail",
                        "-o", str(out_svg)])
    assert rc == 0
    content = out_svg.read_text(encoding="utf-8")
    assert "FAIL" in content
    assert "#da3633" in content


def test_stamp_adds_version_watermark(tmp_path):
    in_svg = tmp_path / "in.svg"
    in_svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="200">'
        '<rect width="400" height="200" fill="#0d1117"/></svg>',
        encoding="utf-8"
    )
    out_svg = tmp_path / "out.svg"
    rc = annotate.main([str(in_svg), "--stamp", "v1.2.0 - 2026-06-10", "-o", str(out_svg)])
    assert rc == 0
    content = out_svg.read_text(encoding="utf-8")
    assert "v1.2.0" in content


def test_ci_ribbon_adds_top_bar(tmp_path):
    in_svg = tmp_path / "in.svg"
    in_svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="200">'
        '<rect width="400" height="200" fill="#0d1117"/></svg>',
        encoding="utf-8"
    )
    out_svg = tmp_path / "out.svg"
    rc = annotate.main([str(in_svg), "--ci-ribbon", "CI passing", "-o", str(out_svg)])
    assert rc == 0
    content = out_svg.read_text(encoding="utf-8")
    assert "CI passing" in content


def test_no_overlay_flag_returns_error(tmp_path):
    in_svg = tmp_path / "in.svg"
    in_svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="200">'
        '<rect width="400" height="200" fill="#0d1117"/></svg>',
        encoding="utf-8"
    )
    out_svg = tmp_path / "out.svg"
    rc = annotate.main([str(in_svg), "-o", str(out_svg)])
    assert rc != 0
