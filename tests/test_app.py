from textual.widgets import Button, DataTable, OptionList

from gpu_vram_cleaner.app import ConfirmDialog, GpuPanel, MenuScreen, ThemeScreen, VramCleanerApp
from gpu_vram_cleaner.killer import KillOutcome, KillResult
from gpu_vram_cleaner.models import GpuInfo, GpuProcess


class FakeProvider:
    def __init__(self):
        self.gpu_list = [
            GpuInfo(0, "RTX Test A", "555.55", 70, 90, 6 * 1024**3, 8 * 1024**3, 40),
            GpuInfo(1, "RTX Test B", "555.55", 40, 10, 1 * 1024**3, 8 * 1024**3, None),
        ]
        self.process_list = [
            GpuProcess(101, "game.exe", 0, 3 * 1024**3, "G"),
            GpuProcess(202, "trainer.exe", 0, 2 * 1024**3, "C"),
            GpuProcess(303, "dwm.exe", 1, 256 * 1024**2, "G"),
        ]

    def gpus(self):
        return list(self.gpu_list)

    def processes(self):
        return list(self.process_list)

    def close(self):
        pass


class FakeKiller:
    def __init__(self):
        self.killed = []
        self.radical_calls = []

    def kill(self, pid):
        self.killed.append(pid)
        return KillResult(pid, "x", KillOutcome.KILLED)

    def radical_clean(self, processes):
        processes = list(processes)
        self.radical_calls.append([p.pid for p in processes])
        return [KillResult(p.pid, p.name, KillOutcome.KILLED) for p in processes]


def make_app(tmp_path):
    killer = FakeKiller()
    app = VramCleanerApp(provider=FakeProvider(), killer=killer, settings_file=tmp_path / "s.json")
    return app, killer


async def test_shows_a_panel_per_gpu_and_lists_processes(tmp_path):
    app, _ = make_app(tmp_path)
    async with app.run_test(size=(140, 50)):
        assert len(app.query(GpuPanel)) == 2
        table = app.query_one(DataTable)
        assert table.row_count == 3


async def test_gpu_panel_shows_model_driver_and_colored_readings(tmp_path):
    app, _ = make_app(tmp_path)
    async with app.run_test(size=(140, 50)):
        text = app.query_one("#gpu-0", GpuPanel).summary_text().plain
        assert "RTX Test A" in text
        assert "555.55" in text
        assert "70°C" in text
        assert "90%" in text
        assert "75%" in text


async def test_arrows_move_and_delete_asks_to_close_with_yes_focused(tmp_path):
    app, killer = make_app(tmp_path)
    async with app.run_test(size=(140, 50)) as pilot:
        await pilot.press("down")
        await pilot.press("delete")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmDialog)
        assert "Close process" in app.screen.title_text
        assert app.screen.focused.id == "yes"
        await pilot.press("enter")
        await app.workers.wait_for_complete()
        assert killer.killed == [202]


async def test_cancel_does_not_kill(tmp_path):
    app, killer = make_app(tmp_path)
    async with app.run_test(size=(140, 50)) as pilot:
        await pilot.press("delete")
        await pilot.pause()
        await pilot.press("right")
        assert app.screen.focused.id == "cancel"
        await pilot.press("enter")
        await pilot.pause()
        assert killer.killed == []
        assert not isinstance(app.screen, ConfirmDialog)


async def test_refresh_appends_history(tmp_path):
    app, _ = make_app(tmp_path)
    async with app.run_test(size=(140, 50)):
        panel = app.query_one("#gpu-0", GpuPanel)
        before = len(panel.vram_history)
        app.refresh_data()
        assert len(panel.vram_history) == before + 1
        assert panel.vram_history.latest == 75.0


async def test_theme_menu_offers_six_themes_and_switches(tmp_path):
    app, _ = make_app(tmp_path)
    async with app.run_test(size=(140, 50)) as pilot:
        await pilot.press("m")
        await pilot.pause()
        assert isinstance(app.screen, MenuScreen)
        app.screen.query_one(OptionList).highlighted = 0
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, ThemeScreen)
        options = app.screen.query_one(OptionList)
        assert options.option_count == 6
        await pilot.press("down", "enter")
        await pilot.pause()
        assert app.theme == "vram-ocean"
        assert '"vram-ocean"' in (tmp_path / "s.json").read_text()


async def test_radical_clean_needs_two_red_confirmations(tmp_path):
    app, killer = make_app(tmp_path)
    async with app.run_test(size=(140, 50)) as pilot:
        app.action_radical_clean()
        await pilot.pause()
        first = app.screen
        assert isinstance(first, ConfirmDialog)
        assert "Dangerous" in first.title_text
        assert first.has_class("-danger")
        assert first.focused.id == "cancel"
        first.query_one("#yes", Button).press()
        await pilot.pause()

        second = app.screen
        assert isinstance(second, ConfirmDialog) and second is not first
        assert second.has_class("-danger")
        assert "This can be potentially unsafe for your system" in second.message
        assert second.focused.id == "cancel"
        assert killer.radical_calls == []

        second.query_one("#yes", Button).press()
        await pilot.pause()
        await app.workers.wait_for_complete()
        assert len(killer.radical_calls) == 1
        assert 303 not in killer.radical_calls[0]


async def test_cancelling_the_second_radical_confirmation_kills_nothing(tmp_path):
    app, killer = make_app(tmp_path)
    async with app.run_test(size=(140, 50)) as pilot:
        app.action_radical_clean()
        await pilot.pause()
        app.screen.query_one("#yes", Button).press()
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await app.workers.wait_for_complete()
        assert killer.radical_calls == []
        assert not isinstance(app.screen, ConfirmDialog)


async def test_close_process_dialog_is_not_marked_dangerous(tmp_path):
    app, _ = make_app(tmp_path)
    async with app.run_test(size=(140, 50)) as pilot:
        await pilot.press("delete")
        await pilot.pause()
        assert not app.screen.has_class("-danger")


async def test_delete_on_protected_process_does_not_offer_to_close(tmp_path):
    app, killer = make_app(tmp_path)
    async with app.run_test(size=(140, 50)) as pilot:
        await pilot.press("down", "down", "delete")
        await pilot.pause()
        assert not isinstance(app.screen, ConfirmDialog)
        assert killer.killed == []
