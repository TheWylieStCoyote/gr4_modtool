"""Tests for run_test (gr4_modtool test) command."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gr4_modtool.commands.run_test import run_block_test


@pytest.fixture()
def cmake_root(tmp_path: Path) -> Path:
    (tmp_path / "CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.22)\n")
    build = tmp_path / "build"
    build.mkdir()
    return tmp_path


@pytest.fixture()
def meson_root(tmp_path: Path) -> Path:
    (tmp_path / "meson.build").write_text("project('x', 'cpp')\n")
    build = tmp_path / "build"
    build.mkdir()
    return tmp_path


def _mock_popen(returncode: int = 0):
    mock = MagicMock()
    mock.wait.return_value = returncode
    return mock


def test_run_block_test_cmake_uses_ctest(cmake_root: Path) -> None:
    with patch("subprocess.Popen", return_value=_mock_popen()) as mock_popen:
        run_block_test(cmake_root, cmake_root / "build", "MyFilter")
    args = mock_popen.call_args[0][0]
    assert args[0] == "ctest"
    assert "-R" in args
    assert "qa_MyFilter" in args


def test_run_block_test_meson_uses_meson_test(meson_root: Path) -> None:
    with patch("subprocess.Popen", return_value=_mock_popen()) as mock_popen:
        run_block_test(meson_root, meson_root / "build", "MyFilter")
    args = mock_popen.call_args[0][0]
    assert args[0] == "meson"
    assert "test" in args
    assert "qa_MyFilter" in args


def test_run_block_test_verbose_flag(cmake_root: Path) -> None:
    with patch("subprocess.Popen", return_value=_mock_popen()) as mock_popen:
        run_block_test(cmake_root, cmake_root / "build", "MyFilter", verbose=True)
    args = mock_popen.call_args[0][0]
    assert "--verbose" in args
