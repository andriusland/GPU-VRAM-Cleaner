"""Textual user interface."""

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Button, DataTable, Footer, Header, Label, OptionList, Static
from textual.widgets.option_list import Option

from .graph import column_heights, render_bars
from .history import History
from .killer import (
    Identify,
    KillOutcome,
    KillResult,
    identify_process,
    own_process_tree,
    plan_radical_clean,
    process_is_protected,
)
from .levels import Level, fan_level, level_color, percent_level, temperature_level
from .models import GpuInfo, GpuProcess
from .provider import GpuProvider
from .themes import THEME_LABELS, THEMES, load_theme_name, save_theme_name

GIB = 1024**3


class Killer(Protocol):
    def kill(self, pid: int) -> KillResult: ...

    def radical_clean(self, processes: list[GpuProcess]) -> list[KillResult]: ...


def colored(value: str, level: Level) -> Text:
    return Text(value, style=f"bold {level_color(level)}")


def fmt_pct(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.0f}%"


def fmt_bytes(value: int | None) -> str:
    if value is None:
        return "N/A"
    if value >= GIB:
        return f"{value / GIB:.2f} GiB"
    return f"{value / 1024**2:.0f} MiB"


class Graph(Widget):
    """Scrolling bar graph of a 0-100 reading; each column is colored by its level."""

    DEFAULT_CSS = """
    Graph {
        height: 100%;
        width: 1fr;
        border: round $secondary;
        border-title-color: $text;
        background: $surface;
        padding: 0 1;
    }
    """

    def __init__(self, label: str, history: History, level_of: Callable[[float | None], Level], **kw) -> None:
        super().__init__(**kw)
        self.label = label
        self.history = history
        self.level_of = level_of
        self.current: float | None = None
        self.border_title = label

    def update_value(self, value: float | None) -> None:
        self.current = value
        title = Text.assemble(f"{self.label} ", colored(fmt_pct(value), self.level_of(value)))
        self.border_title = title.markup
        self.refresh()

    def render(self) -> Text:
        width, height = self.content_size.width, self.content_size.height
        if width <= 0 or height <= 0:
            return Text("")
        samples = list(self.history)
        heights = column_heights(samples, width, height, 100.0)
        padded: list[float | None] = [None] * (width - min(width, len(samples))) + samples[-width:]
        rows = render_bars(samples, width, height, 100.0)
        text = Text()
        for row_index, row in enumerate(rows):
            for col, char in enumerate(row):
                if heights[col] and padded[col] is not None:
                    text.append(char, style=level_color(self.level_of(padded[col])))
                else:
                    text.append(char)
            if row_index < len(rows) - 1:
                text.append("\n")
        return text


