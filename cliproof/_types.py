"""_types.py — public types, dataclasses, and exceptions for the cliproof Python API."""


class CliproofError(Exception):
    """Raised when a cliproof operation fails (non-zero exit, structured error)."""
    def __init__(self, data):
        self.data = data
        reason = data.get("reason", "error")
        step = data.get("step", "?")
        super().__init__("[{}] {}".format(step, reason))


class RedactionBlockedError(CliproofError):
    """Raised when redact() finds a SECRET-class pattern (exit code 3)."""


class CliproofNotReadyError(CliproofError):
    """Raised on import when required tools are missing (lazy_health=False)."""


class CaptureResult:
    __slots__ = ("image", "renderer", "tier", "warnings", "scale", "fmt", "elapsed_s")

    def __init__(self, image, renderer=None, tier=None, warnings=None,
                 scale=1, fmt="svg", elapsed_s=0.0):
        self.image = image
        self.renderer = renderer
        self.tier = tier
        self.warnings = warnings or []
        self.scale = scale
        self.fmt = fmt
        self.elapsed_s = elapsed_s

    def __repr__(self):
        return "CaptureResult(image={!r}, renderer={!r}, tier={})".format(
            self.image, self.renderer, self.tier)


class RedactResult:
    __slots__ = ("findings", "file")

    def __init__(self, findings, file=None):
        self.findings = findings
        self.file = file

    def __repr__(self):
        return "RedactResult(findings={}, file={!r})".format(self.findings, self.file)


class EmbedResult:
    __slots__ = ("readme", "diff")

    def __init__(self, readme, diff=""):
        self.readme = readme
        self.diff = diff


class CheckResult:
    __slots__ = ("total", "drifted")

    def __init__(self, total, drifted):
        self.total = total
        self.drifted = list(drifted)

    @property
    def fresh(self):
        return len(self.drifted) == 0
