"""Guard the 'zero-dependency, no-network core' promise with an actual test.

Parses every bundled script's imports and asserts they are Python standard
library only (plus sibling scripts), and that none import a network module.
"""
import ast
import os
import sys

import pytest

SCRIPTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "skills", "cliproof", "scripts",
)
SCRIPTS = [f for f in os.listdir(SCRIPTS_DIR) if f.endswith(".py")]
SIBLINGS = {f[:-3] for f in SCRIPTS}  # scripts may import each other (e.g. check -> normalize)

# Network-capable stdlib modules a local, no-network tool must not import.
FORBIDDEN = {"socket", "ssl", "urllib", "http", "ftplib", "smtplib",
             "telnetlib", "asyncio", "xmlrpc", "requests", "httpx", "aiohttp"}


def _top_level_imports(path):
    with open(path, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=path)
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                roots.add(n.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                roots.add(node.module.split(".")[0])
    return roots


@pytest.mark.skipif(not hasattr(sys, "stdlib_module_names"),
                    reason="needs Python 3.10+ sys.stdlib_module_names")
@pytest.mark.parametrize("script", SCRIPTS)
def test_only_stdlib_and_siblings(script):
    roots = _top_level_imports(os.path.join(SCRIPTS_DIR, script))
    allowed = set(sys.stdlib_module_names) | SIBLINGS
    extra = roots - allowed
    assert not extra, f"{script} imports non-stdlib modules: {extra}"


@pytest.mark.parametrize("script", SCRIPTS)
def test_no_network_modules(script):
    roots = _top_level_imports(os.path.join(SCRIPTS_DIR, script))
    leaked = roots & FORBIDDEN
    assert not leaked, f"{script} imports network module(s): {leaked}"
