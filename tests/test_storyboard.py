import storyboard

A = '<?xml version="1.0"?>\n<svg xmlns="http://www.w3.org/2000/svg" width="100" height="40"><rect/></svg>'
B = '<svg xmlns="http://www.w3.org/2000/svg" width="120" height="60"><circle/></svg>'


def test_dims_from_attrs():
    assert storyboard.dims(A) == (100.0, 40.0)


def test_dims_from_viewbox():
    vb = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 80"></svg>'
    assert storyboard.dims(vb) == (200.0, 80.0)


def test_stitch_sizes_and_content():
    out = storyboard.stitch([A, B], gap=10)
    # width = max(100,120), height = 40+60+10
    assert 'width="120"' in out and 'height="110"' in out
    assert out.count("<svg") == 3            # outer + two nested
    assert "<rect/>" in out and "<circle/>" in out
    # second frame offset by first height + gap
    assert 'y="50"' in out or 'y="50.0"' in out


def test_stitch_empty_raises():
    try:
        storyboard.stitch([])
        assert False, "expected ValueError"
    except ValueError:
        pass
