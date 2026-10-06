from gpu_vram_cleaner.history import History


def test_history_starts_empty():
    assert list(History(capacity=3)) == []


def test_history_keeps_only_latest_samples():
    history = History(capacity=3)
    for value in [1, 2, 3, 4, 5]:
        history.push(value)
    assert list(history) == [3, 4, 5]
    assert history.latest == 5


def test_history_stores_missing_samples_as_zero():
    history = History(capacity=2)
    history.push(None)
    assert list(history) == [0.0]


def test_latest_of_empty_history_is_none():
    assert History(capacity=2).latest is None
