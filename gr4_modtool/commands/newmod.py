"""newmod command — scaffold a new GNURadio 4 OOT project."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import click
import questionary

from gr4_modtool.project.discovery import ProjectConfig, save_config
from gr4_modtool.templates import render


def write_git_init(cfg: ProjectConfig) -> list[Path]:
    """Run git init and write .gitignore. Returns list of created paths."""
    gitignore = cfg.root / ".gitignore"
    gitignore.write_text(render("gitignore.j2", {"project_name": cfg.name}, cfg.root))
    written = [gitignore]

    if shutil.which("git"):
        subprocess.run(
            ["git", "init", str(cfg.root)],
            check=False,
            capture_output=True,
        )

    return written


def _slug(name: str) -> str:
    return name.lower().replace(" ", "_").replace("-", "_")


def _cmake_prefix(name: str) -> str:
    return f"gr4_{_slug(name)}"


def _blocks_cmake(cfg: ProjectConfig) -> str:
    lines = [
        f"function({cfg.cmake_prefix}_add_ut_test target_name source_file)",
        f"  add_executable(${{target_name}} ${{source_file}})",
        f"  target_link_libraries(${{target_name}} PRIVATE ${{GR4_OOT_GNURADIO4_TARGET}} ${{GR4_OOT_BOOST_UT_TARGET}})",
        f"  add_test(NAME ${{target_name}} COMMAND ${{target_name}})",
        f"endfunction()",
        "",
    ]
    for name in cfg.groups:
        lines.append(f"add_subdirectory({name})")
    lines += [
        "",
        f"add_library({cfg.cmake_prefix}_blocks_headers INTERFACE)",
        f"add_library({cfg.cmake_prefix}::blocks_headers ALIAS {cfg.cmake_prefix}_blocks_headers)",
        "",
        f"target_link_libraries({cfg.cmake_prefix}_blocks_headers INTERFACE",
    ]
    for name in cfg.groups:
        lines.append(f"  {cfg.cmake_prefix}::blocks_{name}_headers")
    lines.append(")")
    return "\n".join(lines) + "\n"


def _blocks_meson(cfg: ProjectConfig) -> str:
    lines = []
    for name in cfg.groups:
        lines.append(f"subdir('{name}')")
    return "\n".join(lines) + "\n"


def _deps_cmake(cmake_prefix: str) -> str:
    return f"""\
include_guard(GLOBAL)

find_package(PkgConfig REQUIRED)

function({cmake_prefix}_resolve_dependencies)
  pkg_check_modules(GR4_OOT_GR4 REQUIRED IMPORTED_TARGET gnuradio4)
  set(GR4_OOT_GNURADIO4_TARGET PkgConfig::GR4_OOT_GR4 PARENT_SCOPE)

  if(ENABLE_TESTING)
    find_package(boost_ut CONFIG QUIET)
    if(TARGET boost_ut::ut)
      set(GR4_OOT_BOOST_UT_TARGET boost_ut::ut PARENT_SCOPE)
    else()
      find_path(_boost_ut_include boost/ut.hpp PATH_SUFFIXES boost-ut/include include)
      if(NOT _boost_ut_include)
        message(FATAL_ERROR "boost-ut headers not found (boost/ut.hpp). Install system boost-ut.")
      endif()
      add_library({cmake_prefix}_boost_ut INTERFACE)
      target_include_directories({cmake_prefix}_boost_ut INTERFACE "${{_boost_ut_include}}")
      add_library({cmake_prefix}::boost_ut ALIAS {cmake_prefix}_boost_ut)
      set(GR4_OOT_BOOST_UT_TARGET {cmake_prefix}::boost_ut PARENT_SCOPE)
    endif()
  endif()
