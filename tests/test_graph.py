from gpu_vram_cleaner.graph import render_bars


def test_render_bars_has_requested_size():
    rows = render_bars([50.0], width=4, height=3, maximum=100)
    assert len(rows) == 3
    assert all(len(row) == 4 for row in rows)


def test_render_bars_right_aligns_latest_samples():
    rows = render_bars([100.0], width=3, height=1, maximum=100)
    assert rows == ["  █"]


def test_full_and_empty_columns():
    rows = render_bars([0.0, 100.0], width=2, height=2, maximum=100)
    assert rows == [" █", " █"]


def test_partial_columns_use_eighth_blocks():
    rows = render_bars([50.0], width=1, height=1, maximum=100)
    assert rows == ["▄"]


def test_values_above_maximum_are_clamped():
    rows = render_bars([250.0], width=1, height=2, maximum=100)
    assert rows == ["█", "█"]


def test_only_the_most_recent_samples_fit():
    rows = render_bars([100.0, 0.0, 0.0], width=2, height=1, maximum=100)
    assert rows == ["  "]
