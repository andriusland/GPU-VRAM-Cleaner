"""Pure text rendering of a bar graph using eighth-block characters."""

from collections.abc import Sequence

_BLOCKS = " ▁▂▃▄▅▆▇█"


def column_heights(values: Sequence[float], width: int, height: int, maximum: float) -> list[int]:
    """Height of each column in eighths of a row, right aligned to the latest sample."""
    recent = list(values)[-width:] if width > 0 else []
    eighths = [round(min(max(v, 0.0), maximum) / maximum * height * 8) if maximum > 0 else 0 for v in recent]
    return [0] * (width - len(eighths)) + eighths


def render_bars(values: Sequence[float], width: int, height: int, maximum: float = 100.0) -> list[str]:
    """Render ``values`` as ``height`` rows of ``width`` characters, top row first."""
    heights = column_heights(values, width, height, maximum)
    rows = []
    for row in range(height - 1, -1, -1):
        floor = row * 8
        rows.append("".join(_BLOCKS[min(max(h - floor, 0), 8)] for h in heights))
    return rows
