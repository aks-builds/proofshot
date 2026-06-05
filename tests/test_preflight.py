import preflight


def test_detect_shape():
    info = preflight.detect()
    assert set(info) >= {"os", "tools", "static_screenshot", "animated_gif"}
    assert set(preflight.TOOLS) <= set(info["tools"])
    assert isinstance(info["static_screenshot"], bool)
    assert isinstance(info["animated_gif"], bool)


def test_json_mode_runs():
    assert preflight.main(["--json"]) == 0


def test_human_mode_runs():
    assert preflight.main([]) == 0
