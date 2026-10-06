import pytest

import gpu_vram_cleaner
from gpu_vram_cleaner import provider as provider_module


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exit_info:
        gpu_vram_cleaner.main(["--version"])
    assert exit_info.value.code == 0
    assert gpu_vram_cleaner.__version__ in capsys.readouterr().out


def test_missing_nvidia_driver_prints_a_hint(monkeypatch, capsys):
    def broken():
        raise provider_module.GpuProviderError("NVML not found")

    monkeypatch.setattr(provider_module, "NvmlGpuProvider", broken)
    assert gpu_vram_cleaner.main([]) == 1
    err = capsys.readouterr().err
    assert "NVML not found" in err
    assert "--demo" in err
