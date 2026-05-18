"""init command — bootstrap .gr4modtool.toml for an existing project."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import click
import questionary

from gr4_modtool.project.discovery import ProjectConfig, save_config, CONFIG_FILE


def scan_project_dir(project_dir: Path) -> dict:
    """Auto-detect project metadata from directory structure.

    Returns dict with keys: name, groups, gr4_include_prefix, has_cmake, has_meson.
    """
    result: dict = {
        "name": None,
        "groups": {},
        "gr4_include_prefix": "gnuradio-4.0",
        "has_cmake": False,
        "has_meson": False,
    }

    cmake_path = project_dir / "CMakeLists.txt"
    meson_path = project_dir / "meson.build"
    result["has_cmake"] = cmake_path.exists()
    result["has_meson"] = meson_path.exists()

    if cmake_path.exists():
        text = cmake_path.read_text()
        m = re.search(r'project\s*\(\s*([^\s)]+)', text)
        if m:
            result["name"] = m.group(1).strip('"').strip("'")

    blocks_dir = project_dir / "blocks"
    if blocks_dir.is_dir():
        for group_dir in sorted(blocks_dir.iterdir()):
            if not group_dir.is_dir():
                continue
            include_dir = group_dir / "include"
            if not include_dir.is_dir():
                continue
            result["groups"][group_dir.name] = f"blocks/{group_dir.name}"

            # Detect gr4_include_prefix from include/<prefix>/<group>/ structure
            if result["gr4_include_prefix"] == "gnuradio-4.0":
                for prefix_dir in sorted(include_dir.iterdir()):
                    if prefix_dir.is_dir() and any(prefix_dir.iterdir()):
                        result["gr4_include_prefix"] = prefix_dir.name
                        break

    return result


def write_init_config(
    project_dir: Path,
    name: str,
    version: str,
    cpp_namespace: str,
    cmake_prefix: str,
    gr4_include_prefix: str,
    build_cmake: bool,
    build_meson: bool,
    groups: dict[str, str],
) -> Path:
    """Write .gr4modtool.toml. Raises FileExistsError if it already exists."""
    config_path = project_dir / CONFIG_FILE
    if config_path.exists():
        raise FileExistsError(f"{config_path} already exists.")

    cfg = ProjectConfig(
        root=project_dir,
        name=name,
        version=version,
        cpp_namespace=cpp_namespace,
        cmake_prefix=cmake_prefix,
        gr4_include_prefix=gr4_include_prefix,
        build_cmake=build_cmake,
        build_meson=build_meson,
        groups=groups,
    )
    save_config(cfg)
    return config_path


@click.command("init")
@click.option("--project-dir", default=None, type=click.Path(exists=True),
              help="Project root (default: cwd).")
@click.option("--yes", "-y", is_flag=True, help="Accept all detected values without prompting.")
def cmd(project_dir: str | None, yes: bool) -> None:
    """Bootstrap .gr4modtool.toml for an existing project."""
    root = Path(project_dir).resolve() if project_dir else Path.cwd()

    config_path = root / CONFIG_FILE
    if config_path.exists():
        click.echo(f"Error: {config_path} already exists. Use 'gr4_modtool info' to inspect.", err=True)
        sys.exit(1)

    detected = scan_project_dir(root)

    if yes:
        name = detected["name"] or root.name
        version = "0.1.0"
        cpp_namespace = f"gr::{name.replace('-', '_')}"
        cmake_prefix = f"gr4_{name.replace('-', '_')}"
        gr4_include_prefix = detected["gr4_include_prefix"]
        build_cmake = detected["has_cmake"]
        build_meson = detected["has_meson"]
        groups = detected["groups"]
    else:
        click.echo(f"\nDetected project at: {root}")
        if detected["groups"]:
            click.echo(f"  Groups: {', '.join(detected['groups'])}")
        click.echo()

        name = questionary.text(
            "Project name:", default=detected["name"] or root.name
        ).ask()
        if name is None:
            sys.exit(0)

        version = questionary.text("Version:", default="0.1.0").ask() or "0.1.0"

        default_ns = f"gr::{name.replace('-', '_')}"
        cpp_namespace = questionary.text("C++ namespace:", default=default_ns).ask() or default_ns

        default_pfx = f"gr4_{name.replace('-', '_')}"
        cmake_prefix = questionary.text("CMake prefix:", default=default_pfx).ask() or default_pfx

        gr4_include_prefix = questionary.text(
            "GNURadio4 include prefix:", default=detected["gr4_include_prefix"]
        ).ask() or detected["gr4_include_prefix"]

        build_cmake = questionary.confirm("CMake build files?", default=detected["has_cmake"]).ask()
        build_meson = questionary.confirm("Meson build files?", default=detected["has_meson"]).ask()
        groups = detected["groups"]

    try:
        path = write_init_config(
            root, name, version, cpp_namespace, cmake_prefix,
            gr4_include_prefix, build_cmake, build_meson, groups,
        )
    except FileExistsError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    click.echo(f"\nCreated {path}")
    click.echo(f"  {len(groups)} group(s) registered: {', '.join(groups) or '(none)'}")
    click.echo("  Run 'gr4_modtool info' to verify.")
