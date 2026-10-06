"""Map raw readings to severity levels and colors."""

from enum import Enum


class Level(Enum):
    OK = "ok"
    WARN = "warn"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


_COLORS = {
    Level.OK: "green",
    Level.WARN: "yellow",
    Level.CRITICAL: "red",
    Level.UNKNOWN: "grey50",
}


def _classify(value: float | None, warn_at: float, critical_at: float) -> Level:
    if value is None:
        return Level.UNKNOWN
    if value >= critical_at:
        return Level.CRITICAL
    if value >= warn_at:
        return Level.WARN
    return Level.OK


def percent_level(value: float | None) -> Level:
    """Level for VRAM usage and GPU load percentages."""
    return _classify(value, warn_at=60, critical_at=85)


def temperature_level(celsius: float | None) -> Level:
    return _classify(celsius, warn_at=65, critical_at=80)


def fan_level(percent: float | None) -> Level:
    return _classify(percent, warn_at=50, critical_at=80)


def level_color(level: Level) -> str:
    return _COLORS[level]
