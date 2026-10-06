from gpu_vram_cleaner.models import GpuInfo
from gpu_vram_cleaner.provider import DemoGpuProvider


def test_gpu_info_computes_vram_percent():
    info = GpuInfo(
        index=0,
        name="GPU",
        driver="1",
        temperature_c=40,
        utilization_pct=10,
        memory_used=2 * 1024**3,
        memory_total=8 * 1024**3,
        fan_pct=30,
    )
    assert info.memory_pct == 25.0


def test_gpu_info_percent_with_zero_total_is_none():
    info = GpuInfo(
        index=0,
        name="GPU",
        driver="1",
        temperature_c=None,
        utilization_pct=None,
        memory_used=0,
        memory_total=0,
        fan_pct=None,
    )
    assert info.memory_pct is None


def test_demo_provider_reports_gpus_and_processes():
    provider = DemoGpuProvider(seed=1)
    gpus = provider.gpus()
    assert len(gpus) == 2
    assert all(0 <= g.memory_used <= g.memory_total for g in gpus)
    processes = provider.processes()
    assert processes
    assert {p.gpu_index for p in processes} <= {g.index for g in gpus}


def test_demo_provider_can_forget_killed_processes():
    provider = DemoGpuProvider(seed=1)
    pid = provider.processes()[0].pid
    provider.forget(pid)
    assert pid not in {p.pid for p in provider.processes()}


def test_fill_missing_process_memory_uses_counter_values():
    from gpu_vram_cleaner.models import GpuProcess
    from gpu_vram_cleaner.provider import fill_missing_memory

    processes = [
        GpuProcess(10, "game.exe", 0, None, "C+G"),
        GpuProcess(20, "cuda.exe", 0, 1234, "C"),
        GpuProcess(30, "idle.exe", 0, None, "G"),
    ]
    filled = fill_missing_memory(processes, {(0, 10): 999})
    assert [p.used_memory for p in filled] == [999, 1234, None]


def test_fill_load_sets_values_and_leaves_unknown_as_zero_only_when_counters_ran():
    from gpu_vram_cleaner.models import GpuProcess
    from gpu_vram_cleaner.provider import fill_load

    processes = [GpuProcess(10, "game.exe", 0, 1, "G"), GpuProcess(20, "idle.exe", 0, 1, "G")]
    filled = fill_load(processes, {(0, 10): 42.0})
    assert [p.load_pct for p in filled] == [42.0, 0.0]
    assert [p.load_pct for p in fill_load(processes, None)] == [None, None]


def test_demo_processes_report_a_load():
    provider = DemoGpuProvider(seed=1)
    assert all(p.load_pct is not None and 0 <= p.load_pct <= 100 for p in provider.processes())


def test_nvml_provider_reads_clocks_and_power(monkeypatch):
    import sys
    from types import SimpleNamespace

    from gpu_vram_cleaner.provider import NvmlGpuProvider

    class NVMLError(Exception):
        pass

    def no_processes(handle):
        return []

    fake = SimpleNamespace(
        NVMLError=NVMLError,
        NVML_TEMPERATURE_GPU=0,
        NVML_CLOCK_GRAPHICS=0,
        NVML_CLOCK_MEM=2,
        nvmlInit=lambda: None,
        nvmlShutdown=lambda: None,
        nvmlSystemGetDriverVersion=lambda: "582.66",
        nvmlDeviceGetCount=lambda: 1,
        nvmlDeviceGetHandleByIndex=lambda i: "h0",
        nvmlDeviceGetName=lambda h: b"GeForce GTX 1080 Ti",
        nvmlDeviceGetMemoryInfo=lambda h: SimpleNamespace(used=2 * 1024**3, total=11 * 1024**3),
        nvmlDeviceGetUtilizationRates=lambda h: SimpleNamespace(gpu=25),
        nvmlDeviceGetTemperature=lambda h, sensor: 34,
        nvmlDeviceGetFanSpeed=lambda h: 33,
        nvmlDeviceGetClockInfo=lambda h, clock: {0: 1731, 2: 5622}[clock],
        nvmlDeviceGetPowerUsage=lambda h: 120400,
        nvmlDeviceGetEnforcedPowerLimit=lambda h: 250000,
        nvmlDeviceGetComputeRunningProcesses=no_processes,
        nvmlDeviceGetGraphicsRunningProcesses=no_processes,
    )
    monkeypatch.setitem(sys.modules, "pynvml", fake)
    gpu = NvmlGpuProvider().gpus()[0]
    assert gpu.name == "GeForce GTX 1080 Ti"
    assert gpu.core_clock_mhz == 1731
    assert gpu.memory_clock_mhz == 5622
    assert gpu.power_w == 120.4
    assert gpu.power_limit_w == 250.0


def test_nvml_provider_tolerates_unsupported_power(monkeypatch):
    import sys
    from types import SimpleNamespace

    from gpu_vram_cleaner.provider import NvmlGpuProvider

    class NVMLError(Exception):
        pass

    def unsupported(*args):
        raise NVMLError("Not Supported")

    fake = SimpleNamespace(
        NVMLError=NVMLError,
        NVML_TEMPERATURE_GPU=0,
        NVML_CLOCK_GRAPHICS=0,
        NVML_CLOCK_MEM=2,
        nvmlInit=lambda: None,
        nvmlShutdown=lambda: None,
        nvmlSystemGetDriverVersion=lambda: "1",
        nvmlDeviceGetCount=lambda: 1,
        nvmlDeviceGetHandleByIndex=lambda i: "h0",
        nvmlDeviceGetName=lambda h: "GPU",
        nvmlDeviceGetMemoryInfo=unsupported,
        nvmlDeviceGetUtilizationRates=unsupported,
        nvmlDeviceGetTemperature=unsupported,
        nvmlDeviceGetFanSpeed=unsupported,
        nvmlDeviceGetClockInfo=unsupported,
        nvmlDeviceGetPowerUsage=unsupported,
        nvmlDeviceGetEnforcedPowerLimit=unsupported,
    )
    monkeypatch.setitem(sys.modules, "pynvml", fake)
    gpu = NvmlGpuProvider().gpus()[0]
    assert (gpu.core_clock_mhz, gpu.memory_clock_mhz, gpu.power_w, gpu.power_limit_w) == (
        None,
        None,
        None,
        None,
    )


def test_demo_gpus_report_clocks_and_power():
    gpu = DemoGpuProvider(seed=1).gpus()[0]
    assert gpu.core_clock_mhz and gpu.memory_clock_mhz
    assert 0 < gpu.power_w <= gpu.power_limit_w


def test_add_counter_processes_lists_apps_nvml_does_not_report():
    from gpu_vram_cleaner.models import GpuProcess
    from gpu_vram_cleaner.provider import add_counter_processes

    processes = [GpuProcess(10, "chrome.exe", 0, 500, "G")]
    memory = {(0, 10): 500, (0, 20): 300, (0, 30): 0}
    names = {20: "Code.exe", 30: "idle.exe"}
    merged = add_counter_processes(processes, memory, names.get)
    rows = [(p.pid, p.name, p.used_memory) for p in merged]
    assert rows == [(10, "chrome.exe", 500), (20, "Code.exe", 300)]
    assert merged[1].kind == "G"
