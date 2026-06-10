"""cliproof — Python library for capturing, redacting, and embedding terminal proofs.

Usage:
    from cliproof import capture, redact, embed, check, health, guard

    result = capture("pytest -q", preset="catppuccin")
    redact(result.image, in_place=True)
    embed("README.md", image=result.image, block_id="tests")
"""
from cliproof._api import capture, redact, embed, check, health, guard
from cliproof._types import (
    CaptureResult, RedactResult, EmbedResult, CheckResult,
    CliproofError, RedactionBlockedError, CliproofNotReadyError,
)

_lazy_health = False


def configure(lazy_health=False):
    """Configure cliproof behaviour.

    Args:
        lazy_health: If True, skip the health check on import (default False).
    """
    global _lazy_health
    _lazy_health = lazy_health


__all__ = [
    "capture", "redact", "embed", "check", "health", "guard", "configure",
    "CaptureResult", "RedactResult", "EmbedResult", "CheckResult",
    "CliproofError", "RedactionBlockedError", "CliproofNotReadyError",
]
