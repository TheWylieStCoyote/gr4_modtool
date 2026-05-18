"""gr4_modtool CLI entry point."""

from __future__ import annotations

import click

from gr4_modtool.commands.info import cmd as info_cmd
from gr4_modtool.commands.newmod import cmd as newmod_cmd
from gr4_modtool.commands.newgroup import cmd as newgroup_cmd
from gr4_modtool.commands.newblock import cmd as newblock_cmd
from gr4_modtool.commands.rm import cmd as rm_cmd
from gr4_modtool.commands.rename import cmd as rename_cmd
from gr4_modtool import plugins as _plugins


@click.group()
@click.version_option()
def cli() -> None:
    """GNURadio 4 OOT module management tool."""


cli.add_command(newmod_cmd, name="newmod")
cli.add_command(newgroup_cmd, name="newgroup")
cli.add_command(newblock_cmd, name="newblock")
cli.add_command(rm_cmd, name="rm")
cli.add_command(rename_cmd, name="rename")
cli.add_command(info_cmd, name="info")


@cli.command("tui")
@click.option("--project-dir", default=None, type=click.Path(exists=True))
def tui_cmd(project_dir: str | None) -> None:
    """Launch the interactive Textual TUI."""
    from gr4_modtool.tui.app import GR4ModtoolApp
    from pathlib import Path

    app = GR4ModtoolApp(project_dir=Path(project_dir) if project_dir else None)
    app.run()


# Load plugin commands
for _extra_cmd in _plugins.load_extra_commands():
    cli.add_command(_extra_cmd)
