"""Decide which processes must never be killed so Windows keeps working."""

from dataclasses import dataclass

# Core Windows, shell and driver processes. Killing any of these can log the
# user out, blank the screen, freeze input or crash the system.
PROTECTED_NAMES = frozenset(
    name.lower()
    for name in [
        "System",
        "Registry",
        "Idle",
        "smss.exe",
        "csrss.exe",
        "wininit.exe",
        "winlogon.exe",
        "services.exe",
        "lsass.exe",
        "lsaiso.exe",
        "svchost.exe",
        "dwm.exe",
        "explorer.exe",
        "fontdrvhost.exe",
        "sihost.exe",
        "ctfmon.exe",
        "taskhostw.exe",
        "audiodg.exe",
        "ShellExperienceHost.exe",
        "StartMenuExperienceHost.exe",
        "SearchHost.exe",
        "SearchApp.exe",
        "TextInputHost.exe",
        "LockApp.exe",
        "LogonUI.exe",
        "RuntimeBroker.exe",
        "ApplicationFrameHost.exe",
        "SecurityHealthSystray.exe",
        "MsMpEng.exe",
        "spoolsv.exe",
        "WUDFHost.exe",
        "dllhost.exe",
        "conhost.exe",
        "OpenConsole.exe",
        "WindowsTerminal.exe",
        "NVDisplay.Container.exe",
        "nvcontainer.exe",
        "nvsphelper64.exe",
    ]
)

SERVICE_ACCOUNTS = frozenset(
    account.lower()
    for account in [
        "NT AUTHORITY\\SYSTEM",
        "NT AUTHORITY\\LOCAL SERVICE",
        "NT AUTHORITY\\NETWORK SERVICE",
        "SYSTEM",
    ]
)

KERNEL_PIDS = frozenset({0, 4})


@dataclass(frozen=True)
class ProcessIdentity:
    pid: int
    name: str
    username: str | None


def is_protected(identity: ProcessIdentity, own_pids: set[int]) -> bool:
    """True when killing the process could break Windows or this app itself."""
    if identity.pid in KERNEL_PIDS or identity.pid in own_pids:
        return True
    if identity.name.lower() in PROTECTED_NAMES:
        return True
    return identity.username is not None and identity.username.lower() in SERVICE_ACCOUNTS
