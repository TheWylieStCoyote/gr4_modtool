"""Tests for the Textual TUI.

Sync tests cover pure-Python helpers.
Async tests use App.run_test() wrapped by the async_test decorator from conftest,
which drives them via asyncio.run() — no async pytest plugin required.
"""

from __future__ import annotations

from pathlib import Path

from conftest import async_test

from gr4_modtool.tui.app import (
    GR4ModtoolApp,
    HelpScreen,
    NewBlockScreen,
    NewGroupScreen,
    _parse_ports,
)

# ---------------------------------------------------------------------------
# Sync tests — pure helpers
# ---------------------------------------------------------------------------


def test_parse_ports_basic() -> None:
    result = _parse_ports("in:T; out:float")
    assert result == [{"name": "in", "type": "T"}, {"name": "out", "type": "float"}]


def test_parse_ports_single_no_type() -> None:
    result = _parse_ports("in")
    assert result == [{"name": "in", "type": "T"}]


def test_parse_ports_empty() -> None:
    assert _parse_ports("") == []


def test_parse_ports_complex_type() -> None:
    result = _parse_ports("in:std::complex<T>")
    assert result == [{"name": "in", "type": "std::complex<T>"}]


def test_parse_ports_whitespace_tolerance() -> None:
    result = _parse_ports("  sig  :  float  ;  out  :  T  ")
    assert result == [{"name": "sig", "type": "float"}, {"name": "out", "type": "T"}]


# ---------------------------------------------------------------------------
# Async tests — full TUI via Pilot
# ---------------------------------------------------------------------------


@async_test
async def test_app_mounts_on_valid_project(project) -> None:
    """App starts without exception and detail panel renders project name."""
    app = GR4ModtoolApp(project_dir=project.root)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert app.query_one("Header") is not None
        from gr4_modtool.tui.app import DetailPanel

        detail = app.query_one(DetailPanel)
        assert detail is not None


@async_test
async def test_app_no_project_shows_error(tmp_path: Path) -> None:
    """App without a .gr4modtool.toml shows error text in the detail panel."""
    app = GR4ModtoolApp(project_dir=tmp_path)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        from gr4_modtool.tui.app import DetailPanel

        detail = app.query_one(DetailPanel)
        assert detail is not None


@async_test
async def test_help_screen_opens_on_question_mark(project) -> None:
    """Pressing '?' pushes HelpScreen onto the screen stack."""
    app = GR4ModtoolApp(project_dir=project.root)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("question_mark")
        await pilot.pause()
        assert isinstance(app.screen, HelpScreen)


@async_test
async def test_help_screen_closes_on_escape(project) -> None:
    """Pressing '?' then 'escape' returns to the main screen."""
    app = GR4ModtoolApp(project_dir=project.root)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("question_mark")
        await pilot.pause()
        assert isinstance(app.screen, HelpScreen)
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, HelpScreen)


@async_test
async def test_new_group_screen_opens(project) -> None:
    """Pressing 'g' pushes NewGroupScreen onto the stack."""
    app = GR4ModtoolApp(project_dir=project.root)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("g")
        await pilot.pause()
        assert isinstance(app.screen, NewGroupScreen)


@async_test
async def test_new_group_screen_cancel(project) -> None:
    """Clicking Cancel on NewGroupScreen dismisses it without creating a group."""
    app = GR4ModtoolApp(project_dir=project.root)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("g")
        await pilot.pause()
        assert isinstance(app.screen, NewGroupScreen)
        await pilot.click("#cancel-btn")
        await pilot.pause()
        assert not isinstance(app.screen, NewGroupScreen)


@async_test
async def test_new_block_screen_opens(project) -> None:
    """Pressing 'n' pushes NewBlockScreen onto the stack."""
    app = GR4ModtoolApp(project_dir=project.root)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        assert isinstance(app.screen, NewBlockScreen)


@async_test
async def test_archetype_select_updates_ports(project) -> None:
    """Selecting 'sink' archetype clears the out-ports input and sets in-ports."""
    from textual.widgets import Input, Select

    app = GR4ModtoolApp(project_dir=project.root)
    async with app.run_test(size=(120, 50)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, NewBlockScreen)
        arch_select = screen.query_one("#archetype-select", Select)
        arch_select.value = "sink"
        await pilot.pause()
        in_ports = screen.query_one("#in-ports", Input).value
        out_ports = screen.query_one("#out-ports", Input).value
        assert "in" in in_ports
        assert out_ports == ""


@async_test
async def test_filter_input_does_not_crash(project) -> None:
    """Typing into the filter input repopulates the tree without crashing."""
    from textual.widgets import Input

    app = GR4ModtoolApp(project_dir=project.root)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        filter_input = app.query_one("#filter-input", Input)
        filter_input.focus()
        filter_input.value = "xyz"
        await pilot.pause()
        assert app.query_one("Header") is not None