endfunction()
"""


@click.command("newmod")
@click.option("--project-dir", default=None, type=click.Path(), help="Where to create the project (default: current dir).")
@click.option("--name", default=None, help="Project name (skips prompt).")
def cmd(project_dir: str | None, name: str | None) -> None:
    """Scaffold a new GNURadio 4 OOT project."""
    dest = Path(project_dir).resolve() if project_dir else Path.cwd()

    if name is None:
        name = questionary.text(
            "Project name (e.g. myblocks):",
            validate=lambda v: bool(v.strip()) or "Name cannot be empty",
        ).ask()
        if name is None:
            sys.exit(1)

    name = name.strip()
    version = questionary.text("Version:", default="0.1.0").ask() or "0.1.0"
    cpp_ns = questionary.text("C++ namespace:", default=f"gr::{_slug(name)}").ask() or f"gr::{_slug(name)}"
    cmake_pfx = questionary.text("CMake prefix:", default=_cmake_prefix(name)).ask() or _cmake_prefix(name)
    gr4_prefix = questionary.text("GNURadio4 include prefix:", default="gnuradio-4.0").ask() or "gnuradio-4.0"

    build_cmake = questionary.confirm("Generate CMake build files?", default=True).ask()
    build_meson = questionary.confirm("Generate Meson build files?", default=True).ask()
    gen_git = questionary.confirm("Initialize git repository?", default=True).ask()
    gen_devcontainer = questionary.confirm("Generate devcontainer?", default=False).ask()
    gen_clang = questionary.confirm("Generate .clang-format and .clang-tidy config?", default=True).ask()
    gen_ci_clang = questionary.confirm("Generate GitHub Actions CI for clang checks?", default=False).ask()
    gen_presets = questionary.confirm("Generate CMakePresets.json (asan/ubsan/tsan)?", default=False).ask()
    gen_ci_sanitizers = questionary.confirm("Generate GitHub Actions CI for sanitizers?", default=False).ask()
    gen_ci_matrix = questionary.confirm("Generate CI build matrix workflow (gcc×clang)?", default=False).ask()
    gen_vscode = questionary.confirm("Generate VS Code settings (.vscode/)?", default=True).ask()
    gen_ci_coverage = questionary.confirm("Generate CI coverage workflow?", default=False).ask()
    gen_ci_release = questionary.confirm("Generate CI release workflow?", default=False).ask()
    gen_precommit = questionary.confirm("Generate .pre-commit-config.yaml?", default=False).ask()
    gen_doxyfile = questionary.confirm("Generate Doxyfile for Doxygen?", default=False).ask()

    first_group = questionary.text(
        "Name of first block group (leave blank to skip):", default="basic"
    ).ask() or ""

    project_root = dest / _slug(name)
    if project_root.exists():
        if not questionary.confirm(f"Directory {project_root} already exists. Continue?", default=False).ask():
            sys.exit(1)

    # Build config
    groups: dict[str, str] = {}
    if first_group:
        groups[first_group] = f"blocks/{first_group}"

    cfg = ProjectConfig(
        root=project_root,
        name=name,
        version=version,
        cpp_namespace=cpp_ns,
        cmake_prefix=cmake_pfx,
        gr4_include_prefix=gr4_prefix,
        build_cmake=build_cmake,
        build_meson=build_meson,
        groups=groups,
    )

    _write_project(
        cfg, first_group,
        gen_git=gen_git or False,
        gen_devcontainer=gen_devcontainer or False,
        gen_clang=gen_clang or False,
        gen_ci_clang=gen_ci_clang or False,
        gen_presets=gen_presets or False,
        gen_ci_sanitizers=gen_ci_sanitizers or False,
        gen_ci_matrix=gen_ci_matrix or False,
        gen_vscode=gen_vscode or False,
        gen_ci_coverage=gen_ci_coverage or False,
        gen_ci_release=gen_ci_release or False,
        gen_precommit=gen_precommit or False,
        gen_doxyfile=gen_doxyfile or False,
    )
    click.echo(f"\nCreated project '{name}' at {project_root}")
    click.echo(f"  cd {project_root}")
    if build_cmake:
        click.echo("  cmake -B build && cmake --build build")
    if build_meson:
        click.echo("  meson setup build && ninja -C build")


def _write_project(
    cfg: ProjectConfig,
    first_group: str,
    *,
    gen_git: bool = False,
    gen_devcontainer: bool = False,
    gen_clang: bool = False,
    gen_ci_clang: bool = False,
    gen_presets: bool = False,
    gen_ci_sanitizers: bool = False,
    gen_ci_matrix: bool = False,
    gen_vscode: bool = False,
    gen_ci_coverage: bool = False,
    gen_ci_release: bool = False,
    gen_precommit: bool = False,
    gen_doxyfile: bool = False,
) -> None:
    root = cfg.root
    root.mkdir(parents=True, exist_ok=True)

    # .gr4modtool.toml
    save_config(cfg)

    ctx = {
        "project_name": cfg.name,
        "version": cfg.version,
        "cmake_prefix": cfg.cmake_prefix,
        "gr4_include_prefix": cfg.gr4_include_prefix,
        "cpp_namespace": cfg.cpp_namespace,
    }

    # Top-level build files
    if cfg.build_cmake:
        (root / "CMakeLists.txt").write_text(render("toplevel_CMakeLists.txt.j2", ctx, root))
        cmake_dir = root / "cmake"
        cmake_dir.mkdir(exist_ok=True)
        (cmake_dir / "Dependencies.cmake").write_text(_deps_cmake(cfg.cmake_prefix))

    if cfg.build_meson:
        (root / "meson.build").write_text(render("toplevel_meson.build.j2", ctx, root))

    # blocks/ directory
    blocks_dir = root / "blocks"
    blocks_dir.mkdir(exist_ok=True)

    if cfg.build_cmake:
        (blocks_dir / "CMakeLists.txt").write_text(_blocks_cmake(cfg))
    if cfg.build_meson:
        (blocks_dir / "meson.build").write_text(_blocks_meson(cfg))

    # First group
    if first_group:
        _create_group_skeleton(cfg, first_group)

    # Git init (done last so all files are present for initial state)
    if gen_git:
        write_git_init(cfg)

    # Devcontainer
    if gen_devcontainer:
        from gr4_modtool.commands.devcontainer import write_devcontainer
        write_devcontainer(cfg)

    # Clang config
    if gen_clang:
        from gr4_modtool.commands.tidy import write_clang_config
        write_clang_config(cfg)

    # CI workflow for clang checks
    if gen_ci_clang:
        from gr4_modtool.commands.tidy import write_ci_clang
        write_ci_clang(cfg)

    # CMakePresets.json
    if gen_presets:
        from gr4_modtool.commands.sanitizers import write_cmake_presets
        write_cmake_presets(cfg)

    # CI workflow for sanitizers
    if gen_ci_sanitizers:
        from gr4_modtool.commands.sanitizers import write_ci_sanitizers
        write_ci_sanitizers(cfg)

    # VS Code settings
    if gen_vscode:
        from gr4_modtool.commands.vscode import write_vscode
        write_vscode(cfg)

    # CI quality workflows
    if gen_ci_coverage:
        from gr4_modtool.commands.ci import write_ci_coverage
        write_ci_coverage(cfg)

    if gen_ci_release:
        from gr4_modtool.commands.ci import write_ci_release
        write_ci_release(cfg)

    if gen_ci_matrix:
        from gr4_modtool.commands.ci import write_ci_matrix
        write_ci_matrix(cfg)

    if gen_precommit:
        from gr4_modtool.commands.precommit import write_precommit
        write_precommit(cfg)

    if gen_doxyfile:
        from gr4_modtool.commands.docs import write_doxyfile
        write_doxyfile(cfg)


def _create_group_skeleton(cfg: ProjectConfig, group_name: str) -> None:
    from gr4_modtool.commands.newgroup import write_group_skeleton
    write_group_skeleton(cfg, group_name)
