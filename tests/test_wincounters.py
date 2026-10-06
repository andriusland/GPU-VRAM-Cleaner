import sys

import pytest

from gpu_vram_cleaner.wincounters import (
    WindowsGpuMemoryCounters,
    adapter_totals,
    match_adapters,
    parse_instance,
    process_memory_by_gpu,
)

LUID_A = "0x00000000_0x0000d1f2"
LUID_B = "0x00000000_0x0000a0b0"


def test_parse_process_instance():
    assert parse_instance("pid_1234_luid_0x00000000_0x0000D1F2_phys_0") == (1234, LUID_A)


def test_parse_adapter_instance():
    assert parse_instance("luid_0x00000000_0x0000D1F2_phys_0") == (None, LUID_A)


def test_parse_rejects_unknown_names():
    assert parse_instance("_Total") is None


def test_adapter_totals_sum_physical_parts():
    samples = {
        "luid_0x00000000_0x0000D1F2_phys_0": 2_000,
        "luid_0x00000000_0x0000D1F2_phys_1": 500,
        "luid_0x00000000_0x0000A0B0_phys_0": 10,
    }
    assert adapter_totals(samples) == {LUID_A: 2_500, LUID_B: 10}


def test_match_adapters_picks_closest_usage():
    totals = {LUID_A: 2_400, LUID_B: 30}
    assert match_adapters({0: 2_500}, totals) == {0: LUID_A}
    assert match_adapters({0: 40, 1: 2_300}, totals) == {0: LUID_B, 1: LUID_A}


def test_match_adapters_with_single_gpu_and_single_adapter():
    assert match_adapters({0: 0}, {LUID_A: 99}) == {0: LUID_A}


def test_process_memory_by_gpu_ignores_other_adapters():
    process_samples = {
        "pid_10_luid_0x00000000_0x0000D1F2_phys_0": 300,
        "pid_10_luid_0x00000000_0x0000A0B0_phys_0": 7,
        "pid_20_luid_0x00000000_0x0000D1F2_phys_0": 50,
    }
    adapter_samples = {
        "luid_0x00000000_0x0000D1F2_phys_0": 350,
        "luid_0x00000000_0x0000A0B0_phys_0": 7,
    }
    result = process_memory_by_gpu({0: 360}, process_samples, adapter_samples)
    assert result == {(0, 10): 300, (0, 20): 50}


def test_process_memory_by_gpu_without_counters_is_empty():
    assert process_memory_by_gpu({0: 100}, {}, {}) == {}


def test_counters_are_unavailable_off_windows():
    if sys.platform == "win32":
        pytest.skip("Windows has the counters")
    counters = WindowsGpuMemoryCounters()
    assert counters.available is False
    assert counters.snapshot() == ({}, {})


@pytest.mark.skipif(sys.platform != "win32", reason="PDH only exists on Windows")
def test_counters_snapshot_on_windows_does_not_fail():
    counters = WindowsGpuMemoryCounters()
    processes, adapters = counters.snapshot()
    assert isinstance(processes, dict)
    assert isinstance(adapters, dict)
    counters.close()
