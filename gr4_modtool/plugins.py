"""Entry-point loader for third-party gr4_modtool extensions."""

from __future__ import annotations

from importlib.metadata import entry_points
from pathlib import Path

import click


def load_extra_commands() -> list[click.BaseCommand]:
    """Return Click commands registered under 'gr4_modtool.commands'."""
    cmds: list[click.BaseCommand] = []
    for ep in entry_points(group="gr4_modtool.commands"):
        try:
            cmd = ep.load()
            if isinstance(cmd, click.BaseCommand):
                cmds.append(cmd)
        except Exception as exc:  # noqa: BLE001
            click.echo(f"[gr4_modtool] Warning: could not load command plugin '{ep.name}': {exc}", err=True)
    return cmds


def load_extra_template_dirs() -> list[Path]:
    """Return template directories registered under 'gr4_modtool.templates'."""
    dirs: list[Path] = []
    for ep in entry_points(group="gr4_modtool.templates"):
        try:
            get_dir = ep.load()
            path = Path(get_dir())
            if path.is_dir():
                dirs.append(path)
        except Exception as exc:  # noqa: BLE001
            click.echo(f"[gr4_modtool] Warning: could not load template plugin '{ep.name}': {exc}", err=True)
    return dirs
