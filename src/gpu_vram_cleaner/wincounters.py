"""Per-process dedicated VRAM from Windows performance counters.

Under the WDDM driver model (every GeForce card on Windows) NVML cannot report how much
VRAM each process uses. Windows itself tracks it in the "GPU Process Memory" counters,
which is where Task Manager gets its "Dedicated GPU memory" column.
"""

import re
import sys
from dataclasses import dataclass, field

_INSTANCE = re.compile(r"^(?:pid_(\d+)_)?luid_(0x[0-9a-f]+_0x[0-9a-f]+)_phys_\d+$", re.IGNORECASE)

_ENGINE = re.compile(
    r"^pid_(\d+)_luid_(0x[0-9a-f]+_0x[0-9a-f]+)_phys_\d+_eng_\d+_engtype_(.*)$", re.IGNORECASE
)

PROCESS_COUNTER = r"\GPU Process Memory(*)\Dedicated Usage"
ADAPTER_COUNTER = r"\GPU Adapter Memory(*)\Dedicated Usage"
ENGINE_COUNTER = r"\GPU Engine(*)\Utilization Percentage"

Samples = dict[str, float]


@dataclass(frozen=True)
class CounterSnapshot:
    processes: Samples = field(default_factory=dict)
    adapters: Samples = field(default_factory=dict)
    engines: Samples = field(default_factory=dict)


def parse_instance(name: str) -> tuple[int | None, str] | None:
    """Split a counter instance name into (pid or None, adapter LUID)."""
    match = _INSTANCE.match(name)
    if not match:
        return None
    pid = int(match.group(1)) if match.group(1) else None
    return pid, match.group(2).lower()


def parse_engine_instance(name: str) -> tuple[int, str, str] | None:
    """Split a GPU Engine instance name into (pid, adapter LUID, engine type)."""
    match = _ENGINE.match(name)
    if not match:
        return None
    return int(match.group(1)), match.group(2).lower(), match.group(3)


def adapter_totals(adapter_samples: Samples) -> dict[str, int]:
    totals: dict[str, int] = {}
    for name, value in adapter_samples.items():
        parsed = parse_instance(name)
        if parsed:
            totals[parsed[1]] = totals.get(parsed[1], 0) + int(value)
    return totals


def match_adapters(nvml_used: dict[int, int], totals: dict[str, int]) -> dict[int, str]:
    """Pair each NVML GPU with the Windows adapter whose dedicated usage is closest to its own."""
    pairs = sorted(
        (abs(used - total), gpu, luid) for gpu, used in nvml_used.items() for luid, total in totals.items()
    )
    matched: dict[int, str] = {}
    taken: set[str] = set()
    for _, gpu, luid in pairs:
        if gpu not in matched and luid not in taken:
            matched[gpu] = luid
            taken.add(luid)
    return matched


def _gpu_of_luid(nvml_used: dict[int, int], adapter_samples: Samples) -> dict[str, int]:
    return {luid: gpu for gpu, luid in match_adapters(nvml_used, adapter_totals(adapter_samples)).items()}


def process_memory_by_gpu(
    nvml_used: dict[int, int], process_samples: Samples, adapter_samples: Samples
) -> dict[tuple[int, int], int]:
    """Dedicated VRAM per (gpu index, pid) for the NVIDIA GPUs only."""
    gpu_of_luid = _gpu_of_luid(nvml_used, adapter_samples)
    result: dict[tuple[int, int], int] = {}
    for name, value in process_samples.items():
        parsed = parse_instance(name)
        if not parsed or parsed[0] is None or parsed[1] not in gpu_of_luid:
            continue
        key = (gpu_of_luid[parsed[1]], parsed[0])
        result[key] = result.get(key, 0) + int(value)
    return result


def process_load_by_gpu(
    nvml_used: dict[int, int], engine_samples: Samples, adapter_samples: Samples
) -> dict[tuple[int, int], float]:
    """GPU load per (gpu index, pid): the busiest engine type, as Task Manager shows it."""
    gpu_of_luid = _gpu_of_luid(nvml_used, adapter_samples)
    per_type: dict[tuple[int, int, str], float] = {}
    for name, value in engine_samples.items():
        parsed = parse_engine_instance(name)
        if not parsed or parsed[1] not in gpu_of_luid:
            continue
        key = (gpu_of_luid[parsed[1]], parsed[0], parsed[2])
        per_type[key] = per_type.get(key, 0.0) + value
    result: dict[tuple[int, int], float] = {}
    for (gpu, pid, _), value in per_type.items():
        result[(gpu, pid)] = min(100.0, max(result.get((gpu, pid), 0.0), value))
    return result


