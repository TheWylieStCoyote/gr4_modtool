"""rm command — remove a block and its test from the project."""

from __future__ import annotations

import sys
from pathlib import Path

import click
import questionary

from gr4_modtool.project.discovery import load_config, discover_groups
from gr4_modtool.project import cmake as cmake_mod
from gr4_modtool.project import meson as meson_mod


@click.command("rm")
@click.argument("block_name", required=False)
@click.option("--project-dir", default=None, type=click.Path(exists=True))
@click.option("--group", default=None, help="Group containing the block.")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
def cmd(block_name: str | None, project_dir: str | None, group: str | None, yes: bool) -> None:
    """Remove a block (header, test, build entries) from the project."""
    cfg = load_config(Path(project_dir) if project_dir else None)
    groups = discover_groups(cfg)

    if not groups:
        click.echo("No groups found in project.", err=True)
        sys.exit(1)

    # Select group
    if group is None:
        group = questionary.select(
            "Group:", choices=[g.name for g in groups]
        ).ask()
        if group is None:
            sys.exit(0)

    group_info = next((g for g in groups if g.name == group), None)
    if group_info is None:
        click.echo(f"Group '{group}' not found.", err=True)
        sys.exit(1)

    # Select block
    if block_name is None:
        block_names = [b.name for b in group_info.blocks]
        if not block_names:
            click.echo(f"No blocks found in group '{group}'.", err=True)
            sys.exit(1)
        block_name = questionary.select("Block to remove:", choices=block_names).ask()
        if block_name is None:
            sys.exit(0)

    header = cfg.group_include_dir(group) / f"{block_name}.hpp"
    test_src = cfg.group_test_dir(group) / f"qa_{block_name}.cpp"

    files_to_remove = [f for f in [header, test_src] if f.exists()]
    build_cmake = cfg.group_test_dir(group) / "CMakeLists.txt"
    build_meson = cfg.group_test_dir(group) / "meson.build"

    click.echo("\nWill remove:")
    for f in files_to_remove:
        click.echo(f"  {f}")
    if build_cmake.exists():
        click.echo(f"  (update) {build_cmake}")
    if build_meson.exists():
        click.echo(f"  (update) {build_meson}")

    if not yes:
        confirm = questionary.confirm("Proceed?", default=False).ask()
        if not confirm:
            sys.exit(0)

    for f in files_to_remove:
        f.unlink()

    if cfg.build_cmake and build_cmake.exists():
        cmake_mod.remove_test_entry(build_cmake, block_name)
    if cfg.build_meson and build_meson.exists():
        meson_mod.remove_test_entry(build_meson, block_name)

    click.echo(f"Removed block '{block_name}' from group '{group}'.")
