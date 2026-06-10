import json
import embed
import _kernel


def test_creates_block_under_heading():
    text = "# Title\n\nIntro.\n\n## Demo\n\nold text\n"
    out = embed.upsert(text, ".github/media/a.png", "a running", "a", "Demo")
    assert "<!-- cliproof:start id=a -->" in out
    assert "![a running](.github/media/a.png)" in out
    # inserted right after the heading
    assert out.index("cliproof:start") > out.index("## Demo")


def test_idempotent_replace_same_id():
    text = "# T\n\n## Demo\n"
    once = embed.upsert(text, ".github/media/a.png", "alt1", "a", "Demo")
    twice = embed.upsert(once, ".github/media/a-v2.png", "alt2", "a", "Demo")
    # exactly one block, updated to the new image
    assert twice.count("<!-- cliproof:start id=a -->") == 1
    assert "a-v2.png" in twice
    assert "alt2" in twice
    assert "alt1" not in twice


def test_different_ids_coexist():
    text = "# T\n"
    out = embed.upsert(text, "x.png", "x", "one", "Demo")
    out = embed.upsert(out, "y.png", "y", "two", "Demo")
    assert out.count("cliproof:start") == 2
    assert "id=one" in out and "id=two" in out


def test_appends_heading_when_absent():
    out = embed.upsert("# T\n\nbody\n", "z.png", "z", "z", "Screenshots")
    assert "## Screenshots" in out
    assert "cliproof:start id=z" in out


def test_bom_readme_rewritten_without_bom(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_bytes("﻿# Title\n\n## Demo\n".encode("utf-8"))
    rc = embed.main([str(readme), "--image", "a.png", "--alt", "a", "--id", "a",
                     "--heading", "Demo", "--no-backup"])
    assert rc == 0
    data = readme.read_bytes()
    assert data[:3] != b"\xef\xbb\xbf"
    assert data.startswith(b"# Title")
    assert b"cliproof:start id=a" in data


def test_output_is_lf_not_crlf(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_bytes(b"# Title\n\nIntro line.\n\n## Demo\n")
    embed.main([str(readme), "--image", "a.png", "--alt", "a", "--id", "a",
                "--heading", "Demo", "--no-backup"])
    data = readme.read_bytes()
    assert b"\r\n" not in data          # no Windows CRLF translation slipped in
    assert b"cliproof:start id=a" in data


def test_windows_path_normalised_to_forward_slashes():
    out = embed.upsert("# T\n", r".github\media\a.png", "a", "a", "Demo")
    assert ".github/media/a.png" in out
    assert "\\" not in out.split("](", 1)[1].split(")", 1)[0]


def test_embed_json_mode(tmp_path, capsys):
    readme = tmp_path / "README.md"
    readme.write_text("# Hello\n", encoding="utf-8")
    img = tmp_path / "shot.svg"
    img.write_text("<svg/>", encoding="utf-8")
    rc = embed.main([
        str(readme), "--image", str(img), "--alt", "demo",
        "--id", "demo", "--heading", "Demo", "--json"
    ])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert out["step"] == "embed"
    assert "diff" in out["outputs"]
