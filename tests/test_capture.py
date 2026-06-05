import capture


def test_partition_extracts_output_and_forwards_rest():
    out, binary, rest = capture.partition(
        ["--execute", "echo hi", "--window", "-o", "a.svg", "--theme", "dracula"]
    )
    assert out == "a.svg"
    assert binary == "freeze"
    # --execute (and its value) and style flags are forwarded untouched
    assert rest == ["--execute", "echo hi", "--window", "--theme", "dracula"]


def test_partition_handles_equals_and_freeze_bin():
    out, binary, rest = capture.partition(
        ["--output=b.png", "--freeze-bin", "/opt/freeze", "--execute", "ls"]
    )
    assert out == "b.png"
    assert binary == "/opt/freeze"
    assert rest == ["--execute", "ls"]


def test_coerce_svg_path():
    assert capture.coerce_svg_path("x.png") == ("x.svg", True)
    assert capture.coerce_svg_path("x.SVG")[1] is False
    assert capture.coerce_svg_path("dir/y.webp") == ("dir/y.svg", True)


def test_needs_language_only_for_execute_without_explicit_lexer():
    assert capture.needs_language(["--execute", "ls"]) is True
    assert capture.needs_language(["--execute", "ls", "--language", "ansi"]) is False
    assert capture.needs_language(["--window"]) is False  # file capture: leave lexer to freeze


def test_build_command_injects_language_and_output():
    cmd = capture.build_command("freeze", ["--execute", "ls", "--window"], "out.svg")
    assert cmd[0] == "freeze"
    assert cmd[-2:] == ["--output", "out.svg"]
    assert "--language" in cmd and "ansi" in cmd


def test_main_closes_stdin_and_coerces_png_to_svg(tmp_path, monkeypatch):
    out_png = tmp_path / "shot.png"
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        seen["kw"] = kw
        target = cmd[cmd.index("--output") + 1]
        with open(target, "w", encoding="utf-8") as fh:
            fh.write("<svg/>")

        class R:
            returncode = 0
            stdout = b""
            stderr = b""

        return R()

    monkeypatch.setattr(capture.subprocess, "run", fake_run)
    monkeypatch.setattr(capture.shutil, "which", lambda _b: "/usr/bin/freeze")

    rc = capture.main(["--execute", "echo hi", "-o", str(out_png)])
    assert rc == 0
    # the critical fix: freeze is always launched with stdin closed
    assert seen["kw"].get("stdin") is capture.subprocess.DEVNULL
    # png was coerced to svg, and that's what got written
    assert (tmp_path / "shot.svg").exists()
    assert not out_png.exists()


def test_main_requires_output(capsys):
    assert capture.main(["--execute", "ls"]) == 1


def test_strip_bom_removes_only_when_present(tmp_path):
    bommed = tmp_path / "b.svg"
    bommed.write_bytes(b"\xef\xbb\xbf<svg/>")
    assert capture.strip_bom(str(bommed)) is True
    assert bommed.read_bytes() == b"<svg/>"

    clean = tmp_path / "c.svg"
    clean.write_bytes(b"<svg/>")
    assert capture.strip_bom(str(clean)) is False
    assert clean.read_bytes() == b"<svg/>"


def test_main_strips_bom_from_freeze_output(tmp_path, monkeypatch):
    out = tmp_path / "shot.svg"

    def fake_run(cmd, **kw):
        target = cmd[cmd.index("--output") + 1]
        # simulate a tool that prepends a BOM
        with open(target, "wb") as fh:
            fh.write(b"\xef\xbb\xbf<svg/>")

        class R:
            returncode = 0
            stdout = b""
            stderr = b""

        return R()

    monkeypatch.setattr(capture.subprocess, "run", fake_run)
    monkeypatch.setattr(capture.shutil, "which", lambda _b: "/usr/bin/freeze")

    assert capture.main(["--execute", "echo hi", "-o", str(out)]) == 0
    assert out.read_bytes()[:3] != b"\xef\xbb\xbf"
