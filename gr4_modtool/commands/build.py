"""build command — configure and build the project."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import click

from gr4_modtool.project.discovery import find_project_root


def run_build(
    project_root: Path,
    build_dir: Path,
    *,
    clean: bool = False,
    run_tests: bool = False,
    jobs: int | None = None,
    reconfigure: bool = False,
    cmake_args: tuple[str, ...] = (),
    preset: str | None = None,
) -> int:
    """Configure + build (+ optionally test). Returns subprocess exit code.

    Does not require .gr4modtool.toml — works on any cmake/meson project.
    When CMakePresets.json is present, uses preset-based invocation so that
    compiler and flag defaults from the preset are applied automatically.
    """
    has_cmake = (project_root / "CMakeLists.txt").exists()
    has_meson = (project_root / "meson.build").exists()

    if not has_cmake and not has_meson:
        click.echo(f"Error: no CMakeLists.txt or meson.build found in {project_root}", err=True)
        return 1

    use_cmake = has_cmake  # prefer cmake when both present

    if clean and build_dir.exists():
        click.echo(f"Cleaning {build_dir} ...")
        shutil.rmtree(build_dir)

    parallel = str(jobs) if jobs else str(os.cpu_count() or 4)

    if use_cmake:
        has_presets = (project_root / "CMakePresets.json").exists()
        use_preset = preset or ("default" if has_presets else None)

        if use_preset:
            # Preset-based flow — binaryDir comes from the preset
            need_configure = reconfigure or not _preset_cache_exists(project_root, use_preset)
            if need_configure:
                configure_cmd = ["cmake", "--preset", use_preset, *cmake_args]
                rc = _run(configure_cmd, cwd=project_root)
                if rc != 0:
                    return rc
            build_cmd = ["cmake", "--build", "--preset", use_preset, "--parallel", parallel]
            rc = _run(build_cmd, cwd=project_root)
            if rc != 0:
                return rc
            if run_tests:
                test_cmd = ["ctest", "--preset", use_preset, "--output-on-failure"]
                rc = _run(test_cmd, cwd=project_root)
        else:
            need_configure = reconfigure or not (build_dir / "CMakeCache.txt").exists()
            if need_configure:
                configure_cmd = [
                    "cmake",
                    "-B",
                    str(build_dir),
                    "-S",
                    str(project_root),
                    *cmake_args,
                ]
                rc = _run(configure_cmd)
                if rc != 0:
                    return rc

            build_cmd = ["cmake", "--build", str(build_dir), "--parallel", parallel]
            rc = _run(build_cmd)
            if rc != 0:
                return rc

            if run_tests:
                test_cmd = ["ctest", "--test-dir", str(build_dir), "--output-on-failure"]
                rc = _run(test_cmd)

    else:
        need_configure = reconfigure or not build_dir.exists()
        if need_configure:
            configure_cmd = ["meson", "setup", str(build_dir), str(project_root)]
            rc = _run(configure_cmd)
            if rc != 0:
                return rc

        build_cmd = ["ninja", "-C", str(build_dir), "-j", parallel]
        rc = _run(build_cmd)
        if rc != 0:
            return rc

        if run_tests:
            test_cmd = ["meson", "test", "-C", str(build_dir)]
            rc = _run(test_cmd)

    return rc


def _preset_cache_exists(project_root: Path, preset: str) -> bool:
    """Return True if a CMakeCache.txt exists in any likely binary dir for this preset."""
    import json

    presets_file = project_root / "CMakePresets.json"
    try:
        data = json.loads(presets_file.read_text())
        for p in data.get("configurePresets", []):
            if p.get("name") == preset:
                binary_dir = p.get("binaryDir", "")
                binary_dir = binary_dir.replace("${sourceDir}", str(project_root))
                return (Path(binary_dir) / "CMakeCache.txt").exists()
    except Exception:  # noqa: BLE001
        pass
    return False


def _run(cmd: list[str], cwd: Path | None = None) -> int:
    click.echo(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if result.stdout:
        click.echo(result.stdout, nl=False)
    if result.stderr:
        click.echo(result.stderr, nl=False, err=True)
    return result.returncode


@click.command("build")
@click.option(
    "--project-dir",
    default=None,
    type=click.Path(exists=True),
    help="Project root (default: discovered from cwd or cwd itself).",
)
@click.option(
    "--build-dir",
    default="build",
    show_default=True,
    help="Build directory (relative to project root or absolute).",
)
@click.option("--clean", is_flag=True, default=False, help="Delete build dir before building.")
@click.option("--test", "run_tests", is_flag=True, default=False, help="Run tests after building.")
@click.option("--jobs", "-j", default=None, type=int, help="Parallel jobs.")
@click.option("--reconfigure", is_flag=True, default=False, help="Force re-run of configure step.")
@click.option(
    "--preset",
    default=None,
    metavar="NAME",
    help="CMake preset to use (auto-detected from CMakePresets.json when present).",
)
@click.option(
    "--cmake-args",
    multiple=True,
    metavar="ARG",
    help="Extra arguments for cmake configure (e.g. -DENABLE_TESTING=OFF).",
)
def cmd(
    project_dir: str | None,
    build_dir: str,
    clean: bool,
    run_tests: bool,
    jobs: int | None,
    reconfigure: bool,
    preset: str | None,
    cmake_args: tuple[str, ...],
) -> None:
    """Configure and build the project using cmake or meson."""
    if project_dir:
        root = Path(project_dir).resolve()
    else:
        root = find_project_root() or Path.cwd()

    bdir = Path(build_dir) if Path(build_dir).is_absolute() else root / build_dir

    rc = run_build(
        root,
        bdir,
        clean=clean,
        run_tests=run_tests,
        jobs=jobs,
        reconfigure=reconfigure,
        cmake_args=cmake_args,
        preset=preset,
    )
    if rc != 0:
        sys.exit(rc)