class GpuPanel(Vertical):
    DEFAULT_CSS = """
    GpuPanel {
        height: 14;
        border: heavy $primary;
        border-title-color: $accent;
        border-title-style: bold;
        background: $panel;
        padding: 0 1;
        margin-bottom: 1;
    }
    GpuPanel .summary { height: 2; }
    GpuPanel Horizontal { height: 1fr; }
    """

    def __init__(self, info: GpuInfo, history_size: int = 120) -> None:
        super().__init__(id=f"gpu-{info.index}")
        self.info = info
        self.vram_history = History(history_size)
        self.fan_history = History(history_size)
        self.load_history = History(history_size)
        self.border_title = f"GPU {info.index} · {info.name}"

    def compose(self) -> ComposeResult:
        yield Static(self.summary_text(), classes="summary")
        with Horizontal():
            yield Graph("VRAM", self.vram_history, percent_level, id=f"vram-{self.info.index}")
            yield Graph("Fan", self.fan_history, fan_level, id=f"fan-{self.info.index}")
            yield Graph("Load", self.load_history, percent_level, id=f"load-{self.info.index}")

    def summary_text(self) -> Text:
        info = self.info
        temp = "N/A" if info.temperature_c is None else f"{info.temperature_c:.0f}°C"
        return Text.assemble(
            ("Model ", "dim"),
            (info.name, "bold"),
            ("   Driver ", "dim"),
            info.driver,
            ("   Temp ", "dim"),
            colored(temp, temperature_level(info.temperature_c)),
            ("   Load ", "dim"),
            colored(fmt_pct(info.utilization_pct), percent_level(info.utilization_pct)),
            "\n",
            ("VRAM ", "dim"),
            f"{fmt_bytes(info.memory_used)} / {fmt_bytes(info.memory_total)} ",
            colored(fmt_pct(info.memory_pct), percent_level(info.memory_pct)),
            ("   Fan ", "dim"),
            colored(fmt_pct(info.fan_pct), fan_level(info.fan_pct)),
        )

    def update_info(self, info: GpuInfo) -> None:
        self.info = info
        self.border_title = f"GPU {info.index} · {info.name}"
        self.vram_history.push(info.memory_pct)
        self.fan_history.push(info.fan_pct)
        self.load_history.push(info.utilization_pct)
        if not self.is_mounted:
            return
        self.query_one(".summary", Static).update(self.summary_text())
        self.query_one(f"#vram-{info.index}", Graph).update_value(info.memory_pct)
        self.query_one(f"#fan-{info.index}", Graph).update_value(info.fan_pct)
        self.query_one(f"#load-{info.index}", Graph).update_value(info.utilization_pct)


