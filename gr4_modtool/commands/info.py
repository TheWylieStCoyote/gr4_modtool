"""info command — list all groups and blocks in the project."""

from __future__ import annotations

import json
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from gr4_modtool.project.discovery import load_config, discover_groups


@click.command("info")
@click.option("--project-dir", default=None, type=click.Path(exists=True), help="Project root directory.")
@click.option("--json", "output_json", is_flag=True, default=False, help="Output as JSON.")
def cmd(project_dir: str | None, output_json: bool) -> None:
    """Show all groups and blocks in the project."""
    cfg = load_config(Path(project_dir) if project_dir else None)
    groups = discover_groups(cfg)

    if output_json:
        data = {
            "name": cfg.name,
            "version": cfg.version,
            "cpp_namespace": cfg.cpp_namespace,
            "build_cmake": cfg.build_cmake,
            "build_meson": cfg.build_meson,
            "groups": [
                {
                    "name": g.name,
                    "blocks": [{"name": b.name} for b in g.blocks],
                }
                for g in groups
            ],
        }
        click.echo(json.dumps(data, indent=2))
        return

    console = Console()
    console.print(f"\n[bold]Project:[/bold] {cfg.name}  v{cfg.version}")
    console.print(f"[bold]Namespace:[/bold] {cfg.cpp_namespace}")
    console.print(f"[bold]Build:[/bold] cmake={cfg.build_cmake}  meson={cfg.build_meson}\n")

    table = Table(title="Groups & Blocks", show_header=True, header_style="bold cyan")
    table.add_column("Group", style="green")
    table.add_column("Block", style="white")
    table.add_column("Header", style="dim")

    for group in groups:
        if not group.blocks:
            table.add_row(group.name, "(no blocks)", "")
        else:
            for i, block in enumerate(group.blocks):
                table.add_row(group.name if i == 0 else "", block.name, str(block.path.name))

    console.print(table)
