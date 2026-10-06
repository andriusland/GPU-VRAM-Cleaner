from gpu_vram_cleaner.themes import THEMES, load_theme_name, save_theme_name


def test_there_are_seven_distinct_themes():
    assert len(THEMES) == 7
    assert len({t.name for t in THEMES}) == 7
    assert len({(t.primary, t.background) for t in THEMES}) == 7


def test_synthwave_neon_theme_exists():
    from gpu_vram_cleaner.themes import THEME_LABELS

    assert THEME_LABELS["vram-synthwave"] == "Synthwave Neon"
    synthwave = next(t for t in THEMES if t.name == "vram-synthwave")
    assert synthwave.dark


def test_theme_choice_round_trips(tmp_path):
    path = tmp_path / "settings.json"
    save_theme_name("vram-ocean", path)
    assert load_theme_name(path) == "vram-ocean"


def test_missing_or_broken_settings_fall_back_to_default(tmp_path):
    assert load_theme_name(tmp_path / "missing.json") == "vram-synthwave"
    broken = tmp_path / "broken.json"
    broken.write_text("{not json")
    assert load_theme_name(broken) == "vram-synthwave"


def test_unknown_theme_falls_back_to_default(tmp_path):
    path = tmp_path / "settings.json"
    save_theme_name("does-not-exist", path)
    assert load_theme_name(path) == "vram-synthwave"
