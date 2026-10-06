from gpu_vram_cleaner.themes import THEMES, load_theme_name, save_theme_name


def test_there_are_six_distinct_themes():
    assert len(THEMES) == 6
    assert len({t.name for t in THEMES}) == 6
    assert len({(t.primary, t.background) for t in THEMES}) == 6


def test_theme_choice_round_trips(tmp_path):
    path = tmp_path / "settings.json"
    save_theme_name("vram-ocean", path)
    assert load_theme_name(path) == "vram-ocean"


def test_missing_or_broken_settings_fall_back_to_default(tmp_path):
    assert load_theme_name(tmp_path / "missing.json") == THEMES[0].name
    broken = tmp_path / "broken.json"
    broken.write_text("{not json")
    assert load_theme_name(broken) == THEMES[0].name


def test_unknown_theme_falls_back_to_default(tmp_path):
    path = tmp_path / "settings.json"
    save_theme_name("does-not-exist", path)
    assert load_theme_name(path) == THEMES[0].name
