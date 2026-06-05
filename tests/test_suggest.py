import json

import suggest


def test_package_json_scripts_ranked(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({
        "name": "demo", "scripts": {"test": "jest", "dev": "vite", "build": "tsc"}
    }), encoding="utf-8")
    results = suggest.scan(str(tmp_path))
    cmds = [r["command"] for r in results]
    assert "npm test" in cmds
    # deterministic/proof commands outrank long-running ones
    assert suggest._score("npm test") > suggest._score("npm run dev")
    assert results[0]["command"] != "npm run dev"


def test_makefile_targets(tmp_path):
    (tmp_path / "Makefile").write_text("test:\n\tpytest\nbuild:\n\tgcc x.c\n", encoding="utf-8")
    cmds = [r["command"] for r in suggest.scan(str(tmp_path))]
    assert "make test" in cmds and "make build" in cmds


def test_readme_quickstart_line(tmp_path):
    (tmp_path / "README.md").write_text("```\n$ mytool --help\n```\n", encoding="utf-8")
    cmds = [r["command"] for r in suggest.scan(str(tmp_path))]
    assert "mytool --help" in cmds


def test_empty_repo_yields_nothing(tmp_path):
    assert suggest.scan(str(tmp_path)) == []
