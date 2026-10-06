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
