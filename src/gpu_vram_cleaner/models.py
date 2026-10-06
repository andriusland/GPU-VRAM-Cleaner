"""Plain data objects shared by the provider, the killer and the UI."""

from dataclasses import dataclass


@dataclass(frozen=True)
class GpuInfo:
    index: int
    name: str
    driver: str
    temperature_c: float | None
    utilization_pct: float | None
    memory_used: int
    memory_total: int
    fan_pct: float | None
    core_clock_mhz: int | None = None
    memory_clock_mhz: int | None = None
    power_w: float | None = None
    power_limit_w: float | None = None

    @property
    def power_pct(self) -> float | None:
        if self.power_w is None or not self.power_limit_w:
            return None
        return self.power_w / self.power_limit_w * 100

    @property
    def memory_pct(self) -> float | None:
        if self.memory_total <= 0:
            return None
        return self.memory_used / self.memory_total * 100


@dataclass(frozen=True)
class GpuProcess:
    pid: int
    name: str
    gpu_index: int
    used_memory: int | None
    kind: str = "G"
    load_pct: float | None = None
