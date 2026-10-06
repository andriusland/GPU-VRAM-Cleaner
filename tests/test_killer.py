import subprocess
import sys
import time

import psutil
import pytest

from gpu_vram_cleaner.killer import KillOutcome, ProcessKiller, plan_radical_clean
from gpu_vram_cleaner.models import GpuProcess
from gpu_vram_cleaner.protection import ProcessIdentity


@pytest.fixture
def sleeper():
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    yield proc
    if proc.poll() is None:
        proc.kill()
    proc.wait()


def test_kill_terminates_a_running_process(sleeper):
    result = ProcessKiller(timeout=5).kill(sleeper.pid)
    assert result.outcome is KillOutcome.KILLED
    sleeper.wait(timeout=5)
    assert not psutil.pid_exists(sleeper.pid) or psutil.Process(sleeper.pid).status() == psutil.STATUS_ZOMBIE


def test_kill_reports_missing_process():
    result = ProcessKiller().kill(2**22 + 12345)
    assert result.outcome is KillOutcome.NOT_FOUND


def test_kill_refuses_protected_process():
    killer = ProcessKiller(identify=lambda pid: ProcessIdentity(pid, "dwm.exe", "andres"), own_pids=set())
    result = killer.kill(4321)
    assert result.outcome is KillOutcome.PROTECTED


def test_plan_radical_clean_splits_targets_and_protected():
    processes = [
        GpuProcess(pid=10, name="game.exe", gpu_index=0, used_memory=1),
        GpuProcess(pid=11, name="dwm.exe", gpu_index=0, used_memory=1),
        GpuProcess(pid=12, name="blender.exe", gpu_index=1, used_memory=1),
        GpuProcess(pid=10, name="game.exe", gpu_index=1, used_memory=1),
    ]
    names = {10: "game.exe", 11: "dwm.exe", 12: "blender.exe"}
    plan = plan_radical_clean(
        processes,
        identify=lambda pid: ProcessIdentity(pid, names[pid], "andres"),
        own_pids={12},
    )
    assert [p.pid for p in plan.targets] == [10]
    assert sorted(p.pid for p in plan.protected) == [11, 12]


def test_radical_clean_kills_every_target(sleeper):
    killer = ProcessKiller(timeout=5)
    processes = [GpuProcess(pid=sleeper.pid, name="python", gpu_index=0, used_memory=None)]
    results = killer.radical_clean(processes)
    assert [r.outcome for r in results] == [KillOutcome.KILLED]


def test_gpu_reported_name_protects_even_when_lookup_fails():
    processes = [GpuProcess(pid=55, name="dwm.exe", gpu_index=0, used_memory=1)]
    plan = plan_radical_clean(processes, identify=lambda pid: None, own_pids=set())
    assert plan.targets == []


def test_demo_killer_never_touches_real_processes(sleeper):
    from gpu_vram_cleaner.killer import DemoKiller
    from gpu_vram_cleaner.provider import DemoGpuProvider

    provider = DemoGpuProvider(seed=1)
    first = provider.processes()[0]
    assert DemoKiller(provider).kill(first.pid).name == first.name
    assert DemoKiller(provider).kill(sleeper.pid).outcome is KillOutcome.KILLED
    assert sleeper.poll() is None


SPAWNER = """
import subprocess, sys, time
child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
child.wait()
time.sleep(60)
"""


@pytest.fixture
def app_with_helper():
    """A parent process with a same-named child, like Chrome and its GPU process."""
    parent = subprocess.Popen([sys.executable, "-c", SPAWNER])
    deadline = time.monotonic() + 15
    leaf = None
    while time.monotonic() < deadline:
        family = psutil.Process(parent.pid).children(recursive=True)
        leaves = [p for p in family if not p.children()]
        if leaves:
            leaf = leaves[-1]
            break
        time.sleep(0.1)
    assert leaf is not None, "helper process never started"
    yield parent, leaf
    for proc in psutil.Process(parent.pid).children(recursive=True) if parent.poll() is None else []:
        proc.kill()
    if parent.poll() is None:
        parent.kill()
    parent.wait()


def test_kill_closes_the_whole_app_when_a_helper_process_holds_the_gpu(app_with_helper):
    parent, helper = app_with_helper
    result = ProcessKiller(timeout=5).kill(helper.pid)
    assert result.outcome is KillOutcome.KILLED
    # Killing only the helper would let the app respawn it; the parent must be gone too.
    parent.wait(timeout=10)
