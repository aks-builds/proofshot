import normalize


def test_durations_neutralised():
    assert normalize.normalize("ran in 0.21s") == "ran in Ns"
    assert normalize.normalize("took 250ms") == "took Nms"
    assert normalize.normalize("elapsed 1.3 s") == "elapsed N s"


def test_timestamps_dates_times():
    assert "<timestamp>" in normalize.normalize("at 2026-06-05T13:24:38.371+05:30 done")
    assert "<date>" in normalize.normalize("on 2026-06-05 today")
    assert "<time>" in normalize.normalize("clock 13:24:38 now")


def test_uuid_hash_tmp_port():
    assert "<uuid>" in normalize.normalize("id 550e8400-e29b-41d4-a716-446655440000")
    assert "<hash>" in normalize.normalize("commit 0a1b2c3d4e5f6789")
    assert normalize.normalize("serving on localhost:3000") == "serving on localhost:PORT"


def test_idempotent():
    s = "done in 0.5s at 2026-06-05T10:00:00Z on localhost:8080"
    once = normalize.normalize(s)
    assert normalize.normalize(once) == once


def test_clean_text_unchanged():
    s = "All 42 tests passed"
    assert normalize.normalize(s) == s