class WindowsGpuMemoryCounters:
    """Reads the GPU memory counters through the Windows PDH API (no extra dependencies)."""

    def __init__(self) -> None:
        self.available = False
        self._query = None
        self._counters: list = []
        if sys.platform != "win32":
            return
        try:
            self._open()
        except OSError:
            self.available = False

    def _open(self) -> None:
        import ctypes
        from ctypes import wintypes

        pdh = ctypes.WinDLL("pdh")
        pdh.PdhOpenQueryW.argtypes = [wintypes.LPCWSTR, ctypes.c_size_t, ctypes.POINTER(wintypes.HANDLE)]
        pdh.PdhOpenQueryW.restype = wintypes.DWORD
        pdh.PdhAddEnglishCounterW.argtypes = [
            wintypes.HANDLE,
            wintypes.LPCWSTR,
            ctypes.c_size_t,
            ctypes.POINTER(wintypes.HANDLE),
        ]
        pdh.PdhAddEnglishCounterW.restype = wintypes.DWORD
        pdh.PdhCollectQueryData.argtypes = [wintypes.HANDLE]
        pdh.PdhCollectQueryData.restype = wintypes.DWORD
        pdh.PdhGetFormattedCounterArrayW.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD),
            ctypes.c_void_p,
        ]
        pdh.PdhGetFormattedCounterArrayW.restype = wintypes.DWORD
        pdh.PdhCloseQuery.argtypes = [wintypes.HANDLE]
        pdh.PdhCloseQuery.restype = wintypes.DWORD
        self._pdh = pdh
        self._ctypes = ctypes
        self._wintypes = wintypes

        query = wintypes.HANDLE()
        if pdh.PdhOpenQueryW(None, 0, ctypes.byref(query)) != 0:
            return
        self._query = query
        for path in (PROCESS_COUNTER, ADAPTER_COUNTER, ENGINE_COUNTER):
            counter = wintypes.HANDLE()
            if pdh.PdhAddEnglishCounterW(query, path, 0, ctypes.byref(counter)) != 0:
                self.close()
                return
            self._counters.append(counter)
        self.available = True

    def _read(self, counter, as_double: bool = False) -> Samples:
        ctypes, wintypes = self._ctypes, self._wintypes
        number = ctypes.c_double if as_double else ctypes.c_longlong

        class Value(ctypes.Structure):
            _fields_ = [("CStatus", wintypes.DWORD), ("value", number)]

        class Item(ctypes.Structure):
            _fields_ = [("szName", wintypes.LPWSTR), ("FmtValue", Value)]

        pdh_fmt_large, pdh_fmt_double, pdh_fmt_nocap100 = 0x00000400, 0x00000200, 0x00008000
        pdh_more_data = 0x800007D2
        fmt = (pdh_fmt_double | pdh_fmt_nocap100) if as_double else pdh_fmt_large
        size, count = wintypes.DWORD(0), wintypes.DWORD(0)
        status = self._pdh.PdhGetFormattedCounterArrayW(
            counter, fmt, ctypes.byref(size), ctypes.byref(count), None
        )
        if status != pdh_more_data or size.value == 0:
            return {}
        buffer = (ctypes.c_byte * size.value)()
        status = self._pdh.PdhGetFormattedCounterArrayW(
            counter, fmt, ctypes.byref(size), ctypes.byref(count), buffer
        )
        if status != 0:
            return {}
        items = ctypes.cast(buffer, ctypes.POINTER(Item * count.value)).contents
        return {item.szName: float(item.FmtValue.value) for item in items if item.FmtValue.CStatus == 0}

    def snapshot(self) -> CounterSnapshot:
        """Current per-process memory, adapter memory and engine utilisation samples.

        Engine utilisation is a rate, so it is only available from the second snapshot on.
        """
        if not self.available or self._pdh.PdhCollectQueryData(self._query) != 0:
            return CounterSnapshot()
        return CounterSnapshot(
            self._read(self._counters[0]),
            self._read(self._counters[1]),
            self._read(self._counters[2], as_double=True),
        )

    def close(self) -> None:
        if self._query is not None:
            self._pdh.PdhCloseQuery(self._query)
            self._query = None
        self.available = False
