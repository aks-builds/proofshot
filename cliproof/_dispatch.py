"""_dispatch.py — locate the cliproof scripts directory at runtime."""
import os


def scripts_dir():
    """Return the absolute path to the cliproof scripts directory.

    Search order:
    1. CLIPROOF_SCRIPTS_DIR environment variable (explicit override)
    2. Relative to this file: ../../skills/cliproof/scripts  (dev / editable install)
    3. Relative to this file: ../skills/cliproof/scripts  (alternative layouts)

    Raises RuntimeError if no valid directory is found.
    """
    env = os.environ.get("CLIPROOF_SCRIPTS_DIR")
    if env:
        env = os.path.abspath(env)
        if os.path.isdir(env) and os.path.exists(os.path.join(env, "capture.py")):
            return env

    this_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.normpath(os.path.join(this_dir, "..", "skills", "cliproof", "scripts")),
        os.path.normpath(os.path.join(this_dir, "scripts")),
    ]
    for candidate in candidates:
        if os.path.isdir(candidate) and os.path.exists(os.path.join(candidate, "capture.py")):
            return candidate

    raise RuntimeError(
        "Cannot locate cliproof scripts. Set the CLIPROOF_SCRIPTS_DIR environment variable "
        "to the absolute path of skills/cliproof/scripts/."
    )
