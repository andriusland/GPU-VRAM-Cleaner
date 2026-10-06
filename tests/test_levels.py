import pytest

from gpu_vram_cleaner.levels import Level, fan_level, level_color, percent_level, temperature_level


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0, Level.OK), (59.9, Level.OK), (60, Level.WARN), (84.9, Level.WARN), (85, Level.CRITICAL), (100, Level.CRITICAL)],
)
def test_percent_level_thresholds(value, expected):
    assert percent_level(value) is expected


@pytest.mark.parametrize(
    ("celsius", "expected"),
    [(30, Level.OK), (64.9, Level.OK), (65, Level.WARN), (79.9, Level.WARN), (80, Level.CRITICAL)],
)
def test_temperature_level_thresholds(celsius, expected):
    assert temperature_level(celsius) is expected


@pytest.mark.parametrize(
    ("fan", "expected"),
    [(0, Level.OK), (49, Level.OK), (50, Level.WARN), (79, Level.WARN), (80, Level.CRITICAL)],
)
def test_fan_level_thresholds(fan, expected):
    assert fan_level(fan) is expected


def test_unknown_values_have_unknown_level():
    assert percent_level(None) is Level.UNKNOWN
    assert temperature_level(None) is Level.UNKNOWN
    assert fan_level(None) is Level.UNKNOWN


def test_each_level_has_a_distinct_color():
    colors = {level_color(level) for level in Level}
    assert len(colors) == len(Level)
    assert level_color(Level.OK) == "green"
    assert level_color(Level.CRITICAL) == "red"
