import pytest

from gpu_vram_cleaner.protection import ProcessIdentity, is_protected


def identity(pid=1234, name="game.exe", username="DESKTOP\\andres"):
    return ProcessIdentity(pid=pid, name=name, username=username)


@pytest.mark.parametrize(
    "name",
    [
        "dwm.exe",
        "csrss.exe",
        "winlogon.exe",
        "explorer.exe",
        "services.exe",
        "lsass.exe",
        "svchost.exe",
        "DWM.EXE",
        "ShellHost.exe",
    ],
)
def test_critical_windows_processes_are_protected(name):
    assert is_protected(identity(name=name), own_pids=set())


@pytest.mark.parametrize(
    "username", ["NT AUTHORITY\\SYSTEM", "NT AUTHORITY\\LOCAL SERVICE", "NT AUTHORITY\\NETWORK SERVICE"]
)
def test_service_accounts_are_protected(username):
    assert is_protected(identity(username=username), own_pids=set())


def test_kernel_pids_are_protected():
    assert is_protected(identity(pid=0), own_pids=set())
    assert is_protected(identity(pid=4), own_pids=set())


def test_own_process_tree_is_protected():
    assert is_protected(identity(pid=777), own_pids={777})


def test_regular_user_process_is_not_protected():
    assert not is_protected(identity(), own_pids={1})


def test_unknown_username_does_not_protect_by_itself():
    assert not is_protected(identity(username=None), own_pids=set())
