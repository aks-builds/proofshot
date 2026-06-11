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


def test_extract_preset_consumes_flag():
    preset, rest = capture.extract_preset(["--preset", "macos", "--window", "--execute", "ls"])
    assert preset == "macos"
    assert rest == ["--window", "--execute", "ls"]
    preset2, rest2 = capture.extract_preset(["--preset=nord", "--execute", "ls"])
    assert preset2 == "nord" and rest2 == ["--execute", "ls"]
    assert capture.extract_preset(["--execute", "ls"]) == (None, ["--execute", "ls"])


def test_build_command_applies_preset_and_user_overrides():
    # preset contributes --theme dracula; build_command injects it
    cmd = capture.build_command("freeze", ["--execute", "ls"], "o.svg", preset="macos")
    assert "--window" in cmd and "dracula" in cmd
    # a user-supplied --theme wins over the preset's
    cmd2 = capture.build_command("freeze", ["--execute", "ls", "--theme", "nord"], "o.svg", preset="macos")
    assert "nord" in cmd2 and "dracula" not in cmd2


def test_main_rejects_unknown_preset(capsys):
    assert capture.main(["--preset", "nope", "--execute", "ls", "-o", "x.svg"]) == 1


import json
import _kernel


def test_json_flag_emits_success_result(tmp_path, monkeypatch, capsys):
    out = tmp_path / "shot.svg"

    def fake_run(cmd, **kw):
        target = cmd[cmd.index("--output") + 1]
        with open(target, "w") as f:
            f.write("<svg/>")
        class R:
            returncode = 0; stdout = b""; stderr = b""
        return R()

    monkeypatch.setattr(capture.subprocess, "run", fake_run)
    monkeypatch.setattr(capture.shutil, "which", lambda b: "/usr/bin/freeze" if b == "freeze" else None)

    rc = capture.main(["--execute", "echo hi", "-o", str(out), "--json"])
    assert rc == 0
    result = json.loads(capsys.readouterr().out)
    assert result["ok"] is True
    assert result["step"] == "capture"
    assert result["renderer"] == "freeze"
    assert result["tier"] == 1
    assert "image" in result["outputs"]


def test_timeout_flag_triggers_exit_4(tmp_path, monkeypatch, capsys):
    import time as _time
    out = tmp_path / "shot.svg"

    def slow_run(cmd, **kw):
        timeout = kw.get("timeout")
        if timeout and timeout < 1:
            raise capture.subprocess.TimeoutExpired(cmd, timeout)
        _time.sleep(10)

    monkeypatch.setattr(capture.subprocess, "run", slow_run)
    monkeypatch.setattr(capture.shutil, "which", lambda b: "/usr/bin/freeze" if b == "freeze" else None)

    rc = capture.main(["--execute", "echo hi", "-o", str(out), "--timeout", "0.1", "--json"])
    assert rc == _kernel.EXIT_TIMEOUT
    result = json.loads(capsys.readouterr().out)
    assert result["ok"] is False
    assert result["reason"] == "timeout"
    assert result["exit_code"] == _kernel.EXIT_TIMEOUT


def test_fallback_to_tier4_text_svg_when_no_renderers(tmp_path, monkeypatch, capsys):
    out = tmp_path / "shot.svg"
    monkeypatch.setattr(capture.shutil, "which", lambda _: None)

    rc = capture.main(["--execute", "echo hello", "-o", str(out), "--json"])
    assert rc == 0
    result = json.loads(capsys.readouterr().out)
    assert result["tier"] == 4
    assert result["renderer"] == "text-svg"
    assert out.exists() and out.stat().st_size > 0


def test_scale_flag_stored_in_result(tmp_path, monkeypatch, capsys):
    out = tmp_path / "shot.svg"

    def fake_run(cmd, **kw):
        target = cmd[cmd.index("--output") + 1]
        with open(target, "w") as f:
            f.write("<svg/>")
        class R:
            returncode = 0; stdout = b""; stderr = b""
        return R()

    monkeypatch.setattr(capture.subprocess, "run", fake_run)
    monkeypatch.setattr(capture.shutil, "which", lambda b: "/usr/bin/freeze" if b == "freeze" else None)

    rc = capture.main(["--execute", "echo hi", "-o", str(out), "--scale", "2", "--json"])
    assert rc == 0
    result = json.loads(capsys.readouterr().out)
    assert result["outputs"].get("scale") == 2


def test_windows_go_crash_prints_clean_message_not_stack_trace(tmp_path, monkeypatch, capsys):
    """freeze ≤0.2.x crashes with a Go runtime stack overflow on Windows.
    capture.py must detect the pattern and emit a clean diagnostic instead of
    dumping the full crash trace, then fall through to tier-4 gracefully."""
    out = tmp_path / "shot.svg"

    # Simulate the Windows Go runtime stack-overflow crash
    GO_CRASH_STDERR = (
        b"runtime: newstack sp=0x2bd69eb59e18 stack=[0x2bd69f386000, 0x2bd69f396000]\n"
        b"\tmorebuf={pc:0x7ff6fcbab335 sp:0x2bd69eb59e28 lr:0x0}\n"
        b"\tsched={pc:0x7ff6fcb8648b sp:0x2bd69eb59e20 lr:0x0 ctxt:0x0}\n"
        b"runtime: split stack overflow\n"
        b"fatal error: runtime: split stack overflow\n"
        b"\nruntime stack:\nruntime.throw(...)\n"
    )

    def freeze_crashes(cmd, **kw):
        class R:
            returncode = 2
            stdout = b""
            stderr = GO_CRASH_STDERR
        return R()

    monkeypatch.setattr(capture.subprocess, "run", freeze_crashes)
    monkeypatch.setattr(capture.shutil, "which",
                        lambda b: "/usr/bin/freeze" if b == "freeze" else None)

    rc = capture.main(["--execute", "echo hi", "-o", str(out), "--json"])

    # Capture stdout + stderr in one call (readouterr clears the buffer)
    captured = capsys.readouterr()

    # Must still succeed via tier-4 fallback
    assert rc == 0
    result = json.loads(captured.out)
    assert result["tier"] == 4
    assert result["renderer"] == "text-svg"

    # The Go crash trace must NOT appear in stderr
    assert "runtime: newstack" not in captured.err
    assert "split stack overflow" not in captured.err

    # A clean, actionable message must appear instead
    assert "Go runtime" in captured.err or "freeze crashed" in captured.err

