#!/usr/bin/env python3
"""preflight.py — backward-compatibility alias for health.py.

Deprecated: use `cliproof health` or `python health.py` instead.
Will be removed in v1.0.0.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import health  # noqa: E402

# Keep detect() and main() importable for backward compat
detect = health.detect
main = health.main

if __name__ == "__main__":
    raise SystemExit(health.main())
