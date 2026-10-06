"""GPU VRAM Cleaner: monitor NVIDIA GPUs and close the processes that hold VRAM."""

import argparse
import sys

from colorama import Fore, Style, just_fix_windows_console

__version__ = "0.1.0"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gpu-vram-cleaner", description=__doc__)
    parser.add_argument("--demo", action="store_true", help="use simulated GPUs (no NVIDIA card needed)")
    parser.add_argument("--interval", type=float, default=1.0, help="refresh interval in seconds (default 1)")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    just_fix_windows_console()
    args = build_parser().parse_args(argv)

    from .app import VramCleanerApp
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
                f"or try {Fore.CYAN}gpu-vram-cleaner --demo{Style.RESET_ALL}",
                file=sys.stderr,
            )
            return 1
        killer = ProcessKiller()

    VramCleanerApp(provider=provider, killer=killer, interval=args.interval).run()
    print(f"{Fore.GREEN}GPU VRAM Cleaner closed.{Style.RESET_ALL}")
    return 0
