import rasterize


def test_svg_pixel_size_from_width_height():
    svg = '<svg width="629.33" height="374.00" xmlns="...">'
    assert rasterize.svg_pixel_size(svg) == (630, 374)


def test_svg_pixel_size_from_viewbox():
    assert rasterize.svg_pixel_size('<svg viewBox="0 0 800 450" xmlns="...">') == (800, 450)


def test_svg_pixel_size_falls_back_to_default():
    assert rasterize.svg_pixel_size("<svg xmlns='...'>") == (1000, 600)


def test_svg_pixel_size_tolerates_leading_bom_char():
    # if a BOM char survived into the text, dimension parsing still works
    assert rasterize.svg_pixel_size('﻿<svg width="100" height="50">') == (100, 50)


def test_build_browser_command_has_screenshot_and_file_uri(tmp_path):
    svg = tmp_path / "a.svg"
    svg.write_text("<svg/>", encoding="utf-8")
    out = tmp_path / "a.png"
    cmd = rasterize.build_render_command("browser", "chrome", str(svg), str(out), (630, 374), 2.0)
    assert "--headless=new" in cmd
    assert "--window-size=630,374" in cmd
    assert any(a.startswith("--screenshot=") for a in cmd)
    assert any(a.startswith("--force-device-scale-factor=2") for a in cmd)
    assert cmd[-1].startswith("file://")  # SVG loaded directly, no re-encode


def test_build_tool_commands():
    rsvg = rasterize.build_render_command("rsvg-convert", "rsvg-convert", "i.svg", "o.png", (1, 1), 2.0)
    assert rsvg == ["rsvg-convert", "--zoom", "2.0", "--output", "o.png", "i.svg"]

    resvg = rasterize.build_render_command("resvg", "resvg", "i.svg", "o.png", (1, 1), 2.0)
    assert resvg == ["resvg", "--zoom", "2.0", "i.svg", "o.png"]

    ink = rasterize.build_render_command("inkscape", "inkscape", "i.svg", "o.png", (1, 1), 2.0)
    assert "--export-type=png" in ink and "--export-dpi=192" in ink

    magick = rasterize.build_render_command("magick", "magick", "i.svg", "o.png", (1, 1), 2.0)
    assert magick[:3] == ["magick", "-density", "192"]


def test_find_renderer_prefers_browser(monkeypatch):
    monkeypatch.setattr(rasterize.shutil, "which",
                        lambda name: "/usr/bin/chromium" if name == "chromium" else None)
    monkeypatch.setattr(rasterize, "_BROWSER_PATHS", [])
    kind, path = rasterize.find_renderer()
    assert kind == "browser"
    assert path == "/usr/bin/chromium"


def test_find_renderer_respects_explicit_tool(monkeypatch):
    monkeypatch.setattr(rasterize.shutil, "which",
                        lambda name: "/usr/bin/resvg" if name == "resvg" else None)
    assert rasterize.find_renderer("resvg") == ("resvg", "/usr/bin/resvg")
    assert rasterize.find_renderer("inkscape") is None


def test_main_writes_output(tmp_path, monkeypatch):
    svg = tmp_path / "a.svg"
    svg.write_text('<svg width="100" height="50"></svg>', encoding="utf-8")
    out = tmp_path / "a.png"

    monkeypatch.setattr(rasterize, "find_renderer", lambda preferred=None: ("resvg", "/usr/bin/resvg"))

    def fake_run(cmd, **kw):
        out.write_bytes(b"\x89PNG fake")

        class R:
            returncode = 0
            stdout = b""
            stderr = b""

        return R()

    monkeypatch.setattr(rasterize.subprocess, "run", fake_run)
    assert rasterize.main([str(svg)]) == 0
    assert out.exists()


def test_main_no_renderer_returns_1(tmp_path, monkeypatch):
    svg = tmp_path / "a.svg"
    svg.write_text("<svg/>", encoding="utf-8")
    monkeypatch.setattr(rasterize, "find_renderer", lambda preferred=None: None)
    assert rasterize.main([str(svg)]) == 1
