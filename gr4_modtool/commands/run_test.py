"""test command — run a single block's qa_* test binary without rebuilding."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import click
from rich.console import Console

from gr4_modtool.commands.lint_headers import lint_header as _lint_header
from gr4_modtool.project.discovery import find_project_root

try:
    from watchdog.events import FileSystemEventHandler as _FileSystemEventHandler
    from watchdog.observers import Observer as _Observer

    _WATCHDOG_AVAILABLE = True
except ImportError:
    _WATCHDOG_AVAILABLE = False
    _Observer = None  # type: ignore[assignment]
    _FileSystemEventHandler = object  # type: ignore[assignment,misc]


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
            "ctest",
            "--test-dir",
            str(build_dir),
            "-R",
            f"qa_{block_name}",
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


def _incremental_build(project_root: Path, build_dir: Path, block_name: str) -> int:
    """Rebuild only qa_<block_name> without a full build."""
    if (project_root / "CMakeLists.txt").exists():
        cmd = ["cmake", "--build", str(build_dir), "--target", f"qa_{block_name}"]
    else:
        cmd = ["meson", "compile", "-C", str(build_dir), f"qa_{block_name}"]
    click.echo(f"  $ {' '.join(cmd)}")
    proc = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)
    return proc.wait()


def _find_block_info(project_root: Path, block_name: str) -> tuple[Path, str] | None:
    """Return (hpp_path, group_name) for block_name, or None if not found in config."""
    try:
        from gr4_modtool.project.discovery import discover_groups, load_config

        cfg = load_config(project_root)
        for group in discover_groups(cfg):
            for block in group.blocks:
                if block.name == block_name:
                    return block.path, group.name
    except Exception:
        pass
    return None


def _find_watch_dir(project_root: Path, block_name: str) -> Path:
    """Return the include directory containing block_name.hpp, or blocks/ as fallback."""
    try:
        from gr4_modtool.project.discovery import discover_groups, load_config

        cfg = load_config(project_root)
        for group in discover_groups(cfg):
            for block in group.blocks:
                if block.name == block_name:
                    return cfg.group_include_dir(group.name)
    except Exception:
        pass
    fallback = project_root / "blocks"
    return fallback if fallback.exists() else project_root


def watch_block_test(
    project_root: Path,
    build_dir: Path,
    block_name: str,
    *,
    verbose: bool = False,
) -> None:
    """Watch block's .hpp for changes, incrementally rebuild and retest on each save."""
    if not _WATCHDOG_AVAILABLE:
        click.echo("watchdog is required for --watch: pip install watchdog", err=True)
        sys.exit(1)

    console = Console()
    last_trigger = -float("inf")
    _block_info = _find_block_info(project_root, block_name)

    def _run_once() -> None:
        nonlocal last_trigger
        now = time.monotonic()
        if now - last_trigger < 1.0:
            return
        last_trigger = now
        console.rule(f"[dim]{time.strftime('%H:%M:%S')} — rebuilding[/dim]")

        if _block_info is not None:
            hpp_path, group_name = _block_info
            issues = _lint_header(hpp_path, group_name)
            if issues:
                for issue in issues:
                    sev_style = "red" if issue.severity == "error" else "yellow"
                    console.print(
                        f"  lint [{sev_style}]{issue.severity}[/{sev_style}]  {issue.issue}"
                    )

        rc = _incremental_build(project_root, build_dir, block_name)
        if rc == 0:
            run_block_test(project_root, build_dir, block_name, verbose=verbose)
        else:
            console.print("[red]Build failed — fix errors and save again[/red]")

    class _Handler(_FileSystemEventHandler):
        def on_modified(self, event):  # type: ignore[override]
            if not event.is_directory and event.src_path.endswith(".hpp"):
                _run_once()

    watch_dir = _find_watch_dir(project_root, block_name)
    console.print(f"[dim]Watching {watch_dir} for .hpp changes (Ctrl+C to stop)[/dim]")
    _run_once()

    observer = _Observer()
    observer.schedule(_Handler(), str(watch_dir), recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()
        console.print("\n[dim]Watch stopped.[/dim]")


@click.command("test")
@click.argument("block_name")
@click.option(
    "--build-dir",
    default="build",
    show_default=True,
    help="Build directory (relative to project root).",
)
@click.option("--verbose", "-v", is_flag=True, help="Pass --verbose to ctest/meson.")
@click.option(
    "--watch", "-w", is_flag=True, help="Rebuild and retest on every .hpp save (requires watchdog)."
)
@click.option("--project-dir", default=None, type=click.Path(exists=True))
def cmd(
    block_name: str,
    build_dir: str,
    verbose: bool,
    watch: bool,
    project_dir: str | None,
) -> None:
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

    if watch:
        watch_block_test(root, bd, block_name, verbose=verbose)
    else:
        rc = run_block_test(root, bd, block_name, verbose=verbose)
        sys.exit(rc)
