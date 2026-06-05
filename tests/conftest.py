"""Make the bundled skill scripts importable from the tests."""
import os
import sys

SCRIPTS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "skills", "proofshot", "scripts",
)
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
