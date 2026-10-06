"""The color themes (borders and backgrounds) and persistence of the choice."""

import json
import os
from pathlib import Path

from textual.theme import Theme

THEMES: list[Theme] = [
    Theme(
        name="vram-nvidia",
        primary="#76B900",
        secondary="#4E7D00",
        accent="#B4F05A",
        background="#0D0F0A",
        surface="#151A10",
        panel="#1E2616",
        foreground="#E6F2D9",
        dark=True,
    ),
    Theme(
        name="vram-ocean",
        primary="#2E9BFF",
        secondary="#1565C0",
        accent="#4DD0E1",
        background="#06121F",
        surface="#0B1D30",
        panel="#11283F",
        foreground="#DCEBFA",
        dark=True,
    ),
    Theme(
        name="vram-dracula",
        primary="#BD93F9",
        secondary="#FF79C6",
        accent="#8BE9FD",
        background="#1E1F29",
        surface="#282A36",
        panel="#343746",
        foreground="#F8F8F2",
        dark=True,
    ),
    Theme(
        name="vram-solar",
        primary="#FF8C00",
        secondary="#E25822",
        accent="#FFD166",
        background="#1A0F05",
        surface="#26170A",
        panel="#33200F",
        foreground="#FFF1DE",
        dark=True,
    ),
    Theme(
        name="vram-nord",
        primary="#88C0D0",
        secondary="#5E81AC",
        accent="#A3BE8C",
        background="#2E3440",
        surface="#3B4252",
        panel="#434C5E",
        foreground="#ECEFF4",
        dark=True,
    ),
    Theme(
        name="vram-paper",
        primary="#C2185B",
        secondary="#6A1B9A",
        accent="#00897B",
        background="#F7F3EA",
        surface="#FFFDF7",
        panel="#EDE6D6",
        foreground="#2B2B2B",
        dark=False,
    ),
    Theme(
        name="vram-synthwave",
        primary="#FF2BD6",
        secondary="#00F0FF",
        accent="#FFE600",
        background="#12002B",
        surface="#1D0540",
        panel="#2A0A5C",
        foreground="#F6E9FF",
        dark=True,
    ),
]

THEME_LABELS = {
    "vram-nvidia": "NVIDIA Green",
    "vram-ocean": "Deep Ocean",
    "vram-dracula": "Dracula Night",
    "vram-solar": "Solar Flare",
    "vram-nord": "Nord Frost",
    "vram-paper": "Paper Light",
    "vram-synthwave": "Synthwave Neon",
}

DEFAULT_THEME = THEMES[0].name


def settings_path() -> Path:
    base = os.environ.get("APPDATA")
    root = Path(base) if base else Path.home() / ".config"
    return root / "gpu-vram-cleaner" / "settings.json"


def load_theme_name(path: Path | None = None) -> str:
    path = path or settings_path()
    try:
        name = json.loads(path.read_text(encoding="utf-8")).get("theme")
    except (OSError, ValueError, AttributeError):
        return DEFAULT_THEME
    return name if name in THEME_LABELS else DEFAULT_THEME


def save_theme_name(name: str, path: Path | None = None) -> None:
    path = path or settings_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"theme": name}), encoding="utf-8")
    except OSError:
        pass
