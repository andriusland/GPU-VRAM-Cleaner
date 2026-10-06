# GPU VRAM Cleaner

[![Windows](https://img.shields.io/badge/Windows-0078D6?logo=windows&logoColor=white)](#install)
[![Linux](https://img.shields.io/badge/Linux-FCC624?logo=linux&logoColor=black)](#install)
[![macOS demo](https://img.shields.io/badge/macOS-demo%20only-000000?logo=apple&logoColor=white)](#install)
[![NVIDIA](https://img.shields.io/badge/NVIDIA-NVML-76B900?logo=nvidia&logoColor=white)](https://developer.nvidia.com/management-library-nvml)
[![PyPI](https://img.shields.io/pypi/v/gpu-vram-cleaner?logo=pypi&logoColor=white)](https://pypi.org/project/gpu-vram-cleaner/)
[![Python](https://img.shields.io/pypi/pyversions/gpu-vram-cleaner?logo=python&logoColor=white)](https://pypi.org/project/gpu-vram-cleaner/)
[![Downloads](https://img.shields.io/pepy/dt/gpu-vram-cleaner)](https://pepy.tech/project/gpu-vram-cleaner)
[![CI](https://github.com/andriusland/GPU-VRAM-Cleaner/actions/workflows/ci.yml/badge.svg)](https://github.com/andriusland/GPU-VRAM-Cleaner/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](https://github.com/andriusland/GPU-VRAM-Cleaner/blob/main/LICENSE)
[![Built with Textual](https://img.shields.io/badge/built%20with-Textual-5A4FCF)](https://textual.textualize.io/)

**Tired of not being able to kill the processes that eat up your GPU? Now you finally can.**

A terminal UI (Textual + colorama) for Windows Terminal / PowerShell that shows every NVIDIA GPU in the
system and the processes holding its VRAM, and lets you close them to free memory.

![GPU VRAM Cleaner with the Synthwave Neon theme](https://raw.githubusercontent.com/andriusland/GPU-VRAM-Cleaner/main/docs/main-synthwave.png)

## Features

- One panel per GPU with model, driver version, temperature (°C), load, VRAM used/total, core and memory
  clocks (MHz) and power draw against the power limit (W).
- Three live graphs per GPU, refreshed every second: **VRAM %**, **fan %** and **load %**.
- Percentages and temperatures change color with their level (green / yellow / red):

  | Reading      | Green  | Yellow   | Red     |
  |--------------|--------|----------|---------|
  | VRAM, load   | < 60 % | 60–84 %  | ≥ 85 %  |
  | Fan          | < 50 % | 50–79 %  | ≥ 80 %  |
  | Temperature  | < 65 °C| 65–79 °C | ≥ 80 °C |

- Process list with each process's VRAM and GPU **load %** (the busiest GPU engine it uses, like Task
  Manager's GPU column, colored by level). Move with **↑ / ↓**, press **Del** to get a *Close process* confirmation with **Yes**
  (selected by default) and **Cancel** (use ← / → to switch, Enter to confirm, Esc to cancel).
- Menu (**m**) with:
  - **Change theme**: 7 color themes for borders and backgrounds (NVIDIA Green, Deep Ocean, Dracula Night,
    Solar Flare, Nord Frost, Paper Light and Synthwave Neon, the default). Themes preview live as you
    move; the choice is saved.
  - **Radical clean**: closes every process using VRAM in one go. It is marked **Dangerous**: two red
    confirmation popups, the second one asking "Are you sure? This can be potentially unsafe for your
    system." (Cancel is the default in both).

| Close process | Radical clean (Dangerous) |
|---|---|
| ![Close process dialog](https://raw.githubusercontent.com/andriusland/GPU-VRAM-Cleaner/main/docs/close-process.png) | ![Radical clean second confirmation](https://raw.githubusercontent.com/andriusland/GPU-VRAM-Cleaner/main/docs/radical-clean.png) |

| NVIDIA Green theme | Theme menu |
|---|---|
| ![NVIDIA Green theme](https://raw.githubusercontent.com/andriusland/GPU-VRAM-Cleaner/main/docs/main-nvidia.png) | ![Theme menu](https://raw.githubusercontent.com/andriusland/GPU-VRAM-Cleaner/main/docs/themes.png) |

## Keeping Windows safe

Both the single close and the radical clean refuse to touch processes that Windows needs, so the desktop,
login session and drivers keep working:

- core system processes (`System`, `csrss.exe`, `wininit.exe`, `winlogon.exe`, `services.exe`, `lsass.exe`,
  `svchost.exe`, `dwm.exe`, `explorer.exe`, `sihost.exe`, `ctfmon.exe`, shell hosts, NVIDIA display
  container, ...);
- anything running as `SYSTEM`, `LOCAL SERVICE` or `NETWORK SERVICE`, or that the app cannot inspect;
- the app itself and its parent processes (the PowerShell and Windows Terminal running it).

Protected rows are marked `protected` in the list. Everything else that holds VRAM (games, browsers,
Python/CUDA jobs, Blender, OBS, Discord, ...) is closed: first politely (`terminate`), then forcefully
(`kill`) if it does not exit within 3 seconds. Closing processes owned by other users requires running the
terminal as administrator.

## Install

`gpu-vram-cleaner` is on [PyPI](https://pypi.org/project/gpu-vram-cleaner/) and works on Windows and Linux
with an NVIDIA GPU and its driver installed (NVML ships with the driver). On macOS, or any machine without
an NVIDIA card, it runs in `--demo` mode.

### System-wide (recommended)

Install `gpu-cleaner` as a command available from any terminal with [uv](https://docs.astral.sh/uv/):

```powershell
uv tool install gpu-vram-cleaner
uv tool update-shell   # only the first time: adds uv's tool folder to your PATH
```

If you don't have uv yet, install it first:

```powershell
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

```bash
# Linux / macOS
curl -LsSf https://astral.sh/uv/install.sh | sh
```

[pipx](https://pipx.pypa.io/) works too: `pipx install gpu-vram-cleaner`.

Open a new terminal and run:

```powershell
gpu-cleaner
```

Update to the latest version with `uv tool upgrade gpu-vram-cleaner`, and remove it with
`uv tool uninstall gpu-vram-cleaner`.

> Tip: to close processes owned by other users or by system services, open the terminal as
> administrator (Windows) or run with `sudo` (Linux).

### From a clone (development)

```powershell
git clone https://github.com/andriusland/GPU-VRAM-Cleaner
cd GPU-VRAM-Cleaner
uv run gpu-cleaner
```

Options:

```text
--demo          simulated GPUs and processes (nothing real is closed); handy without an NVIDIA card
--interval S    refresh interval in seconds (default 1)
```

Keys: `↑/↓` select · `Del` close process · `m` menu · `t` theme · `x` radical clean · `q` quit.

> On Windows, NVML cannot report per-process VRAM under the WDDM driver model (every GeForce card), so the
> app reads it from the Windows "GPU Process Memory" performance counters instead, the same source as Task
> Manager's "Dedicated GPU memory" column. Per-process load comes from the "GPU Engine" counters the same way
> (it shows `N/A` for the first second while Windows takes its first sample).

## Development

The project was built test first (red → green → refactor).

```powershell
uv run pytest          # tests (core logic + Textual UI driven with a fake GPU provider)
uv run ruff check .    # lint
uv run ruff format .   # format
```

Layout (`src/gpu_vram_cleaner/`):

| Module          | Responsibility                                                    |
|-----------------|-------------------------------------------------------------------|
| `provider.py`   | `NvmlGpuProvider` (real GPUs via nvidia-ml-py) and `DemoGpuProvider` |
| `models.py`     | `GpuInfo`, `GpuProcess`                                           |
| `levels.py`     | thresholds and colors for percentages and temperatures            |
| `history.py`    | rolling sample buffer for the graphs                              |
| `graph.py`      | pure text rendering of the bar graphs                             |
| `protection.py` | which processes must never be closed                              |
| `wincounters.py` | per-process VRAM on Windows from the GPU performance counters     |
| `killer.py`     | closing processes with psutil, radical clean planning             |
| `themes.py`     | the color themes and saving the chosen one                        |
| `app.py`        | the Textual app, dialogs and menus                                |

## License

Licensed under the [Apache License 2.0](LICENSE).
