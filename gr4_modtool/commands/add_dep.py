"""add-dep command — add a library dependency to cmake/Dependencies.cmake and meson.build."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import click

from gr4_modtool.project.discovery import load_config, ProjectConfig


def add_cmake_dep(
    deps_cmake: Path,
    var_name: str,
    pkg_name: str | None,
    cmake_pkg: str | None,
) -> None:
    """Insert a dependency into cmake/Dependencies.cmake before endfunction().

    Raises FileNotFoundError if deps_cmake does not exist.
    Raises ValueError if var_name is already present.
    """
    if not deps_cmake.exists():
        raise FileNotFoundError(f"Dependencies.cmake not found: {deps_cmake}")

    text = deps_cmake.read_text()
    if var_name in text:
        raise ValueError(f"'{var_name}' is already declared in {deps_cmake.name}")

    if pkg_name:
        snippet = (
            f"  pkg_check_modules({var_name} REQUIRED IMPORTED_TARGET {pkg_name})\n"
            f"  set({var_name}_TARGET PkgConfig::{var_name} PARENT_SCOPE)\n"
        )
    else:
        snippet = (
            f"  find_package({cmake_pkg} REQUIRED)\n"
            f"  set({var_name}_TARGET {cmake_pkg}::{cmake_pkg} PARENT_SCOPE)\n"
        )

    text = re.sub(r"(endfunction\(\))", snippet + r"\1", text)
    deps_cmake.write_text(text)


def add_meson_dep(meson_build: Path, var_name: str, pkg_name: str) -> None:
    """Append a dependency() call to meson.build.

    Raises FileNotFoundError if meson_build does not exist.
    Raises ValueError if the dep variable is already present.
    """
    if not meson_build.exists():
        raise FileNotFoundError(f"meson.build not found: {meson_build}")

    dep_var = f"{var_name.lower()}_dep"
    text = meson_build.read_text()
    if dep_var in text:
        raise ValueError(f"'{dep_var}' is already declared in {meson_build.name}")

    line = f"{dep_var} = dependency('{pkg_name}')\n"
    meson_build.write_text(text.rstrip() + "\n" + line)


@click.command("add-dep")
@click.argument("var_name", metavar="VAR_NAME")
@click.option("--pkg-config", "pkg_name", default=None,
              help="pkg-config module name (e.g. fftw3).")
@click.option("--cmake-package", "cmake_pkg", default=None,
              help="CMake find_package name (e.g. FFTW3).")
@click.option("--project-dir", default=None, type=click.Path(exists=True))
def cmd(
    var_name: str,
    pkg_name: str | None,
    cmake_pkg: str | None,
    project_dir: str | None,
) -> None:
    """Add a library dependency to cmake/Dependencies.cmake (and meson.build).

    VAR_NAME is the CMake variable prefix, e.g. FFTW3.

    Examples:
      gr4_modtool add-dep FFTW3 --pkg-config fftw3
      gr4_modtool add-dep Eigen3 --cmake-package Eigen3
    """
    if not pkg_name and not cmake_pkg:
        click.echo(
            "Error: provide --pkg-config <name> or --cmake-package <name>.", err=True
        )
        sys.exit(1)

    cfg = load_config(Path(project_dir) if project_dir else None)
    modified: list[Path] = []

    deps_cmake = cfg.root / "cmake" / "Dependencies.cmake"
    if deps_cmake.exists():
        try:
            add_cmake_dep(deps_cmake, var_name, pkg_name, cmake_pkg)
            modified.append(deps_cmake)
        except ValueError as exc:
            click.echo(f"cmake: {exc}", err=True)

    if cfg.build_meson and pkg_name:
        meson_build = cfg.root / "meson.build"
        if meson_build.exists():
            try:
                add_meson_dep(meson_build, var_name, pkg_name)
                modified.append(meson_build)
            except ValueError as exc:
                click.echo(f"meson: {exc}", err=True)

    if modified:
        click.echo("Modified:")
        for p in modified:
            click.echo(f"  {p}")
    else:
        click.echo("No files modified.")
