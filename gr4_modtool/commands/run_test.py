"""test command — run a single block's qa_* test binary without rebuilding."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import click

from gr4_modtool.project.discovery import find_project_root


def run_block_test(
    project_root: Path,
    build_dir: Path,
    block_name: str,
    *,
    verbose: bool = False,
) -> int:
    """Run qa_<block_name> inside build_dir using ctest (cmake) or meson test.

    Detects build system from project_root. Returns the subprocess exit code.
    """
    if (project_root / "CMakeLists.txt").exists():
        cmd = [
            "ctest", "--test-dir", str(build_dir),
            "-R", f"qa_{block_name}",
            "--output-on-failure",
        ]
        if verbose:
            cmd.append("--verbose")
    else:
        cmd = ["meson", "test", "-C", str(build_dir), f"qa_{block_name}"]
        if verbose:
            cmd.append("--verbose")

    click.echo(f"  $ {' '.join(cmd)}")
    proc = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)
    return proc.wait()


@click.command("test")
@click.argument("block_name")
@click.option("--build-dir", default="build", show_default=True,
              help="Build directory (relative to project root).")
@click.option("--verbose", "-v", is_flag=True, help="Pass --verbose to ctest/meson.")
@click.option("--project-dir", default=None, type=click.Path(exists=True))
def cmd(block_name: str, build_dir: str, verbose: bool, project_dir: str | None) -> None:
    """Run a single block's test binary without rebuilding."""
    if project_dir:
        root = Path(project_dir)
    else:
        root = find_project_root() or Path.cwd()

    bd = (root / build_dir) if not Path(build_dir).is_absolute() else Path(build_dir)

    if not bd.exists():
        click.echo(f"Build directory not found: {bd}", err=True)
        click.echo("Run 'gr4_modtool build' first.", err=True)
        sys.exit(1)

    rc = run_block_test(root, bd, block_name, verbose=verbose)
    sys.exit(rc)
