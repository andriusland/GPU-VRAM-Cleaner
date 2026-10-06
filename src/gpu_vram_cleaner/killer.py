"""Close processes with psutil, never touching protected ones."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import Enum

import psutil

from .models import GpuProcess
from .protection import ProcessIdentity, is_protected

Identify = Callable[[int], ProcessIdentity | None]


class KillOutcome(Enum):
    KILLED = "killed"
    NOT_FOUND = "not found"
    ACCESS_DENIED = "access denied"
    PROTECTED = "protected"
    FAILED = "failed"


@dataclass(frozen=True)
class KillResult:
    pid: int
    name: str
    outcome: KillOutcome


@dataclass(frozen=True)
class RadicalPlan:
    targets: list[GpuProcess]
    protected: list[GpuProcess]


def identify_process(pid: int) -> ProcessIdentity | None:
    try:
        proc = psutil.Process(pid)
        name = proc.name()
    except (psutil.NoSuchProcess, psutil.ZombieProcess):
        return None
    except psutil.AccessDenied:
        # Processes we cannot even inspect belong to the system or another user.
        return ProcessIdentity(pid, f"pid {pid}", "SYSTEM")
    try:
        username = proc.username()
    except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
        username = None
    return ProcessIdentity(pid, name, username)


def own_process_tree() -> set[int]:
    """This process and its ancestors (the shell and terminal hosting the app)."""
    me = psutil.Process()
    return {me.pid, *(parent.pid for parent in me.parents())}


def process_is_protected(process: GpuProcess, identify: Identify, own_pids: set[int]) -> bool:
    """Check both the name the GPU driver reported and the live process identity."""
    if is_protected(ProcessIdentity(process.pid, process.name, None), own_pids):
        return True
    identity = identify(process.pid)
    return identity is not None and is_protected(identity, own_pids)


def plan_radical_clean(
    processes: Iterable[GpuProcess], identify: Identify = identify_process, own_pids: set[int] | None = None
) -> RadicalPlan:
    own = own_process_tree() if own_pids is None else own_pids
    targets: list[GpuProcess] = []
    protected: list[GpuProcess] = []
    seen: set[int] = set()
    for process in processes:
        if process.pid in seen:
            continue
        seen.add(process.pid)
        if process_is_protected(process, identify, own):
            protected.append(process)
        else:
            targets.append(process)
    return RadicalPlan(targets, protected)


class ProcessKiller:
    def __init__(
        self, timeout: float = 3.0, identify: Identify = identify_process, own_pids: set[int] | None = None
    ) -> None:
        self.timeout = timeout
        self.identify = identify
        self.own_pids = own_process_tree() if own_pids is None else own_pids

    def kill(self, pid: int) -> KillResult:
        identity = self.identify(pid)
        if identity is None:
            return KillResult(pid, f"pid {pid}", KillOutcome.NOT_FOUND)
        if is_protected(identity, self.own_pids):
            return KillResult(pid, identity.name, KillOutcome.PROTECTED)
        return KillResult(pid, identity.name, self._terminate(pid))

    def _terminate(self, pid: int) -> KillOutcome:
        try:
            proc = psutil.Process(pid)
            proc.terminate()
            try:
                proc.wait(timeout=self.timeout)
            except psutil.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=self.timeout)
        except psutil.NoSuchProcess:
            return KillOutcome.KILLED
        except psutil.AccessDenied:
            return KillOutcome.ACCESS_DENIED
        except psutil.TimeoutExpired:
            return KillOutcome.FAILED
        return KillOutcome.KILLED

    def radical_clean(self, processes: Iterable[GpuProcess]) -> list[KillResult]:
        plan = plan_radical_clean(processes, self.identify, self.own_pids)
        return [self.kill(process.pid) for process in plan.targets]


class DemoKiller:
    """Pretends to close the simulated processes of the demo provider; never touches real ones."""

    def __init__(self, provider) -> None:
        self.provider = provider

    def kill(self, pid: int) -> KillResult:
        name = next((p.name for p in self.provider.processes() if p.pid == pid), f"pid {pid}")
        return KillResult(pid, name, KillOutcome.KILLED)

    def radical_clean(self, processes: Iterable[GpuProcess]) -> list[KillResult]:
        return [self.kill(process.pid) for process in processes]
