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
    assert m["name"] == "proofshot"
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
    fm = _frontmatter(os.path.join(ROOT, "skills", "proofshot", "SKILL.md"))
    name, desc = fm.get("name", ""), fm.get("description", "")
    assert KEBAB.match(name) and len(name) <= 64
    assert not any(r in name.lower() for r in RESERVED), "name must not contain reserved words"
    assert 0 < len(desc) <= 1024
    assert "<" not in name and ">" not in name


def test_skill_dir_matches_manifest_keyword():
    assert os.path.isdir(os.path.join(ROOT, "skills", "proofshot"))
    assert os.path.isfile(os.path.join(ROOT, "skills", "proofshot", "SKILL.md"))
