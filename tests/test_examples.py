"""The repository's examples are executable documentation — so run them.

Each example is run end to end and its *output* is checked, not just its exit
code: an example that silently stops scaffolding half way through still exits 0.
The assertions below mirror what the example's own README claims it produces,
so a change that breaks the documented behaviour fails here rather than in
someone's terminal.

These run in the ordinary suite. They need no GNURadio 4: the CLI tour skips its
compile step when ``pkg-config gnuradio4`` finds nothing, and everything else is
pure code generation. Where GR4 *is* installed the tour compiles as well, and
these tests simply cover that too.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = REPO_ROOT / "examples"
CLI_TOUR = EXAMPLES / "gr4_modtool_cli_tour" / "tour.sh"
PYTHON_API = EXAMPLES / "gr4_modtool_python_api" / "build_project.py"
PLUGIN = EXAMPLES / "gr4_modtool_example_plugin"

# The tour calls the console script. Point PATH at the interpreter running the
# tests, so it finds the gr4_modtool this suite is exercising rather than some
# other one earlier on PATH — or none at all.
_BIN_DIR = str(Path(sys.executable).parent)


def _run(command: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, "PATH": os.pathsep.join([_BIN_DIR, os.environ.get("PATH", "")])}
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        # Generous: with GNURadio 4 installed the tour also compiles the project.
        timeout=1800,
    )


def _assert_ok(result: subprocess.CompletedProcess, what: str) -> None:
    assert result.returncode == 0, (
        f"{what} exited {result.returncode}\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )


# --------------------------------------------------------------------------- #
# examples/gr4_modtool_cli_tour
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def cli_tour(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str]:
    """Run the CLI tour once; return its project root and transcript."""
    if shutil.which("bash") is None:
        pytest.skip("bash not available")
    workdir = tmp_path_factory.mktemp("cli_tour")
    result = _run(["bash", str(CLI_TOUR), str(workdir)])
    _assert_ok(result, "examples/gr4_modtool_cli_tour/tour.sh")
    return workdir / "gr4_demo", result.stdout


def test_cli_tour_scaffolds_the_documented_project(cli_tour: tuple[Path, str]) -> None:
    root, _ = cli_tour
    dsp = root / "blocks" / "dsp" / "include" / "gnuradio-4.0" / "dsp"
    filters = root / "blocks" / "filters" / "include" / "gnuradio-4.0" / "filters"

    assert (root / ".gr4modtool.toml").exists()
    # newblock --spec: three blocks from the YAML spec
    assert sorted(p.name for p in dsp.glob("*.hpp")) == [
        "Decimator.hpp",
        "Gain.hpp",
        "NoiseSource.hpp",
    ]
    # newgroup + cp + rename: Attenuator was copied from Gain, then renamed
    assert [p.name for p in filters.glob("*.hpp")] == ["Pad.hpp"]
    assert "Attenuator" not in (filters / "Pad.hpp").read_text()
    assert "struct Pad" in (filters / "Pad.hpp").read_text()
    # cp + mv + rm: Gain2 was created, moved to filters, then removed
    assert not (filters / "Gain2.hpp").exists()
    assert not (dsp / "Gain2.hpp").exists()


def test_cli_tour_evolves_blocks(cli_tour: tuple[Path, str]) -> None:
    root, _ = cli_tour
    gain = (root / "blocks/dsp/include/gnuradio-4.0/dsp/Gain.hpp").read_text()
    # newparam: the member is declared and reflected
    assert 'Annotated<float, "gain", Doc<"Gain factor">> gain{1.0f};' in gain
    assert "GR_MAKE_REFLECTABLE(Gain, in, out, gain)" in gain
    # add-test: NoiseSource was generated without a test, then given one
    assert (root / "blocks/dsp/test/qa_NoiseSource.cpp").exists()
    # newbench --wire-build: benchmark source and its build entry
    assert (root / "blocks/dsp/benchmarks/bench_Gain.cpp").exists()
    bench_cmake = (root / "blocks/dsp/benchmarks/CMakeLists.txt").read_text()
    assert "bench_Gain" in bench_cmake


def test_cli_tour_writes_specs_and_bumps_the_version(cli_tour: tuple[Path, str]) -> None:
    root, _ = cli_tour
    # export-spec --output project --out-dir specs
    spec = root / "specs" / "blocks.yaml"
    assert spec.exists()
    assert "Gain" in spec.read_text()
    # version-bump --minor, from the 0.1.0 newmod default
    assert 'version = "0.2.0"' in (root / ".gr4modtool.toml").read_text()


def test_cli_tour_health_checks_report_clean(cli_tour: tuple[Path, str]) -> None:
    """check/validate/lint-headers run inside the tour; `set -e` means a
    non-zero exit would already have failed it. Confirm they were reached and
    that nothing reported a problem."""
    _, transcript = cli_tour
    for command in ("gr4_modtool check", "gr4_modtool validate", "gr4_modtool lint-headers"):
        assert command in transcript, f"the tour no longer runs {command!r}"
    assert "Traceback" not in transcript


def test_cli_tour_skips_the_compile_step_without_gnuradio4(cli_tour: tuple[Path, str]) -> None:
    """The tour must stay runnable on a machine with no GNURadio 4 — that is
    what makes it usable as a first-run demo, and testable here."""
    _, transcript = cli_tour
    if shutil.which("pkg-config") and _has_gr4():
        pytest.skip("gnuradio4 is installed; the tour compiles instead of skipping")
    assert "skipping the compile step" in transcript


def _has_gr4() -> bool:
    try:
        return (
            subprocess.run(["pkg-config", "--exists", "gnuradio4"], capture_output=True).returncode
            == 0
        )
    except OSError:
        return False


# --------------------------------------------------------------------------- #
# examples/gr4_modtool_python_api
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def python_api(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str]:
    workdir = tmp_path_factory.mktemp("python_api")
    result = _run([sys.executable, str(PYTHON_API), str(workdir)])
    _assert_ok(result, "examples/gr4_modtool_python_api/build_project.py")
    return workdir / "gr4_demo", result.stdout


def test_python_api_example_builds_the_documented_project(python_api: tuple[Path, str]) -> None:
    root, _ = python_api
    dsp = root / "blocks" / "dsp" / "include" / "gnuradio-4.0" / "dsp"
    filters = root / "blocks" / "filters" / "include" / "gnuradio-4.0" / "filters"

    # Both call styles the example demonstrates: keywords, and a spec dict via **
    assert sorted(p.name for p in dsp.glob("*.hpp")) == [
        "Gain.hpp",
        "NoiseSource.hpp",
        "Squelch.hpp",
    ]
    assert [p.name for p in filters.glob("*.hpp")] == ["Pad.hpp"]
    assert (
        'Annotated<float, "gain", Doc<"Gain factor">> gain{1.0f};' in (dsp / "Gain.hpp").read_text()
    )
    # gen_presets / gen_clang
    assert (root / "CMakePresets.json").exists()
    assert (root / ".clang-format").exists()


def test_python_api_example_sync_fills_the_missing_test(python_api: tuple[Path, str]) -> None:
    """NoiseSource is created with gen_test=False specifically so sync() has
    something to reconcile — the point of that section of the example."""
    root, transcript = python_api
    assert (root / "blocks/dsp/test/qa_NoiseSource.cpp").exists()
    assert "sync: 1 action(s) planned" in transcript
    assert "generate_test: dsp/NoiseSource" in transcript


def test_python_api_example_reports_a_clean_audit(python_api: tuple[Path, str]) -> None:
    _, transcript = python_api
    assert "audit: 0 issue(s)" in transcript
    assert "status: 4 block(s), 4 tested" in transcript


# --------------------------------------------------------------------------- #
# examples/gr4_modtool_example_plugin
# --------------------------------------------------------------------------- #


def test_plugin_example_entry_points_resolve() -> None:
    """The plugin is not installed in this environment, so load its entry-point
    targets directly: the paths in its pyproject.toml must still be importable
    and of the type the loader requires."""
    import importlib.util
    import tomllib

    import click

    metadata = tomllib.loads((PLUGIN / "pyproject.toml").read_text())
    entry_points = metadata["project"]["entry-points"]
    sys.path.insert(0, str(PLUGIN))
    try:
        for spec in entry_points["gr4_modtool.commands"].values():
            module_path, _, attribute = spec.partition(":")
            assert importlib.util.find_spec(module_path) is not None, module_path
            module = importlib.import_module(module_path)
            # click.Command covers Group too; the loader's check is BaseCommand,
            # which is deprecated in Click 8 and gone in 9.
            assert isinstance(getattr(module, attribute), click.Command)

        for spec in entry_points["gr4_modtool.templates"].values():
            module_path, _, attribute = spec.partition(":")
            module = importlib.import_module(module_path)
            directory = Path(getattr(module, attribute)())
            assert directory.is_dir(), directory
    finally:
        sys.path.remove(str(PLUGIN))
