"""Validate the plugin/marketplace manifests and SKILL.md frontmatter.

Pure stdlib (no PyYAML) — the frontmatter we author is simple `key: value`.
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
RESERVED = ("anthropic", "claude")


def _load(*parts):
    with open(os.path.join(ROOT, *parts), "r", encoding="utf-8") as fh:
        return json.load(fh)


def test_plugin_manifest():
    m = _load(".claude-plugin", "plugin.json")
    assert KEBAB.match(m["name"]), m["name"]
    assert m["name"] == "cliproof"
    assert m.get("license") == "MIT"
    assert isinstance(m.get("keywords", []), list)


def test_marketplace_manifest():
    m = _load(".claude-plugin", "marketplace.json")
    # required top-level fields: name (kebab), owner{name}, plugins[]
    assert KEBAB.match(m["name"]), m["name"]
    assert m["owner"]["name"]
    assert isinstance(m["plugins"], list) and m["plugins"]
    for plugin in m["plugins"]:
        assert plugin["name"]      # required
        assert plugin["source"]    # required


def _frontmatter(path):
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    assert text.startswith("---"), "missing frontmatter"
    block = text.split("---", 2)[1]
    fm = {}
    for line in block.splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip()
    return fm


def test_skill_frontmatter():
    fm = _frontmatter(os.path.join(ROOT, "skills", "cliproof", "SKILL.md"))
    name, desc = fm.get("name", ""), fm.get("description", "")
    assert KEBAB.match(name) and len(name) <= 64
    assert not any(r in name.lower() for r in RESERVED), "name must not contain reserved words"
    assert 0 < len(desc) <= 1024
    assert "<" not in name and ">" not in name


def test_skill_dir_matches_manifest_keyword():
    assert os.path.isdir(os.path.join(ROOT, "skills", "cliproof"))
    assert os.path.isfile(os.path.join(ROOT, "skills", "cliproof", "SKILL.md"))


import os


def test_all_theme_files_are_valid():
    import json as _json
    themes_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "skills", "cliproof", "themes"
    )
    assert os.path.isdir(themes_dir), "themes/ directory missing"
    files = [f for f in os.listdir(themes_dir) if f.endswith(".json")]
    assert len(files) >= 6, "expected at least 6 theme files, got {}".format(len(files))
    for fn in files:
        path = os.path.join(themes_dir, fn)
        with open(path, encoding="utf-8") as fh:
            data = _json.load(fh)
        assert "name" in data, "{} missing 'name'".format(fn)
        assert "flags" in data, "{} missing 'flags'".format(fn)
        for pair in data["flags"]:
            assert len(pair) == 2, "{} flag entry must be [flag, value_or_null]".format(fn)


def test_file_based_theme_loaded_in_capture():
    import sys
    scripts_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "skills", "cliproof", "scripts"
    )
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import capture
    presets = capture._all_presets()
    assert "catppuccin" in presets
    assert "tokyo-night" in presets
    assert "dracula" in presets
    # Verify catppuccin theme contributes --theme flag
    cmd = capture.build_command("freeze", ["--execute", "ls"], "o.svg", preset="catppuccin")
    assert "--theme" in cmd
    assert "catppuccin-mocha" in cmd
