"""Non-interactive clean for scripts: close every unprotected VRAM process and exit."""

import sys
from typing import TextIO

from colorama import Fore, Style

from .killer import Identify, KillOutcome, identify_process, plan_radical_clean

CLOSED = {KillOutcome.KILLED, KillOutcome.NOT_FOUND}


def _mib(value: int | None) -> str:
    return f"{(value or 0) / 1024**2:.0f} MiB"


def run_autoclean(
    provider,
    killer,
    *,
    dry_run: bool = False,
    identify: Identify = identify_process,
    own_pids: set[int] | None = None,
    out: TextIO | None = None,
) -> int:
    """Close the processes radical clean would close. Returns 0 if all of them are gone, else 1."""
    out = out or sys.stdout
    plan = plan_radical_clean(provider.processes(), identify, own_pids)

    for process in plan.protected:
        print(f"{Fore.CYAN}keep{Style.RESET_ALL}   {process.pid:>7}  {process.name}  (protected)", file=out)

    if not plan.targets:
        print(
            f"{Fore.GREEN}Nothing to close:{Style.RESET_ALL} no unprotected process is using VRAM.", file=out
        )
        return 0

    total = _mib(sum(p.used_memory or 0 for p in plan.targets))
    if dry_run:
        for process in plan.targets:
            print(
                f"{Fore.YELLOW}would close{Style.RESET_ALL}  {process.pid:>7}  {process.name}  "
                f"{_mib(process.used_memory)}",
                file=out,
            )
        print(f"Dry run: {len(plan.targets)} process(es) holding {total} would be closed.", file=out)
        return 0

    failed = 0
    for process in plan.targets:
        result = killer.kill(process.pid)
        row = f"{process.pid:>7}  {process.name}"
        if result.outcome in CLOSED:
            print(
                f"{Fore.GREEN}closed{Style.RESET_ALL} {row}  {_mib(process.used_memory)}",
                file=out,
            )
        else:
            failed += 1
            print(
                f"{Fore.RED}failed{Style.RESET_ALL} {row}  ({result.outcome.value})",
                file=out,
            )

    closed = len(plan.targets) - failed
    print(f"Closed {closed} of {len(plan.targets)} process(es) holding {total}.", file=out)
    return 1 if failed else 0
