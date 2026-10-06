import io

import gpu_vram_cleaner
from gpu_vram_cleaner import provider as provider_module
from gpu_vram_cleaner.autoclean import run_autoclean
from gpu_vram_cleaner.killer import KillOutcome, KillResult
from gpu_vram_cleaner.models import GpuProcess
from gpu_vram_cleaner.protection import ProcessIdentity

MIB = 1024**2


class FakeProvider:
    def __init__(self, processes):
        self._processes = processes
        self.closed = False

    def processes(self):
        return list(self._processes)

    def close(self):
        self.closed = True


class FakeKiller:
    def __init__(self, outcomes=None):
        self.outcomes = outcomes or {}
        self.killed = []

    def kill(self, pid):
        self.killed.append(pid)
        return KillResult(pid, f"pid {pid}", self.outcomes.get(pid, KillOutcome.KILLED))


def identify(pid):
    return ProcessIdentity(pid, {1: "python.exe", 2: "dwm.exe", 3: "chrome.exe"}.get(pid, "x"), "me")


PROCESSES = [
    GpuProcess(pid=1, name="python.exe", gpu_index=0, used_memory=6000 * MIB),
    GpuProcess(pid=2, name="dwm.exe", gpu_index=0, used_memory=300 * MIB),
    GpuProcess(pid=3, name="chrome.exe", gpu_index=0, used_memory=500 * MIB),
]


def run(processes=PROCESSES, killer=None, dry_run=False):
    out = io.StringIO()
    killer = killer or FakeKiller()
    provider = FakeProvider(processes)
    code = run_autoclean(provider, killer, dry_run=dry_run, identify=identify, own_pids=set(), out=out)
    return code, killer, out.getvalue()


def test_autoclean_closes_every_unprotected_process_and_keeps_protected_ones():
    code, killer, text = run()
    assert code == 0
    assert killer.killed == [1, 3]
    assert "python.exe" in text and "chrome.exe" in text
    assert "dwm.exe" in text and "protected" in text
    assert "6500 MiB" in text


def test_autoclean_dry_run_lists_targets_without_closing_anything():
    code, killer, text = run(dry_run=True)
    assert code == 0
    assert killer.killed == []
    assert "python.exe" in text and "dry run" in text.lower()


def test_autoclean_with_nothing_to_close_succeeds():
    code, killer, text = run(processes=[PROCESSES[1]])
    assert code == 0
    assert killer.killed == []
    assert "nothing to close" in text.lower()


def test_autoclean_fails_when_a_process_could_not_be_closed():
    code, _, text = run(killer=FakeKiller({3: KillOutcome.ACCESS_DENIED}))
    assert code == 1
    assert "access denied" in text


def test_autoclean_treats_already_exited_processes_as_closed():
    code, _, _ = run(killer=FakeKiller({1: KillOutcome.NOT_FOUND}))
    assert code == 0


def test_cli_autoclean_runs_without_the_tui(monkeypatch):
    calls = {}

    def fake_run(provider, killer, *, dry_run, **_):
        calls["dry_run"] = dry_run
        calls["provider"] = provider
        return 0

    monkeypatch.setattr("gpu_vram_cleaner.autoclean.run_autoclean", fake_run)

    def no_tui(self):
        raise AssertionError("the TUI must not start with --autoclean")

    monkeypatch.setattr("gpu_vram_cleaner.app.VramCleanerApp.run", no_tui)
    assert gpu_vram_cleaner.main(["--demo", "--autoclean", "--dry-run"]) == 0
    assert calls["dry_run"] is True
    assert isinstance(calls["provider"], provider_module.DemoGpuProvider)


def test_dry_run_requires_autoclean(capsys):
    import pytest

    with pytest.raises(SystemExit) as exit_info:
        gpu_vram_cleaner.main(["--dry-run"])
    assert exit_info.value.code == 2
    assert "--autoclean" in capsys.readouterr().err