class ConfirmDialog(ModalScreen[bool]):
    DEFAULT_CSS = """
    ConfirmDialog { align: center middle; background: $background 60%; }
    ConfirmDialog #dialog {
        width: 60; height: auto; padding: 1 2;
        border: thick $primary; background: $surface;
    }
    ConfirmDialog #title { text-style: bold; color: $accent; width: 100%; content-align: center middle; }
    ConfirmDialog #message { width: 100%; margin: 1 0; content-align: center middle; }
    ConfirmDialog Horizontal { height: auto; align: center middle; }
    ConfirmDialog Button { margin: 0 2; min-width: 12; }
    ConfirmDialog.-danger { background: #3A0000 60%; }
    ConfirmDialog.-danger #dialog { border: thick #FF3B3B; background: #5C0A0A; }
    ConfirmDialog.-danger #title { color: #FFFFFF; background: #D32F2F; }
    ConfirmDialog.-danger #message { color: #FFE5E5; text-style: bold; }
    ConfirmDialog.-danger #yes, ConfirmDialog.-danger #cancel {
        background: #8E1B1B; color: #FFFFFF; border-top: tall #B23A3A; border-bottom: tall #4A0808;
    }
    ConfirmDialog.-danger #yes:focus, ConfirmDialog.-danger #cancel:focus {
        background: #FF3B3B; text-style: bold reverse;
    }
    """
    BINDINGS = [
        Binding("left", "app.focus_previous", "Previous", show=False),
        Binding("right", "app.focus_next", "Next", show=False),
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, title: str, message: str, default_yes: bool = True, danger: bool = False) -> None:
        super().__init__(classes="-danger" if danger else None)
        self.title_text = title
        self.message = message
        self.default_yes = default_yes

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(self.title_text, id="title")
            yield Label(self.message, id="message")
            with Horizontal():
                yield Button("Yes", id="yes", variant="error")
                yield Button("Cancel", id="cancel", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#yes" if self.default_yes else "#cancel", Button).focus()

    @on(Button.Pressed)
    def choose(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")

    def action_cancel(self) -> None:
        self.dismiss(False)


class _ListScreen(ModalScreen[str | None]):
    DEFAULT_CSS = """
    _ListScreen { align: center middle; background: $background 60%; }
    _ListScreen #box {
        width: 44; height: auto; border: thick $primary; background: $surface; padding: 1;
    }
    _ListScreen #heading { text-style: bold; color: $accent; margin-bottom: 1; }
    _ListScreen OptionList { height: auto; max-height: 12; }
    _ListScreen OptionList, _ListScreen OptionList:focus { border: none; }
    """
    BINDINGS = [Binding("escape", "close", "Close")]
    heading = ""

    def options(self) -> list[Option]:
        raise NotImplementedError

    def compose(self) -> ComposeResult:
        with Vertical(id="box"):
            yield Label(self.heading, id="heading")
            yield OptionList(*self.options())

    def action_close(self) -> None:
        self.dismiss(None)

    @on(OptionList.OptionSelected)
    def selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id)


class MenuScreen(_ListScreen):
    heading = "Menu"

    def options(self) -> list[Option]:
        return [
            Option("Change theme", id="theme"),
            Option("Radical clean (close every VRAM process)", id="radical"),
            Option("Quit", id="quit"),
        ]


class ThemeScreen(_ListScreen):
    heading = "Choose a theme"

    def __init__(self, current: str) -> None:
        super().__init__()
        self.original = current

    def options(self) -> list[Option]:
        return [Option(THEME_LABELS[t.name], id=t.name) for t in THEMES]

    def on_mount(self) -> None:
        options = self.query_one(OptionList)
        names = [t.name for t in THEMES]
        options.highlighted = names.index(self.original) if self.original in names else 0
        options.focus()

    @on(OptionList.OptionHighlighted)
    def preview(self, event: OptionList.OptionHighlighted) -> None:
        if event.option.id:
            self.app.theme = event.option.id

    def action_close(self) -> None:
        self.app.theme = self.original
        self.dismiss(None)


class VramCleanerApp(App):
    TITLE = "GPU VRAM Cleaner"
    CSS = """
    #gpus { height: auto; max-height: 75%; padding: 0 1; }
    #processes {
        height: 1fr; min-height: 8;
        border: heavy $primary; border-title-color: $accent; border-title-style: bold;
        background: $surface; margin: 0 1;
    }
    """
    BINDINGS = [
        Binding("delete", "close_process", "Close process"),
        Binding("m", "menu", "Menu"),
        Binding("t", "themes", "Theme"),
        Binding("x", "radical_clean", "Radical clean"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(
        self,
        provider: GpuProvider,
        killer: Killer,
        settings_file: Path | None = None,
        identify: Identify = identify_process,
        own_pids: set[int] | None = None,
        interval: float = 1.0,
    ) -> None:
        super().__init__()
        self.provider = provider
        self.killer = killer
        self.settings_file = settings_file
        self.identify = identify
        self.own_pids = own_process_tree() if own_pids is None else own_pids
        self.interval = interval
        self.processes: list[GpuProcess] = []
        for theme in THEMES:
            self.register_theme(theme)
        self.theme = load_theme_name(settings_file)

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="gpus"):
            for info in self.provider.gpus():
                yield GpuPanel(info)
        table = DataTable(id="processes", cursor_type="row", zebra_stripes=True)
        table.border_title = "Processes using the GPU  (↑/↓ select · Del close)"
        yield table
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("PID", "Process", "GPU", "VRAM", "Load", "Type", "Status")
        table.focus()
        self.refresh_data()
        self.set_interval(self.interval, self.refresh_data)

    def refresh_data(self) -> None:
        for info in self.provider.gpus():
            for panel in self.query(GpuPanel):
                if panel.info.index == info.index:
                    panel.update_info(info)
        self.processes = self.provider.processes()
        self._fill_table()

    def _is_protected(self, process: GpuProcess) -> bool:
        return process_is_protected(process, self.identify, self.own_pids)

    def _fill_table(self) -> None:
        table = self.query_one(DataTable)
        selected = self.selected_process()
        table.clear()
        for process in self.processes:
            status = Text("protected", style="yellow") if self._is_protected(process) else Text("")
            table.add_row(
                str(process.pid),
                process.name,
                str(process.gpu_index),
                fmt_bytes(process.used_memory),
                colored(fmt_pct(process.load_pct), percent_level(process.load_pct)),
                process.kind,
                status,
                key=f"{process.gpu_index}:{process.pid}",
            )
        if selected is not None:
            for row, process in enumerate(self.processes):
                if (process.pid, process.gpu_index) == (selected.pid, selected.gpu_index):
                    table.move_cursor(row=row)
                    break

    def selected_process(self) -> GpuProcess | None:
        table = self.query_one(DataTable)
        if table.row_count == 0 or not 0 <= table.cursor_row < len(self.processes):
            return None
        return self.processes[table.cursor_row]

    def action_close_process(self) -> None:
        process = self.selected_process()
        if process is None:
            return
        if self._is_protected(process):
            self.notify(
                f"{process.name} (PID {process.pid}) is a protected Windows process and will not be closed.",
                title="Protected",
                severity="warning",
            )
            return

        def confirmed(yes: bool | None) -> None:
            if yes:
                self._kill(process.pid)

        self.push_screen(
            ConfirmDialog("Close process", f"Close {process.name} (PID {process.pid})?", default_yes=True),
            confirmed,
        )

    @work(thread=True, exclusive=True, group="kill")
    def _kill(self, pid: int) -> None:
        result = self.killer.kill(pid)
        self.call_from_thread(self._after_kill, [result])

    def action_radical_clean(self) -> None:
        plan = plan_radical_clean(self.processes, self.identify, self.own_pids)
        if not plan.targets:
            self.notify("No closable process is using VRAM.", title="Radical clean")
            return

        def second_confirmation(yes: bool | None) -> None:
            if yes:
                self._radical(plan.targets)

        def first_confirmation(yes: bool | None) -> None:
            if yes:
                self.push_screen(
                    ConfirmDialog(
                        "⚠ Dangerous",
                        "Are you sure?\nThis can be potentially unsafe for your system.",
                        default_yes=False,
                        danger=True,
                    ),
                    second_confirmation,
                )

        self.push_screen(
            ConfirmDialog(
                "⚠ Dangerous · Radical clean",
                f"Close {len(plan.targets)} process(es) using VRAM?\n"
                f"{len(plan.protected)} protected Windows process(es) will be kept.",
                default_yes=False,
                danger=True,
            ),
            first_confirmation,
        )

    @work(thread=True, exclusive=True, group="kill")
    def _radical(self, targets: list[GpuProcess]) -> None:
        results = self.killer.radical_clean(targets)
        self.call_from_thread(self._after_kill, results)

    def _after_kill(self, results: list[KillResult]) -> None:
        forget = getattr(self.provider, "forget", None)
        killed = [r for r in results if r.outcome is KillOutcome.KILLED]
        failed = [r for r in results if r.outcome is not KillOutcome.KILLED]
        if forget:
            for result in killed:
                forget(result.pid)
        if len(results) == 1:
            result = results[0]
            if killed:
                self.notify(f"Closed {result.name} (PID {result.pid}).", title="Process closed")
            else:
                self.notify(self._failure_hint(result), title="Could not close process", severity="error")
        else:
            message = f"Closed {len(killed)} process(es)."
            if failed:
                message += f" {len(failed)} could not be closed: " + ", ".join(
                    f"{r.name} ({r.outcome.value})" for r in failed
                )
            self.notify(message, title="Radical clean", severity="warning" if failed else "information")
        self.refresh_data()

    @staticmethod
    def _failure_hint(result: KillResult) -> str:
        if result.outcome is KillOutcome.ACCESS_DENIED:
            return f"Access denied for {result.name}. Run the terminal as administrator."
        return f"{result.name} (PID {result.pid}): {result.outcome.value}."

    def action_menu(self) -> None:
        def chosen(choice: str | None) -> None:
            if choice == "theme":
                self.action_themes()
            elif choice == "radical":
                self.action_radical_clean()
            elif choice == "quit":
                self.exit()

        self.push_screen(MenuScreen(), chosen)

    def action_themes(self) -> None:
        def chosen(name: str | None) -> None:
            if name:
                self.theme = name
                save_theme_name(name, self.settings_file)

        self.push_screen(ThemeScreen(self.theme), chosen)

    def on_unmount(self) -> None:
        self.provider.close()
