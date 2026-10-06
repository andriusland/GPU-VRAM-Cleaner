"""Fixed-size sample history used by the graphs."""

from collections import deque
from collections.abc import Iterator


class History:
    def __init__(self, capacity: int = 120) -> None:
        self._samples: deque[float] = deque(maxlen=capacity)

    def push(self, value: float | None) -> None:
        self._samples.append(0.0 if value is None else float(value))

    @property
    def latest(self) -> float | None:
        return self._samples[-1] if self._samples else None

    def __iter__(self) -> Iterator[float]:
        return iter(self._samples)

    def __len__(self) -> int:
        return len(self._samples)
