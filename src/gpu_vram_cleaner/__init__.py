"""GPU VRAM Cleaner: monitor NVIDIA GPUs and close the processes that hold VRAM."""

import argparse
import sys

from colorama import Fore, Style, just_fix_windows_console

__version__ = "0.2.1"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gpu-cleaner", description=__doc__)
    parser.add_argument("--demo", action="store_true", help="use simulated GPUs (no NVIDIA card needed)")
    parser.add_argument("--interval", type=float, default=1.0, help="refresh interval in seconds (default 1)")
    parser.add_argument(
        "--autoclean",
        action="store_true",
        help="close every unprotected process using VRAM and exit, without the UI (for scripts)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="with --autoclean: only list what would be closed"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    just_fix_windows_console()
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.dry_run and not args.autoclean:
        parser.error("--dry-run only works together with --autoclean")

    from . import autoclean
    from .killer import DemoKiller, ProcessKiller
    from .provider import DemoGpuProvider, GpuProviderError, NvmlGpuProvider

    if args.demo:
        provider = DemoGpuProvider()
        killer = DemoKiller(provider)
    else:
        try:
            provider = NvmlGpuProvider()
        except GpuProviderError as exc:
            print(f"{Fore.RED}{Style.BRIGHT}Error:{Style.RESET_ALL} {exc}", file=sys.stderr)
            print(
                f"{Fore.YELLOW}Make sure an NVIDIA GPU and driver are installed, "
                f"or try {Fore.CYAN}gpu-cleaner --demo{Style.RESET_ALL}",
                file=sys.stderr,
            )
            return 1
        killer = ProcessKiller()

    if args.autoclean:
        try:
            return autoclean.run_autoclean(provider, killer, dry_run=args.dry_run)
        finally:
            provider.close()

    from .app import VramCleanerApp

    VramCleanerApp(provider=provider, killer=killer, interval=args.interval).run()
    print(f"{Fore.GREEN}GPU VRAM Cleaner closed.{Style.RESET_ALL}")
    return 0
