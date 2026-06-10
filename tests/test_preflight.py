import preflight


def test_detect_shape():
    """preflight.detect() delegates to health.detect() — verify the new key contract."""
    info = preflight.detect()
    assert set(info) >= {"ok", "renderers", "modes", "gif", "python", "os"}
    assert isinstance(info["ok"], bool)
    assert isinstance(info["gif"], bool)


def test_json_mode_runs():
    assert preflight.main(["--json"]) == 0


def test_human_mode_runs():
    assert preflight.main([]) == 0
