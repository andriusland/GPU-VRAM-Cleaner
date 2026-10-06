"""Sources of GPU readings: NVIDIA NVML on real hardware, or a demo simulator."""

import math
import random
from typing import Protocol

import psutil

from .models import GpuInfo, GpuProcess


class GpuProviderError(RuntimeError):
    """Raised when GPU data cannot be read (no NVIDIA driver, NVML missing...)."""


class GpuProvider(Protocol):
    def gpus(self) -> list[GpuInfo]: ...

    def processes(self) -> list[GpuProcess]: ...

    def close(self) -> None: ...


def _process_name(pid: int) -> str:
    try:
        return psutil.Process(pid).name()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return f"pid {pid}"


class NvmlGpuProvider:
    """Reads NVIDIA GPUs through NVML (nvidia-ml-py)."""

    def __init__(self) -> None:
        try:
            import pynvml
        except ImportError as exc:  # pragma: no cover - dependency is declared
            raise GpuProviderError("nvidia-ml-py is not installed") from exc
        self._nvml = pynvml
        try:
            pynvml.nvmlInit()
        except pynvml.NVMLError as exc:
            raise GpuProviderError(f"Could not initialise NVIDIA NVML: {exc}") from exc
        self._driver = self._text(pynvml.nvmlSystemGetDriverVersion())
        self._handles = [pynvml.nvmlDeviceGetHandleByIndex(i) for i in range(pynvml.nvmlDeviceGetCount())]
        self._names = [self._text(pynvml.nvmlDeviceGetName(h)) for h in self._handles]

    @staticmethod
    def _text(value: str | bytes) -> str:
        return value.decode() if isinstance(value, bytes) else value

    def _optional(self, func, *args):
        try:
            return func(*args)
        except self._nvml.NVMLError:
            return None

    def gpus(self) -> list[GpuInfo]:
        nvml = self._nvml
        result = []
        for index, handle in enumerate(self._handles):
            memory = self._optional(nvml.nvmlDeviceGetMemoryInfo, handle)
            utilization = self._optional(nvml.nvmlDeviceGetUtilizationRates, handle)
            result.append(
                GpuInfo(
                    index=index,
                    name=self._names[index],
                    driver=self._driver,
                    temperature_c=self._optional(
                        nvml.nvmlDeviceGetTemperature, handle, nvml.NVML_TEMPERATURE_GPU
                    ),
                    utilization_pct=utilization.gpu if utilization else None,
                    memory_used=memory.used if memory else 0,
                    memory_total=memory.total if memory else 0,
                    fan_pct=self._optional(nvml.nvmlDeviceGetFanSpeed, handle),
                )
            )
        return result

    def processes(self) -> list[GpuProcess]:
        nvml = self._nvml
        found: dict[tuple[int, int], GpuProcess] = {}
        for index, handle in enumerate(self._handles):
            for kind, getter in (
                ("C", nvml.nvmlDeviceGetComputeRunningProcesses),
                ("G", nvml.nvmlDeviceGetGraphicsRunningProcesses),
            ):
                for proc in self._optional(getter, handle) or []:
                    key = (index, proc.pid)
                    if key in found:
                        previous = found[key]
                        found[key] = GpuProcess(proc.pid, previous.name, index, previous.used_memory, "C+G")
                        continue
                    used = getattr(proc, "usedGpuMemory", None)
                    found[key] = GpuProcess(proc.pid, _process_name(proc.pid), index, used, kind)
        return sorted(found.values(), key=lambda p: (p.gpu_index, -(p.used_memory or 0), p.pid))

    def close(self) -> None:
        try:
            self._nvml.nvmlShutdown()
        except self._nvml.NVMLError:
            pass


_DEMO_PROCESSES = [
    ("dwm.exe", "G", 0.4),
    ("explorer.exe", "G", 0.15),
    ("chrome.exe", "G", 0.9),
    ("Code.exe", "G", 0.3),
    ("python.exe", "C", 6.5),
    ("blender.exe", "C+G", 3.2),
    ("Discord.exe", "G", 0.25),
    ("obs64.exe", "G", 0.6),
]


class DemoGpuProvider:
    """Simulated GPUs so the UI can be tried on machines without an NVIDIA card."""

    def __init__(self, seed: int | None = None) -> None:
        self._random = random.Random(seed)
        self._tick = 0
        self._gpus = [("NVIDIA GeForce RTX 4090 (demo)", 24), ("NVIDIA GeForce RTX 3060 (demo)", 12)]
        self._processes = [
            GpuProcess(90000 + i, name, i % 2 if kind != "C" else 0, int(gib * 1024**3), kind)
            for i, (name, kind, gib) in enumerate(_DEMO_PROCESSES)
        ]

    def gpus(self) -> list[GpuInfo]:
        self._tick += 1
        result = []
        for index, (name, total_gib) in enumerate(self._gpus):
            total = total_gib * 1024**3
            base = sum(p.used_memory or 0 for p in self._processes if p.gpu_index == index) + 512 * 1024**2
            jitter = int(self._random.uniform(-0.02, 0.02) * total)
            used = max(0, min(total, base + jitter))
            wave = (math.sin(self._tick / (6 + index * 3)) + 1) / 2
            load = min(100.0, wave * 90 + self._random.uniform(0, 10))
            result.append(
                GpuInfo(
                    index=index,
                    name=name,
                    driver="560.94 (demo)",
                    temperature_c=round(38 + load * 0.45 + self._random.uniform(-1, 1)),
                    utilization_pct=round(load),
                    memory_used=used,
                    memory_total=total,
                    fan_pct=round(min(100.0, 25 + load * 0.7)),
                )
            )
        return result

    def processes(self) -> list[GpuProcess]:
        return list(self._processes)

    def forget(self, pid: int) -> None:
        self._processes = [p for p in self._processes if p.pid != pid]

    def close(self) -> None:
        pass
